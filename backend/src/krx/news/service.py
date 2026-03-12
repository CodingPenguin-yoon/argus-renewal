from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import logging
import re
from typing import Any

from ..company_master.db import get_connection, utcnow_iso
from ..publisher_registry import build_publisher_definition, ensure_publisher_definition
from ..provider_registry import (
    PROVIDER_FAMILY_TREND_SIGNAL,
    RAW_NEWS_PROVIDER_FAMILIES,
    ProviderDefinition,
    list_provider_definitions,
    resolve_provider_definition,
)
from ..source_ingestion.document_time import effective_document_time, effective_document_time_sql
from ..source_ingestion.event_taxonomy import (
    SOURCE_TRUST_SCORES,
    classify_event_type,
    classify_sentiment,
)
from ..source_ingestion.normalize import normalize_title
from ..source_ingestion.providers import (
    NaverDatalabTrendProvider,
    TrendKeywordGroup,
)

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


def _storage_policy_rank(storage_policy: str | None) -> int:
    if storage_policy == "CANONICAL_EVENT":
        return 0
    if storage_policy == "PERSISTENT_EVIDENCE":
        return 1
    return 2


def _provider_priority(definition: ProviderDefinition) -> int:
    return int(definition.priority if definition.priority is not None else 100)


def _published_sort_rank(value: str | None) -> float:
    parsed = _parse_iso_datetime(value)
    if parsed is None:
        return float("inf")
    return -parsed.timestamp()


