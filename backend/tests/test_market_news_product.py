from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.config.env import get_settings
from src.krx.company_master.db import get_connection, utcnow_iso
from src.krx.news.batch_triage_ai import (
    NewsBatchTriageRequestItem,
    NewsBatchTriageResponseItem,
)
from src.krx.news.editorial_ai import (
    NewsEditorialAIBriefingRequest,
    NewsEditorialAIBriefingResponse,
    NewsEditorialAICompareRequest,
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

    def __init__(
        self,
        response_by_title: dict[str, NewsEditorialAIResponse] | None = None,
        response_by_cluster_key: dict[str, NewsEditorialAIResponse] | None = None,
        briefing_response: NewsEditorialAIBriefingResponse | None = None,
    ) -> None:
        self.response_by_title = response_by_title or {}
        self.response_by_cluster_key = response_by_cluster_key or {}
        self.briefing_response = briefing_response
        self.compare_requests: list[NewsEditorialAICompareRequest] = []
        self.briefing_requests: list[NewsEditorialAIBriefingRequest] = []

    def is_enabled(self) -> tuple[bool, str | None]:
        return True, None

    def model_name(self) -> str | None:
        return "stub-model"

    def compare(self, request: NewsEditorialAICompareRequest) -> dict[str, NewsEditorialAIResponse]:
        self.compare_requests.append(request)
        responses: dict[str, NewsEditorialAIResponse] = {}
        for candidate in request.candidates:
            if candidate.cluster_key in self.response_by_cluster_key:
                responses[candidate.cluster_key] = self.response_by_cluster_key[candidate.cluster_key]
                continue
            if candidate.title in self.response_by_title:
                responses[candidate.cluster_key] = self.response_by_title[candidate.title]
        return responses

    def enrich(self, request: NewsEditorialAIRequest) -> NewsEditorialAIResponse | None:
        return self.response_by_cluster_key.get(request.cluster_key) or self.response_by_title.get(request.title)

    def compose_briefing(self, request: NewsEditorialAIBriefingRequest) -> NewsEditorialAIBriefingResponse | None:
        self.briefing_requests.append(request)
        return self.briefing_response


class StubBatchTriageProvider:
    provider_name = "stub_batch_triage"

    def __init__(self, response_by_raw_document_id: dict[int, NewsBatchTriageResponseItem] | None = None) -> None:
        self.response_by_raw_document_id = response_by_raw_document_id or {}
        self.requests: list[list[NewsBatchTriageRequestItem]] = []

    def is_enabled(self) -> tuple[bool, str | None]:
        return True, None

    def model_name(self) -> str | None:
        return "stub-batch-model"

    def triage(self, request_items: list[NewsBatchTriageRequestItem]) -> dict[int, NewsBatchTriageResponseItem]:
        self.requests.append(list(request_items))
        return {
            raw_document_id: response
            for raw_document_id, response in self.response_by_raw_document_id.items()
            if any(item.raw_document_id == raw_document_id for item in request_items)
        }


def _make_db_path(tmp_path: Path) -> str:
    return str(tmp_path / "market-news.db")


def _make_news_service(
    db_path: str,
    *,
    scores: dict[str, float] | None = None,
    disabled_reason: str | None = None,
    batch_triage_provider=None,
    batch_triage_batch_size: int = 15,
    batch_triage_upgrade_legacy_rows: bool = True,
    editorial_provider=None,
    editorial_candidate_limit: int = 8,
    editorial_min_score: float = 0.55,
) -> NewsProductService:
    return NewsProductService(
        db_path=db_path,
        datalab_provider=StubDatalabProvider(scores=scores, disabled_reason=disabled_reason),
        batch_triage_provider=batch_triage_provider,
        editorial_ai_provider=editorial_provider,
        lookback_days=7,
        card_limit=12,
        representative_evidence_limit=3,
        refresh_ttl_seconds=300,
        datalab_window_days=7,
        batch_triage_batch_size=batch_triage_batch_size,
        batch_triage_upgrade_legacy_rows=batch_triage_upgrade_legacy_rows,
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


def test_market_news_product_reuses_persisted_triage_for_dashboard(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    raw_document_id = _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-PERSIST-001",
        title="코스피 수급 개선, 외국인 순매수 확대",
        summary="국내 증시 수급 개선 기사",
        publisher="매일경제",
        source_url="https://example.com/persisted-triage",
        canonical_url="https://example.com/persisted-triage",
        query_text="코스피 증시",
    )

    news_service = _make_news_service(db_path, scores={"group-1": 42.0})
    news_service.refresh_materialized(force=True)

    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT triage_metadata_json
            FROM news_batch_triage
            WHERE raw_document_id = ?
            """,
            (raw_document_id,),
        ).fetchone()
        assert row is not None
        triage_metadata = json.loads(row["triage_metadata_json"])
        triage_metadata.update(
            {
                "event_type": triage_metadata.get("event_type") or "macro",
                "event_subtype": triage_metadata.get("event_subtype") or "generic",
                "impact_horizon": triage_metadata.get("impact_horizon") or "short",
                "source_type": triage_metadata.get("source_type") or "CURATED_NEWS",
                "canonical_anchor": False,
            }
        )
        connection.execute(
            """
            UPDATE news_batch_triage
            SET
                market_scope = 'global_market',
                primary_region = 'GLOBAL',
                impact_direction = 'negative',
                market_importance_prelim = 'high',
                reason_short = '글로벌 변수',
                triage_metadata_json = ?,
                updated_at = ?
            WHERE raw_document_id = ?
            """,
            (
                json.dumps(triage_metadata, ensure_ascii=False, sort_keys=True),
                utcnow_iso(),
                raw_document_id,
            ),
        )

    news_service.refresh_materialized(force=True)
    kr_cards = news_service.list_cards(region="KR", limit=10)
    global_cards = news_service.list_cards(region="GLOBAL", limit=10)

    assert kr_cards == []
    assert global_cards
    assert global_cards[0]["title"] == "코스피 수급 개선, 외국인 순매수 확대"
    assert global_cards[0]["primary_region"] == "GLOBAL"
    assert global_cards[0]["market_scope"] == "global_market"


def test_market_news_product_refresh_preserves_existing_triage_rows(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    raw_document_id = _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-PERSIST-002",
        title="코스피 반도체 밸류체인 개선",
        summary="기존 triage row가 재생성 때 유지돼야 한다.",
        publisher="매일경제",
        source_url="https://example.com/persisted-row",
        canonical_url="https://example.com/persisted-row",
        query_text="코스피 증시",
    )

    news_service = _make_news_service(db_path, scores={"group-1": 37.0})
    news_service.refresh_materialized(force=True)

    with get_connection(db_path) as connection:
        first_row = connection.execute(
            """
            SELECT batch_key, created_at, updated_at
            FROM news_batch_triage
            WHERE raw_document_id = ?
            """,
            (raw_document_id,),
        ).fetchone()

    assert first_row is not None

    news_service.refresh_materialized(force=True)

    with get_connection(db_path) as connection:
        second_row = connection.execute(
            """
            SELECT batch_key, created_at, updated_at
            FROM news_batch_triage
            WHERE raw_document_id = ?
            """,
            (raw_document_id,),
        ).fetchone()
        row_count = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM news_batch_triage
            WHERE raw_document_id = ?
            """,
            (raw_document_id,),
        ).fetchone()

    assert second_row is not None
    assert row_count is not None
    assert row_count["count"] == 1
    assert second_row["batch_key"] == first_row["batch_key"]
    assert second_row["created_at"] == first_row["created_at"]


def test_market_news_product_batch_triage_persists_llm_rows(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    first_raw_document_id = _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-BATCH-001",
        title="미국 CPI 둔화에 나스닥 선물 강세",
        summary="글로벌 위험선호 개선 기사",
        publisher="매일경제",
        source_url="https://example.com/batch-1",
        canonical_url="https://example.com/batch-1",
        query_text="미국 CPI",
    )
    second_raw_document_id = _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-BATCH-002",
        title="코스피 수급 안정, 외국인 순매수 확대",
        summary="국내 증시 수급 개선 기사",
        publisher="매일경제",
        source_url="https://example.com/batch-2",
        canonical_url="https://example.com/batch-2",
        query_text="코스피 증시",
    )
    batch_provider = StubBatchTriageProvider(
        response_by_raw_document_id={
            first_raw_document_id: NewsBatchTriageResponseItem(
                raw_document_id=first_raw_document_id,
                market_scope="global_market",
                primary_region="GLOBAL",
                importance_label="high",
                impact_direction="positive",
                reason_short="미국 물가 둔화가 글로벌 위험선호를 자극했습니다.",
                confidence=0.84,
                raw_output={"raw_document_id": first_raw_document_id, "market_scope": "global_market"},
            ),
            second_raw_document_id: NewsBatchTriageResponseItem(
                raw_document_id=second_raw_document_id,
                market_scope="kr_market",
                primary_region="KR",
                importance_label="high",
                impact_direction="positive",
                reason_short="국내 수급 개선 신호가 지수 해석에 직접 연결됩니다.",
                confidence=0.77,
                raw_output={"raw_document_id": second_raw_document_id, "market_scope": "kr_market"},
            ),
        }
    )
    news_service = _make_news_service(db_path, batch_triage_provider=batch_provider)

    news_service.refresh_materialized(force=True)

    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT raw_document_id, market_scope, primary_region, triage_metadata_json
            FROM news_batch_triage
            ORDER BY raw_document_id ASC
            """
        ).fetchall()

    assert len(batch_provider.requests) == 1
    assert {item.raw_document_id for item in batch_provider.requests[0]} == {
        first_raw_document_id,
        second_raw_document_id,
    }
    assert len(rows) == 2
    first_metadata = json.loads(rows[0]["triage_metadata_json"])
    second_metadata = json.loads(rows[1]["triage_metadata_json"])
    assert rows[0]["market_scope"] == "global_market"
    assert rows[0]["primary_region"] == "GLOBAL"
    assert first_metadata["triage_method"] == "llm_batch"
    assert first_metadata["triage_provider"] == "stub_batch_triage"
    assert first_metadata["triage_model"] == "stub-batch-model"
    assert abs(float(first_metadata["triage_confidence"]) - 0.84) < 1e-6
    assert rows[1]["market_scope"] == "kr_market"
    assert second_metadata["triage_method"] == "llm_batch"


def test_market_news_product_batch_triage_upgrades_legacy_rows(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    raw_document_id = _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-LEGACY-001",
        title="미국 CPI 둔화에 나스닥 선물 강세",
        summary="글로벌 위험선호 개선 기사",
        publisher="매일경제",
        source_url="https://example.com/legacy-batch",
        canonical_url="https://example.com/legacy-batch",
        query_text="미국 CPI",
    )
    baseline_service = _make_news_service(db_path)
    baseline_service.refresh_materialized(force=True)

    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT triage_metadata_json
            FROM news_batch_triage
            WHERE raw_document_id = ?
            """,
            (raw_document_id,),
        ).fetchone()
        assert row is not None
        triage_metadata = json.loads(row["triage_metadata_json"])
        triage_metadata.pop("triage_method", None)
        triage_metadata.pop("triage_provider", None)
        triage_metadata.pop("triage_model", None)
        triage_metadata.pop("triage_confidence", None)
        triage_metadata.pop("triage_raw_output", None)
        connection.execute(
            """
            UPDATE news_batch_triage
            SET triage_metadata_json = ?, market_scope = 'ignore', primary_region = 'KR', updated_at = ?
            WHERE raw_document_id = ?
            """,
            (json.dumps(triage_metadata, ensure_ascii=False, sort_keys=True), utcnow_iso(), raw_document_id),
        )

    batch_provider = StubBatchTriageProvider(
        response_by_raw_document_id={
            raw_document_id: NewsBatchTriageResponseItem(
                raw_document_id=raw_document_id,
                market_scope="global_market",
                primary_region="GLOBAL",
                importance_label="high",
                impact_direction="positive",
                reason_short="글로벌 이벤트로 다시 분류했습니다.",
                confidence=0.88,
                raw_output={"raw_document_id": raw_document_id},
            )
        }
    )
    news_service = _make_news_service(db_path, batch_triage_provider=batch_provider)
    news_service.refresh_materialized(force=True)

    with get_connection(db_path) as connection:
        upgraded_row = connection.execute(
            """
            SELECT market_scope, primary_region, triage_metadata_json
            FROM news_batch_triage
            WHERE raw_document_id = ?
            """,
            (raw_document_id,),
        ).fetchone()

    assert upgraded_row is not None
    upgraded_metadata = json.loads(upgraded_row["triage_metadata_json"])
    assert upgraded_row["market_scope"] == "global_market"
    assert upgraded_row["primary_region"] == "GLOBAL"
    assert upgraded_metadata["triage_method"] == "llm_batch"
    assert upgraded_metadata["triage_provider"] == "stub_batch_triage"


