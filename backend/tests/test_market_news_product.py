from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.config.env import get_settings
from src.krx.company_master.db import get_connection, utcnow_iso
from src.krx.news.editorial_ai import (
    NewsEditorialAIRequest,
    NewsEditorialAIResponse,
    OpenAICompatibleNewsEditorialAIProvider,
)
from src.krx.news.service import NewsProductService
from src.krx.provider_registry import build_provider_definition, ensure_provider_definition
from src.krx.source_ingestion.providers.naver_datalab_provider import (
    TrendKeywordGroup,
    TrendScore,
    TrendScoreBatch,
)
from src.main import app

_UNSET = object()


class StubDatalabProvider:
    def __init__(self, scores: dict[str, float] | None = None, *, disabled_reason: str | None = None) -> None:
        self.scores = scores or {}
        self.disabled_reason = disabled_reason

    def fetch_interest_scores(self, *, start_date, end_date, groups: list[TrendKeywordGroup]) -> TrendScoreBatch:
        if self.disabled_reason:
            return TrendScoreBatch(scores={}, disabled_reason=self.disabled_reason)
        return TrendScoreBatch(
            scores={
                group.group_name: TrendScore(
                    group_name=group.group_name,
                    latest_ratio=self.scores.get(group.group_name, 0.0),
                    average_ratio=self.scores.get(group.group_name, 0.0),
                    latest_period=end_date.isoformat(),
                    datapoint_count=3,
                )
                for group in groups
            }
        )


class StubEditorialAIProvider:
    provider_name = "stub_editorial_ai"

    def __init__(self, response_by_title: dict[str, NewsEditorialAIResponse] | None = None) -> None:
        self.response_by_title = response_by_title or {}

    def is_enabled(self) -> tuple[bool, str | None]:
        return True, None

    def model_name(self) -> str | None:
        return "stub-model"

    def enrich(self, request: NewsEditorialAIRequest) -> NewsEditorialAIResponse | None:
        return self.response_by_title.get(request.title)


def _make_db_path(tmp_path: Path) -> str:
    return str(tmp_path / "market-news.db")


def _make_news_service(
    db_path: str,
    *,
    scores: dict[str, float] | None = None,
    disabled_reason: str | None = None,
    editorial_provider=None,
    editorial_candidate_limit: int = 8,
    editorial_min_score: float = 0.55,
) -> NewsProductService:
    return NewsProductService(
        db_path=db_path,
        datalab_provider=StubDatalabProvider(scores=scores, disabled_reason=disabled_reason),
        editorial_ai_provider=editorial_provider,
        lookback_days=7,
        card_limit=12,
        representative_evidence_limit=3,
        refresh_ttl_seconds=300,
        datalab_window_days=7,
        editorial_ai_candidate_limit=editorial_candidate_limit,
        editorial_ai_min_editorial_score=editorial_min_score,
    )


def _insert_company(
    db_path: str,
    *,
    canonical_key: str,
    canonical_name: str,
    primary_stock_code: str | None = None,
    market_classification: str | None = None,
) -> int:
    now = utcnow_iso()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO companies (
                canonical_key,
                canonical_name,
                primary_stock_code,
                market_classification,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (canonical_key, canonical_name, primary_stock_code, market_classification, now, now),
        )
        row = connection.execute("SELECT last_insert_rowid() AS id").fetchone()
    assert row is not None
    return int(row["id"])


def _insert_dart_mapping(db_path: str, *, corp_code: str, corp_name: str, company_id: int) -> None:
    now = utcnow_iso()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO company_source_mappings (
                source_system,
                source_record_id,
                source_name,
                company_id,
                mapping_status,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("DART", corp_code, corp_name, company_id, "MAPPED", now, now),
        )


