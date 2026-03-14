from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import re
from typing import Any

from ..company_master.db import get_connection, utcnow_iso
from ..provider_registry import (
    PROVIDER_FAMILY_TREND_SIGNAL,
    RAW_NEWS_PROVIDER_FAMILIES,
    ProviderDefinition,
    list_provider_definitions,
    resolve_provider_definition,
)
from .editorial_ai import (
    DisabledNewsEditorialAIProvider,
    NewsEditorialAIProvider,
    NewsEditorialAIRequest,
)
from ..source_ingestion.document_time import effective_document_time, effective_document_time_sql
from ..source_ingestion.event_taxonomy import (
    SOURCE_TRUST_SCORES,
    classify_dart_disclosure,
    classify_event_type,
    classify_sentiment,
)
from ..source_ingestion.normalize import normalize_title
from ..source_ingestion.providers import NaverDatalabTrendProvider, TrendKeywordGroup

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]{2,}")
_LOW_QUALITY_HEADLINE_MARKERS = (
    "속보",
    "단독",
    "충격",
    "급등",
    "급락",
    "관련주",
    "테마주",
    "눈길",
    "주목",
)
_KR_MARKET_TERMS = (
    "코스피",
    "코스닥",
    "국내증시",
    "한국 증시",
    "원달러",
    "원/달러",
    "한국은행",
    "국장",
)
_GLOBAL_MARKET_TERMS = (
    "연준",
    "fed",
    "fomc",
    "미국",
    "중국",
    "유럽",
    "일본",
    "엔비디아",
    "나스닥",
    "s&p",
    "다우",
    "달러",
    "유가",
    "wti",
    "브렌트",
    "cpi",
    "pce",
    "boj",
    "ecb",
)
_SECTOR_TERMS = (
    "업종",
    "섹터",
    "테마",
    "반도체",
    "2차전지",
    "금융",
    "자동차",
    "바이오",
    "에너지",
)
_TITLE_STOPWORDS = {
    "시장",
    "증시",
    "뉴스",
    "기사",
    "발표",
    "관련",
    "공시",
    "보고서",
    "확대",
    "급등",
    "급락",
    "오늘",
    "주가",
}
_WHY_IT_MATTERS_BY_SCOPE = {
    "kr_market": "국내 지수와 수급 해석에 바로 연결될 수 있는 이슈입니다.",
    "global_market": "해외 변수지만 원화, 위험선호, 한국 증시 수급에 연동될 가능성이 큽니다.",
    "sector": "같은 업종과 테마 종목으로 파급될 수 있는 이슈입니다.",
    "company": "개별 종목 영향이 우선이어서 시장 전체보다 종목 반응을 먼저 확인해야 합니다.",
    "ignore": "시장 전체 영향이 제한적이라 보조 맥락으로만 보는 편이 적절합니다.",
}
_MARKET_IMPACT_PREFIX = {
    "positive": "상방 민감도",
    "negative": "하방 압력",
    "neutral": "중립 이벤트",
    "mixed": "변동성 확대",
}
_MARKET_SCOPE_PRIORITY = {
    "kr_market": 1.0,
    "global_market": 0.92,
    "sector": 0.58,
    "company": 0.18,
    "ignore": 0.0,
}
_EVENT_TYPE_MATERIALITY_BASE = {
    "earnings": 0.82,
    "guidance": 0.74,
    "contract_order": 0.8,
    "supply_customer": 0.78,
    "capex_factory": 0.72,
    "mna_investment": 0.88,
    "shareholder_return": 0.8,
    "financing": 0.78,
    "regulation_policy": 0.76,
    "product_launch": 0.6,
    "management_change_of_control": 0.84,
    "legal_dispute": 0.84,
    "accident_outage_incident": 0.86,
    "macro_theme": 0.64,
}
_MATERIALITY_SCOPE_BONUS = {
    "kr_market": 0.12,
    "global_market": 0.1,
    "sector": 0.08,
    "company": 0.1,
    "ignore": 0.0,
}
_MATERIALITY_DIRECTION_BONUS = {
    "positive": 0.05,
    "negative": 0.05,
    "mixed": 0.06,
    "neutral": 0.02,
}
_MATERIALITY_HORIZON_BONUS = {
    "intraday": 0.04,
    "short": 0.05,
    "medium": 0.03,
}
_MATERIALITY_SOURCE_BONUS = {
    "DISCLOSURE": 0.08,
    "CURATED_NEWS": 0.03,
    "DISCOVERY_NEWS": 0.0,
}
_ALLOWED_SECTORS = {
    "테크",
    "반도체",
    "자동차",
    "에너지",
    "금융",
    "헬스케어",
    "소비재",
    "산업재",
    "커뮤니케이션",
}
_STOCK_CATEGORY_BY_EVENT_TYPE = {
    "earnings": "실적",
    "guidance": "가이던스",
    "mna_investment": "M&A",
    "product_launch": "제품 출시",
    "legal_dispute": "규제/소송",
    "accident_outage_incident": "규제/소송",
    "management_change_of_control": "경영진 변화",
    "contract_order": "수주/계약",
    "supply_customer": "수주/계약",
    "capex_factory": "수주/계약",
    "shareholder_return": "수주/계약",
    "financing": "수주/계약",
}
_DISCLOSURE_IMPORTANCE_HINTS = {
    "capital_return",
    "capital_structure",
    "contract_award",
    "contract_termination",
    "ownership_change",
    "legal_risk",
    "distress_event",
    "asset_investment",
    "earnings_update",
}


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _json_load(value: str | None) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _published_sort_rank(value: str | None) -> float:
    parsed = _parse_iso_datetime(value)
    if parsed is None:
        return float("inf")
    return -parsed.timestamp()


def _storage_policy_rank(storage_policy: str | None) -> int:
    if storage_policy == "CANONICAL_EVENT":
        return 0
    if storage_policy == "PERSISTENT_EVIDENCE":
        return 1
    return 2


def _provider_priority(definition: ProviderDefinition) -> int:
    return int(definition.priority if definition.priority is not None else 100)