def test_market_news_product_batch_triage_fallback_marks_provenance(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    first_raw_document_id = _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-FALLBACK-001",
        title="코스피 수급 안정, 외국인 순매수 확대",
        summary="국내 증시 수급 개선 기사",
        publisher="매일경제",
        source_url="https://example.com/fallback-1",
        canonical_url="https://example.com/fallback-1",
        query_text="코스피 증시",
    )
    second_raw_document_id = _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-FALLBACK-002",
        title="반도체 업종 혼조, 실적 발표 대기",
        summary="업종 단위 기사",
        publisher="매일경제",
        source_url="https://example.com/fallback-2",
        canonical_url="https://example.com/fallback-2",
        query_text="반도체 업종",
    )
    batch_provider = StubBatchTriageProvider(
        response_by_raw_document_id={
            first_raw_document_id: NewsBatchTriageResponseItem(
                raw_document_id=first_raw_document_id,
                market_scope="kr_market",
                primary_region="KR",
                importance_label="high",
                impact_direction="positive",
                reason_short="국내 수급 개선 신호입니다.",
                confidence=0.73,
                raw_output={"raw_document_id": first_raw_document_id},
            )
        }
    )
    news_service = _make_news_service(db_path, batch_triage_provider=batch_provider)

    news_service.refresh_materialized(force=True)

    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT raw_document_id, triage_metadata_json
            FROM news_batch_triage
            ORDER BY raw_document_id ASC
            """
        ).fetchall()

    metadata_by_raw_document_id = {
        int(row["raw_document_id"]): json.loads(row["triage_metadata_json"])
        for row in rows
    }
    assert metadata_by_raw_document_id[first_raw_document_id]["triage_method"] == "llm_batch"
    assert metadata_by_raw_document_id[second_raw_document_id]["triage_method"] == "llm_batch_fallback"
    assert metadata_by_raw_document_id[second_raw_document_id]["triage_provider"] is None


def test_market_news_product_batch_triage_keeps_duplicate_cluster_key(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    primary_raw_document_id = _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-DUPE-PRIMARY",
        title="미국 CPI 둔화에 나스닥 선물 강세",
        summary="글로벌 위험선호 개선 기사",
        publisher="매일경제",
        source_url="https://example.com/duplicate-primary",
        canonical_url="https://example.com/duplicate-primary",
        query_text="미국 CPI",
    )
    duplicate_raw_document_id = _insert_raw_document(
        db_path,
        provider="NAVER_NEWS",
        document_type="NEWS_CANDIDATE",
        title="미국 CPI 둔화에 나스닥 선물 강세",
        summary="같은 이슈를 다른 출처가 다시 보도했다.",
        publisher="매경",
        source_url="https://example.com/duplicate-secondary",
        canonical_url="https://example.com/duplicate-primary",
        query_text="미국 CPI",
        is_duplicate=1,
        duplicate_of_document_id=primary_raw_document_id,
    )
    batch_provider = StubBatchTriageProvider(
        response_by_raw_document_id={
            primary_raw_document_id: NewsBatchTriageResponseItem(
                raw_document_id=primary_raw_document_id,
                market_scope="global_market",
                primary_region="GLOBAL",
                importance_label="high",
                impact_direction="positive",
                reason_short="주요 글로벌 매크로 뉴스입니다.",
                confidence=0.9,
                raw_output={"raw_document_id": primary_raw_document_id},
            ),
            duplicate_raw_document_id: NewsBatchTriageResponseItem(
                raw_document_id=duplicate_raw_document_id,
                market_scope="kr_market",
                primary_region="KR",
                importance_label="medium",
                impact_direction="mixed",
                reason_short="중복 기사라도 응답이 달라질 수 있습니다.",
                confidence=0.42,
                raw_output={"raw_document_id": duplicate_raw_document_id},
            ),
        }
    )
    news_service = _make_news_service(db_path, batch_triage_provider=batch_provider)

    news_service.refresh_materialized(force=True)

    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT raw_document_id, cluster_key
            FROM news_batch_triage
            WHERE raw_document_id IN (?, ?)
            ORDER BY raw_document_id ASC
            """,
            (primary_raw_document_id, duplicate_raw_document_id),
        ).fetchall()

    assert len(rows) == 2
    assert rows[0]["cluster_key"] == rows[1]["cluster_key"]