def _insert_raw_document(
    db_path: str,
    *,
    provider: str,
    document_type: str,
    title: str,
    summary: str | None,
    publisher: str | None,
    source_url: str,
    canonical_url: str | None,
    provider_document_id: str | None = None,
    company_id: int | None = None,
    company_ref: str | None = None,
    query_text: str | None = None,
    provider_metadata: dict[str, object] | None = None,
    is_duplicate: int = 0,
    duplicate_of_document_id: int | None = None,
    published_at: str | object = _UNSET,
    observed_at: str | object = _UNSET,
    receipt_at: str | object = _UNSET,
    published_at_source: str | object = _UNSET,
) -> int:
    now = utcnow_iso()
    resolved_published_at = now if published_at is _UNSET else published_at
    resolved_observed_at = now if observed_at is _UNSET else observed_at
    resolved_receipt_at = now if receipt_at is _UNSET else receipt_at
    resolved_published_at_source = "PROVIDER" if published_at_source is _UNSET else published_at_source
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO raw_documents (
                provider,
                provider_document_id,
                document_type,
                title,
                summary,
                publisher,
                source_url,
                canonical_url,
                published_at,
                observed_at,
                published_at_source,
                receipt_at,
                report_type,
                company_id,
                company_ref,
                query_text,
                normalized_title_hash,
                is_duplicate,
                duplicate_of_document_id,
                provider_metadata_json,
                raw_payload_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                provider,
                provider_document_id,
                document_type,
                title,
                summary,
                publisher,
                source_url,
                canonical_url,
                resolved_published_at,
                resolved_observed_at,
                resolved_published_at_source,
                resolved_receipt_at,
                title,
                company_id,
                company_ref,
                query_text,
                None,
                is_duplicate,
                duplicate_of_document_id,
                json.dumps(provider_metadata or {}, ensure_ascii=False, sort_keys=True),
                json.dumps({"title": title}, ensure_ascii=False, sort_keys=True),
                now,
                now,
            ),
        )
        row = connection.execute("SELECT last_insert_rowid() AS id").fetchone()
    assert row is not None
    return int(row["id"])


def _register_provider(
    db_path: str,
    *,
    provider_key: str,
    provider_family: str,
    trust_score: float,
    priority: int,
) -> None:
    with get_connection(db_path) as connection:
        ensure_provider_definition(
            connection,
            build_provider_definition(
                provider_key=provider_key,
                provider_family=provider_family,
                trust_score=trust_score,
                priority=priority,
            ),
        )


def test_market_news_product_materializes_event_first_cards(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    samsung_id = _insert_company(
        db_path,
        canonical_key="manual:samsung",
        canonical_name="삼성전자",
        primary_stock_code="005930",
        market_classification="반도체",
    )
    _insert_dart_mapping(db_path, corp_code="00126380", corp_name="삼성전자", company_id=samsung_id)

    _insert_raw_document(
        db_path,
        provider="DART",
        document_type="DISCLOSURE",
        provider_document_id="20260310000111",
        title="삼성전자 공급계약 공시",
        summary="공급 계약 관련 공시",
        publisher="DART",
        source_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260310000111",
        canonical_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260310000111",
        company_id=samsung_id,
        provider_metadata={"corp_code": "00126380", "corp_name": "삼성전자"},
    )

    primary_curated_id = _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-100",
        title="코스피 반도체주 강세, 외국인 순매수 확대",
        summary="반도체 업종과 코스피 수급이 동시에 개선됐다.",
        publisher="한국경제",
        source_url="https://example.com/kr-market",
        canonical_url="https://example.com/kr-market",
        company_id=samsung_id,
        query_text="반도체 증시",
    )

    _insert_raw_document(
        db_path,
        provider="NAVER_NEWS",
        document_type="NEWS_CANDIDATE",
        title="코스피 반도체주 강세, 외국인 순매수 확대",
        summary="같은 이슈를 네이버 탐색 결과로 발견",
        publisher="연합뉴스",
        source_url="https://example.com/kr-market?utm_source=naver",
        canonical_url="https://example.com/kr-market",
        company_id=samsung_id,
        query_text="반도체 증시",
        is_duplicate=1,
        duplicate_of_document_id=primary_curated_id,
    )

    _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-200",
        title="연준 매파 발언에 달러 강세, 아시아 위험자산 경계감 확대",
        summary="미국 금리 기대가 높아지면서 원화와 외국인 수급 부담이 커졌다.",
        publisher="매일경제",
        source_url="https://example.com/global-market",
        canonical_url="https://example.com/global-market",
        query_text="연준 증시",
    )


    news_service = _make_news_service(
        db_path,
        scores={"group-1": 74.0, "group-2": 61.0, "group-3": 12.0},
    )
    news_service.refresh_materialized(force=True)
    kr_cards = news_service.list_cards(region="KR", limit=10)
    global_cards = news_service.list_cards(region="GLOBAL", limit=10)
    disclosure_cards = news_service.list_disclosure_cards(limit=10)

    with get_connection(db_path) as connection:
        triage_rows = connection.execute(
            """
            SELECT provider, market_scope, market_importance_prelim
            FROM news_batch_triage
            ORDER BY provider, raw_document_id
            """
        ).fetchall()
        candidate_rows = connection.execute(
            """
            SELECT surface_key, source_kind
            FROM market_surface_candidates
            ORDER BY surface_key, ranking_score DESC, id DESC
            """
        ).fetchall()
        state_rows = connection.execute(
            """
            SELECT surface_key, active_candidate_key
            FROM market_surface_state
            WHERE surface_key IN ('KR', 'GLOBAL', 'DISCLOSURE')
            ORDER BY surface_key
            """
        ).fetchall()
        history_rows = connection.execute(
            """
            SELECT surface_key, change_type
            FROM market_surface_history
            ORDER BY id
            """
        ).fetchall()

    assert {row["provider"] for row in triage_rows} >= {"DART", "MK_RSS", "NAVER_NEWS"}
    assert any(row["provider"] == "DART" and row["market_scope"] == "company" for row in triage_rows)
    assert {row["surface_key"] for row in candidate_rows} >= {"KR", "GLOBAL", "DISCLOSURE"}
    assert {row["surface_key"] for row in state_rows} == {"DISCLOSURE", "GLOBAL", "KR"}
    assert {row["surface_key"] for row in history_rows} >= {"KR", "GLOBAL", "DISCLOSURE"}
    assert any(card["market_scope"] == "kr_market" and card["evidence_count"] >= 2 for card in kr_cards)
    assert global_cards
    assert disclosure_cards


