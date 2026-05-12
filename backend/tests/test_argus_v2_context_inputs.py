from __future__ import annotations

from datetime import date, datetime, timezone
import json

import httpx

from src.argus_v2.dashboard import build_dashboard_from_storage
from src.argus_v2.db import get_connection
from src.argus_v2.providers.context_inputs import run_context_collection
from src.argus_v2.storage import ArgusV2Storage
from src.config.env import Settings


def _ai_decision_response(decision: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": json.dumps(decision, ensure_ascii=False)}}]},
    )


def _decision_for_ai_request(request: httpx.Request, decisions_by_title: dict[str, dict]) -> dict:
    payload = json.loads(request.content.decode())
    user_content = payload["messages"][-1]["content"]
    news = json.loads(user_content)["news"]
    title = news["title"]
    source_url = news.get("source_url")
    if source_url and source_url in decisions_by_title:
        return decisions_by_title[source_url]
    return decisions_by_title.get(
        title,
        {
            "should_use": False,
            "impact": "neutral",
            "relevance_score": 0,
            "connection_strength": "unclear",
            "affected_factors": [],
            "summary": "",
            "reason": "테스트 기본 미사용",
            "confidence": "low",
        },
    )


def _news_ai_settings() -> dict[str, str]:
    return {
        "argus_news_ai_provider": "openai",
        "argus_news_ai_base_url": "https://ai.test",
        "argus_news_ai_chat_path": "/v1/chat/completions",
        "argus_news_ai_api_key": "test-key",
        "argus_news_ai_model": "test-model",
    }


def test_context_collection_persists_mock_market_reaction_and_news(tmp_path):
    db_path = str(tmp_path / "argus-v2.db")
    settings = Settings(db_path=db_path)

    result = run_context_collection(
        settings=settings,
        trade_date=date(2026, 5, 12),
        snapshot_time=datetime(2026, 5, 12, 3, 10, tzinfo=timezone.utc),
    )

    assert [provider.provider_key for provider in result.providers] == ["v2_market_reaction", "v2_news_triggers"]
    assert result.providers[0].status == "success"
    assert result.providers[0].market_reaction_snapshot_count == 1
    assert result.providers[1].status == "success"
    assert result.providers[1].news_trigger_count == 2

    with get_connection(db_path) as connection:
        dashboard = build_dashboard_from_storage(ArgusV2Storage(connection))

    assert dashboard is not None
    assert dashboard.reaction.strong_sectors[0].name == "반도체"
    assert dashboard.triggers[0].title in {"미국 금리 상승 경계", "반도체 상대 강세"}
    assert dashboard.provider_health[2].status == "fresh"
    assert dashboard.provider_health[3].status == "fresh"


def test_context_collection_reads_rss_news_triggers(tmp_path):
    db_path = str(tmp_path / "argus-v2.db")
    feed_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>테스트 경제 뉴스</title>
    <item>
      <title>반도체 강세, 코스피 낙폭 제한</title>
      <link>https://example.test/chip</link>
      <description>AI 반도체 수요 회복으로 대형주가 강세입니다.</description>
      <pubDate>Tue, 12 May 2026 12:30:00 +0900</pubDate>
    </item>
    <item>
      <title>오래된 금리 뉴스</title>
      <link>https://example.test/old</link>
      <description>금리 상승 부담</description>
      <pubDate>Mon, 11 May 2026 08:00:00 +0900</pubDate>
    </item>
  </channel>