class NewsProductService:
    def __init__(
        self,
        *,
        db_path: str,
        datalab_provider: NaverDatalabTrendProvider,
        lookback_days: int = 7,
        card_limit: int = 12,
        representative_evidence_limit: int = 3,
        refresh_ttl_seconds: int = 300,
        datalab_window_days: int = 7,
    ) -> None:
        self.db_path = db_path
        self.datalab_provider = datalab_provider
        self.lookback_days = max(1, lookback_days)
        self.card_limit = max(1, card_limit)
        self.representative_evidence_limit = max(1, representative_evidence_limit)
        self.refresh_ttl_seconds = max(30, refresh_ttl_seconds)
        self.datalab_window_days = max(1, datalab_window_days)

    def list_cards(self, *, region: str, limit: int | None = None) -> list[dict[str, Any]]:
        self._ensure_materialized()
        column_key = "KR" if region.upper() == "KR" else "GLOBAL"

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    nc.card_key,
                    nc.column_key,
                    nc.title,
                    nc.one_line_summary,
                    nc.why_it_matters,
                    nc.market_impact,
                    nc.market_scope,
                    nc.primary_region,
                    nc.trust_score,
                    nc.novelty_score,
                    nc.attention_score,
                    nc.ranking_score,
                    nc.evidence_count,
                    nc.published_at,
                    nc.updated_at,
                    ne.cluster_key,
                    ne.cross_source_score,
                    ne.provenance_json
                FROM news_cards nc
                JOIN normalized_events ne ON ne.id = nc.normalized_event_id
                WHERE nc.column_key = ?
                ORDER BY nc.ranking_score DESC, COALESCE(nc.published_at, nc.updated_at) DESC, nc.id DESC
                LIMIT ?
                """,
                (column_key, limit or self.card_limit),
            ).fetchall()

            items: list[dict[str, Any]] = []
            for row in rows:
                evidence_rows = connection.execute(
                    """
                    SELECT
                        ee.evidence_role,
                        ee.provider,
                        ee.title,
                        ee.snippet,
                        ee.publisher,
                        ee.source_url,
                        ee.published_at,
                        sd.storage_policy,
                        sd.canonical_url
                    FROM event_evidence ee
                    JOIN news_cards nc ON nc.normalized_event_id = ee.normalized_event_id
                    JOIN source_documents sd ON sd.id = ee.source_document_id
                    WHERE nc.card_key = ?
                    ORDER BY ee.sort_order ASC, COALESCE(ee.published_at, ee.updated_at) DESC
                    LIMIT ?
                    """,
                    (row["card_key"], self.representative_evidence_limit),
                ).fetchall()

                items.append(
                    {
                        "id": row["card_key"],
                        "title": row["title"],
                        "one_line_summary": row["one_line_summary"],
                        "why_it_matters": row["why_it_matters"],
                        "market_impact": row["market_impact"],
                        "market_scope": row["market_scope"],
                        "primary_region": row["primary_region"],
                        "trust_score": float(row["trust_score"] or 0.0),
                        "novelty_score": float(row["novelty_score"] or 0.0),
                        "attention_score": float(row["attention_score"] or 0.0),
                        "ranking_score": float(row["ranking_score"] or 0.0),
                        "evidence_count": int(row["evidence_count"] or 0),
                        "cross_source_score": float(row["cross_source_score"] or 0.0),
                        "published_at": row["published_at"],
                        "updated_at": row["updated_at"],
                        "evidence": [
                            {
                                "role": evidence["evidence_role"],
                                "provider": evidence["provider"],
                                "title": evidence["title"],
                                "snippet": evidence["snippet"],
                                "publisher": evidence["publisher"],
                                "source_url": evidence["source_url"],
                                "canonical_url": evidence["canonical_url"],
                                "storage_policy": evidence["storage_policy"],
                                "published_at": evidence["published_at"],
                            }
                            for evidence in evidence_rows
                        ],
                        "provenance": _json_load(row["provenance_json"]) or {},
                    }
                )

        return items

    def get_header_context(self) -> dict[str, Any]:
        self._ensure_materialized()
        kr_cards = self.list_cards(region="KR", limit=1)
        global_cards = self.list_cards(region="GLOBAL", limit=1)
        coverage = self.get_coverage()

        updated_at = self._latest_timestamp(
            [coverage.get("updated_at"), kr_cards[0]["updated_at"] if kr_cards else None, global_cards[0]["updated_at"] if global_cards else None]
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
                    "count": len(self.list_cards(region="KR")),
                    "lead_title": kr_cards[0]["title"] if kr_cards else None,
                    "lead_scope": kr_cards[0]["market_scope"] if kr_cards else None,
                },
                {
                    "key": "GLOBAL",
                    "label": "글로벌 증시",
                    "count": len(self.list_cards(region="GLOBAL")),
                    "lead_title": global_cards[0]["title"] if global_cards else None,
                    "lead_scope": global_cards[0]["market_scope"] if global_cards else None,
                },
            ],
        }

    def get_coverage(self) -> dict[str, Any]:
        self._ensure_materialized()
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    sc.*,
                    COALESCE(pr.priority, 999) AS provider_priority
                FROM source_coverage sc
                LEFT JOIN provider_registry pr
                    ON pr.provider_key = sc.provider
                WHERE sc.surface_key = 'news_tab'
                ORDER BY provider_priority ASC, sc.provider ASC
                """
            ).fetchall()

        items = []
        available_count = 0
        updated_candidates: list[str | None] = []
        for row in rows:
            status = str(row["status"])
            if status == "available":
                available_count += 1
            elif status == "partial":
                available_count += 0.5
            updated_candidates.append(row["updated_at"])
            items.append(
                {
                    "provider": row["provider"],
                    "status": status,
                    "document_count": int(row["document_count"] or 0),
                    "event_count": int(row["event_count"] or 0),
                    "evidence_count": int(row["evidence_count"] or 0),
                    "last_published_at": row["last_published_at"],
                    "last_synced_at": row["last_synced_at"],
                    "note": row["note"],
                    "metadata": _json_load(row["metadata_json"]) or {},
                }
            )

        expected_sources = len(items)
        coverage_ratio = round(available_count / expected_sources, 2) if expected_sources else 0.0
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

    def refresh_materialized(self, *, force: bool = False) -> None:
        self._ensure_materialized(force=force)

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
        latest_materialized = connection.execute(
            "SELECT MAX(updated_at) AS updated_at FROM news_cards"
        ).fetchone()["updated_at"]
        if latest_materialized is None:
            return True

        latest_source = connection.execute(
            """
            SELECT MAX(updated_at) AS updated_at
            FROM (
                SELECT updated_at FROM raw_documents
                UNION ALL
                SELECT updated_at FROM events
            )
            """
        ).fetchone()["updated_at"]
        if latest_source and latest_source > latest_materialized:
            return True

        latest_trend = connection.execute(
            """
            SELECT MAX(sc.updated_at) AS updated_at
            FROM source_coverage sc
            LEFT JOIN provider_registry pr
                ON pr.provider_key = sc.provider
            WHERE sc.surface_key = 'news_tab'
              AND COALESCE(pr.provider_family, '') = ?
            """,
            (PROVIDER_FAMILY_TREND_SIGNAL,),
        ).fetchone()
        if latest_trend is None:
            return True

        refreshed_at = _parse_iso_datetime(latest_trend["updated_at"])
        if refreshed_at is None:
            return True
        return datetime.now(timezone.utc) - refreshed_at > timedelta(seconds=self.refresh_ttl_seconds)

    def _rebuild_materialized(self, connection) -> None:
        now = utcnow_iso()
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
        cutoff_iso = cutoff_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        provider_definitions = list_provider_definitions(connection)

        raw_documents = self._load_recent_raw_documents(connection, cutoff_iso)
        event_map = self._load_recent_event_map(connection, cutoff_iso)
        latest_runs = self._load_latest_runs(connection)

        source_document_id_by_raw_id = self._rebuild_source_documents(
            connection,
            raw_documents,
            now,
            provider_definitions,
        )
        clusters = self._build_clusters(
            raw_documents=raw_documents,
            event_map=event_map,
            source_document_id_by_raw_id=source_document_id_by_raw_id,
            provider_definitions=provider_definitions,
        )
        attention_scores, datalab_status = self._resolve_attention_scores(clusters)
        self._replace_materialized_events(connection, clusters, attention_scores, now)
        self._replace_source_coverage(
            connection,
            now=now,
            raw_documents=raw_documents,
            clusters=clusters,
            latest_runs=latest_runs,
            datalab_status=datalab_status,
            provider_definitions=provider_definitions,
        )

        logger.info(
            "news_product_refresh_completed",
            extra={
                "raw_document_count": len(raw_documents),
                "cluster_count": len(clusters),
                "cutoff": cutoff_iso,
            },
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

    def _load_recent_event_map(self, connection, cutoff_iso: str) -> dict[int, dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT
                e.*,
                edge.company_id AS edge_company_id,
                edge.impact_tier,
                edge.reason AS edge_reason,
                edge.evidence_text,
                edge.mapping_rule_source,
                edge.confidence AS edge_confidence,
                c.canonical_name AS edge_company_name,
                c.primary_stock_code AS edge_primary_stock_code
            FROM events e
            LEFT JOIN event_company_edges edge ON edge.event_id = e.id
            LEFT JOIN companies c ON c.id = edge.company_id
            WHERE COALESCE(e.occurred_at, e.updated_at, e.created_at) >= ?
              AND e.status != 'REJECTED'
            ORDER BY e.id ASC
            """,
            (cutoff_iso,),
        ).fetchall()

        grouped: dict[int, dict[str, Any]] = {}
        for row in rows:
            primary_document_id = int(row["primary_document_id"])
            item = grouped.get(primary_document_id)
            if item is None:
                item = {
                    "event_id": int(row["id"]),
                    "primary_document_id": primary_document_id,
                    "event_type": row["event_type"],
                    "summary": row["summary"],
                    "sentiment": row["sentiment"],
                    "source_type": row["source_type"],
                    "source_provider": row["source_provider"],
                    "trust_score": float(row["trust_score"] or 0.0),
                    "confidence": float(row["confidence"] or 0.0),
                    "occurred_at": row["occurred_at"],
                    "metadata": _json_load(row["metadata_json"]) or {},
                    "companies": [],
                }
                grouped[primary_document_id] = item

            if row["edge_company_id"] is None:
                continue
            item["companies"].append(
                {
                    "company_id": int(row["edge_company_id"]),
                    "impact_tier": row["impact_tier"],
                    "reason": row["edge_reason"],
                    "evidence_text": row["evidence_text"],
                    "mapping_rule_source": row["mapping_rule_source"],
                    "confidence": float(row["edge_confidence"] or 0.0),
                    "company_name": row["edge_company_name"],
                    "primary_stock_code": row["edge_primary_stock_code"],
                }
            )

        return grouped

    def _load_latest_runs(self, connection) -> dict[str, dict[str, Any]]:
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

    def _rebuild_source_documents(
        self,
        connection,
        raw_documents: list[dict[str, Any]],
        now: str,
        provider_definitions: dict[str, ProviderDefinition],
    ) -> dict[int, int]:
        connection.execute("DELETE FROM source_coverage")
        connection.execute("DELETE FROM news_cards")
        connection.execute("DELETE FROM event_tags")
        connection.execute("DELETE FROM event_evidence")
        connection.execute("DELETE FROM normalized_events")
        connection.execute("DELETE FROM source_documents")

        source_document_id_by_raw_id: dict[int, int] = {}
        for row in raw_documents:
            definition = resolve_provider_definition(
                provider_definitions,
                provider_key=str(row["provider"]),
                document_type=str(row.get("document_type") or ""),
            )
            publisher_definition = ensure_publisher_definition(
                connection,
                publisher_name=row.get("publisher"),
                publisher_key=row.get("publisher_key"),
            )
            publisher_key = publisher_definition.publisher_key if publisher_definition is not None else None
            row["publisher_key"] = publisher_key
            provenance = {
                "raw_document_id": int(row["id"]),
                "duplicate_of_document_id": row["duplicate_of_document_id"],
                "first_seen_run_id": row["first_seen_run_id"],
                "last_seen_run_id": row["last_seen_run_id"],
            }
            metadata = _json_load(row.get("provider_metadata_json")) or {}
            connection.execute(
                """
                INSERT INTO source_documents (
                    raw_document_id,
                    provider,
                    provider_document_id,
                    document_kind,
                    storage_policy,
                    title,
                    snippet,
                    publisher,
                    publisher_key,
                    source_url,
                    canonical_url,
                    published_at,
                    observed_at,
                    published_at_source,
                    receipt_at,
                    company_id,
                    company_ref,
                    query_text,
                    source_metadata_json,
                    provenance_json,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(row["id"]),
                    row["provider"],
                    row["provider_document_id"],
                    definition.document_kind,
                    definition.storage_policy,
                    row["title"],
                    row["summary"],
                    row["publisher"],
                    publisher_key,
                    row["source_url"],
                    row["canonical_url"],
                    row["published_at"],
                    row.get("observed_at"),
                    row.get("published_at_source"),
                    row["receipt_at"],
                    row["company_id"],
                    row["company_ref"],
                    row["query_text"],
                    json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                    json.dumps(provenance, ensure_ascii=False, sort_keys=True),
                    now,
                    now,
                ),
            )
            source_document_id = int(connection.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
            source_document_id_by_raw_id[int(row["id"])] = source_document_id
        return source_document_id_by_raw_id

    def _build_clusters(
        self,
        *,
        raw_documents: list[dict[str, Any]],
        event_map: dict[int, dict[str, Any]],
        source_document_id_by_raw_id: dict[int, int],
        provider_definitions: dict[str, ProviderDefinition],
    ) -> list[dict[str, Any]]:
        cluster_key_by_raw_id: dict[int, str] = {}
        clusters: dict[str, dict[str, Any]] = {}
        ordered_docs = sorted(raw_documents, key=lambda item: int(item["is_duplicate"] or 0))

        for row in ordered_docs:
            raw_document_id = int(row["id"])
            duplicate_of = int(row["duplicate_of_document_id"]) if row["duplicate_of_document_id"] is not None else None
            base_event = event_map.get(duplicate_of or raw_document_id)
            scope_payload = self._classify_scope(row=row, base_event=base_event)

            if duplicate_of is not None and duplicate_of in cluster_key_by_raw_id:
                cluster_key = cluster_key_by_raw_id[duplicate_of]
            else:
                cluster_key = self._cluster_key_for(row=row, base_event=base_event, scope_payload=scope_payload)

            cluster_key_by_raw_id[raw_document_id] = cluster_key
            cluster = clusters.get(cluster_key)
            if cluster is None:
                base_published_at = effective_document_time(
                    document_type=str(row.get("document_type") or ""),
                    published_at=row.get("published_at"),
                    observed_at=row.get("observed_at"),
                    receipt_at=row.get("receipt_at"),
                    updated_at=(base_event or {}).get("occurred_at") or row.get("updated_at"),
                    created_at=row.get("created_at"),
                )
                cluster = {
                    "cluster_key": cluster_key,
                    "event_id": (base_event or {}).get("event_id"),
                    "title": row["title"] or self._fallback_title(base_event),
                    "one_line_summary": self._one_line_summary(row=row, base_event=base_event),
                    "why_it_matters": self._why_it_matters(scope_payload["market_scope"], base_event),
                    "market_impact": self._market_impact(scope_payload["market_scope"], base_event),
                    "market_scope": scope_payload["market_scope"],
                    "primary_region": scope_payload["primary_region"],
                    "trust_score": float(
                        (base_event or {}).get("trust_score")
                        or self._trust_score_for(
                            provider_definitions,
                            provider=str(row["provider"]),
                            document_type=str(row.get("document_type") or ""),
                        )
                    ),
                    "novelty_score": 0.0,
                    "attention_score": 0.0,
                    "cross_source_score": 0.0,
                    "ranking_score": 0.0,
                    "published_at": base_published_at,
                    "updated_at": base_published_at,
                    "providers": set(),
                    "evidence": [],
                    "tags": set(),
                    "quality_flags": set(),
                    "direct_company_names": set(scope_payload["direct_company_names"]),
                    "sector_tags": set(scope_payload["sector_tags"]),
                    "keyword_tags": set(scope_payload["keyword_tags"]),
                }
                clusters[cluster_key] = cluster

            provider = str(row["provider"])
            cluster["providers"].add(provider)
            cluster["tags"].add(("region", scope_payload["primary_region"]))
            cluster["tags"].add(("scope", scope_payload["market_scope"]))
            event_type = (base_event or {}).get("event_type") or classify_event_type(
                " ".join(filter(None, [row.get("title"), row.get("summary")]))
            )
            cluster["tags"].add(("event_type", event_type))

            for company_name in scope_payload["direct_company_names"]:
                cluster["tags"].add(("company", company_name))
            for sector_tag in scope_payload["sector_tags"]:
                cluster["tags"].add(("sector", sector_tag))
            for keyword_tag in scope_payload["keyword_tags"]:
                cluster["tags"].add(("keyword", keyword_tag))

            quality_flags = self._quality_flags(row)
            for flag in quality_flags:
                cluster["quality_flags"].add(flag)
                cluster["tags"].add(("quality", flag))

            publisher_definition = build_publisher_definition(
                publisher_name=row.get("publisher"),
                publisher_key=row.get("publisher_key"),
            )
            cluster["evidence"].append(
                {
                    "source_document_id": source_document_id_by_raw_id[raw_document_id],
                    "provider": provider,
                    "title": row["title"],
                    "snippet": row["summary"],
                    "publisher": row["publisher"],
                    "publisher_key": publisher_definition.publisher_key if publisher_definition is not None else None,
                    "source_url": row["source_url"] or row["canonical_url"],
                    "canonical_url": row["canonical_url"],
                    "published_at": effective_document_time(
                        document_type=str(row.get("document_type") or ""),
                        published_at=row.get("published_at"),
                        observed_at=row.get("observed_at"),
                        receipt_at=row.get("receipt_at"),
                        updated_at=row.get("updated_at"),
                        created_at=row.get("created_at"),
                    ),
                    "observed_at": row.get("observed_at"),
                    "storage_policy": resolve_provider_definition(
                        provider_definitions,
                        provider_key=provider,
                        document_type=str(row.get("document_type") or ""),
                    ).storage_policy,
                    "is_duplicate": bool(row["is_duplicate"]),
                }
            )

            current_published = _parse_iso_datetime(cluster["published_at"])
            candidate_published = _parse_iso_datetime(
                effective_document_time(
                    document_type=str(row.get("document_type") or ""),
                    published_at=row.get("published_at"),
                    observed_at=row.get("observed_at"),
                    receipt_at=row.get("receipt_at"),
                    updated_at=row.get("updated_at"),
                    created_at=row.get("created_at"),
                )
            )
            if candidate_published and (current_published is None or candidate_published > current_published):
                cluster["published_at"] = candidate_published.replace(microsecond=0).isoformat().replace("+00:00", "Z")

        return self._finalize_clusters(list(clusters.values()), provider_definitions)

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
                    _provider_priority(
                        resolve_provider_definition(
                            provider_definitions,
                            provider_key=item["provider"],
                        )
                    ),
                    _storage_policy_rank(item["storage_policy"]),
                    _published_sort_rank(item["published_at"]),
                ),
            )
            cluster["evidence"] = evidence
            distinct_providers = len(cluster["providers"])
            cluster["cross_source_score"] = _clamp(0.22 if distinct_providers >= 3 else 0.12 if distinct_providers == 2 else 0.0)
            published_at = _parse_iso_datetime(cluster["published_at"]) or now
            age_hours = max((now - published_at).total_seconds() / 3600.0, 0.0)
            recency_score = _clamp(1.0 - (age_hours / (self.lookback_days * 24.0)))
            repetition_penalty = min(max(len(evidence) - 1, 0) * 0.05, 0.25)
            cluster["novelty_score"] = _clamp(
                recency_score
                - repetition_penalty
                + (0.06 if evidence and evidence[0]["storage_policy"] == "CANONICAL_EVENT" else 0.0)
            )
            cluster["updated_at"] = utcnow_iso()

            quality_penalty = 0.14 if "low_quality_headline" in cluster["quality_flags"] else 0.0
            scope_priority = _MARKET_SCOPE_PRIORITY.get(cluster["market_scope"], 0.0)
            cluster["ranking_score"] = round(
                max(
                    0.0,
                    (cluster["trust_score"] * 0.45)
                    + (scope_priority * 0.25)
                    + (cluster["novelty_score"] * 0.15)
                    + cluster["cross_source_score"]
                    - quality_penalty,
                ),
                4,
            )
            results.append(cluster)
        return results

    def _resolve_attention_scores(
        self,
        clusters: list[dict[str, Any]],
    ) -> tuple[dict[str, float], dict[str, Any]]:
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

    def _replace_materialized_events(
        self,
        connection,
        clusters: list[dict[str, Any]],
        attention_scores: dict[str, float],
        now: str,
    ) -> None:
        for cluster in clusters:
            attention_score = attention_scores.get(cluster["cluster_key"], 0.0)
            cluster["attention_score"] = attention_score
            cluster["ranking_score"] = round(cluster["ranking_score"] + (attention_score * 0.08), 4)
            connection.execute(
                """
                INSERT INTO normalized_events (
                    event_id,
                    cluster_key,
                    title,
                    one_line_summary,
                    why_it_matters,
                    market_impact,
                    market_scope,
                    primary_region,
                    trust_score,
                    novelty_score,
                    attention_score,
                    cross_source_score,
                    ranking_score,
                    published_at,
                    source_count,
                    evidence_count,
                    provenance_json,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cluster["event_id"],
                    cluster["cluster_key"],
                    cluster["title"],
                    cluster["one_line_summary"],
                    cluster["why_it_matters"],
                    cluster["market_impact"],
                    cluster["market_scope"],
                    cluster["primary_region"],
                    cluster["trust_score"],
                    cluster["novelty_score"],
                    attention_score,
                    cluster["cross_source_score"],
                    cluster["ranking_score"],
                    cluster["published_at"],
                    len(cluster["providers"]),
                    len(cluster["evidence"]),
                    json.dumps(
                        {
                            "providers": sorted(cluster["providers"]),
                            "quality_flags": sorted(cluster["quality_flags"]),
                            "direct_company_names": sorted(cluster["direct_company_names"]),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    now,
                    now,
                ),
            )
            normalized_event_id = int(connection.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])

            representative_evidence_id: int | None = None
            for sort_order, evidence in enumerate(cluster["evidence"], start=1):
                role = self._evidence_role(evidence, sort_order)
                connection.execute(
                    """
                    INSERT INTO event_evidence (
                        normalized_event_id,
                        source_document_id,
                        evidence_role,
                        provider,
                        title,
                        snippet,
                        publisher,
                        publisher_key,
                        source_url,
                        published_at,
                        observed_at,
                        sort_order,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized_event_id,
                        evidence["source_document_id"],
                        role,
                        evidence["provider"],
                        evidence["title"],
                        evidence["snippet"],
                        evidence["publisher"],
                        evidence.get("publisher_key"),
                        evidence["source_url"],
                        evidence["published_at"],
                        evidence.get("observed_at"),
                        sort_order,
                        now,
                        now,
                    ),
                )
                evidence_id = int(connection.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
                if representative_evidence_id is None:
                    representative_evidence_id = evidence_id

            for tag_type, tag_value in sorted(cluster["tags"]):
                connection.execute(
                    """
                    INSERT INTO event_tags (
                        normalized_event_id,
                        tag_type,
                        tag_value,
                        tag_score,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        normalized_event_id,
                        tag_type,
                        tag_value,
                        1.0,
                        now,
                    ),
                )

            if cluster["market_scope"] == "ignore":
                continue

            if cluster["primary_region"] == "KR":
                column_key = "KR"
            else:
                column_key = "GLOBAL"

            if cluster["market_scope"] == "company" and cluster["ranking_score"] < 0.92:
                continue

            connection.execute(
                """
                INSERT INTO news_cards (
                    card_key,
                    normalized_event_id,
                    column_key,
                    title,
                    one_line_summary,
                    why_it_matters,
                    market_impact,
                    market_scope,
                    primary_region,
                    trust_score,
                    novelty_score,
                    attention_score,
                    ranking_score,
                    representative_evidence_id,
                    evidence_count,
                    published_at,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"news-card-{normalized_event_id}",
                    normalized_event_id,
                    column_key,
                    cluster["title"],
                    cluster["one_line_summary"],
                    cluster["why_it_matters"],
                    cluster["market_impact"],
                    cluster["market_scope"],
                    cluster["primary_region"],
                    cluster["trust_score"],
                    cluster["novelty_score"],
                    attention_score,
                    cluster["ranking_score"],
                    representative_evidence_id,
                    len(cluster["evidence"]),
                    cluster["published_at"],
                    now,
                    now,
                ),
            )

    def _replace_source_coverage(
        self,
        connection,
        *,
        now: str,
        raw_documents: list[dict[str, Any]],
        clusters: list[dict[str, Any]],
        latest_runs: dict[str, dict[str, Any]],
        datalab_status: dict[str, Any],
        provider_definitions: dict[str, ProviderDefinition],
    ) -> None:
        docs_by_provider: dict[str, list[dict[str, Any]]] = defaultdict(list)
        evidence_counts: dict[str, int] = defaultdict(int)
        event_counts: dict[str, int] = defaultdict(int)

        for row in raw_documents:
            docs_by_provider[str(row["provider"])].append(row)

        for cluster in clusters:
            providers = set(cluster["providers"])
            for provider in providers:
                event_counts[provider] += 1
            for evidence in cluster["evidence"]:
                evidence_counts[str(evidence["provider"])] += 1

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
                _provider_priority(
                    resolve_provider_definition(
                        provider_definitions,
                        provider_key=provider,
                    )
                ),
                provider,
            ),
        )

        for provider in ordered_raw_news_providers:
            rows = docs_by_provider.get(provider, [])
            latest_run = latest_runs.get(provider, {})
            status = "available" if rows else "missing"
            note = None
            if latest_run:
                latest_status = str(latest_run.get("status") or "")
                if latest_status in {"FAILED", "SKIPPED_DISABLED"} and rows:
                    status = "partial"
                elif latest_status in {"FAILED", "SKIPPED_DISABLED"} and not rows:
                    status = "missing"
                metadata = latest_run.get("metadata") or {}
                disabled_reason = metadata.get("disabled_reason") if isinstance(metadata, dict) else None
                note = disabled_reason or latest_run.get("error_message")

            last_published_at = self._latest_timestamp(
                [
                    effective_document_time(
                        document_type=str(row.get("document_type") or ""),
                        published_at=row.get("published_at"),
                        observed_at=row.get("observed_at"),
                        receipt_at=row.get("receipt_at"),
                        updated_at=row.get("updated_at"),
                        created_at=row.get("created_at"),
                    )
                    for row in rows
                ]
            )
            connection.execute(
                """
                INSERT INTO source_coverage (
                    surface_key,
                    provider,
                    status,
                    document_count,
                    event_count,
                    evidence_count,
                    last_published_at,
                    last_synced_at,
                    note,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "news_tab",
                    provider,
                    status,
                    len(rows),
                    event_counts.get(provider, 0),
                    evidence_counts.get(provider, 0),
                    last_published_at,
                    latest_run.get("finished_at"),
                    note,
                    json.dumps(latest_run or {}, ensure_ascii=False, sort_keys=True),
                    now,
                    now,
                ),
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
            connection.execute(
                """
                INSERT INTO source_coverage (
                    surface_key,
                    provider,
                    status,
                    document_count,
                    event_count,
                    evidence_count,
                    last_published_at,
                    last_synced_at,
                    note,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "news_tab",
                    provider,
                    datalab_status["status"],
                    0,
                    0,
                    0,
                    None,
                    now,
                    datalab_status.get("note"),
                    json.dumps(datalab_status, ensure_ascii=False, sort_keys=True),
                    now,
                    now,
                ),
            )

    def _classify_scope(
        self,
        *,
        row: dict[str, Any],
        base_event: dict[str, Any] | None,
    ) -> dict[str, Any]:
        text = " ".join(
            filter(
                None,
                [
                    str(row.get("title") or ""),
                    str(row.get("summary") or ""),
                    str(row.get("query_text") or ""),
                    str((base_event or {}).get("summary") or ""),
                ],
            )
        )
        normalized = normalize_title(text) or ""
        event_companies = list((base_event or {}).get("companies") or [])
        direct_companies = [
            company
            for company in event_companies
            if str(company.get("impact_tier") or "").lower() == "direct"
        ]
        direct_company_names = {
            str(company.get("company_name") or "").strip()
            for company in direct_companies
            if str(company.get("company_name") or "").strip()
        }
        if row.get("company_name"):
            direct_company_names.add(str(row["company_name"]).strip())

        sector_tags = set()
        if row.get("market_classification"):
            sector_tags.add(str(row["market_classification"]).strip())
        keyword_tags = set(self._headline_tokens(text)[:4])

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

        return {
            "market_scope": market_scope,
            "primary_region": primary_region,
            "direct_company_names": sorted(name for name in direct_company_names if name),
            "sector_tags": sorted(tag for tag in sector_tags if tag),
            "keyword_tags": sorted(keyword_tags),
        }

    def _cluster_key_for(
        self,
        *,
        row: dict[str, Any],
        base_event: dict[str, Any] | None,
        scope_payload: dict[str, Any],
    ) -> str:
        published_at = _parse_iso_datetime(
            effective_document_time(
                document_type=str(row.get("document_type") or ""),
                published_at=row.get("published_at"),
                observed_at=row.get("observed_at"),
                receipt_at=row.get("receipt_at"),
                updated_at=(base_event or {}).get("occurred_at"),
                created_at=row.get("created_at"),
            )
        )
        date_bucket = published_at.date().isoformat() if published_at else "unknown"
        event_type = (base_event or {}).get("event_type") or classify_event_type(
            " ".join(filter(None, [row.get("title"), row.get("summary")]))
        )
        signature = "|".join(self._headline_tokens(" ".join(filter(None, [row.get("title"), row.get("summary")])) )[:5])
        company_part = "|".join(scope_payload["direct_company_names"]) or str(row.get("company_ref") or "")
        seed = "|".join(
            [
                str(event_type),
                date_bucket,
                str(scope_payload["primary_region"]),
                str(scope_payload["market_scope"]),
                company_part,
                signature or str(row.get("canonical_url") or row.get("title") or row.get("id")),
            ]
        )
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()

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

    def _why_it_matters(self, market_scope: str, base_event: dict[str, Any] | None) -> str:
        if base_event and base_event.get("summary") and market_scope in {"kr_market", "global_market"}:
            return _WHY_IT_MATTERS_BY_SCOPE[market_scope]
        return _WHY_IT_MATTERS_BY_SCOPE.get(market_scope, _WHY_IT_MATTERS_BY_SCOPE["ignore"])

    def _market_impact(self, market_scope: str, base_event: dict[str, Any] | None) -> str:
        sentiment = str((base_event or {}).get("sentiment") or "neutral")
        prefix = _MARKET_IMPACT_PREFIX.get(sentiment, _MARKET_IMPACT_PREFIX["neutral"])
        if market_scope == "kr_market":
            return f"{prefix}가 국내 지수와 수급에 반영될 가능성이 큽니다."
        if market_scope == "global_market":
            return f"{prefix}가 환율과 위험선호를 통해 국내 증시에 전이될 수 있습니다."
        if market_scope == "sector":
            return f"{prefix}가 업종 전반으로 번질 수 있습니다."
        if market_scope == "company":
            return f"{prefix}가 개별 종목에 집중될 가능성이 큽니다."
        return "시장 전체 영향은 제한적입니다."

    def _one_line_summary(self, *, row: dict[str, Any], base_event: dict[str, Any] | None) -> str:
        summary = str((base_event or {}).get("summary") or row.get("summary") or row.get("title") or "").strip()
        if not summary:
            return "시장 이벤트가 감지되었습니다."
        return summary[:140]

    def _fallback_title(self, base_event: dict[str, Any] | None) -> str:
        if base_event and base_event.get("summary"):
            return str(base_event["summary"])[:80]
        return "시장 이벤트"

    def _attention_keywords(self, cluster: dict[str, Any]) -> list[str]:
        keywords = []
        keywords.extend(sorted(cluster["direct_company_names"]))
        keywords.extend(sorted(cluster["sector_tags"]))
        keywords.extend(sorted(cluster["keyword_tags"]))
        if not keywords:
            title_tokens = self._headline_tokens(cluster["title"])
            keywords.extend(title_tokens[:4])

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
        if sort_order == 1 or evidence["storage_policy"] == "CANONICAL_EVENT":
            return "PRIMARY"
        if evidence["storage_policy"] == "TRANSIENT_DISCOVERY":
            return "DISCOVERY"
        return "CONFIRMING"

    def _latest_timestamp(self, values: list[str | None]) -> str | None:
        parsed = [value for value in values if value]
        if not parsed:
            return None
        return max(parsed)