def test_market_news_product_ranking_prefers_confirmed_high_quality_events(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    primary_id = _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-301",
        title="코스피 수급 개선, 외국인 순매수 확대",
        summary="국내 지수와 수급이 동반 개선됐다.",
        publisher="한국경제",
        source_url="https://example.com/rank-high",
        canonical_url="https://example.com/rank-high",
        query_text="코스피 증시",
    )
    _insert_raw_document(
        db_path,
        provider="NAVER_NEWS",
        document_type="NEWS_CANDIDATE",
        title="코스피 수급 개선, 외국인 순매수 확대",
        summary="탐색 경로에서도 같은 이슈가 확인됐다.",
        publisher="연합뉴스",
        source_url="https://example.com/rank-high?utm_source=naver",
        canonical_url="https://example.com/rank-high",
        query_text="코스피 증시",
        is_duplicate=1,
        duplicate_of_document_id=primary_id,
    )
    _insert_raw_document(
        db_path,
        provider="NAVER_NEWS",
        document_type="NEWS_CANDIDATE",
        title="속보 코스피 관련주 급등",
        summary="관련주 중심 단기 반응",
        publisher="블로그",
        source_url="https://example.com/rank-low",
        canonical_url="https://example.com/rank-low",
        query_text="코스피 증시",
    )

    news_service = _make_news_service(
        db_path,
        scores={"group-1": 55.0, "group-2": 10.0},
    )
    news_service.refresh_materialized(force=True)

    cards = news_service.list_cards(region="KR", limit=10)

    assert len(cards) >= 2
    assert cards[0]["title"] == "코스피 수급 개선, 외국인 순매수 확대"
    assert cards[0]["materiality_score"] >= cards[1]["materiality_score"]
    assert cards[0]["editorial_score"] >= cards[1]["editorial_score"]
    assert cards[0]["ranking_score"] > cards[1]["ranking_score"]


