from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.config.env import get_settings
from src.krx.company_master.db import get_connection, utcnow_iso
from src.krx.news.service import NewsProductService
from src.krx.source_ingestion.event_service import EventNormalizationService
from src.krx.source_ingestion.llm import DisabledLLMExtractionProvider
from src.krx.source_ingestion.providers.naver_datalab_provider import (
    TrendKeywordGroup,
    TrendScore,
    TrendScoreBatch,
)
from src.main import app


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
) -> int:
    now = utcnow_iso()
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                now,
                now,
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

    primary_bigkinds_id = _insert_raw_document(
        db_path,
        provider="BIGKINDS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="BK-100",
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
        duplicate_of_document_id=primary_bigkinds_id,
    )

    _insert_raw_document(
        db_path,
        provider="BIGKINDS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="BK-200",
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
    assert ("BIGKINDS", "PERSISTENT_EVIDENCE") in {(row["provider"], row["storage_policy"]) for row in source_documents}
    assert ("NAVER_NEWS", "TRANSIENT_DISCOVERY") in {(row["provider"], row["storage_policy"]) for row in source_documents}
    assert any(row["market_scope"] == "kr_market" and row["evidence_count"] >= 2 for row in evidence_rows)
    assert {row["column_key"] for row in card_rows} == {"KR", "GLOBAL"}


def test_market_news_product_ranking_prefers_confirmed_high_quality_events(tmp_path: Path) -> None:
    _, db_path = _make_event_service(tmp_path)

    primary_id = _insert_raw_document(
        db_path,
        provider="BIGKINDS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="BK-301",
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
    _, db_path = _make_event_service(tmp_path)

    _insert_raw_document(
        db_path,
        provider="BIGKINDS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="BK-401",
        title="코스피 수급 안정, 프로그램 매수 유입",
        summary="한국 증시 전반에 수급 안정 신호가 나타났다.",
        publisher="한국경제",
        source_url="https://example.com/api-kr",
        canonical_url="https://example.com/api-kr",
        query_text="코스피 증시",
    )
    _insert_raw_document(
        db_path,
        provider="BIGKINDS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="BK-402",
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
        kr_response = client.get("/api/news/kr")
        global_response = client.get("/api/news/global")
        header_response = client.get("/api/news/header-context")
        coverage_response = client.get("/api/news/coverage")
    finally:
        get_settings.cache_clear()

    assert kr_response.status_code == 200
    assert global_response.status_code == 200
    assert header_response.status_code == 200
    assert coverage_response.status_code == 200
    assert len(kr_response.json()["items"]) >= 1
    assert len(global_response.json()["items"]) >= 1
    assert header_response.json()["columns"][0]["label"] == "한국 증시"
    assert "items" in coverage_response.json()