def test_market_news_product_applies_editorial_ai_enrichment(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-EDITORIAL-BASE",
        title="코스피 수급 안정, 프로그램 매수 유입",
        summary="기존 한국 증시 대표 카드",
        publisher="매일경제",
        source_url="https://example.com/editorial-base",
        canonical_url="https://example.com/editorial-base",
        query_text="코스피 증시",
    )
    _make_news_service(db_path, scores={"group-1": 35.0}).refresh_materialized(force=True)

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
    editorial_provider = StubEditorialAIProvider(
        response_by_title={"코스피 반도체주 강세, 외국인 순매수 확대": response}
    )
    news_service = _make_news_service(
        db_path,
        scores={"group-1": 61.0, "group-2": 42.0},
        editorial_provider=editorial_provider,
        editorial_candidate_limit=3,
        editorial_min_score=0.2,
    )
    news_service.refresh_materialized(force=True)

    cards = news_service.list_cards(region="KR", limit=10)

    assert len(editorial_provider.compare_requests) == 1
    compare_request = editorial_provider.compare_requests[0]
    assert any(surface.surface_key == "KR" for surface in compare_request.current_surfaces)
    assert any(candidate.title == "코스피 반도체주 강세, 외국인 순매수 확대" for candidate in compare_request.candidates)
    assert cards
    assert cards[0]["story_state"] == "ONGOING"
    assert cards[0]["importance_label"] == "high"
    assert cards[0]["editorial_reason"] == response.editorial_reason
    assert abs(float(cards[0]["ai_confidence"]) - 0.81) < 1e-6
    assert abs(float(cards[0]["ranking_score"]) - float(cards[0]["editorial_score"])) < 1e-6
    assert cards[0]["provenance"]["ai_provider"] == "stub_editorial_ai"