class NewsProductService:
    def __init__(
        self,
        *,
        db_path: str,
        datalab_provider: NaverDatalabTrendProvider,
        editorial_ai_provider: NewsEditorialAIProvider | None = None,
        lookback_days: int = 7,
        card_limit: int = 12,
        representative_evidence_limit: int = 3,
        refresh_ttl_seconds: int = 300,
        datalab_window_days: int = 7,
        editorial_ai_candidate_limit: int = 8,
        editorial_ai_min_editorial_score: float = 0.55,
    ) -> None:
        self.db_path = db_path
        self.datalab_provider = datalab_provider
        self.editorial_ai_provider = editorial_ai_provider or DisabledNewsEditorialAIProvider()
        self.lookback_days = max(1, lookback_days)
        self.card_limit = max(1, card_limit)
        self.representative_evidence_limit = max(1, representative_evidence_limit)
        self.refresh_ttl_seconds = max(30, refresh_ttl_seconds)
        self.datalab_window_days = max(1, datalab_window_days)
        self.editorial_ai_candidate_limit = max(0, editorial_ai_candidate_limit)
        self.editorial_ai_min_editorial_score = _clamp(editorial_ai_min_editorial_score)

    def list_cards(self, *, region: str, limit: int | None = None) -> list[dict[str, Any]]:
        self._ensure_materialized()
        surface_key = "KR" if region.upper() == "KR" else "GLOBAL"
        with get_connection(self.db_path) as connection:
            return self._load_cards(connection, surface_key=surface_key, limit=limit or self.card_limit)

    def list_disclosure_cards(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        self._ensure_materialized()
        with get_connection(self.db_path) as connection:
            return self._load_cards(connection, surface_key="DISCLOSURE", limit=limit or self.card_limit)

    def list_feed_items(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        surface_limit = max(limit or self.card_limit, self.card_limit)
        cards_by_id: dict[str, dict[str, Any]] = {}
        for card in self.list_cards(region="KR", limit=surface_limit):
            cards_by_id[card["id"]] = card
        for card in self.list_cards(region="GLOBAL", limit=surface_limit):
            cards_by_id[card["id"]] = card
        for card in self.list_disclosure_cards(limit=surface_limit):
            cards_by_id[card["id"]] = card

        items = [
            self._feed_item_from_card(card)
            for card in sorted(
                cards_by_id.values(),
                key=lambda item: (
                    -(float(item.get("ranking_score") or 0.0)),
                    str(item.get("updated_at") or item.get("published_at") or ""),
                    str(item.get("id") or ""),
                ),
            )
        ]
        return items[: limit or len(items)]

    def get_feed_item(self, *, news_id: str) -> dict[str, Any] | None:
        self._ensure_materialized()
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM market_surface_candidates
                WHERE card_key = ?
                """,
                (news_id,),
            ).fetchone()
            if row is None:
                return None
            card = _json_load(row["payload_json"])
            if not isinstance(card, dict):
                return None
            return self._feed_item_from_card(card)

    def search_feed_items(self, *, query: str, limit: int = 20) -> list[dict[str, Any]]:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return []
        items = []
        for item in self.list_feed_items(limit=max(limit * 3, 36)):
            haystack = [
                str(item["title"]),
                str(item["summary"]),
                str(item["why_it_matters"]),
                " ".join(item.get("related_tickers") or []),
                " ".join(item.get("tags") or []),
            ]
            if normalized_query in " ".join(haystack).lower():
                items.append(item)
        return items[:limit]

    def list_feed_items_by_ticker(self, *, ticker: str, limit: int = 20) -> list[dict[str, Any]]:
        normalized_ticker = ticker.strip().upper()
        if not normalized_ticker:
            return []
        return [
            item
            for item in self.list_feed_items(limit=max(limit * 3, 36))
            if any(str(candidate).upper() == normalized_ticker for candidate in item.get("related_tickers") or [])
        ][:limit]

    def get_header_context(self) -> dict[str, Any]:
        self._ensure_materialized()
        with get_connection(self.db_path) as connection:
            kr_cards = self._load_cards(connection, surface_key="KR", limit=self.card_limit)
            global_cards = self._load_cards(connection, surface_key="GLOBAL", limit=self.card_limit)
            coverage = self._load_coverage(connection)
            return self._build_header_context(
                kr_cards=kr_cards,
                global_cards=global_cards,
                coverage=coverage,
            )

    def get_coverage(self) -> dict[str, Any]:
        self._ensure_materialized()
        with get_connection(self.db_path) as connection:
            return self._load_coverage(connection)

    def get_dashboard(self) -> dict[str, Any]:
        self._ensure_materialized()
        with get_connection(self.db_path) as connection:
            kr_cards = self._load_cards(connection, surface_key="KR", limit=self.card_limit)
            global_cards = self._load_cards(connection, surface_key="GLOBAL", limit=self.card_limit)
            disclosure_cards = self._load_cards(connection, surface_key="DISCLOSURE", limit=self.card_limit)
            coverage = self._load_coverage(connection)
            header_context = self._build_header_context(
                kr_cards=kr_cards,
                global_cards=global_cards,
                coverage=coverage,
            )
            return {
                "kr_cards": kr_cards,
                "global_cards": global_cards,
                "disclosure_cards": disclosure_cards,
                "header_context": header_context,
                "coverage": coverage,
            }

    def refresh_materialized(self, *, force: bool = False) -> None:
        self._ensure_materialized(force=force)

    def _load_cards(self, connection, *, surface_key: str, limit: int) -> list[dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT payload_json
            FROM market_surface_candidates
            WHERE surface_key = ?
            ORDER BY ranking_score DESC, COALESCE(published_at, updated_at) DESC, id DESC
            LIMIT ?
            """,
            (surface_key, limit),
        ).fetchall()
        cards: list[dict[str, Any]] = []
        for row in rows:
            payload = _json_load(row["payload_json"])
            if isinstance(payload, dict):
                cards.append(payload)
        return cards

    def _load_coverage(self, connection) -> dict[str, Any]:
        row = connection.execute(
            """
            SELECT state_json
            FROM market_surface_state
            WHERE surface_key = 'COVERAGE'
            """
        ).fetchone()
        payload = _json_load(row["state_json"]) if row is not None else None
        if isinstance(payload, dict):
            return payload
        return {
            "state": "empty",
            "coverage_ratio": 0.0,
            "available_sources": 0,
            "expected_sources": 0,
            "summary": "표시 가능한 뉴스 소스가 없습니다.",
            "updated_at": None,
            "items": [],
        }

    def _build_header_context(
        self,
        *,
        kr_cards: list[dict[str, Any]],
        global_cards: list[dict[str, Any]],
        coverage: dict[str, Any],
    ) -> dict[str, Any]:
        updated_at = self._latest_timestamp(
            [
                coverage.get("updated_at"),
                kr_cards[0]["updated_at"] if kr_cards else None,
                global_cards[0]["updated_at"] if global_cards else None,
            ]
        )
        lead = kr_cards[0] if kr_cards else (global_cards[0] if global_cards else None)
        if lead is None:
            summary_line = "표시 가능한 이벤트 카드가 아직 준비되지 않았습니다."
        else:
            summary_line = f"{lead['title']} 중심으로 {lead['primary_region']} 이슈를 먼저 확인할 수 있습니다."
        return {
            "updated_at": updated_at,
            "summary_line": summary_line,
            "coverage": {
                "state": coverage["state"],
                "coverage_ratio": coverage["coverage_ratio"],
                "available_sources": coverage["available_sources"],
                "expected_sources": coverage["expected_sources"],
                "summary": coverage["summary"],
            },
            "columns": [
                {
                    "key": "KR",
                    "label": "한국 증시",
                    "count": len(kr_cards),
                    "lead_title": kr_cards[0]["title"] if kr_cards else None,
                    "lead_scope": kr_cards[0]["market_scope"] if kr_cards else None,
                },
                {
                    "key": "GLOBAL",
                    "label": "글로벌 증시",
                    "count": len(global_cards),
                    "lead_title": global_cards[0]["title"] if global_cards else None,
                    "lead_scope": global_cards[0]["market_scope"] if global_cards else None,
                },
            ],
        }

    def _ensure_materialized(self, *, force: bool = False) -> None:
        try:
            with get_connection(self.db_path) as connection:
                if not force and not self._needs_refresh(connection):
                    return
                self._rebuild_materialized(connection)
        except Exception as error:  # noqa: BLE001
            logger.exception(
                "news_product_refresh_failed",
                extra={"error": str(error), "force": force},
            )

    def _needs_refresh(self, connection) -> bool:
        row = connection.execute(
            """
            SELECT updated_at
            FROM market_surface_state
            WHERE surface_key = 'REFRESH_META'
            """
        ).fetchone()
        if row is None or row["updated_at"] is None:
            return True
        latest_materialized = row["updated_at"]
        latest_source = connection.execute(
            """
            SELECT MAX(updated_at) AS updated_at
            FROM raw_documents
            """
        ).fetchone()["updated_at"]
        if latest_source and latest_source > latest_materialized:
            return True
        refreshed_at = _parse_iso_datetime(latest_materialized)
        if refreshed_at is None:
            return True
        return datetime.now(timezone.utc) - refreshed_at > timedelta(seconds=self.refresh_ttl_seconds)

    def _rebuild_materialized(self, connection) -> None:
        now = utcnow_iso()
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
        cutoff_iso = cutoff_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        provider_definitions = list_provider_definitions(connection)
        raw_documents = self._load_recent_raw_documents(connection, cutoff_iso)
        latest_runs = self._load_latest_runs(connection)
        clusters, triage_rows = self._build_clusters(
            raw_documents=raw_documents,
            provider_definitions=provider_definitions,
        )
        attention_scores, datalab_status = self._resolve_attention_scores(clusters)
        editorial_ai_enrichments = self._resolve_editorial_ai_enrichments(
            clusters=clusters,
            attention_scores=attention_scores,
        )
        coverage_payload = self._build_coverage(
            raw_documents=raw_documents,
            clusters=clusters,
            latest_runs=latest_runs,
            datalab_status=datalab_status,
            provider_definitions=provider_definitions,
            now=now,
        )
        self._replace_materialized(
            connection,
            clusters=clusters,
            triage_rows=triage_rows,
            attention_scores=attention_scores,
            editorial_ai_enrichments=editorial_ai_enrichments,
            coverage_payload=coverage_payload,
            now=now,
            provider_definitions=provider_definitions,
        )

    def _load_recent_raw_documents(self, connection, cutoff_iso: str) -> list[dict[str, Any]]:
        effective_time_sql = effective_document_time_sql(alias="rd")
        rows = connection.execute(
            f"""
            SELECT
                rd.*,
                c.canonical_name AS company_name,
                c.primary_stock_code,
                c.market_classification
            FROM raw_documents rd
            LEFT JOIN companies c ON c.id = rd.company_id
            WHERE {effective_time_sql} >= ?
            ORDER BY rd.is_duplicate ASC, {effective_time_sql} DESC, rd.id DESC
            """,
            (cutoff_iso,),
        ).fetchall()
        return [dict(row) for row in rows]

    def _load_latest_runs(self, connection) -> dict[str, dict[str, Any]]:
        if connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM sqlite_master
            WHERE type = 'table' AND name = 'raw_document_fetch_runs'
            """
        ).fetchone()["count"] == 0:
            return {}
        rows = connection.execute(
            """
            SELECT provider, status, finished_at, error_message, metadata_json
            FROM raw_document_fetch_runs
            WHERE id IN (
                SELECT MAX(id)
                FROM raw_document_fetch_runs
                GROUP BY provider
            )
            """
        ).fetchall()
        return {
            str(row["provider"]): {
                "status": row["status"],
                "finished_at": row["finished_at"],
                "error_message": row["error_message"],
                "metadata": _json_load(row["metadata_json"]) or {},
            }
            for row in rows
        }

    def _build_clusters(
        self,
        *,
        raw_documents: list[dict[str, Any]],
        provider_definitions: dict[str, ProviderDefinition],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        clusters: dict[str, dict[str, Any]] = {}
        cluster_key_by_raw_id: dict[int, str] = {}
        triage_rows: list[dict[str, Any]] = []
        batch_key = utcnow_iso()

        for row in raw_documents:
            triage = self._triage_document(row=row, provider_definitions=provider_definitions)
            raw_document_id = int(row["id"])
            duplicate_of = int(row["duplicate_of_document_id"]) if row["duplicate_of_document_id"] is not None else None
            if duplicate_of is not None and duplicate_of in cluster_key_by_raw_id:
                cluster_key = cluster_key_by_raw_id[duplicate_of]
            else:
                cluster_key = self._cluster_key_for(row=row, triage=triage)
            cluster_key_by_raw_id[raw_document_id] = cluster_key

            triage_rows.append(
                {
                    "raw_document_id": raw_document_id,
                    "batch_key": batch_key,
                    "cluster_key": cluster_key,
                    "provider": row["provider"],
                    "document_type": row.get("document_type") or "",
                    "market_scope": triage["market_scope"],
                    "primary_region": triage["primary_region"],
                    "market_importance_prelim": triage["importance_label"],
                    "impact_direction": triage["impact_direction"],
                    "reason_short": triage["reason_short"],
                    "affected_companies_json": json.dumps(
                        {
                            "names": triage["direct_company_names"],
                            "tickers": triage["direct_company_tickers"],
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    "related_sectors_json": json.dumps(triage["sector_tags"], ensure_ascii=False, sort_keys=True),
                    "keyword_tags_json": json.dumps(triage["keyword_tags"], ensure_ascii=False, sort_keys=True),
                    "triage_metadata_json": json.dumps(
                        {
                            "event_type": triage["event_type"],
                            "event_subtype": triage["event_subtype"],
                            "impact_horizon": triage["impact_horizon"],
                            "source_type": triage["source_type"],
                            "canonical_anchor": triage["storage_policy"] == "CANONICAL_EVENT",
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                }
            )

            cluster = clusters.get(cluster_key)
            if cluster is None:
                published_at = self._document_published_at(row)
                cluster = {
                    "cluster_key": cluster_key,
                    "title": str(row.get("title") or "").strip() or "시장 이벤트",
                    "one_line_summary": self._one_line_summary(row=row),
                    "why_it_matters": self._why_it_matters(triage["market_scope"]),
                    "market_impact": self._market_impact(triage["market_scope"], triage["impact_direction"]),
                    "market_scope": triage["market_scope"],
                    "primary_region": triage["primary_region"],
                    "event_type": triage["event_type"],
                    "event_subtype": triage["event_subtype"],
                    "impact_direction": triage["impact_direction"],
                    "impact_horizon": triage["impact_horizon"],
                    "source_type": triage["source_type"],
                    "trust_score": triage["trust_score"],
                    "published_at": published_at,
                    "providers": {str(row["provider"])},
                    "direct_company_names": set(triage["direct_company_names"]),
                    "direct_company_tickers": set(triage["direct_company_tickers"]),
                    "sector_tags": set(triage["sector_tags"]),
                    "keyword_tags": set(triage["keyword_tags"]),
                    "quality_flags": set(self._quality_flags(row)),
                    "evidence": [],
                }
                clusters[cluster_key] = cluster
            else:
                cluster["providers"].add(str(row["provider"]))
                cluster["trust_score"] = max(cluster["trust_score"], triage["trust_score"])
                cluster["direct_company_names"].update(triage["direct_company_names"])
                cluster["direct_company_tickers"].update(triage["direct_company_tickers"])
                cluster["sector_tags"].update(triage["sector_tags"])
                cluster["keyword_tags"].update(triage["keyword_tags"])
                cluster["quality_flags"].update(self._quality_flags(row))
                cluster["market_scope"] = self._prefer_scope(cluster["market_scope"], triage["market_scope"])
                cluster["primary_region"] = self._prefer_region(cluster["primary_region"], triage["primary_region"])
                cluster["source_type"] = self._prefer_source_type(cluster["source_type"], triage["source_type"])
                cluster["event_type"] = self._prefer_event_type(cluster["event_type"], triage["event_type"])
                cluster["event_subtype"] = self._prefer_event_subtype(cluster["event_subtype"], triage["event_subtype"])
                cluster["impact_direction"] = self._prefer_direction(cluster["impact_direction"], triage["impact_direction"])
                cluster["impact_horizon"] = self._prefer_horizon(cluster["impact_horizon"], triage["impact_horizon"])
                cluster["why_it_matters"] = self._why_it_matters(cluster["market_scope"])
                cluster["market_impact"] = self._market_impact(cluster["market_scope"], cluster["impact_direction"])
                cluster["one_line_summary"] = self._prefer_summary(cluster["one_line_summary"], row.get("summary"))
                candidate_published_at = self._document_published_at(row)
                if self._latest_timestamp([cluster["published_at"], candidate_published_at]) == candidate_published_at:
                    cluster["published_at"] = candidate_published_at

            cluster["evidence"].append(
                {
                    "raw_document_id": raw_document_id,
                    "provider": str(row["provider"]),
                    "title": row.get("title"),
                    "snippet": row.get("summary"),
                    "publisher": row.get("publisher"),
                    "source_url": row.get("source_url"),
                    "canonical_url": row.get("canonical_url"),
                    "published_at": self._document_published_at(row),
                    "storage_policy": triage["storage_policy"],
                    "document_type": str(row.get("document_type") or ""),
                }
            )

        return self._finalize_clusters(list(clusters.values()), provider_definitions), triage_rows

    def _finalize_clusters(
        self,
        clusters: list[dict[str, Any]],
        provider_definitions: dict[str, ProviderDefinition],
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        results: list[dict[str, Any]] = []
        for cluster in clusters:
            evidence = sorted(
                cluster["evidence"],
                key=lambda item: (
                    _storage_policy_rank(item["storage_policy"]),
                    _provider_priority(
                        resolve_provider_definition(
                            provider_definitions,
                            provider_key=item["provider"],
                            document_type=item["document_type"],
                        )
                    ),
                    _published_sort_rank(item["published_at"]),
                    item["raw_document_id"],
                ),
            )
            cluster["evidence"] = evidence
            distinct_providers = len({item["provider"] for item in evidence})
            distinct_publishers = {self._publisher_identity(item) for item in evidence if self._publisher_identity(item)}
            has_canonical_anchor = any(item["storage_policy"] == "CANONICAL_EVENT" for item in evidence)
            has_persistent_evidence = any(item["storage_policy"] == "PERSISTENT_EVIDENCE" for item in evidence)
            provider_confirmation = 0.0
            if distinct_providers >= 2:
                provider_confirmation += 0.06
            if distinct_providers >= 3:
                provider_confirmation += 0.04
            publisher_confirmation = 0.0
            if len(distinct_publishers) >= 2:
                publisher_confirmation += 0.04
            if len(distinct_publishers) >= 3:
                publisher_confirmation += 0.02
            cluster["cross_source_score"] = _clamp(provider_confirmation + publisher_confirmation)
            published_at = _parse_iso_datetime(cluster["published_at"]) or now
            age_hours = max((now - published_at).total_seconds() / 3600.0, 0.0)
            cluster["novelty_score"] = _clamp(1.0 - (age_hours / (self.lookback_days * 24.0)) - min(max(len(evidence) - 1, 0) * 0.05, 0.25))
            cluster["has_canonical_anchor"] = has_canonical_anchor
            cluster["has_persistent_evidence"] = has_persistent_evidence
            cluster["materiality_score"] = self._materiality_score(
                event_type=cluster["event_type"],
                event_subtype=cluster["event_subtype"],
                market_scope=cluster["market_scope"],
                impact_direction=cluster["impact_direction"],
                impact_horizon=cluster["impact_horizon"],
                source_type=cluster["source_type"],
                has_canonical_anchor=has_canonical_anchor,
                has_persistent_evidence=has_persistent_evidence,
                quality_flags=cluster["quality_flags"],
            )
            cluster["editorial_score"] = self._editorial_score(
                trust_score=cluster["trust_score"],
                materiality_score=cluster["materiality_score"],
                novelty_score=cluster["novelty_score"],
                cross_source_score=cluster["cross_source_score"],
                attention_score=0.0,
                market_scope=cluster["market_scope"],
                has_canonical_anchor=has_canonical_anchor,
                has_persistent_evidence=has_persistent_evidence,
                quality_flags=cluster["quality_flags"],
            )
            cluster["ranking_score"] = cluster["editorial_score"]
            results.append(cluster)
        return results

    def _resolve_attention_scores(self, clusters: list[dict[str, Any]]) -> tuple[dict[str, float], dict[str, Any]]:
        target_clusters = [
            cluster
            for cluster in sorted(clusters, key=lambda item: item["ranking_score"], reverse=True)
            if cluster["market_scope"] != "ignore"
        ][: min(max(self.card_limit * 2, 5), 20)]

        groups: list[TrendKeywordGroup] = []
        for index, cluster in enumerate(target_clusters, start=1):
            keywords = self._attention_keywords(cluster)
            if not keywords:
                continue
            groups.append(TrendKeywordGroup(group_name=f"group-{index}", keywords=keywords))

        if not groups:
            status = "missing" if not clusters else "partial"
            return {}, {"status": status, "note": "attention_groups_empty", "disabled_reason": None}

        start_date = (datetime.now(timezone.utc) - timedelta(days=self.datalab_window_days)).date()
        end_date = datetime.now(timezone.utc).date()
        scores: dict[str, float] = {}
        score_by_group_name: dict[str, float] = {}
        disabled_reason: str | None = None

        try:
            for start_index in range(0, len(groups), 5):
                batch_groups = groups[start_index : start_index + 5]
                batch = self.datalab_provider.fetch_interest_scores(
                    start_date=start_date,
                    end_date=end_date,
                    groups=batch_groups,
                )
                if batch.disabled_reason:
                    disabled_reason = batch.disabled_reason
                    break
                for group_name, score in batch.scores.items():
                    score_by_group_name[group_name] = _clamp(score.latest_ratio / 100.0)
        except Exception as error:  # noqa: BLE001
            logger.warning("news_product_attention_fetch_failed", extra={"error": str(error)})
            return {}, {"status": "partial", "note": "attention_fetch_failed", "disabled_reason": str(error)}

        for index, cluster in enumerate(target_clusters, start=1):
            group_name = f"group-{index}"
            if group_name in score_by_group_name:
                scores[cluster["cluster_key"]] = score_by_group_name[group_name]

        if disabled_reason:
            return {}, {"status": "missing", "note": disabled_reason, "disabled_reason": disabled_reason}
        return scores, {"status": "available", "note": "ok", "disabled_reason": None}

    def _resolve_editorial_ai_enrichments(
        self,
        *,
        clusters: list[dict[str, Any]],
        attention_scores: dict[str, float],
    ) -> dict[str, dict[str, Any]]:
        if self.editorial_ai_candidate_limit <= 0:
            return {}
        enabled, reason = self.editorial_ai_provider.is_enabled()
        if not enabled:
            logger.info("news_editorial_ai_skipped", extra={"reason": reason})
            return {}

        candidates: list[tuple[float, dict[str, Any]]] = []
        for cluster in clusters:
            if cluster["market_scope"] == "ignore":
                continue
            provisional = self._editorial_score(
                trust_score=cluster["trust_score"],
                materiality_score=cluster["materiality_score"],
                novelty_score=cluster["novelty_score"],
                cross_source_score=cluster["cross_source_score"],
                attention_score=attention_scores.get(cluster["cluster_key"], 0.0),
                market_scope=cluster["market_scope"],
                has_canonical_anchor=cluster["has_canonical_anchor"],
                has_persistent_evidence=cluster["has_persistent_evidence"],
                quality_flags=cluster["quality_flags"],
            )
            if provisional < self.editorial_ai_min_editorial_score:
                continue
            candidates.append((provisional, cluster))

        enrichments: dict[str, dict[str, Any]] = {}
        for _, cluster in sorted(candidates, key=lambda item: item[0], reverse=True)[: self.editorial_ai_candidate_limit]:
            request = self._build_editorial_ai_request(
                cluster=cluster,
                attention_score=attention_scores.get(cluster["cluster_key"], 0.0),
            )
            try:
                response = self.editorial_ai_provider.enrich(request)
            except Exception as error:  # noqa: BLE001
                logger.warning("news_editorial_ai_failed", extra={"title": cluster["title"], "error": str(error)})
                continue
            if response is None:
                continue
            enrichments[cluster["cluster_key"]] = {
                "story_state": response.story_state,
                "importance_label": response.importance_label,
                "editorial_reason": response.editorial_reason,
                "editorial_boost": float(response.editorial_boost or 0.0),
                "ai_confidence": float(response.confidence or 0.0),
                "raw_output": response.raw_output or {},
                "provider_name": self.editorial_ai_provider.provider_name,
                "model_name": self.editorial_ai_provider.model_name(),
            }
        return enrichments

    def _build_editorial_ai_request(self, *, cluster: dict[str, Any], attention_score: float) -> NewsEditorialAIRequest:
        return NewsEditorialAIRequest(
            cluster_key=cluster["cluster_key"],
            title=cluster["title"],
            one_line_summary=cluster["one_line_summary"],
            why_it_matters=cluster["why_it_matters"],
            market_impact=cluster["market_impact"],
            market_scope=cluster["market_scope"],
            primary_region=cluster["primary_region"],
            event_type=cluster["event_type"],
            event_subtype=cluster["event_subtype"],
            impact_direction=cluster["impact_direction"],
            impact_horizon=cluster["impact_horizon"],
            source_type=cluster["source_type"],
            trust_score=float(cluster["trust_score"]),
            materiality_score=float(cluster["materiality_score"]),
            novelty_score=float(cluster["novelty_score"]),
            cross_source_score=float(cluster["cross_source_score"]),
            attention_score=float(attention_score),
            evidence_count=len(cluster["evidence"]),
            direct_company_names=sorted(cluster["direct_company_names"]),
            direct_company_tickers=sorted(cluster["direct_company_tickers"]),
            sector_tags=sorted(cluster["sector_tags"]),
            keyword_tags=sorted(cluster["keyword_tags"]),
            evidence=[
                {
                    "title": evidence["title"],
                    "snippet": evidence["snippet"],
                    "provider": evidence["provider"],
                    "publisher": evidence["publisher"],
                }
                for evidence in cluster["evidence"][: self.representative_evidence_limit]
            ],
        )

    def _build_coverage(
        self,
        *,
        raw_documents: list[dict[str, Any]],
        clusters: list[dict[str, Any]],
        latest_runs: dict[str, dict[str, Any]],
        datalab_status: dict[str, Any],
        provider_definitions: dict[str, ProviderDefinition],
        now: str,
    ) -> dict[str, Any]:
        docs_by_provider: dict[str, list[dict[str, Any]]] = defaultdict(list)
        surface_counts: dict[str, int] = defaultdict(int)
        evidence_counts: dict[str, int] = defaultdict(int)
        for row in raw_documents:
            docs_by_provider[str(row["provider"])].append(row)
        for cluster in clusters:
            for provider in {evidence["provider"] for evidence in cluster["evidence"]}:
                surface_counts[provider] += 1
            for evidence in cluster["evidence"]:
                evidence_counts[evidence["provider"]] += 1

        raw_news_provider_keys = {
            definition.provider_key
            for definition in provider_definitions.values()
            if definition.is_active and definition.provider_family in RAW_NEWS_PROVIDER_FAMILIES
        }
        raw_news_provider_keys.update(docs_by_provider.keys())
        raw_news_provider_keys.update(latest_runs.keys())

        ordered_raw_news_providers = sorted(
            raw_news_provider_keys,
            key=lambda provider: (
                _provider_priority(resolve_provider_definition(provider_definitions, provider_key=provider)),
                provider,
            ),
        )

        items: list[dict[str, Any]] = []
        updated_candidates: list[str | None] = []
        availability_score = 0.0
        for provider in ordered_raw_news_providers:
            rows = docs_by_provider.get(provider, [])
            latest_run = latest_runs.get(provider, {})
            status = "available" if rows else "missing"
            note = None
            if latest_run:
                run_status = str(latest_run.get("status") or "")
                if run_status in {"FAILED", "SKIPPED_DISABLED"} and rows:
                    status = "partial"
                elif run_status in {"FAILED", "SKIPPED_DISABLED"} and not rows:
                    status = "missing"
                metadata = latest_run.get("metadata") or {}
                note = (metadata.get("disabled_reason") if isinstance(metadata, dict) else None) or latest_run.get("error_message")
            if status == "available":
                availability_score += 1.0
            elif status == "partial":
                availability_score += 0.5
            last_published_at = self._latest_timestamp([self._document_published_at(row) for row in rows])
            updated_candidates.extend([last_published_at, latest_run.get("finished_at")])
            items.append(
                {
                    "provider": provider,
                    "status": status,
                    "document_count": len(rows),
                    "event_count": surface_counts.get(provider, 0),
                    "evidence_count": evidence_counts.get(provider, 0),
                    "last_published_at": last_published_at,
                    "last_synced_at": latest_run.get("finished_at"),
                    "note": note,
                    "metadata": latest_run.get("metadata") or {},
                }
            )

        trend_provider_keys = sorted(
            {
                definition.provider_key
                for definition in provider_definitions.values()
                if definition.is_active and definition.provider_family == PROVIDER_FAMILY_TREND_SIGNAL
            },
            key=lambda provider: (
                _provider_priority(
                    resolve_provider_definition(
                        provider_definitions,
                        provider_key=provider,
                        provider_family=PROVIDER_FAMILY_TREND_SIGNAL,
                    )
                ),
                provider,
            ),
        )
        for provider in trend_provider_keys:
            status = datalab_status["status"]
            if status == "available":
                availability_score += 1.0
            elif status == "partial":
                availability_score += 0.5
            updated_candidates.append(now if status != "missing" else None)
            items.append(
                {
                    "provider": provider,
                    "status": status,
                    "document_count": 0,
                    "event_count": 0,
                    "evidence_count": 0,
                    "last_published_at": None,
                    "last_synced_at": now if status != "missing" else None,
                    "note": datalab_status.get("note"),
                    "metadata": datalab_status,
                }
            )

        expected_sources = len(items)
        coverage_ratio = round(availability_score / expected_sources, 2) if expected_sources else 0.0
        state = "empty"
        if coverage_ratio >= 0.99:
            state = "full"
        elif coverage_ratio > 0:
            state = "partial"
        if not items:
            summary = "아직 수집/정규화된 뉴스 소스가 없습니다."
        elif state == "full":
            summary = "핵심 소스와 관심도 신호가 모두 반영되었습니다."
        elif state == "partial":
            summary = "일부 소스 또는 관심도 신호가 비어 있어 랭킹이 부분적으로만 반영됩니다."
        else:
            summary = "표시 가능한 뉴스 소스가 없습니다."
        return {
            "state": state,
            "coverage_ratio": coverage_ratio,
            "available_sources": sum(1 for item in items if item["status"] == "available"),
            "expected_sources": expected_sources,
            "summary": summary,
            "updated_at": self._latest_timestamp(updated_candidates),
            "items": items,
        }

    def _replace_materialized(
        self,
        connection,
        *,
        clusters: list[dict[str, Any]],
        triage_rows: list[dict[str, Any]],
        attention_scores: dict[str, float],
        editorial_ai_enrichments: dict[str, dict[str, Any]],
        coverage_payload: dict[str, Any],
        now: str,
        provider_definitions: dict[str, ProviderDefinition],
    ) -> None:
        previous_state = {
            row["surface_key"]: dict(row)
            for row in connection.execute(
                """
                SELECT surface_key, active_candidate_key, state_json
                FROM market_surface_state
                """
            ).fetchall()
        }
        connection.execute("DELETE FROM news_batch_triage")
        connection.execute("DELETE FROM market_surface_candidates")
        connection.execute("DELETE FROM market_surface_state")

        for row in triage_rows:
            connection.execute(
                """
                INSERT INTO news_batch_triage (
                    raw_document_id,
                    batch_key,
                    cluster_key,
                    provider,
                    document_type,
                    market_scope,
                    primary_region,
                    market_importance_prelim,
                    impact_direction,
                    reason_short,
                    affected_companies_json,
                    related_sectors_json,
                    keyword_tags_json,
                    triage_metadata_json,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["raw_document_id"],
                    row["batch_key"],
                    row["cluster_key"],
                    row["provider"],
                    row["document_type"],
                    row["market_scope"],
                    row["primary_region"],
                    row["market_importance_prelim"],
                    row["impact_direction"],
                    row["reason_short"],
                    row["affected_companies_json"],
                    row["related_sectors_json"],
                    row["keyword_tags_json"],
                    row["triage_metadata_json"],
                    now,
                    now,
                ),
            )

        candidates_by_surface: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for cluster in clusters:
            attention_score = float(attention_scores.get(cluster["cluster_key"], 0.0))
            editorial = editorial_ai_enrichments.get(cluster["cluster_key"], {})
            base_editorial_score = self._editorial_score(
                trust_score=cluster["trust_score"],
                materiality_score=cluster["materiality_score"],
                novelty_score=cluster["novelty_score"],
                cross_source_score=cluster["cross_source_score"],
                attention_score=attention_score,
                market_scope=cluster["market_scope"],
                has_canonical_anchor=cluster["has_canonical_anchor"],
                has_persistent_evidence=cluster["has_persistent_evidence"],
                quality_flags=cluster["quality_flags"],
            )
            editorial_boost = _clamp(float(editorial.get("editorial_boost") or 0.0), 0.0, 0.2)
            editorial_score = round(_clamp(base_editorial_score + editorial_boost), 4)
            ranking_score = editorial_score
            story_state = editorial.get("story_state") or self._default_story_state(cluster=cluster, attention_score=attention_score)
            importance_label = editorial.get("importance_label") or self._legacy_importance_from_score(cluster["materiality_score"])
            editorial_reason = editorial.get("editorial_reason")
            ai_confidence = float(editorial.get("ai_confidence") or 0.0)

            evidence_payload = [
                {
                    "role": self._evidence_role(evidence, index),
                    "provider": evidence["provider"],
                    "title": evidence["title"],
                    "snippet": evidence["snippet"],
                    "publisher": evidence["publisher"],
                    "source_url": evidence["source_url"],
                    "canonical_url": evidence["canonical_url"],
                    "storage_policy": evidence["storage_policy"],
                    "published_at": evidence["published_at"],
                }
                for index, evidence in enumerate(cluster["evidence"][: self.representative_evidence_limit], start=1)
            ]
            provenance = {
                "providers": sorted(cluster["providers"]),
                "publisher_keys": sorted(
                    {publisher for publisher in (self._publisher_identity(item) for item in cluster["evidence"]) if publisher}
                ),
                "event_type": cluster["event_type"],
                "event_subtype": cluster["event_subtype"],
                "impact_direction": cluster["impact_direction"],
                "impact_horizon": cluster["impact_horizon"],
                "source_type": cluster["source_type"],
                "canonical_anchor": cluster["has_canonical_anchor"],
                "persistent_evidence": cluster["has_persistent_evidence"],
                "materiality_score": cluster["materiality_score"],
                "base_editorial_score": base_editorial_score,
                "editorial_score": editorial_score,
                "editorial_boost": editorial_boost,
                "story_state": story_state,
                "importance_label": importance_label,
                "editorial_reason": editorial_reason,
                "ai_confidence": ai_confidence,
                "ai_provider": editorial.get("provider_name"),
                "ai_model": editorial.get("model_name"),
                "quality_flags": sorted(cluster["quality_flags"]),
                "direct_company_names": sorted(cluster["direct_company_names"]),
                "direct_company_tickers": sorted(cluster["direct_company_tickers"]),
                "sector_tags": sorted(cluster["sector_tags"]),
                "keyword_tags": sorted(cluster["keyword_tags"]),
            }
            card_base = {
                "title": cluster["title"],
                "one_line_summary": cluster["one_line_summary"],
                "why_it_matters": cluster["why_it_matters"],
                "market_impact": cluster["market_impact"],
                "market_scope": cluster["market_scope"],
                "primary_region": cluster["primary_region"],
                "trust_score": float(cluster["trust_score"]),
                "materiality_score": float(cluster["materiality_score"]),
                "novelty_score": float(cluster["novelty_score"]),
                "attention_score": attention_score,
                "editorial_score": editorial_score,
                "ranking_score": ranking_score,
                "evidence_count": len(cluster["evidence"]),
                "cross_source_score": float(cluster["cross_source_score"]),
                "published_at": cluster["published_at"],
                "updated_at": now,
                "story_state": story_state,
                "importance_label": importance_label,
                "editorial_reason": editorial_reason,
                "ai_confidence": ai_confidence,
                "evidence": evidence_payload,
                "provenance": provenance,
            }

            if cluster["market_scope"] != "ignore":
                surface_key = "KR" if cluster["primary_region"] == "KR" else "GLOBAL"
                if not (cluster["market_scope"] == "company" and ranking_score < self._company_surface_threshold(cluster)):
                    candidates_by_surface[surface_key].append(
                        self._candidate_record(
                            card_prefix="news-card",
                            surface_key=surface_key,
                            source_kind="news",
                            cluster=cluster,
                            card_payload=card_base,
                            ranking_score=ranking_score,
                            editorial_score=editorial_score,
                        )
                    )

            if cluster["has_canonical_anchor"]:
                candidates_by_surface["DISCLOSURE"].append(
                    self._candidate_record(
                        card_prefix="disclosure-card",
                        surface_key="DISCLOSURE",
                        source_kind="disclosure",
                        cluster=cluster,
                        card_payload=card_base,
                        ranking_score=ranking_score,
                        editorial_score=editorial_score,
                    )
                )

        for surface_key, candidates in candidates_by_surface.items():
            ordered = sorted(
                candidates,
                key=lambda item: (-item["ranking_score"], item["published_at"] or "", item["candidate_key"]),
            )
            for candidate in ordered:
                connection.execute(
                    """
                    INSERT INTO market_surface_candidates (
                        candidate_key,
                        card_key,
                        surface_key,
                        cluster_key,
                        source_kind,
                        source_document_ids_json,
                        title,
                        one_line_summary,
                        why_it_matters,
                        market_impact,
                        market_scope,
                        primary_region,
                        trust_score,
                        materiality_score,
                        novelty_score,
                        attention_score,
                        cross_source_score,
                        editorial_score,
                        ranking_score,
                        evidence_count,
                        published_at,
                        payload_json,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        candidate["candidate_key"],
                        candidate["card_key"],
                        candidate["surface_key"],
                        candidate["cluster_key"],
                        candidate["source_kind"],
                        candidate["source_document_ids_json"],
                        candidate["title"],
                        candidate["one_line_summary"],
                        candidate["why_it_matters"],
                        candidate["market_impact"],
                        candidate["market_scope"],
                        candidate["primary_region"],
                        candidate["trust_score"],
                        candidate["materiality_score"],
                        candidate["novelty_score"],
                        candidate["attention_score"],
                        candidate["cross_source_score"],
                        candidate["editorial_score"],
                        candidate["ranking_score"],
                        candidate["evidence_count"],
                        candidate["published_at"],
                        candidate["payload_json"],
                        now,
                        now,
                    ),
                )

        state_rows = {
            surface_key: (
                sorted(
                    candidates,
                    key=lambda item: (-item["ranking_score"], item["published_at"] or "", item["candidate_key"]),
                )[0]
                if candidates
                else None
            )
            for surface_key, candidates in candidates_by_surface.items()
        }
        state_rows.setdefault("KR", None)
        state_rows.setdefault("GLOBAL", None)
        state_rows.setdefault("DISCLOSURE", None)

        for surface_key in ("KR", "GLOBAL", "DISCLOSURE"):
            lead = state_rows[surface_key]
            state_json = json.dumps(
                {
                    "surface_key": surface_key,
                    "lead_card_id": lead["card_key"] if lead else None,
                    "count": len(candidates_by_surface.get(surface_key, [])),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            connection.execute(
                """
                INSERT INTO market_surface_state (
                    surface_key,
                    active_candidate_key,
                    state_json,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (surface_key, lead["candidate_key"] if lead else None, state_json, now, now),
            )
            previous = previous_state.get(surface_key, {})
            if previous.get("active_candidate_key") != (lead["candidate_key"] if lead else None):
                connection.execute(
                    """
                    INSERT INTO market_surface_history (
                        surface_key,
                        candidate_key,
                        change_type,
                        snapshot_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        surface_key,
                        lead["candidate_key"] if lead else None,
                        "refresh",
                        state_json,
                        now,
                    ),
                )

        connection.execute(
            """
            INSERT INTO market_surface_state (
                surface_key,
                active_candidate_key,
                state_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("COVERAGE", None, json.dumps(coverage_payload, ensure_ascii=False, sort_keys=True), now, now),
        )
        connection.execute(
            """
            INSERT INTO market_surface_state (
                surface_key,
                active_candidate_key,
                state_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                "REFRESH_META",
                None,
                json.dumps(
                    {
                        "cluster_count": len(clusters),
                        "provider_count": len(provider_definitions),
                        "raw_document_count": len(triage_rows),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                now,
                now,
            ),
        )

    def _candidate_record(
        self,
        *,
        card_prefix: str,
        surface_key: str,
        source_kind: str,
        cluster: dict[str, Any],
        card_payload: dict[str, Any],
        ranking_score: float,
        editorial_score: float,
    ) -> dict[str, Any]:
        card_hash = self._hash_text(f"{surface_key}:{cluster['cluster_key']}")
        card_key = f"{card_prefix}-{card_hash[:16]}"
        candidate_key = f"{surface_key.lower()}-{card_hash[:24]}"
        payload = dict(card_payload)
        payload["id"] = card_key
        payload["editorial_score"] = editorial_score
        payload["ranking_score"] = ranking_score
        payload["provenance"] = dict(card_payload["provenance"])
        return {
            "candidate_key": candidate_key,
            "card_key": card_key,
            "surface_key": surface_key,
            "cluster_key": cluster["cluster_key"],
            "source_kind": source_kind,
            "source_document_ids_json": json.dumps(
                [evidence["raw_document_id"] for evidence in cluster["evidence"]],
                ensure_ascii=False,
                sort_keys=True,
            ),
            "title": payload["title"],
            "one_line_summary": payload["one_line_summary"],
            "why_it_matters": payload["why_it_matters"],
            "market_impact": payload["market_impact"],
            "market_scope": payload["market_scope"],
            "primary_region": payload["primary_region"],
            "trust_score": payload["trust_score"],
            "materiality_score": payload["materiality_score"],
            "novelty_score": payload["novelty_score"],
            "attention_score": payload["attention_score"],
            "cross_source_score": payload["cross_source_score"],
            "editorial_score": payload["editorial_score"],
            "ranking_score": payload["ranking_score"],
            "evidence_count": payload["evidence_count"],
            "published_at": payload["published_at"],
            "payload_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        }

    def _triage_document(
        self,
        *,
        row: dict[str, Any],
        provider_definitions: dict[str, ProviderDefinition],
    ) -> dict[str, Any]:
        provider_key = str(row["provider"])
        definition = resolve_provider_definition(
            provider_definitions,
            provider_key=provider_key,
            document_type=str(row.get("document_type") or ""),
        )
        source_type = definition.source_type or "DISCOVERY_NEWS"
        storage_policy = definition.storage_policy or "TRANSIENT_DISCOVERY"
        title = str(row.get("title") or "")
        summary = str(row.get("summary") or "")
        text = " ".join(filter(None, [title, summary, str(row.get("query_text") or "")]))
        normalized = normalize_title(text) or ""

        direct_company_names = []
        direct_company_tickers = []
        if row.get("company_name"):
            direct_company_names.append(str(row["company_name"]).strip())
        if row.get("primary_stock_code"):
            direct_company_tickers.append(str(row["primary_stock_code"]).strip())
        sector_tags = [str(row["market_classification"]).strip()] if row.get("market_classification") else []
        keyword_tags = self._headline_tokens(text)[:4]

        if str(row.get("document_type") or "").upper() == "DISCLOSURE":
            disclosure = classify_dart_disclosure(str(row.get("report_type") or row.get("title") or ""))
            event_type = disclosure.event_type
            event_subtype = disclosure.event_subtype
            impact_direction = disclosure.impact_direction
            impact_horizon = disclosure.impact_horizon
        else:
            event_type = classify_event_type(text)
            event_subtype = "generic"
            impact_direction = classify_sentiment(text)
            impact_horizon = "short"

        has_kr_market = any(term.casefold() in normalized for term in _KR_MARKET_TERMS)
        has_global_market = any(term.casefold() in normalized for term in _GLOBAL_MARKET_TERMS)
        has_sector_term = any(term.casefold() in normalized for term in _SECTOR_TERMS)
        primary_region = "GLOBAL" if has_global_market and not has_kr_market else "KR"

        if has_kr_market:
            market_scope = "kr_market"
        elif has_global_market:
            market_scope = "global_market"
        elif has_sector_term or len(direct_company_names) >= 2:
            market_scope = "sector"
        elif str(row.get("document_type") or "").upper() == "DISCLOSURE":
            market_scope = "company"
        elif direct_company_names:
            market_scope = "company"
        else:
            market_scope = "ignore"

        trust_score = self._trust_score_for(
            provider_definitions,
            provider=provider_key,
            document_type=str(row.get("document_type") or ""),
        )
        importance_score = self._materiality_score(
            event_type=event_type,
            event_subtype=event_subtype,
            market_scope=market_scope,
            impact_direction=impact_direction,
            impact_horizon=impact_horizon,
            source_type=source_type,
            has_canonical_anchor=storage_policy == "CANONICAL_EVENT",
            has_persistent_evidence=storage_policy == "PERSISTENT_EVIDENCE",
            quality_flags=self._quality_flags(row),
        )
        importance_label = self._legacy_importance_from_score(importance_score)
        if event_subtype in _DISCLOSURE_IMPORTANCE_HINTS and importance_label == "low":
            importance_label = "medium"
        reason_short = self._why_it_matters(market_scope)
        return {
            "event_type": event_type,
            "event_subtype": event_subtype,
            "impact_direction": impact_direction,
            "impact_horizon": impact_horizon,
            "market_scope": market_scope,
            "primary_region": primary_region,
            "importance_label": importance_label,
            "reason_short": reason_short,
            "source_type": source_type,
            "storage_policy": storage_policy,
            "trust_score": trust_score,
            "direct_company_names": [name for name in direct_company_names if name],
            "direct_company_tickers": [ticker for ticker in direct_company_tickers if ticker],
            "sector_tags": [tag for tag in sector_tags if tag],
            "keyword_tags": keyword_tags,
        }

    def _cluster_key_for(self, *, row: dict[str, Any], triage: dict[str, Any]) -> str:
        published_at = _parse_iso_datetime(self._document_published_at(row))
        date_bucket = published_at.date().isoformat() if published_at else "unknown"
        title_signature = "|".join(self._headline_tokens(str(row.get("title") or ""))[:6])
        signature = title_signature or "|".join(
            self._headline_tokens(" ".join(filter(None, [row.get("title"), row.get("summary")])))[:6]
        )
        company_part = "|".join(triage["direct_company_names"]) or "|".join(triage["direct_company_tickers"])
        identity = signature or company_part or str(row.get("canonical_url") or "")
        seed = "|".join(
            [
                triage["event_type"],
                date_bucket,
                triage["primary_region"],
                triage["market_scope"],
                company_part,
                identity or str(row.get("provider_document_id") or row.get("id")),
            ]
        )
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()

    def _document_published_at(self, row: dict[str, Any]) -> str | None:
        return effective_document_time(
            document_type=str(row.get("document_type") or ""),
            published_at=row.get("published_at"),
            observed_at=row.get("observed_at"),
            receipt_at=row.get("receipt_at"),
            updated_at=row.get("updated_at"),
            created_at=row.get("created_at"),
        )

    def _prefer_scope(self, current: str, candidate: str) -> str:
        order = {"kr_market": 5, "global_market": 4, "sector": 3, "company": 2, "ignore": 1}
        return current if order.get(current, 0) >= order.get(candidate, 0) else candidate

    def _prefer_region(self, current: str, candidate: str) -> str:
        if current == "KR":
            return current
        return candidate or current

    def _prefer_source_type(self, current: str, candidate: str) -> str:
        return current if self._source_priority_rank(current) <= self._source_priority_rank(candidate) else candidate

    def _prefer_event_type(self, current: str, candidate: str) -> str:
        return current if current != "macro_theme" else candidate

    def _prefer_event_subtype(self, current: str, candidate: str) -> str:
        return current if current not in {"generic", "generic_disclosure"} else candidate

    def _prefer_direction(self, current: str, candidate: str) -> str:
        if current in {"positive", "negative"}:
            return current
        return candidate

    def _prefer_horizon(self, current: str, candidate: str) -> str:
        if current == "medium":
            return current
        return candidate

    def _prefer_summary(self, current: str, candidate: Any) -> str:
        text = str(candidate or "").strip()
        if not text:
            return current
        return current if len(current) >= len(text) else text[:140]

    def _headline_tokens(self, text: str) -> list[str]:
        seen: set[str] = set()
        tokens: list[str] = []
        for token in _TOKEN_RE.findall(normalize_title(text) or ""):
            if token in _TITLE_STOPWORDS or token in seen:
                continue
            seen.add(token)
            tokens.append(token)
        return tokens

    def _quality_flags(self, row: dict[str, Any]) -> set[str]:
        flags: set[str] = set()
        title = normalize_title(str(row.get("title") or "")) or ""
        if any(marker.casefold() in title for marker in _LOW_QUALITY_HEADLINE_MARKERS):
            flags.add("low_quality_headline")
        if len(self._headline_tokens(title)) < 2:
            flags.add("thin_headline")
        return flags

    def _trust_score_for(
        self,
        provider_definitions: dict[str, ProviderDefinition],
        *,
        provider: str,
        document_type: str | None = None,
    ) -> float:
        definition = resolve_provider_definition(
            provider_definitions,
            provider_key=provider,
            document_type=document_type,
        )
        if definition.trust_score is not None:
            return float(definition.trust_score)
        source_type = definition.source_type or "DISCOVERY_NEWS"
        return SOURCE_TRUST_SCORES[source_type]

    def _source_priority_rank(self, source_type: str | None) -> int:
        normalized = str(source_type or "").strip().upper()
        if normalized == "DISCLOSURE":
            return 0
        if normalized == "CURATED_NEWS":
            return 1
        if normalized == "DISCOVERY_NEWS":
            return 2
        return 3

    def _why_it_matters(self, market_scope: str) -> str:
        return _WHY_IT_MATTERS_BY_SCOPE.get(market_scope, _WHY_IT_MATTERS_BY_SCOPE["ignore"])

    def _market_impact(self, market_scope: str, impact_direction: str) -> str:
        prefix = _MARKET_IMPACT_PREFIX.get(impact_direction, _MARKET_IMPACT_PREFIX["neutral"])
        if market_scope == "kr_market":
            return f"{prefix}가 국내 지수와 수급에 반영될 가능성이 큽니다."
        if market_scope == "global_market":
            return f"{prefix}가 환율과 위험선호를 통해 국내 증시에 전이될 수 있습니다."
        if market_scope == "sector":
            return f"{prefix}가 업종 전반으로 번질 수 있습니다."
        if market_scope == "company":
            return f"{prefix}가 개별 종목에 집중될 가능성이 큽니다."
        return "시장 전체 영향은 제한적입니다."

    def _one_line_summary(self, *, row: dict[str, Any]) -> str:
        summary = str(row.get("summary") or row.get("title") or "").strip()
        if not summary:
            return "시장 이벤트가 감지되었습니다."
        return summary[:140]

    def _attention_keywords(self, cluster: dict[str, Any]) -> list[str]:
        keywords = []
        keywords.extend(sorted(cluster["direct_company_names"]))
        keywords.extend(sorted(cluster["sector_tags"]))
        keywords.extend(sorted(cluster["keyword_tags"]))
        if not keywords:
            keywords.extend(self._headline_tokens(cluster["title"])[:4])
        deduped: list[str] = []
        seen: set[str] = set()
        for keyword in keywords:
            normalized = str(keyword).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped[:8]

    def _evidence_role(self, evidence: dict[str, Any], sort_order: int) -> str:
        if evidence["storage_policy"] == "CANONICAL_EVENT":
            return "PRIMARY"
        if sort_order == 1:
            return "PRIMARY"
        if evidence["storage_policy"] == "TRANSIENT_DISCOVERY":
            return "DISCOVERY"
        return "CONFIRMING"

    def _publisher_identity(self, evidence: dict[str, Any]) -> str | None:
        normalized = normalize_title(str(evidence.get("publisher") or "")) or ""
        return normalized or None

    def _materiality_score(
        self,
        *,
        event_type: str,
        event_subtype: str,
        market_scope: str,
        impact_direction: str,
        impact_horizon: str,
        source_type: str,
        has_canonical_anchor: bool,
        has_persistent_evidence: bool,
        quality_flags: set[str],
    ) -> float:
        score = _EVENT_TYPE_MATERIALITY_BASE.get(event_type, 0.56)
        score += _MATERIALITY_SCOPE_BONUS.get(market_scope, 0.0)
        score += _MATERIALITY_DIRECTION_BONUS.get(impact_direction, 0.02)
        score += _MATERIALITY_HORIZON_BONUS.get(impact_horizon, 0.0)
        score += _MATERIALITY_SOURCE_BONUS.get(source_type, 0.0)
        if event_subtype not in {"generic", "generic_disclosure", "periodic_report"}:
            score += 0.03
        if has_canonical_anchor:
            score += 0.05
        if has_persistent_evidence:
            score += 0.02
        if "low_quality_headline" in quality_flags:
            score -= 0.12
        if "thin_headline" in quality_flags:
            score -= 0.04
        return round(_clamp(score), 4)

    def _editorial_score(
        self,
        *,
        trust_score: float,
        materiality_score: float,
        novelty_score: float,
        cross_source_score: float,
        attention_score: float,
        market_scope: str,
        has_canonical_anchor: bool,
        has_persistent_evidence: bool,
        quality_flags: set[str],
    ) -> float:
        score = (
            (materiality_score * 0.44)
            + (trust_score * 0.12)
            + (novelty_score * 0.16)
            + (cross_source_score * 0.1)
            + (attention_score * 0.08)
            + (_MARKET_SCOPE_PRIORITY.get(market_scope, 0.0) * 0.1)
        )
        if has_canonical_anchor:
            score += 0.05
        if has_persistent_evidence:
            score += 0.03
        if "low_quality_headline" in quality_flags:
            score -= 0.14
        if "thin_headline" in quality_flags:
            score -= 0.04
        return round(_clamp(score), 4)

    def _default_story_state(self, *, cluster: dict[str, Any], attention_score: float) -> str:
        if cluster["has_canonical_anchor"] and len(cluster["evidence"]) >= 2:
            return "DISCLOSURE_CONFIRMED"
        if cluster["novelty_score"] < 0.58 or attention_score >= 0.42 or len(cluster["evidence"]) >= 3:
            return "ONGOING"
        return "NEW"

    def _company_surface_threshold(self, cluster: dict[str, Any]) -> float:
        threshold = 0.92
        if cluster["has_canonical_anchor"]:
            threshold = 0.82
            if cluster["event_subtype"] not in {"generic", "generic_disclosure", "periodic_report"}:
                threshold = 0.76
        return threshold

    def _hash_text(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _legacy_importance_from_score(self, materiality_score: float) -> str:
        if materiality_score >= 0.8:
            return "high"
        if materiality_score >= 0.62:
            return "medium"
        return "low"

    def _legacy_news_type(self, card: dict[str, Any]) -> str:
        return "stock" if card.get("market_scope") == "company" else "macro"

    def _legacy_sentiment(self, card: dict[str, Any]) -> str:
        provenance = card.get("provenance") or {}
        impact_direction = str(provenance.get("impact_direction") or "").strip().lower()
        if impact_direction in {"positive", "negative"}:
            return impact_direction
        return "neutral"

    def _legacy_importance(self, card: dict[str, Any]) -> str:
        return self._legacy_importance_from_score(float(card.get("materiality_score") or 0.0))

    def _legacy_category(self, card: dict[str, Any]) -> str:
        provenance = card.get("provenance") or {}
        event_type = str(provenance.get("event_type") or "")
        item_type = self._legacy_news_type(card)
        if item_type == "stock":
            return _STOCK_CATEGORY_BY_EVENT_TYPE.get(event_type, "수주/계약")

        text = normalize_title(
            " ".join(
                filter(
                    None,
                    [
                        card.get("title"),
                        card.get("one_line_summary"),
                        str(provenance.get("event_subtype") or ""),
                    ],
                )
            )
        ) or ""
        if any(keyword in text for keyword in ("금리", "연준", "fomc", "기준금리", "boj", "ecb")):
            return "금리"
        if any(keyword in text for keyword in ("cpi", "pce", "물가", "인플레이션")):
            return "인플레이션"
        if any(keyword in text for keyword in ("고용", "실업", "노동")):
            return "고용"
        if any(keyword in text for keyword in ("환율", "달러", "원화", "엔화")):
            return "환율"
        if any(keyword in text for keyword in ("유가", "에너지", "원유", "wti", "브렌트")):
            return "유가/에너지"
        if any(keyword in text for keyword in ("전쟁", "지정학", "중동", "러시아", "우크라이나", "대만")):
            return "전쟁/지정학"
        if any(keyword in text for keyword in ("반도체", "ai", "엔비디아")):
            return "AI/반도체"
        return "규제"

    def _feed_item_from_card(self, card: dict[str, Any]) -> dict[str, Any]:
        provenance = card.get("provenance") or {}
        evidence = card.get("evidence") or []
        primary_evidence = evidence[0] if evidence else {}
        related_sectors = [sector for sector in provenance.get("sector_tags") or [] if sector in _ALLOWED_SECTORS]
        related_tickers = [str(ticker) for ticker in provenance.get("direct_company_tickers") or [] if str(ticker)]
        event_type = str(provenance.get("event_type") or "")
        event_subtype = str(provenance.get("event_subtype") or "")
        tags = [
            *[str(keyword) for keyword in provenance.get("keyword_tags") or [] if str(keyword)],
            *[str(name) for name in provenance.get("direct_company_names") or [] if str(name)],
            *related_sectors,
        ]
        for extra_tag in (event_type, event_subtype):
            if extra_tag:
                tags.append(extra_tag)
        return {
            "id": card["id"],
            "type": self._legacy_news_type(card),
            "title": card["title"],
            "summary": card["one_line_summary"],
            "why_it_matters": card["why_it_matters"],
            "source": primary_evidence.get("publisher") or primary_evidence.get("provider") or "Argus",
            "source_url": primary_evidence.get("canonical_url") or primary_evidence.get("source_url") or "",
            "published_at": card.get("published_at") or card.get("updated_at"),
            "credibility_score": float(card.get("trust_score") or 0.0),
            "materiality_score": float(card.get("materiality_score") or 0.0),
            "editorial_score": float(card.get("editorial_score") or 0.0),
            "story_state": card.get("story_state") or "NEW",
            "editorial_reason": card.get("editorial_reason"),
            "ai_confidence": float(card.get("ai_confidence") or 0.0),
            "sentiment": self._legacy_sentiment(card),
            "importance": str(card.get("importance_label") or self._legacy_importance(card)),
            "related_sectors": related_sectors,
            "related_tickers": related_tickers,
            "category": self._legacy_category(card),
            "tags": list(dict.fromkeys(tag for tag in tags if tag)),
        }

    def _latest_timestamp(self, values: list[str | None]) -> str | None:
        parsed = [value for value in values if value]
        if not parsed:
            return None
        return max(parsed)