def test_market_news_product_applies_editorial_ai_enrichment(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-EDITORIAL-1",
        title="코스피 반도체주 강세, 외국인 순매수 확대",
        summary="한국 증시 대표 섹터에 수급 개선이 겹쳤다.",
        publisher="매일경제",
        source_url="https://example.com/editorial-1",
        canonical_url="https://example.com/editorial-1",
        query_text="반도체 증시",
    )

    response = NewsEditorialAIResponse(
        story_state="ONGOING",
        importance_label="high",
        editorial_reason="외국인 수급과 핵심 섹터 흐름이 겹쳐 오늘 요약판 상단 후보입니다.",
        editorial_boost=0.06,
        confidence=0.81,
        raw_output={
            "story_state": "ONGOING",
            "importance_label": "high",
            "editorial_reason": "외국인 수급과 핵심 섹터 흐름이 겹쳐 오늘 요약판 상단 후보입니다.",
            "editorial_boost": 0.06,
            "confidence": 0.81,
        },
    )
    news_service = _make_news_service(
        db_path,
        scores={"group-1": 61.0},
        editorial_provider=StubEditorialAIProvider(
            response_by_title={"코스피 반도체주 강세, 외국인 순매수 확대": response}
        ),
        editorial_candidate_limit=3,
        editorial_min_score=0.2,
    )
    news_service.refresh_materialized(force=True)

    cards = news_service.list_cards(region="KR", limit=10)

    assert cards
    assert cards[0]["story_state"] == "ONGOING"
    assert cards[0]["importance_label"] == "high"
    assert cards[0]["editorial_reason"] == response.editorial_reason
    assert abs(float(cards[0]["ai_confidence"]) - 0.81) < 1e-6
    assert abs(float(cards[0]["ranking_score"]) - float(cards[0]["editorial_score"])) < 1e-6
    assert cards[0]["provenance"]["ai_provider"] == "stub_editorial_ai"


def test_market_news_product_canonical_dart_event_prefers_primary_disclosure_evidence(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    samsung_id = _insert_company(
        db_path,
        canonical_key="manual:samsung-dividend",
        canonical_name="삼성전자",
        primary_stock_code="005930",
        market_classification="반도체",
    )
    _insert_dart_mapping(db_path, corp_code="00126380", corp_name="삼성전자", company_id=samsung_id)

    _insert_raw_document(
        db_path,
        provider="DART",
        document_type="DISCLOSURE",
        provider_document_id="20260311000001",
        title="삼성전자 현금ㆍ현물배당결정",
        summary="배당 결정 공시",
        publisher="DART",
        source_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260311000001",
        canonical_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260311000001",
        company_id=samsung_id,
        provider_metadata={"corp_code": "00126380", "corp_name": "삼성전자"},
    )

    primary_curated_id = _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-501",
        title="삼성전자 현금ㆍ현물배당결정",
        summary="매일경제에서 배당 결정 배경을 설명했다.",
        publisher="매일경제",
        source_url="https://www.mk.co.kr/news/stock/12000001",
        canonical_url="https://www.mk.co.kr/news/stock/12000001",
        company_id=samsung_id,
        query_text="삼성전자 배당",
    )

    _insert_raw_document(
        db_path,
        provider="NAVER_NEWS",
        document_type="NEWS_CANDIDATE",
        title="삼성전자 현금ㆍ현물배당결정",
        summary="네이버 검색 결과에서도 같은 배당 이슈가 확인됐다.",
        publisher="매경",
        source_url="https://search.naver.com/search.naver?query=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90+%EB%B0%B0%EB%8B%B9",
        canonical_url="https://www.mk.co.kr/news/stock/12000001",
        company_id=samsung_id,
        query_text="삼성전자 배당",
        is_duplicate=1,
        duplicate_of_document_id=primary_curated_id,
    )


    news_service = _make_news_service(db_path, scores={"group-1": 58.0})
    news_service.refresh_materialized(force=True)

    cards = news_service.list_cards(region="KR", limit=10)
    disclosure_cards = news_service.list_disclosure_cards(limit=10)
    dart_card = next((card for card in cards if card["evidence"] and card["evidence"][0]["provider"] == "DART"), None)

    assert dart_card is not None
    assert disclosure_cards
    assert disclosure_cards[0]["evidence"][0]["provider"] == "DART"
    assert dart_card["market_scope"] == "company"
    assert [evidence["provider"] for evidence in dart_card["evidence"][:3]] == ["DART", "MK_RSS", "NAVER_NEWS"]
    assert [evidence["role"] for evidence in dart_card["evidence"][:3]] == ["PRIMARY", "CONFIRMING", "DISCOVERY"]

    with get_connection(db_path) as connection:
        candidate = connection.execute(
            """
            SELECT payload_json, source_kind, surface_key
            FROM market_surface_candidates
            WHERE card_key = ?
            """,
            (dart_card["id"],),
        ).fetchone()

    assert candidate is not None
    assert candidate["source_kind"] == "news"
    assert candidate["surface_key"] == "KR"
    provenance = json.loads(candidate["payload_json"])["provenance"]
    assert provenance["canonical_anchor"] is True
    assert provenance["persistent_evidence"] is True
    assert provenance["event_subtype"] == "capital_return"
    assert provenance["impact_direction"] == "positive"
    assert {"매일경제", "dart"} <= set(provenance["publisher_keys"])