def test_market_news_product_allows_negative_editorial_boost(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-EDITORIAL-NEG",
        title="코스피 수급 안정, 프로그램 매수 유입",
        summary="기존 대비 새로움이 낮은 기사",
        publisher="매일경제",
        source_url="https://example.com/editorial-neg",
        canonical_url="https://example.com/editorial-neg",
        query_text="코스피 증시",
    )

    editorial_provider = StubEditorialAIProvider(
        response_by_title={
            "코스피 수급 안정, 프로그램 매수 유입": NewsEditorialAIResponse(
                story_state="ONGOING",
                importance_label="medium",
                editorial_reason="이미 반영된 흐름이라 우선순위를 낮춥니다.",
                editorial_boost=-0.05,
                confidence=0.72,
                raw_output={
                    "story_state": "ONGOING",
                    "importance_label": "medium",
                    "editorial_reason": "이미 반영된 흐름이라 우선순위를 낮춥니다.",
                    "editorial_boost": -0.05,
                    "confidence": 0.72,
                },
            )
        }
    )
    news_service = _make_news_service(
        db_path,
        scores={"group-1": 48.0},
        editorial_provider=editorial_provider,
        editorial_candidate_limit=2,
        editorial_min_score=0.1,
    )

    news_service.refresh_materialized(force=True)
    cards = news_service.list_cards(region="KR", limit=10)

    assert cards
    provenance = cards[0]["provenance"]
    assert abs(float(provenance["editorial_boost"]) - (-0.05)) < 1e-6
    assert float(cards[0]["ranking_score"]) < float(provenance["base_editorial_score"])


