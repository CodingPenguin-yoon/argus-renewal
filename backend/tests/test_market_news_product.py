from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.config.env import get_settings
from src.krx.company_master.db import get_connection, utcnow_iso
from src.krx.news.service import NewsProductService
from src.krx.provider_registry import build_provider_definition, ensure_provider_definition
from src.krx.source_ingestion.event_service import EventNormalizationService
from src.krx.source_ingestion.llm import DisabledLLMExtractionProvider
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


def _make_event_service(tmp_path: Path) -> tuple[EventNormalizationService, str]:
    db_path = str(tmp_path / "market-news.db")
    return (
        EventNormalizationService(
            db_path=db_path,
            llm_provider=DisabledLLMExtractionProvider(),
            low_confidence_threshold=0.55,
        ),
        db_path,
    )


def _make_news_service(
    db_path: str,
    *,
    scores: dict[str, float] | None = None,
    disabled_reason: str | None = None,
) -> NewsProductService:
    return NewsProductService(
        db_path=db_path,
        datalab_provider=StubDatalabProvider(scores=scores, disabled_reason=disabled_reason),
        lookback_days=7,
        card_limit=12,
        representative_evidence_limit=3,
        refresh_ttl_seconds=300,
        datalab_window_days=7,
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
    event_service, db_path = _make_event_service(tmp_path)

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

    result = event_service.normalize_pending_documents(limit=50, include_llm=False)
    assert result.status == "SUCCESS"

    news_service = _make_news_service(
        db_path,
        scores={"group-1": 74.0, "group-2": 61.0, "group-3": 12.0},
    )
    news_service.refresh_materialized(force=True)

    with get_connection(db_path) as connection:
        source_documents = connection.execute(
            "SELECT provider, storage_policy FROM source_documents ORDER BY provider, id"
        ).fetchall()
        evidence_rows = connection.execute(
            """
            SELECT ne.market_scope, COUNT(*) AS evidence_count
            FROM event_evidence ee
            JOIN normalized_events ne ON ne.id = ee.normalized_event_id
            GROUP BY ne.market_scope
            ORDER BY ne.market_scope
            """
        ).fetchall()
        card_rows = connection.execute(
            "SELECT column_key, market_scope FROM news_cards ORDER BY ranking_score DESC, id DESC"
        ).fetchall()

    assert ("DART", "CANONICAL_EVENT") in {(row["provider"], row["storage_policy"]) for row in source_documents}
    assert ("MK_RSS", "PERSISTENT_EVIDENCE") in {(row["provider"], row["storage_policy"]) for row in source_documents}
    assert ("NAVER_NEWS", "TRANSIENT_DISCOVERY") in {(row["provider"], row["storage_policy"]) for row in source_documents}
    assert any(row["market_scope"] == "kr_market" and row["evidence_count"] >= 2 for row in evidence_rows)
    assert {row["column_key"] for row in card_rows} == {"KR", "GLOBAL"}


def test_market_news_product_ranking_prefers_confirmed_high_quality_events(tmp_path: Path) -> None:
    _, db_path = _make_event_service(tmp_path)

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
    assert cards[0]["ranking_score"] > cards[1]["ranking_score"]


def test_market_news_product_canonical_dart_event_prefers_primary_disclosure_evidence(tmp_path: Path) -> None:
    event_service, db_path = _make_event_service(tmp_path)

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

    result = event_service.normalize_pending_documents(limit=50, include_llm=False)
    assert result.status == "SUCCESS"

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
        normalized_event = connection.execute(
            """
            SELECT ne.provenance_json
            FROM news_cards nc
            JOIN normalized_events ne ON ne.id = nc.normalized_event_id
            WHERE nc.card_key = ?
            """,
            (dart_card["id"],),
        ).fetchone()

    assert normalized_event is not None
    provenance = json.loads(normalized_event["provenance_json"])
    assert provenance["canonical_anchor"] is True
    assert provenance["persistent_evidence"] is True
    assert provenance["event_subtype"] == "capital_return"
    assert provenance["impact_direction"] == "positive"
    assert set(provenance["publisher_keys"]) == {"DART", "매일경제"}


def test_market_news_product_uses_observed_at_when_news_published_at_missing(tmp_path: Path) -> None:
    event_service, db_path = _make_event_service(tmp_path)
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

    result = event_service.normalize_pending_documents(limit=20, include_llm=False)
    assert result.status == "SUCCESS"

    news_service = _make_news_service(db_path)
    news_service.refresh_materialized(force=True)

    with get_connection(db_path) as connection:
        source_document = connection.execute(
            """
            SELECT provider, published_at, observed_at, published_at_source
            FROM source_documents
            WHERE provider = 'MK_RSS'
            """
        ).fetchone()
        evidence = connection.execute(
            """
            SELECT provider, published_at, observed_at
            FROM event_evidence
            WHERE provider = 'MK_RSS'
            """
        ).fetchone()
        card = connection.execute(
            """
            SELECT published_at
            FROM news_cards
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    assert source_document is not None
    assert source_document["published_at"] is None
    assert source_document["observed_at"] == observed_at
    assert source_document["published_at_source"] == "OBSERVED_AT"
    assert evidence is not None
    assert evidence["published_at"] == observed_at
    assert evidence["observed_at"] == observed_at
    assert card is not None
    assert card["published_at"] == observed_at


def test_market_news_product_accepts_unregistered_custom_provider(tmp_path: Path) -> None:
    _, db_path = _make_event_service(tmp_path)

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
        source_document = connection.execute(
            """
            SELECT provider, document_kind, storage_policy
            FROM source_documents
            WHERE provider = 'CUSTOM_RSS'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    assert source_document is not None
    assert source_document["document_kind"] == "DISCOVERY_CANDIDATE"
    assert source_document["storage_policy"] == "TRANSIENT_DISCOVERY"
    assert any(item["provider"] == "CUSTOM_RSS" and item["status"] == "available" for item in coverage["items"])
    assert cards
    assert cards[0]["evidence"][0]["provider"] == "CUSTOM_RSS"


def test_market_news_product_registered_custom_provider_uses_registry_storage_policy(tmp_path: Path) -> None:
    _, db_path = _make_event_service(tmp_path)
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

    with get_connection(db_path) as connection:
        source_document = connection.execute(
            """
            SELECT provider, document_kind, storage_policy
            FROM source_documents
            WHERE provider = 'CUSTOM_RSS'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        coverage_row = connection.execute(
            """
            SELECT provider, status
            FROM source_coverage
            WHERE surface_key = 'news_tab' AND provider = 'CUSTOM_RSS'
            """
        ).fetchone()

    assert source_document is not None
    assert source_document["document_kind"] == "CURATED_NEWS"
    assert source_document["storage_policy"] == "PERSISTENT_EVIDENCE"
    assert coverage_row is not None
    assert coverage_row["status"] == "available"


def test_market_news_product_empty_and_partial_coverage_states(tmp_path: Path) -> None:
    _, db_path = _make_event_service(tmp_path)
    news_service = _make_news_service(db_path, disabled_reason="missing_naver_datalab_credentials")
    news_service.refresh_materialized(force=True)

    coverage = news_service.get_coverage()
    header = news_service.get_header_context()

    assert coverage["state"] == "empty"
    assert coverage["expected_sources"] == 4
    assert any(item["provider"] == "NAVER_DATALAB" and item["status"] == "missing" for item in coverage["items"])
    assert header["summary_line"] == "표시 가능한 이벤트 카드가 아직 준비되지 않았습니다."


def test_market_news_product_api_endpoints(tmp_path: Path, monkeypatch) -> None:
    event_service, db_path = _make_event_service(tmp_path)

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

    result = event_service.normalize_pending_documents(limit=50, include_llm=False)
    assert result.status == "SUCCESS"

    monkeypatch.setenv("DB_PATH", db_path)
    get_settings.cache_clear()

    client = TestClient(app)
    try:
        kr_response = client.get("/api/news/kr")
        global_response = client.get("/api/news/global")
        disclosures_response = client.get("/api/news/disclosures")
        header_response = client.get("/api/news/header-context")
        coverage_response = client.get("/api/news/coverage")
    finally:
        get_settings.cache_clear()

    assert kr_response.status_code == 200
    assert global_response.status_code == 200
    assert disclosures_response.status_code == 200
    assert header_response.status_code == 200
    assert coverage_response.status_code == 200
    assert len(kr_response.json()["items"]) >= 1
    assert len(global_response.json()["items"]) >= 1
    assert len(disclosures_response.json()["items"]) >= 1
    assert disclosures_response.json()["items"][0]["evidence"][0]["provider"] == "DART"
    assert header_response.json()["columns"][0]["label"] == "한국 증시"
    assert "items" in coverage_response.json()