def test_market_news_product_uses_observed_at_when_news_published_at_missing(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)
    observed_at = "2026-03-10T09:15:00Z"

    _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-OBS-001",
        title="코스피 금리 경계감 확산",
        summary="발행시각 없이 수집됐지만 국내 증시 해석에는 필요한 기사",
        publisher="매일경제",
        source_url="https://www.mk.co.kr/news/economy/11985698",
        canonical_url="https://www.mk.co.kr/news/economy/11985698",
        query_text="금리",
        published_at=None,
        observed_at=observed_at,
        receipt_at=None,
        published_at_source="OBSERVED_AT",
    )


    news_service = _make_news_service(db_path)
    news_service.refresh_materialized(force=True)
    cards = news_service.list_cards(region="KR", limit=10)

    assert cards
    assert cards[0]["published_at"] == observed_at
    assert cards[0]["evidence"][0]["provider"] == "MK_RSS"
    assert cards[0]["evidence"][0]["published_at"] == observed_at


def test_market_news_product_accepts_unregistered_custom_provider(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    _insert_raw_document(
        db_path,
        provider="CUSTOM_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="RSS-201",
        title="코스피 반도체 업황 개선, 외국인 순매수 확대",
        summary="사용자 지정 RSS에서도 같은 시장 이슈가 수집됐다.",
        publisher="사용자 RSS",
        source_url="https://rss.example.com/201",
        canonical_url="https://rss.example.com/201",
        query_text="코스피 증시",
    )

    news_service = _make_news_service(
        db_path,
        scores={"group-1": 52.0},
    )
    news_service.refresh_materialized(force=True)

    coverage = news_service.get_coverage()
    cards = news_service.list_cards(region="KR", limit=10)

    with get_connection(db_path) as connection:
        triage_row = connection.execute(
            """
            SELECT provider, triage_metadata_json
            FROM news_batch_triage
            WHERE provider = 'CUSTOM_RSS'
            """
        ).fetchone()

    assert triage_row is not None
    assert any(item["provider"] == "CUSTOM_RSS" and item["status"] == "available" for item in coverage["items"])
    assert cards
    assert cards[0]["evidence"][0]["provider"] == "CUSTOM_RSS"
    assert cards[0]["evidence"][0]["storage_policy"] == "TRANSIENT_DISCOVERY"


def test_market_news_product_registered_custom_provider_uses_registry_storage_policy(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)
    _register_provider(
        db_path,
        provider_key="CUSTOM_RSS",
        provider_family="CURATED_NEWS",
        trust_score=0.86,
        priority=15,
    )

    _insert_raw_document(
        db_path,
        provider="CUSTOM_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="RSS-301",
        title="코스피 반도체 밸류체인 개선",
        summary="등록된 provider 의미가 뉴스 materialization에도 반영돼야 한다.",
        publisher="사용자 RSS",
        source_url="https://rss.example.com/301",
        canonical_url="https://rss.example.com/301",
        query_text="코스피 증시",
    )

    news_service = _make_news_service(
        db_path,
        scores={"group-1": 47.0},
    )
    news_service.refresh_materialized(force=True)
    cards = news_service.list_cards(region="KR", limit=10)

    with get_connection(db_path) as connection:
        triage_row = connection.execute(
            """
            SELECT provider
            FROM news_batch_triage
            WHERE provider = 'CUSTOM_RSS'
            """
        ).fetchone()

    assert triage_row is not None
    assert cards
    assert cards[0]["evidence"][0]["provider"] == "CUSTOM_RSS"
    assert cards[0]["evidence"][0]["storage_policy"] == "PERSISTENT_EVIDENCE"
    assert any(item["provider"] == "CUSTOM_RSS" and item["status"] == "available" for item in news_service.get_coverage()["items"])


def test_market_news_product_empty_and_partial_coverage_states(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)
    news_service = _make_news_service(db_path, disabled_reason="missing_naver_datalab_credentials")
    news_service.refresh_materialized(force=True)

    coverage = news_service.get_coverage()
    header = news_service.get_header_context()

    assert coverage["state"] == "empty"
    assert coverage["expected_sources"] == 4
    assert any(item["provider"] == "NAVER_DATALAB" and item["status"] == "missing" for item in coverage["items"])
    assert header["summary_line"] == "표시 가능한 이벤트 카드가 아직 준비되지 않았습니다."


def test_market_news_product_api_endpoints(tmp_path: Path, monkeypatch) -> None:
    db_path = _make_db_path(tmp_path)

    samsung_id = _insert_company(
        db_path,
        canonical_key="manual:samsung-api",
        canonical_name="삼성전자",
        primary_stock_code="005930",
        market_classification="반도체",
    )
    _insert_dart_mapping(db_path, corp_code="00126380", corp_name="삼성전자", company_id=samsung_id)

    _insert_raw_document(
        db_path,
        provider="DART",
        document_type="DISCLOSURE",
        provider_document_id="20260312000001",
        title="삼성전자 공급계약 체결",
        summary="대형 공급계약 공시",
        publisher="DART",
        source_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260312000001",
        canonical_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260312000001",
        company_id=samsung_id,
        provider_metadata={"corp_code": "00126380", "corp_name": "삼성전자"},
    )

    _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-401",
        title="코스피 수급 안정, 프로그램 매수 유입",
        summary="한국 증시 전반에 수급 안정 신호가 나타났다.",
        publisher="한국경제",
        source_url="https://example.com/api-kr",
        canonical_url="https://example.com/api-kr",
        query_text="코스피 증시",
    )
    _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-402",
        title="미국 CPI 경계감에 환율 민감도 확대",
        summary="글로벌 이벤트가 원화와 위험선호에 전이될 수 있다.",
        publisher="매일경제",
        source_url="https://example.com/api-global",
        canonical_url="https://example.com/api-global",
        query_text="미국 증시",
    )


    monkeypatch.setenv("DB_PATH", db_path)
    get_settings.cache_clear()

    client = TestClient(app)
    try:
        dashboard_response = client.get("/api/news/dashboard")
        kr_response = client.get("/api/news/kr")
        global_response = client.get("/api/news/global")
        disclosures_response = client.get("/api/news/disclosures")
        header_response = client.get("/api/news/header-context")
        coverage_response = client.get("/api/news/coverage")
        all_news_response = client.get("/api/krx/news")
        macro_news_response = client.get("/api/krx/news/macro")
        stock_news_response = client.get("/api/krx/news/stock")
        ticker_news_response = client.get("/api/krx/news/by-ticker/005930")
        search_response = client.get("/api/krx/news/search?q=%EA%B3%B5%EA%B8%89%EA%B3%84%EC%95%BD")
    finally:
        get_settings.cache_clear()

    assert dashboard_response.status_code == 200
    assert kr_response.status_code == 200
    assert global_response.status_code == 200
    assert disclosures_response.status_code == 200
    assert header_response.status_code == 200
    assert coverage_response.status_code == 200
    assert len(dashboard_response.json()["kr_cards"]) >= 1
    assert len(dashboard_response.json()["global_cards"]) >= 1
    assert len(dashboard_response.json()["disclosure_cards"]) >= 1
    assert dashboard_response.json()["header_context"]["columns"][0]["label"] == "한국 증시"
    assert dashboard_response.json()["coverage"]["items"]
    assert len(kr_response.json()["items"]) >= 1
    assert len(global_response.json()["items"]) >= 1
    assert len(disclosures_response.json()["items"]) >= 1
    assert disclosures_response.json()["items"][0]["evidence"][0]["provider"] == "DART"
    assert "materiality_score" in kr_response.json()["items"][0]
    assert "editorial_score" in kr_response.json()["items"][0]
    assert all_news_response.status_code == 200
    assert macro_news_response.status_code == 200
    assert stock_news_response.status_code == 200
    assert ticker_news_response.status_code == 200
    assert search_response.status_code == 200
    assert len(all_news_response.json()["items"]) >= 2
    assert "credibility_score" in all_news_response.json()["items"][0]
    assert "materiality_score" in all_news_response.json()["items"][0]
    assert "editorial_score" in all_news_response.json()["items"][0]
    assert any(item["type"] == "macro" for item in macro_news_response.json()["items"])
    assert any(item["type"] == "stock" for item in stock_news_response.json()["items"])
    assert len(ticker_news_response.json()["items"]) >= 1
    assert all("005930" in item["related_tickers"] for item in ticker_news_response.json()["items"])
    assert any("공급계약" in item["title"] for item in search_response.json()["items"])
    assert header_response.json()["columns"][0]["label"] == "한국 증시"
    assert "items" in coverage_response.json()

    detail_response = client.get(f"/api/krx/news/{ticker_news_response.json()['items'][0]['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["item"]["related_tickers"] == ["005930"]


class _RecordingHTTPClient:
    def __init__(self) -> None:
        self.last_url: str | None = None

    def post(self, url, headers=None, json=None, timeout=None):  # noqa: ANN001
        self.last_url = url
        return _StaticResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json_module.dumps(
                                {
                                    "story_state": "NEW",
                                    "importance_label": "medium",
                                    "editorial_reason": "stub",
                                    "editorial_boost": 0.01,
                                    "confidence": 0.8,
                                }
                            )
                        }
                    }
                ]
            }
        )