def test_market_news_product_state_json_captures_lead_editorial_metadata(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-STATE-001",
        title="코스피 반도체주 강세, 외국인 순매수 확대",
        summary="핵심 섹터와 수급이 동시에 개선됐다.",
        publisher="매일경제",
        source_url="https://example.com/state-json",
        canonical_url="https://example.com/state-json",
        query_text="반도체 증시",
    )

    editorial_provider = StubEditorialAIProvider(
        response_by_title={
            "코스피 반도체주 강세, 외국인 순매수 확대": NewsEditorialAIResponse(
                story_state="ONGOING",
                importance_label="high",
                editorial_reason="핵심 섹터와 외국인 수급이 겹쳐 대표 카드로 유지합니다.",
                editorial_boost=0.04,
                confidence=0.83,
                raw_output={
                    "story_state": "ONGOING",
                    "importance_label": "high",
                    "editorial_reason": "핵심 섹터와 외국인 수급이 겹쳐 대표 카드로 유지합니다.",
                    "editorial_boost": 0.04,
                    "confidence": 0.83,
                },
            )
        }
    )
    news_service = _make_news_service(
        db_path,
        scores={"group-1": 56.0},
        editorial_provider=editorial_provider,
        editorial_candidate_limit=2,
        editorial_min_score=0.1,
    )

    news_service.refresh_materialized(force=True)

    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT state_json
            FROM market_surface_state
            WHERE surface_key = 'KR'
            """
        ).fetchone()

    assert row is not None
    state_payload = json.loads(row["state_json"])
    assert state_payload["lead_title"] == "코스피 반도체주 강세, 외국인 순매수 확대"
    assert state_payload["lead_story_state"] == "ONGOING"
    assert state_payload["lead_importance_label"] == "high"
    assert state_payload["lead_editorial_reason"] == "핵심 섹터와 외국인 수급이 겹쳐 대표 카드로 유지합니다."
    assert abs(float(state_payload["lead_ai_confidence"]) - 0.83) < 1e-6
    assert state_payload["lead_ai_provider"] == "stub_editorial_ai"
    assert state_payload["lead_ai_model"] == "stub-model"


def test_market_news_product_history_tracks_same_lead_metadata_updates(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-HISTORY-001",
        title="코스피 수급 안정, 프로그램 매수 유입",
        summary="대표 카드가 유지되는 흐름",
        publisher="매일경제",
        source_url="https://example.com/history-json",
        canonical_url="https://example.com/history-json",
        query_text="코스피 증시",
    )

    first_editorial_provider = StubEditorialAIProvider(
        response_by_title={
            "코스피 수급 안정, 프로그램 매수 유입": NewsEditorialAIResponse(
                story_state="ONGOING",
                importance_label="medium",
                editorial_reason="장중 수급 흐름이 유지됩니다.",
                editorial_boost=0.01,
                confidence=0.62,
                raw_output={
                    "story_state": "ONGOING",
                    "importance_label": "medium",
                    "editorial_reason": "장중 수급 흐름이 유지됩니다.",
                    "editorial_boost": 0.01,
                    "confidence": 0.62,
                },
            )
        }
    )
    _make_news_service(
        db_path,
        scores={"group-1": 44.0},
        editorial_provider=first_editorial_provider,
        editorial_candidate_limit=2,
        editorial_min_score=0.1,
    ).refresh_materialized(force=True)

    second_editorial_provider = StubEditorialAIProvider(
        response_by_title={
            "코스피 수급 안정, 프로그램 매수 유입": NewsEditorialAIResponse(
                story_state="ONGOING",
                importance_label="high",
                editorial_reason="프로그램 매수 강도가 더 커져 대표 카드 설명을 갱신합니다.",
                editorial_boost=0.03,
                confidence=0.79,
                raw_output={
                    "story_state": "ONGOING",
                    "importance_label": "high",
                    "editorial_reason": "프로그램 매수 강도가 더 커져 대표 카드 설명을 갱신합니다.",
                    "editorial_boost": 0.03,
                    "confidence": 0.79,
                },
            )
        }
    )
    _make_news_service(
        db_path,
        scores={"group-1": 44.0},
        editorial_provider=second_editorial_provider,
        editorial_candidate_limit=2,
        editorial_min_score=0.1,
    ).refresh_materialized(force=True)

    with get_connection(db_path) as connection:
        state_row = connection.execute(
            """
            SELECT active_candidate_key, state_json
            FROM market_surface_state
            WHERE surface_key = 'KR'
            """
        ).fetchone()
        history_rows = connection.execute(
            """
            SELECT candidate_key, change_type, snapshot_json
            FROM market_surface_history
            WHERE surface_key = 'KR'
            ORDER BY id
            """
        ).fetchall()

    assert state_row is not None
    assert len(history_rows) == 2
    assert history_rows[0]["change_type"] == "refresh"
    assert history_rows[1]["change_type"] == "metadata_update"
    assert history_rows[0]["candidate_key"] == history_rows[1]["candidate_key"] == state_row["active_candidate_key"]

    final_state_payload = json.loads(state_row["state_json"])
    metadata_update_payload = json.loads(history_rows[1]["snapshot_json"])
    assert final_state_payload["lead_importance_label"] == "high"
    assert metadata_update_payload["lead_importance_label"] == "high"
    assert metadata_update_payload["lead_editorial_reason"] == "프로그램 매수 강도가 더 커져 대표 카드 설명을 갱신합니다."


def test_market_news_product_persists_live_briefing_payload(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-BRIEFING-001",
        title="코스피 반도체주 강세, 외국인 순매수 확대",
        summary="핵심 섹터와 외국인 수급이 동시에 개선됐다.",
        publisher="매일경제",
        source_url="https://example.com/briefing-kr",
        canonical_url="https://example.com/briefing-kr",
        query_text="반도체 증시",
    )
    _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-BRIEFING-002",
        title="연준 발언 경계에 달러 강세 재확인",
        summary="원화와 외국인 수급에 부담이 될 수 있다.",
        publisher="매일경제",
        source_url="https://example.com/briefing-global",
        canonical_url="https://example.com/briefing-global",
        query_text="연준 증시",
    )

    editorial_provider = StubEditorialAIProvider(
        briefing_response=NewsEditorialAIBriefingResponse(
            headline="장중 핵심 브리핑",
            summary="국내 수급 개선과 글로벌 달러 강세가 함께 시장 해석을 움직이고 있습니다.",
            key_points=["반도체와 외국인 수급 개선", "달러 강세로 환율 민감도 확대"],
            confidence=0.79,
            raw_output={"headline": "장중 핵심 브리핑"},
        )
    )
    news_service = _make_news_service(
        db_path,
        scores={"group-1": 61.0, "group-2": 33.0},
        editorial_provider=editorial_provider,
        editorial_candidate_limit=3,
        editorial_min_score=0.1,
    )

    news_service.refresh_materialized(force=True)
    dashboard = news_service.get_dashboard()

    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT state_json
            FROM market_surface_state
            WHERE surface_key = 'SUMMARY_BRIEFING'
            """
        ).fetchone()

    assert row is not None
    assert len(editorial_provider.briefing_requests) == 1
    assert dashboard["briefing"]["headline"] == "장중 핵심 브리핑"
    assert dashboard["briefing"]["generation_method"] == "llm"
    assert dashboard["briefing"]["ai_provider"] == "stub_editorial_ai"
    assert dashboard["briefing"]["linked_headlines"]
    assert dashboard["briefing"]["linked_headlines"][0]["source_url"] == "https://example.com/briefing-kr"

    state_payload = json.loads(row["state_json"])
    assert state_payload["headline"] == "장중 핵심 브리핑"
    assert state_payload["generation_method"] == "llm"
    assert state_payload["linked_headlines"]