</rss>
"""

    decisions = {
        "반도체 강세, 코스피 낙폭 제한": {
            "should_use": True,
            "impact": "positive",
            "relevance_score": 82,
            "connection_strength": "strong",
            "affected_factors": ["반도체", "코스피"],
            "summary": "반도체 강세가 코스피 낙폭을 제한합니다.",
            "reason": "국내 지수 영향도가 큰 업종 흐름입니다.",
            "confidence": "high",
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return _ai_decision_response(_decision_for_ai_request(request, decisions))
        return httpx.Response(200, text=feed_xml)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    settings = Settings(
        db_path=db_path,
        argus_market_reaction_provider="disabled",
        argus_news_triggers_provider="rss",
        argus_news_triggers_rss_urls="https://example.test/rss",
        argus_news_triggers_query="반도체",
        argus_news_triggers_lookback_hours=24,
        **_news_ai_settings(),
    )

    try:
        result = run_context_collection(
            settings=settings,
            trade_date=date(2026, 5, 12),
            snapshot_time=datetime(2026, 5, 12, 4, 0, tzinfo=timezone.utc),
            http_client=client,
        )
    finally:
        client.close()

    assert result.providers[0].status == "skipped"
    assert result.providers[1].status == "success"
    assert result.providers[1].news_trigger_count == 1

    with get_connection(db_path) as connection:
        triggers = ArgusV2Storage(connection).get_latest_news_triggers()

    assert len(triggers) == 1
    assert triggers[0]["title"] == "반도체 강세, 코스피 낙폭 제한"
    assert triggers[0]["impact"] == "positive"


def test_context_collection_filters_news_by_market_importance(tmp_path):
    db_path = str(tmp_path / "argus-v2.db")
    feed_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>테스트 경제 뉴스</title>
    <item>
      <title>연예 소식 모음</title>
      <link>https://example.test/entertainment</link>
      <description>시장 판단과 무관한 저신호 기사입니다.</description>
      <pubDate>Tue, 12 May 2026 12:50:00 +0900</pubDate>
    </item>
    <item>
      <title>반도체 강세, 코스피 낙폭 제한</title>
      <link>https://example.test/chip</link>
      <description>AI 반도체 수요 회복으로 대형주가 강세입니다.</description>
      <pubDate>Tue, 12 May 2026 12:40:00 +0900</pubDate>
    </item>
    <item>
      <title>FOMC 금리 경계와 환율 상승</title>
      <link>https://example.test/fomc</link>
      <description>미국 국채금리와 달러 강세가 위험자산에 부담입니다.</description>
      <pubDate>Tue, 12 May 2026 12:20:00 +0900</pubDate>
    </item>
  </channel>
</rss>
"""

    decisions = {
        "연예 소식 모음": {
            "should_use": False,
            "impact": "neutral",
            "relevance_score": 0,
            "connection_strength": "unclear",
            "affected_factors": [],
            "summary": "",
            "reason": "시장 판단과 무관합니다.",
            "confidence": "high",
        },
        "반도체 강세, 코스피 낙폭 제한": {
            "should_use": True,
            "impact": "positive",
            "relevance_score": 78,
            "connection_strength": "medium",
            "affected_factors": ["반도체", "코스피"],
            "summary": "반도체 강세가 코스피 낙폭을 제한합니다.",
            "reason": "국내 지수 비중 업종 흐름입니다.",
            "confidence": "medium",
        },
        "FOMC 금리 경계와 환율 상승": {
            "should_use": True,
            "impact": "negative",
            "relevance_score": 92,
            "connection_strength": "strong",
            "affected_factors": ["FOMC", "금리", "환율"],
            "summary": "FOMC 금리 경계와 환율 상승은 위험자산에 부담입니다.",
            "reason": "한국장 개장 전 매크로 압력입니다.",
            "confidence": "high",
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return _ai_decision_response(_decision_for_ai_request(request, decisions))
        return httpx.Response(200, text=feed_xml)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    settings = Settings(
        db_path=db_path,
        argus_market_reaction_provider="disabled",
        argus_news_triggers_provider="rss",
        argus_news_triggers_rss_urls="https://example.test/rss",
        argus_news_triggers_query="",
        argus_news_triggers_limit=2,
        argus_news_triggers_lookback_hours=24,
        **_news_ai_settings(),
    )

    try:
        result = run_context_collection(
            settings=settings,
            trade_date=date(2026, 5, 12),
            snapshot_time=datetime(2026, 5, 12, 4, 0, tzinfo=timezone.utc),
            http_client=client,
        )
    finally:
        client.close()

    assert result.providers[1].status == "success"
    assert result.providers[1].news_trigger_count == 2

    with get_connection(db_path) as connection:
        storage = ArgusV2Storage(connection)
        triggers = storage.get_latest_news_triggers(limit=2)
        latest_run = connection.execute(
            """
            SELECT id, metadata_json
            FROM argus_v2_provider_runs
            WHERE provider_key = 'v2_news_triggers'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        samples = connection.execute(
            """
            SELECT payload_json
            FROM argus_v2_provider_samples
            WHERE run_id = ?
            """,
            (latest_run["id"],),
        ).fetchall()

    assert [trigger["title"] for trigger in triggers] == [
        "FOMC 금리 경계와 환율 상승",
        "반도체 강세, 코스피 낙폭 제한",
    ]
    assert triggers[0]["connection_strength"] == "strong"
    assert triggers[1]["connection_strength"] == "medium"
    assert "연예 소식 모음" not in {trigger["title"] for trigger in triggers}
    assert '"filtered_count": 2' in latest_run["metadata_json"]
    assert any("_argus_ai_relevance_score" in row["payload_json"] for row in samples)


def test_context_collection_does_not_keyword_classify_live_news_without_ai(tmp_path):
    db_path = str(tmp_path / "argus-v2.db")
    feed_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>테스트 경제 뉴스</title>
    <item>
      <title>FOMC 금리 경계와 환율 상승</title>
      <link>https://example.test/fomc</link>
      <description>미국 국채금리와 달러 강세가 위험자산에 부담입니다.</description>
      <pubDate>Tue, 12 May 2026 12:20:00 +0900</pubDate>
    </item>
  </channel>
</rss>
"""

    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=feed_xml)))
    settings = Settings(
        db_path=db_path,
        argus_market_reaction_provider="disabled",
        argus_news_triggers_provider="rss",
        argus_news_triggers_rss_urls="https://example.test/rss",
        argus_news_triggers_query="금리,환율,FOMC",
        argus_news_triggers_lookback_hours=24,
        argus_news_ai_provider="disabled",
    )

    try:
        result = run_context_collection(
            settings=settings,
            trade_date=date(2026, 5, 12),
            snapshot_time=datetime(2026, 5, 12, 4, 0, tzinfo=timezone.utc),
            http_client=client,
        )
    finally:
        client.close()

    assert result.providers[1].status == "success"
    assert result.providers[1].news_trigger_count == 0