class _StaticResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.payload


json_module = json


def _sample_editorial_request() -> NewsEditorialAIRequest:
    return NewsEditorialAIRequest(
        cluster_key="cluster-1",
        title="삼성전자 공급계약 체결",
        one_line_summary="대형 공급계약",
        why_it_matters="실적 가시성 개선",
        market_impact="반도체 대형주 심리 개선",
        market_scope="kr_market",
        primary_region="KR",
        event_type="contract",
        event_subtype="supply",
        impact_direction="positive",
        impact_horizon="short",
        source_type="CURATED_NEWS",
        trust_score=0.8,
        materiality_score=0.72,
        novelty_score=0.6,
        cross_source_score=0.4,
        attention_score=0.5,
        evidence_count=2,
        direct_company_names=["삼성전자"],
        direct_company_tickers=["005930"],
        sector_tags=["반도체"],
        keyword_tags=["공급계약"],
        evidence=[{"title": "삼성전자 공급계약 체결"}],
    )


def test_openai_compatible_editorial_ai_supports_gemini_openai_base_url() -> None:
    client = _RecordingHTTPClient()
    provider = OpenAICompatibleNewsEditorialAIProvider(
        enabled=True,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        api_key="test-key",
        model="gemini-2.5-flash",
        timeout_seconds=20.0,
        max_retries=1,
        backoff_seconds=0.0,
        http_client=client,
    )

    response = provider.enrich(_sample_editorial_request())

    assert response is not None
    assert client.last_url == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"


def test_openai_compatible_editorial_ai_keeps_standard_v1_base_url() -> None:
    client = _RecordingHTTPClient()
    provider = OpenAICompatibleNewsEditorialAIProvider(
        enabled=True,
        base_url="https://api.openai.com",
        api_key="test-key",
        model="gpt-5-mini",
        timeout_seconds=20.0,
        max_retries=1,
        backoff_seconds=0.0,
        http_client=client,
    )

    response = provider.enrich(_sample_editorial_request())

    assert response is not None
    assert client.last_url == "https://api.openai.com/v1/chat/completions"