def test_market_news_product_briefing_falls_back_to_rule_based_links(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-BRIEFING-FALLBACK-001",
        title="코스피 수급 안정, 프로그램 매수 유입",
        summary="국내 지수 해석에 직접 연결되는 흐름이다.",
        publisher="매일경제",
        source_url="https://example.com/briefing-fallback",
        canonical_url="https://example.com/briefing-fallback",
        query_text="코스피 증시",
    )

    news_service = _make_news_service(db_path, scores={"group-1": 41.0})
    news_service.refresh_materialized(force=True)
    dashboard = news_service.get_dashboard()

    assert dashboard["briefing"]["generation_method"] == "rule_based"
    assert dashboard["briefing"]["headline"] == "지금 시장 리포트"
    assert "\n\n" in dashboard["briefing"]["summary"]
    assert "현재 시장 해석의 중심은" not in dashboard["briefing"]["summary"]
    assert "흐름으로 바로 연결되고 있습니다" not in dashboard["briefing"]["summary"]
    assert dashboard["briefing"]["linked_headlines"]
    assert dashboard["briefing"]["linked_headlines"][0]["source_url"] == "https://example.com/briefing-fallback"


def test_market_news_product_briefing_keeps_story_without_safe_url(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-BRIEFING-UNSAFE-001",
        title="코스피 변동성 확대, 장중 수급 경계",
        summary="국내 시장 해석에는 중요하지만 원문 링크는 안전하지 않습니다.",
        publisher="매일경제",
        source_url="javascript:alert('xss')",
        canonical_url="javascript:alert('xss')",
        query_text="코스피 변동성",
    )

    news_service = _make_news_service(db_path, scores={"group-1": 52.0})
    news_service.refresh_materialized(force=True)
    dashboard = news_service.get_dashboard()

    assert dashboard["briefing"]["linked_headlines"]
    assert dashboard["briefing"]["linked_headlines"][0]["title"] == "코스피 변동성 확대, 장중 수급 경계"
    assert dashboard["briefing"]["linked_headlines"][0]["source_url"] is None
    assert dashboard["briefing"]["linked_headlines"][0]["source_label"] == "매일경제"