def test_context_collection_prefers_quality_news_source_and_filters_market_spam(tmp_path):
    db_path = str(tmp_path / "argus-v2.db")
    feed_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>테스트 경제 뉴스</title>
    <item>
      <title>FOMC 금리 경계와 환율 상승</title>
      <link>https://blog.naver.com/spam/fomc</link>
      <description>무료추천 리딩방에서 달러 강세 대응 종목을 소개합니다.</description>
      <pubDate>Tue, 12 May 2026 12:50:00 +0900</pubDate>
    </item>
    <item>
      <title>FOMC 금리 경계와 환율 상승</title>
      <link>https://www.reuters.com/markets/rates-fx</link>
      <description>미국 국채금리와 달러 강세가 위험자산에 부담입니다.</description>
      <pubDate>Tue, 12 May 2026 12:20:00 +0900</pubDate>
    </item>
    <item>
      <title>반도체 급등주 무료추천</title>
      <link>https://example.test/promo</link>
      <description>리딩방에서 반도체 종목추천을 제공합니다.</description>
      <pubDate>Tue, 12 May 2026 12:15:00 +0900</pubDate>
    </item>
    <item>
      <title>코스피 수급, 외국인 선물 매도 지속</title>
      <link>https://www.mk.co.kr/news/market/flow</link>
      <description>외국인 선물 매도와 기관 수급이 장중 지수에 부담입니다.</description>
      <pubDate>Tue, 12 May 2026 12:10:00 +0900</pubDate>
    </item>
  </channel>