def test_market_news_product_summary_briefing_history_tracks_state_changes(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-BRIEFING-HISTORY-001",
        title="반도체 수급 개선과 코스피 강세",
        summary="국내 수급 개선이 시장 해석 중심입니다.",
        publisher="매일경제",
        source_url="https://example.com/briefing-history-1",
        canonical_url="https://example.com/briefing-history-1",
        query_text="반도체 증시",
    )

    first_provider = StubEditorialAIProvider(
        briefing_response=NewsEditorialAIBriefingResponse(
            headline="1차 브리핑",
            summary="첫 번째 브리핑입니다.",
            key_points=["반도체 수급 개선"],
            confidence=0.61,
            raw_output={"headline": "1차 브리핑"},
        )
    )
    _make_news_service(
        db_path,
        scores={"group-1": 56.0},
        editorial_provider=first_provider,
        editorial_candidate_limit=3,
        editorial_min_score=0.1,
    ).refresh_materialized(force=True)

    second_provider = StubEditorialAIProvider(
        briefing_response=NewsEditorialAIBriefingResponse(
            headline="2차 브리핑",
            summary="두 번째 브리핑입니다.",
            key_points=["반도체 수급 개선", "장중 강세 지속"],
            confidence=0.77,
            raw_output={"headline": "2차 브리핑"},
        )
    )
    _make_news_service(
        db_path,
        scores={"group-1": 56.0},
        editorial_provider=second_provider,
        editorial_candidate_limit=3,
        editorial_min_score=0.1,
    ).refresh_materialized(force=True)

    with get_connection(db_path) as connection:
        history_rows = connection.execute(
            """
            SELECT change_type, snapshot_json
            FROM market_surface_history
            WHERE surface_key = 'SUMMARY_BRIEFING'
            ORDER BY id
            """
        ).fetchall()

    assert len(history_rows) == 2
    assert history_rows[0]["change_type"] == "metadata_update"
    assert history_rows[1]["change_type"] == "metadata_update"
    assert json.loads(history_rows[0]["snapshot_json"])["headline"] == "1차 브리핑"
    assert json.loads(history_rows[1]["snapshot_json"])["headline"] == "2차 브리핑"


def test_market_news_product_refresh_rolls_back_if_briefing_generation_fails(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-ROLLBACK-001",
        title="코스피 반등 시도, 외국인 선물 순매수",
        summary="기존 상태를 먼저 만든다.",
        publisher="매일경제",
        source_url="https://example.com/rollback-1",
        canonical_url="https://example.com/rollback-1",
        query_text="코스피 반등",
    )

    baseline_service = _make_news_service(db_path, scores={"group-1": 47.0})
    baseline_service.refresh_materialized(force=True)

    with get_connection(db_path) as connection:
        baseline_state_rows = connection.execute(
            """
            SELECT surface_key, active_candidate_key, state_json
            FROM market_surface_state
            ORDER BY surface_key
            """
        ).fetchall()

    _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-ROLLBACK-002",
        title="환율 경계감에 장중 변동성 재확대",
        summary="두 번째 refresh는 briefing 단계에서 실패한다.",
        publisher="매일경제",
        source_url="https://example.com/rollback-2",
        canonical_url="https://example.com/rollback-2",
        query_text="환율 변동성",
    )

    class FailingBriefingNewsService(NewsProductService):
        def _build_summary_briefing_payload(self, *, ordered_candidates_by_surface, coverage, updated_at):
            raise RuntimeError("briefing generation exploded")

    failing_service = FailingBriefingNewsService(
        db_path=db_path,
        datalab_provider=StubDatalabProvider(scores={"group-1": 47.0, "group-2": 32.0}),
        batch_triage_provider=None,
        editorial_ai_provider=None,
        lookback_days=7,
        card_limit=12,
        representative_evidence_limit=3,
        refresh_ttl_seconds=300,
        datalab_window_days=7,
        batch_triage_batch_size=15,
        batch_triage_upgrade_legacy_rows=True,
        editorial_ai_candidate_limit=8,
        editorial_ai_min_editorial_score=0.55,
    )

    failing_service.refresh_materialized(force=True)

    with get_connection(db_path) as connection:
        after_rows = connection.execute(
            """
            SELECT surface_key, active_candidate_key, state_json
            FROM market_surface_state
            ORDER BY surface_key
            """
        ).fetchall()

    assert [tuple(row) for row in after_rows] == [tuple(row) for row in baseline_state_rows]


def test_market_news_product_summary_briefing_persists_llm_payload(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-BRIEF-KR-001",
        title="코스피 반도체주 강세, 외국인 순매수 확대",
        summary="국내 핵심 섹터와 수급이 동시에 개선됐다.",
        publisher="매일경제",
        source_url="https://example.com/brief-kr",
        canonical_url="https://example.com/brief-kr",
        query_text="반도체 증시",
    )
    _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-BRIEF-GLOBAL-001",
        title="연준 발언 여파로 달러 강세, 원화 변동성 확대",
        summary="글로벌 변수로 환율과 외국인 수급 부담이 커졌다.",
        publisher="매일경제",
        source_url="https://example.com/brief-global",
        canonical_url="https://example.com/brief-global",
        query_text="환율 증시",
    )

    editorial_provider = StubEditorialAIProvider(
        briefing_response=NewsEditorialAIBriefingResponse(
            headline="외국인 수급과 환율 변수를 함께 봐야 하는 장세입니다.",
            summary=(
                "국내에서는 반도체와 외국인 수급이 지수를 끌어올리고 있습니다.\n\n"
                "동시에 달러 강세가 원화 변동성과 외국인 흐름을 흔들 수 있어 상단은 열려 있지만 변동성 관리가 필요합니다.\n\n"
                "따라서 장중에는 반도체 주도 흐름이 이어지는지와 환율 반응이 함께 확인돼야 합니다."
            ),
            key_points=[
                "반도체와 외국인 순매수가 국내 주도 흐름입니다.",
                "환율 변수는 장중 변동성 확대 요인입니다.",
                "환율 변수는 장중 변동성 확대 요인입니다.",
            ],
            confidence=0.82,
            raw_output={"headline": "외국인 수급과 환율 변수를 함께 봐야 하는 장세입니다."},
        )
    )
    news_service = _make_news_service(
        db_path,
        scores={"group-1": 61.0, "group-2": 39.0},
        editorial_provider=editorial_provider,
        editorial_candidate_limit=3,
        editorial_min_score=0.1,
    )

    news_service.refresh_materialized(force=True)
    dashboard = news_service.get_dashboard()

    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT state_json
            FROM market_surface_state
            WHERE surface_key = 'SUMMARY_BRIEFING'
            """
        ).fetchone()

    assert len(editorial_provider.briefing_requests) == 1
    assert row is not None
    state_payload = json.loads(row["state_json"])
    assert state_payload["generation_method"] == "llm"
    assert state_payload["ai_provider"] == "stub_editorial_ai"
    assert state_payload["headline"] == "외국인 수급과 환율 변수를 함께 봐야 하는 장세입니다."
    assert "\n\n" in state_payload["summary"]
    assert state_payload["key_points"] == [
        "반도체와 외국인 순매수가 국내 주도 흐름입니다.",
        "환율 변수는 장중 변동성 확대 요인입니다.",
    ]
    assert len(state_payload["linked_headlines"]) >= 2
    assert dashboard["briefing"]["headline"] == state_payload["headline"]
    assert dashboard["briefing"]["linked_headlines"][0]["source_url"]



def test_market_news_product_summary_briefing_falls_back_without_ai(tmp_path: Path) -> None:
    db_path = _make_db_path(tmp_path)

    _insert_raw_document(
        db_path,
        provider="MK_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="MK-BRIEF-FALLBACK-001",
        title="코스피 수급 안정, 프로그램 매수 유입",
        summary="국내 시장 수급이 안정되는 기사",
        publisher="매일경제",
        source_url="https://example.com/brief-fallback",
        canonical_url="https://example.com/brief-fallback",
        query_text="코스피 증시",
    )

    news_service = _make_news_service(db_path, scores={"group-1": 48.0})
    news_service.refresh_materialized(force=True)
    dashboard = news_service.get_dashboard()

    assert dashboard["briefing"]["generation_method"] == "rule_based"
    assert dashboard["briefing"]["headline"] == "지금 시장 리포트"
    assert "\n\n" in dashboard["briefing"]["summary"]
    assert dashboard["briefing"]["linked_headlines"]
    assert dashboard["briefing"]["linked_headlines"][0]["source_url"] == "https://example.com/brief-fallback"


def test_market_news_product_fallback_summary_avoids_filing_style_global_titles(tmp_path: Path) -> None:
    news_service = _make_news_service(_make_db_path(tmp_path))

    briefing = news_service._build_fallback_summary_briefing(
        cards_by_surface={
            "KR": [
                {
                    "id": "kr-1",
                    "title": "개미 이달들어 벌써 17조 담아…月최대 순매수 가나",
                    "one_line_summary": "개인 매수세가 지수 하단을 떠받치며 수급 해석의 중심이 되고 있습니다.",
                    "why_it_matters": "개인 매수세가 지수 하단을 떠받치며 수급 해석의 중심이 되고 있습니다.",
                    "market_impact": "수급 하단 지지 여부를 확인할 필요가 있습니다.",
                    "market_scope": "kr_market",
                    "primary_region": "KR",
                    "published_at": "2026-03-15T06:00:00Z",
                    "updated_at": "2026-03-15T06:01:00Z",
                    "evidence": [],
                }
            ],
            "GLOBAL": [
                {
                    "id": "global-1",
                    "title": "증권발행실적보고서(집합투자증권)(삼성미국서학개미증권자투자신탁H[주식])",
                    "one_line_summary": "해외 투자 심리와 자금 흐름을 읽을 때 참고할 수 있는 관련 공시입니다.",
                    "why_it_matters": "해외 투자 심리와 자금 흐름을 읽을 때 참고할 수 있는 관련 공시입니다.",
                    "market_impact": "환율과 위험선호 변화를 해석할 때 보조 신호가 됩니다.",
                    "market_scope": "global_market",
                    "primary_region": "GLOBAL",
                    "published_at": "2026-03-15T06:05:00Z",
                    "updated_at": "2026-03-15T06:06:00Z",
                    "evidence": [],
                }
            ],
            "DISCLOSURE": [],
        },
        coverage={
            "summary": "핵심 소스 반영 중",
        },
        updated_at="2026-03-15T06:10:00Z",
    )

    assert "증권발행실적보고서" not in briefing["summary"]
    assert "해외 투자 심리와 자금 흐름" in briefing["summary"]



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
                                    "items": [
                                        {
                                            "cluster_key": "cluster-1",
                                            "story_state": "NEW",
                                            "importance_label": "medium",
                                            "editorial_reason": "stub",
                                            "editorial_boost": 0.01,
                                            "confidence": 0.8,
                                        }
                                    ]
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