</rss>
"""

    decisions = {
        "https://blog.naver.com/spam/fomc": {
            "should_use": False,
            "impact": "neutral",
            "relevance_score": 0,
            "connection_strength": "unclear",
            "affected_factors": [],
            "summary": "",
            "reason": "프로모션성 문맥이라 사용하지 않습니다.",
            "confidence": "high",
        },
        "https://www.reuters.com/markets/rates-fx": {
            "should_use": True,
            "impact": "negative",
            "relevance_score": 92,
            "connection_strength": "strong",
            "affected_factors": ["FOMC", "금리", "환율"],
            "summary": "FOMC 금리 경계와 환율 상승은 위험자산에 부담입니다.",
            "reason": "신뢰 가능한 원문 기준으로 한국장 매크로 압력입니다.",
            "confidence": "high",
        },
        "반도체 급등주 무료추천": {
            "should_use": False,
            "impact": "neutral",
            "relevance_score": 0,
            "connection_strength": "unclear",
            "affected_factors": [],
            "summary": "",
            "reason": "프로모션 성격이라 시장 판단에 쓰지 않습니다.",
            "confidence": "high",
        },
        "코스피 수급, 외국인 선물 매도 지속": {
            "should_use": True,
            "impact": "negative",
            "relevance_score": 84,
            "connection_strength": "strong",
            "affected_factors": ["외국인 선물", "수급", "코스피"],
            "summary": "외국인 선물 매도는 장중 지수에 부담입니다.",
            "reason": "파생 수급과 지수 방향성에 직접 연결됩니다.",
            "confidence": "high",
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            decision = _decision_for_ai_request(request, decisions)
            if request.url.host == "ai.test":
                return _ai_decision_response(decision)
        return httpx.Response(200, text=feed_xml)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    settings = Settings(
        db_path=db_path,
        argus_market_reaction_provider="disabled",
        argus_news_triggers_provider="rss",
        argus_news_triggers_rss_urls="https://example.test/rss",
        argus_news_triggers_query="",
        argus_news_triggers_limit=2,
        argus_news_triggers_lookback_hours=24,
        **_news_ai_settings(),
    )

    try:
        result = run_context_collection(
            settings=settings,
            trade_date=date(2026, 5, 12),
            snapshot_time=datetime(2026, 5, 12, 4, 0, tzinfo=timezone.utc),
            http_client=client,
        )
    finally:
        client.close()

    assert result.providers[1].status == "success"
    assert result.providers[1].news_trigger_count == 2

    with get_connection(db_path) as connection:
        triggers = ArgusV2Storage(connection).get_latest_news_triggers(limit=3)
        samples = connection.execute("SELECT payload_json FROM argus_v2_provider_samples").fetchall()

    assert [trigger["title"] for trigger in triggers] == [
        "FOMC 금리 경계와 환율 상승",
        "코스피 수급, 외국인 선물 매도 지속",
    ]
    assert triggers[0]["source_url"] == "https://www.reuters.com/markets/rates-fx"
    assert "반도체 급등주 무료추천" not in {trigger["title"] for trigger in triggers}
    assert any("_argus_ai_relevance_score" in row["payload_json"] for row in samples)


def test_context_collection_normalizes_macro_events_as_triggers(tmp_path):
    db_path = str(tmp_path / "argus-v2.db")
    settings = Settings(
        db_path=db_path,
        argus_market_reaction_provider="disabled",
        argus_news_triggers_provider="macro",
        argus_macro_events_provider="mock",
    )

    result = run_context_collection(
        settings=settings,
        trade_date=date(2026, 5, 12),
        snapshot_time=datetime(2026, 5, 12, 4, 0, tzinfo=timezone.utc),
    )

    assert result.providers[1].status == "success"
    assert result.providers[1].news_trigger_count == 2

    with get_connection(db_path) as connection:
        triggers = ArgusV2Storage(connection).get_latest_news_triggers(limit=2)

    assert triggers[0]["title"] in {"미국 10년물 금리 상승", "나스닥 반도체 강세"}
    assert {trigger["source_name"] for trigger in triggers} == {"mock.macro.rates", "mock.macro.us_equity"}
    assert all(trigger["connection_strength"] in {"strong", "medium"} for trigger in triggers)


def test_context_collection_reads_kis_market_reaction(tmp_path):
    db_path = str(tmp_path / "argus-v2.db")
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json={"access_token": "issued-token", "token_type": "Bearer", "expires_in": 86400})

        assert request.headers["authorization"] == "Bearer issued-token"
        if request.url.path.endswith("/inquire-index-price"):
            index_code = request.url.params["FID_INPUT_ISCD"]
            if index_code == "0001":
                return httpx.Response(
                    200,
                    json={
                        "output": {
                            "bstp_nmix_prdy_ctrt": "-0.42",
                            "ascn_issu_cnt": "410",
                            "down_issu_cnt": "520",
                        }
                    },
                )
            if index_code == "1001":
                return httpx.Response(
                    200,
                    json={
                        "output": {
                            "bstp_nmix_prdy_ctrt": "0.18",
                            "ascn_issu_cnt": "390",
                            "down_issu_cnt": "260",
                        }
                    },
                )

        if request.url.path.endswith("/inquire-index-category-price"):
            return httpx.Response(
                200,
                json={
                    "output2": [
                        {"hts_kor_isnm": "F-K200 인버스-3X", "bstp_nmix_prdy_ctrt": "9.84"},
                        {"hts_kor_isnm": "Nikkei 225 Futures Leveraged Index", "bstp_nmix_prdy_ctrt": "8.80"},
                        {"hts_kor_isnm": "Bloomberg WTI Crude Oil Single TR", "bstp_nmix_prdy_ctrt": "7.80"},
                        {"hts_kor_isnm": "반도체", "bstp_nmix_prdy_ctrt": "1.24"},
                        {"hts_kor_isnm": "코스닥 150 헬스케어", "bstp_nmix_prdy_ctrt": "0.90"},
                        {"hts_kor_isnm": "금융", "bstp_nmix_prdy_ctrt": "-0.72"},
                        {"hts_kor_isnm": "건설", "bstp_nmix_prdy_ctrt": "-1.50"},
                        {"hts_kor_isnm": "K건설", "bstp_nmix_prdy_ctrt": "-1.70"},
                        {"hts_kor_isnm": "바이오", "bstp_nmix_prdy_ctrt": "0.51"},
                    ]
                },
            )

        if request.url.path.endswith("/inquire-investor-time-by-market"):
            assert request.url.params["FID_INPUT_ISCD"] == "999"
            assert request.url.params["FID_INPUT_ISCD_2"] == "S001"
            return httpx.Response(
                200,
                json={
                    "output": {
                        "frgn_ntby_tr_pbmn": "-8200000",
                        "orgn_ntby_tr_pbmn": "3400000",
                        "prsn_ntby_tr_pbmn": "4800000",
                    }
                },
            )

        return httpx.Response(404, json={"error": "unexpected path"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(
        db_path=db_path,
        kis_app_key="app-key",
        kis_app_secret="app-secret",
        kis_token_cache_path=str(tmp_path / "kis_token_cache.json"),
        argus_market_reaction_provider="kis",
        argus_news_triggers_provider="disabled",
    )

    try:
        result = run_context_collection(
            settings=settings,
            trade_date=date(2026, 5, 12),
            snapshot_time=datetime(2026, 5, 12, 4, 0, tzinfo=timezone.utc),
            http_client=client,
        )
    finally:
        client.close()

    assert result.providers[0].status == "success"
    assert result.providers[0].market_reaction_snapshot_count == 1
    assert result.providers[1].status == "skipped"
    assert len(requests) == 6

    with get_connection(db_path) as connection:
        reaction = ArgusV2Storage(connection).get_latest_market_reaction_snapshot()

    assert reaction is not None
    assert reaction["kospi_change_rate"] == -0.42
    assert reaction["kosdaq_change_rate"] == 0.18
    assert reaction["advancing_count"] == 800
    assert reaction["declining_count"] == 780
    assert reaction["spot_foreign_net_buy"] == -82_000_000_000
    assert reaction["spot_institution_net_buy"] == 34_000_000_000
    assert reaction["spot_individual_net_buy"] == 48_000_000_000
    assert reaction["strong_sectors"][0]["name"] == "반도체"
    assert reaction["weak_sectors"][0]["name"] == "건설"
    assert reaction["weak_sectors"][0]["change_rate"] == -1.7
    strong_sector_names = {sector["name"] for sector in reaction["strong_sectors"]}
    assert "Nikkei 225 Futures Leveraged Index" not in strong_sector_names
    assert "Bloomberg WTI Crude Oil Single TR" not in strong_sector_names
    assert "헬스케어" in strong_sector_names


def test_context_collection_reads_naver_news_triggers(tmp_path):
    db_path = str(tmp_path / "argus-v2.db")
    decisions = {
        "환율 상승과 반도체 강세": {
            "should_use": True,
            "impact": "neutral",
            "relevance_score": 80,
            "connection_strength": "strong",
            "affected_factors": ["환율", "반도체"],
            "summary": "환율 부담과 반도체 강세가 동시에 관찰됩니다.",
            "reason": "국내 지수와 대형주 흐름에 연결됩니다.",
            "confidence": "medium",
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return _ai_decision_response(_decision_for_ai_request(request, decisions))
        assert request.headers["X-Naver-Client-Id"] == "naver-id"
        assert request.headers["X-Naver-Client-Secret"] == "naver-secret"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "title": "환율 상승과 반도체 강세",
                        "originallink": "https://example.test/naver-news",
                        "description": "달러 강세 부담에도 반도체가 강세입니다.",
                        "pubDate": "Tue, 12 May 2026 12:40:00 +0900",
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(
        db_path=db_path,
        argus_market_reaction_provider="disabled",
        argus_news_triggers_provider="naver",
        argus_news_triggers_query="반도체",
        argus_news_naver_client_id="naver-id",
        argus_news_naver_client_secret="naver-secret",
        argus_news_naver_display=1,
        argus_news_naver_page_limit=1,
        **_news_ai_settings(),
    )

    try:
        result = run_context_collection(
            settings=settings,
            trade_date=date(2026, 5, 12),
            snapshot_time=datetime(2026, 5, 12, 4, 0, tzinfo=timezone.utc),
            http_client=client,
        )
    finally:
        client.close()

    assert result.providers[1].status == "success"
    assert result.providers[1].news_trigger_count == 1

    with get_connection(db_path) as connection:
        trigger = ArgusV2Storage(connection).get_latest_news_triggers()[0]

    assert trigger["title"] == "환율 상승과 반도체 강세"
    assert trigger["source_name"] == "example.test"


def test_context_collection_reads_dart_disclosure_triggers(tmp_path):
    db_path = str(tmp_path / "argus-v2.db")
    decisions = {
        "테스트전자 단일판매ㆍ공급계약체결": {
            "should_use": True,
            "impact": "positive",
            "relevance_score": 76,
            "connection_strength": "medium",
            "affected_factors": ["DART", "공급계약"],
            "summary": "테스트전자 공급계약 공시는 개별 대형주 수급에 우호적입니다.",
            "reason": "공시 원문 기반의 기업 이벤트입니다.",
            "confidence": "medium",
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return _ai_decision_response(_decision_for_ai_request(request, decisions))
        assert request.url.params["crtfc_key"] == "dart-key"
        assert request.url.params["bgn_de"] == "20260512"
        assert request.url.params["end_de"] == "20260512"
        return httpx.Response(
            200,
            json={
                "status": "000",
                "list": [
                    {
                        "corp_name": "테스트전자",
                        "corp_code": "00123456",
                        "stock_code": "000001",
                        "corp_cls": "Y",
                        "report_nm": "단일판매ㆍ공급계약체결",
                        "rcept_no": "20260512000001",
                        "rcept_dt": "20260512",
                        "flr_nm": "테스트전자",
                    }
                ],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(
        db_path=db_path,
        argus_market_reaction_provider="disabled",
        argus_news_triggers_provider="dart",
        argus_disclosure_dart_api_key="dart-key",
        argus_disclosure_dart_corp_cls="Y",
        argus_disclosure_dart_pblntf_ty="I",
        **_news_ai_settings(),
    )

    try:
        result = run_context_collection(
            settings=settings,
            trade_date=date(2026, 5, 12),
            snapshot_time=datetime(2026, 5, 12, 4, 0, tzinfo=timezone.utc),
            http_client=client,
        )
    finally:
        client.close()

    assert result.providers[1].status == "success"
    assert result.providers[1].news_trigger_count == 1

    with get_connection(db_path) as connection:
        trigger = ArgusV2Storage(connection).get_latest_news_triggers()[0]

    assert trigger["external_id"] == "dart-20260512000001"
    assert trigger["title"] == "테스트전자 단일판매ㆍ공급계약체결"
    assert trigger["impact"] == "positive"
