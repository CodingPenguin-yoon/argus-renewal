from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Any

from ..company_master.db import get_connection, utcnow_iso
from ..publisher_registry import ensure_publisher_definition
from ..provider_registry import list_provider_definitions, resolve_provider_definition
from .document_time import effective_document_time
from .event_taxonomy import (
    EVENT_TAXONOMY,
    RELATIONSHIP_KEYWORDS,
    SOURCE_TRUST_SCORES,
    THEME_KEYWORDS,
    classify_event_type,
    classify_sentiment,
    event_type_label,
    normalize_event_type,
)
from .llm import (
    DisabledLLMExtractionProvider,
    LLMCompanyImpact,
    LLMExtractionProvider,
    LLMExtractionRequest,
    LLMExtractionResponse,
)
from .normalize import normalize_title

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EventNormalizationResult:
    run_id: int
    status: str
    processed_count: int
    created_event_count: int
    updated_event_count: int
    review_enqueued_count: int
    failed_count: int


class EventNormalizationService:
    def __init__(
        self,
        *,
        db_path: str,
        llm_provider: LLMExtractionProvider | None = None,
        low_confidence_threshold: float = 0.55,
    ) -> None:
        self.db_path = db_path
        self.llm_provider = llm_provider or DisabledLLMExtractionProvider()
        self.low_confidence_threshold = max(0.0, min(1.0, low_confidence_threshold))

    def normalize_pending_documents(
        self,
        *,
        limit: int = 200,
        include_llm: bool = True,
    ) -> EventNormalizationResult:
        with get_connection(self.db_path) as connection:
            run_id = self._start_sync_run(
                connection,
                job_name="event_normalization_sync",
                source_system="EVENT_PIPELINE",
            )

            processed_count = 0
            created_event_count = 0
            updated_event_count = 0
            review_enqueued_count = 0
            failed_count = 0

            try:
                pending_rows = self._load_pending_documents(connection, limit=limit)
                aliases = self._load_company_aliases(connection)

                for row in pending_rows:
                    processed_count += 1
                    try:
                        outcome = self._process_document(
                            connection,
                            row=dict(row),
                            aliases=aliases,
                            include_llm=include_llm,
                        )
                        created_event_count += int(outcome["created"])
                        updated_event_count += int(outcome["updated"])
                        review_enqueued_count += int(outcome["review_enqueued"])
                    except Exception as error:  # noqa: BLE001
                        failed_count += 1
                        logger.exception(
                            "event_document_process_failed",
                            extra={
                                "run_id": run_id,
                                "raw_document_id": row["id"],
                                "error": str(error),
                            },
                        )
                        self._upsert_event_extraction(
                            connection,
                            raw_document_id=int(row["id"]),
                            event_id=None,
                            extraction_method="FALLBACK_RULE",
                            llm_provider=None,
                            llm_model=None,
                            parse_status="FAILED",
                            input_hash=self._hash_text(self._document_text(dict(row))),
                            output_payload={"error": str(error)},
                            confidence=None,
                            error_message=str(error),
                        )

                self._finish_sync_run(
                    connection,
                    run_id=run_id,
                    status="SUCCESS",
                    processed_count=processed_count,
                    inserted_count=created_event_count,
                    updated_count=updated_event_count,
                    failed_count=failed_count,
                    metadata={
                        "review_enqueued_count": review_enqueued_count,
                        "llm_enabled": include_llm,
                    },
                )
                return EventNormalizationResult(
                    run_id=run_id,
                    status="SUCCESS",
                    processed_count=processed_count,
                    created_event_count=created_event_count,
                    updated_event_count=updated_event_count,
                    review_enqueued_count=review_enqueued_count,
                    failed_count=failed_count,
                )
            except Exception as error:  # noqa: BLE001
                self._finish_sync_run(
                    connection,
                    run_id=run_id,
                    status="FAILED",
                    processed_count=processed_count,
                    inserted_count=created_event_count,
                    updated_count=updated_event_count,
                    failed_count=failed_count,
                    metadata={"review_enqueued_count": review_enqueued_count, "llm_enabled": include_llm},
                    error_message=str(error),
                )
                raise

    def list_recent_events(
        self,
        *,
        limit: int,
        event_type: str | None,
        impact_tier: str | None,
        min_confidence: float | None,
        source_type: str | None,
    ) -> list[dict[str, Any]]:
        return self._list_events(
            limit=limit,
            company_id=None,
            event_type=event_type,
            impact_tier=impact_tier,
            min_confidence=min_confidence,
            source_type=source_type,
        )

    def list_company_events(
        self,
        *,
        company_id: int,
        limit: int,
        event_type: str | None,
        impact_tier: str | None,
        min_confidence: float | None,
        source_type: str | None,
    ) -> list[dict[str, Any]]:
        return self._list_events(
            limit=limit,
            company_id=company_id,
            event_type=event_type,
            impact_tier=impact_tier,
            min_confidence=min_confidence,
            source_type=source_type,
        )

    def list_review_queue(self, *, limit: int, status: str | None) -> list[dict[str, Any]]:
        normalized_status = status.strip().upper() if status else None
        if normalized_status and normalized_status not in {"PENDING", "APPROVED", "REJECTED"}:
            raise ValueError("status must be one of PENDING, APPROVED, REJECTED")

        with get_connection(self.db_path) as connection:
            params: list[Any] = []
            filters: list[str] = []

            if normalized_status:
                filters.append("q.queue_status = ?")
                params.append(normalized_status)

            where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
            params.append(limit)

            rows = connection.execute(
                f"""
                SELECT
                    q.*, e.event_type, e.event_type_label, e.summary, e.sentiment,
                    e.source_type, e.confidence, e.trust_score, e.occurred_at,
                    rd.title AS source_title,
                    rd.provider AS source_provider,
                    rd.publisher AS source_publisher,
                    rd.source_url AS source_url,
                    rd.canonical_url AS canonical_url
                FROM event_review_queue q
                JOIN events e ON e.id = q.event_id
                JOIN raw_documents rd ON rd.id = e.primary_document_id
                {where_clause}
                ORDER BY q.created_at DESC, q.id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        return [dict(row) for row in rows]

    def apply_review_decision(
        self,
        *,
        event_id: int,
        decision: str,
        reviewer: str,
        note: str | None,
    ) -> dict[str, Any]:
        normalized_decision = decision.strip().lower()
        if normalized_decision not in {"approve", "reject"}:
            raise ValueError("decision must be approve or reject")

        queue_status = "APPROVED" if normalized_decision == "approve" else "REJECTED"
        event_status = "APPROVED" if normalized_decision == "approve" else "REJECTED"

        with get_connection(self.db_path) as connection:
            event_row = connection.execute(
                "SELECT id FROM events WHERE id = ?",
                (event_id,),
            ).fetchone()
            if event_row is None:
                raise ValueError(f"event not found: {event_id}")

            now = utcnow_iso()
            connection.execute(
                "UPDATE events SET status = ?, updated_at = ? WHERE id = ?",
                (event_status, now, event_id),
            )

            queue_row = connection.execute(
                "SELECT id, created_at FROM event_review_queue WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if queue_row is None:
                connection.execute(
                    """
                    INSERT INTO event_review_queue (
                        event_id,
                        queue_status,
                        review_reason,
                        reviewer,
                        review_note,
                        reviewed_at,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        queue_status,
                        "manual_review_decision",
                        reviewer.strip() or "reviewer",
                        note,
                        now,
                        now,
                        now,
                    ),
                )
            else:
                connection.execute(
                    """
                    UPDATE event_review_queue
                    SET
                        queue_status = ?,
                        reviewer = ?,
                        review_note = ?,
                        reviewed_at = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        queue_status,
                        reviewer.strip() or "reviewer",
                        note,
                        now,
                        now,
                        int(queue_row["id"]),
                    ),
                )

            row = connection.execute(
                """
                SELECT
                    q.*, e.status AS event_status, e.event_type, e.summary
                FROM event_review_queue q
                JOIN events e ON e.id = q.event_id
                WHERE q.event_id = ?
                """,
                (event_id,),
            ).fetchone()

        assert row is not None
        return dict(row)

    def _process_document(
        self,
        connection,
        *,
        row: dict[str, Any],
        aliases: dict[int, set[str]],
        include_llm: bool,
    ) -> dict[str, bool]:
        raw_document_id = int(row["id"])
        metadata = self._json_load(row.get("provider_metadata_json")) or {}
        if not isinstance(metadata, dict):
            metadata = {}

        source_type, trust_score = self._resolve_source_type(
            connection,
            provider=str(row["provider"]),
            document_type=row.get("document_type"),
        )
        normalized_text = self._document_text(row)
        mentions = self._extract_company_mentions(row=row, aliases=aliases)
        direct_company_ids = self._resolve_direct_company_ids(connection, row=row, metadata=metadata)

        extraction_method = "FALLBACK_RULE"
        llm_provider_name: str | None = None
        llm_model_name: str | None = None

        llm_response: LLMExtractionResponse | None = None

        if row.get("provider") == "DART" and direct_company_ids:
            extraction_method = "DETERMINISTIC_DART"
        elif include_llm:
            enabled, reason = self.llm_provider.is_enabled()
            if enabled:
                try:
                    llm_response = self.llm_provider.extract_event(
                        LLMExtractionRequest(
                            raw_document_id=raw_document_id,
                            normalized_text=normalized_text,
                            candidate_companies=[
                                {
                                    "company_id": item["company_id"],
                                    "company_name": item["company_name"],
                                    "matched_alias": item["matched_alias"],
                                }
                                for item in mentions
                            ],
                            taxonomy=list(EVENT_TAXONOMY),
                        )
                    )
                    if llm_response is not None:
                        extraction_method = "LLM"
                        llm_provider_name = self.llm_provider.provider_name
                        llm_model_name = self.llm_provider.model_name()
                except Exception as error:  # noqa: BLE001
                    logger.warning(
                        "event_llm_extract_failed_fallback",
                        extra={"raw_document_id": raw_document_id, "error": str(error)},
                    )
            else:
                logger.info(
                    "event_llm_extract_skipped",
                    extra={"raw_document_id": raw_document_id, "reason": reason},
                )

        if extraction_method == "DETERMINISTIC_DART":
            event_type = classify_event_type(normalized_text)
            summary = self._make_summary(row=row)
            sentiment = classify_sentiment(normalized_text)
            edges = self._build_dart_direct_edges(
                row=row,
                mentions=mentions,
                direct_company_ids=direct_company_ids,
                trust_score=trust_score,
            )
            risk_flags: list[str] = []
            extraction_confidence = max(0.86, trust_score * 0.92)
            output_payload = {
                "event_type": event_type,
                "summary": summary,
                "sentiment": sentiment,
                "companies": [self._serialize_edge(edge) for edge in edges],
                "risk_flags": risk_flags,
                "confidence": extraction_confidence,
            }
        elif llm_response is not None:
            event_type = llm_response.event_type
            summary = llm_response.summary
            sentiment = llm_response.sentiment
            edges = self._build_edges_from_llm(
                response=llm_response,
                mentions=mentions,
                direct_company_ids=direct_company_ids,
                trust_score=trust_score,
            )
            if not edges:
                edges = self._build_rule_edges(
                    row=row,
                    mentions=mentions,
                    direct_company_ids=direct_company_ids,
                    event_type=event_type,
                    trust_score=trust_score,
                )
            risk_flags = llm_response.risk_flags
            extraction_confidence = self._compose_confidence(
                trust_score=trust_score,
                extraction_confidence=llm_response.confidence,
                edges=edges,
                source_type=source_type,
                used_llm=True,
            )
            output_payload = llm_response.raw_output
        else:
            event_type = classify_event_type(normalized_text)
            summary = self._make_summary(row=row)
            sentiment = classify_sentiment(normalized_text)
            edges = self._build_rule_edges(
                row=row,
                mentions=mentions,
                direct_company_ids=direct_company_ids,
                event_type=event_type,
                trust_score=trust_score,
            )
            risk_flags = self._build_fallback_risk_flags(
                source_type=source_type,
                edges=edges,
                event_type=event_type,
            )
            extraction_confidence = self._compose_confidence(
                trust_score=trust_score,
                extraction_confidence=0.52,
                edges=edges,
                source_type=source_type,
                used_llm=False,
            )
            output_payload = {
                "event_type": event_type,
                "summary": summary,
                "sentiment": sentiment,
                "companies": [self._serialize_edge(edge) for edge in edges],
                "risk_flags": risk_flags,
                "confidence": extraction_confidence,
            }

        if not summary:
            summary = "normalized_event"

        event_id, created = self._upsert_event(
            connection,
            row=row,
            event_type=event_type,
            summary=summary,
            sentiment=sentiment,
            source_type=source_type,
            trust_score=trust_score,
            risk_flags=risk_flags,
            confidence=extraction_confidence,
            metadata={
                "source_url": row.get("source_url"),
                "canonical_url": row.get("canonical_url"),
                "provider_document_id": row.get("provider_document_id"),
                "publisher": row.get("publisher"),
                "report_type": row.get("report_type"),
                "snippet": self._source_snippet(row),
                "raw_document_id": raw_document_id,
            },
        )

        self._replace_event_edges(connection, event_id=event_id, edges=edges)
        review_enqueued = self._upsert_review_queue(
            connection,
            event_id=event_id,
            confidence=extraction_confidence,
            threshold=self.low_confidence_threshold,
            reason=self._review_reason(source_type=source_type, edges=edges, confidence=extraction_confidence),
        )

        self._upsert_event_extraction(
            connection,
            raw_document_id=raw_document_id,
            event_id=event_id,
            extraction_method=extraction_method,
            llm_provider=llm_provider_name,
            llm_model=llm_model_name,
            parse_status="SUCCESS",
            input_hash=self._hash_text(normalized_text),
            output_payload=output_payload,
            confidence=extraction_confidence,
            error_message=None,
        )

        return {
            "created": created,
            "updated": not created,
            "review_enqueued": review_enqueued,
        }

    def _load_pending_documents(self, connection, *, limit: int) -> list[Any]:
        return connection.execute(
            """
            SELECT rd.*
            FROM raw_documents rd
            WHERE rd.is_duplicate = 0
              AND NOT EXISTS (
                  SELECT 1
                  FROM event_extractions ee
                  WHERE ee.raw_document_id = rd.id
                    AND ee.parse_status = 'SUCCESS'
              )
            ORDER BY rd.id ASC
            LIMIT ?
            """,
            (max(1, limit),),
        ).fetchall()

    def _load_company_aliases(self, connection) -> dict[int, set[str]]:
        aliases: dict[int, set[str]] = {}

        for row in connection.execute(
            """
            SELECT id, canonical_name, canonical_name_en
            FROM companies
            """
        ).fetchall():
            payload = dict(row)
            company_id = int(payload["id"])
            aliases.setdefault(company_id, set())
            for candidate in (payload.get("canonical_name"), payload.get("canonical_name_en")):
                normalized = normalize_title(str(candidate) if candidate is not None else None)
                if normalized and len(normalized) >= 2:
                    aliases[company_id].add(normalized)

        for row in connection.execute(
            """
            SELECT company_id, source_name, source_name_en
            FROM company_source_mappings
            WHERE company_id IS NOT NULL
            """
        ).fetchall():
            payload = dict(row)
            company_id = int(payload["company_id"])
            aliases.setdefault(company_id, set())
            for candidate in (payload.get("source_name"), payload.get("source_name_en")):
                normalized = normalize_title(str(candidate) if candidate is not None else None)
                if normalized and len(normalized) >= 2:
                    aliases[company_id].add(normalized)

        return aliases

    def _extract_company_mentions(
        self,
        *,
        row: dict[str, Any],
        aliases: dict[int, set[str]],
    ) -> list[dict[str, Any]]:
        title_normalized = normalize_title(row.get("title")) or ""
        summary_normalized = normalize_title(row.get("summary")) or ""
        combined = f"{title_normalized}\n{summary_normalized}".strip()

        mentions: list[dict[str, Any]] = []

        if not combined:
            return mentions

        for company_id, candidate_aliases in aliases.items():
            if not candidate_aliases:
                continue

            matched_alias = None
            in_title = False
            for alias in sorted(candidate_aliases, key=len, reverse=True):
                if alias in title_normalized:
                    matched_alias = alias
                    in_title = True
                    break
                if alias in summary_normalized:
                    matched_alias = alias
                    in_title = False
                    break

            if matched_alias is None:
                continue

            mentions.append(
                {
                    "company_id": company_id,
                    "company_name": self._company_name_from_alias(candidate_aliases),
                    "matched_alias": matched_alias,
                    "in_title": in_title,
                    "evidence_text": self._mention_evidence(row=row, alias=matched_alias),
                }
            )

        mentions.sort(
            key=lambda item: (
                0 if item["in_title"] else 1,
                -len(str(item["matched_alias"])),
            )
        )
        return mentions[:25]

    def _resolve_direct_company_ids(self, connection, *, row: dict[str, Any], metadata: dict[str, Any]) -> set[int]:
        direct_ids: set[int] = set()

        if row.get("company_id") is not None:
            try:
                direct_ids.add(int(row["company_id"]))
            except (TypeError, ValueError):
                pass

        if row.get("provider") != "DART":
            return direct_ids

        corp_code = str(metadata.get("corp_code") or "").strip()
        if not corp_code:
            return direct_ids

        mapped_row = connection.execute(
            """
            SELECT company_id
            FROM company_source_mappings
            WHERE source_system = 'DART'
              AND source_record_id = ?
              AND company_id IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (corp_code,),
        ).fetchone()

        if mapped_row and mapped_row["company_id"] is not None:
            direct_ids.add(int(mapped_row["company_id"]))

        return direct_ids

    def _build_dart_direct_edges(
        self,
        *,
        row: dict[str, Any],
        mentions: list[dict[str, Any]],
        direct_company_ids: set[int],
        trust_score: float,
    ) -> list[dict[str, Any]]:
        edges: list[dict[str, Any]] = []

        if not direct_company_ids:
            return edges

        mention_map = {int(item["company_id"]): item for item in mentions}
        for company_id in sorted(direct_company_ids):
            mention = mention_map.get(company_id)
            edges.append(
                {
                    "company_id": company_id,
                    "impact_tier": "direct",
                    "reason": "DART filer mapping",
                    "evidence_text": (mention or {}).get("evidence_text") or self._source_snippet(row),
                    "mapping_rule_source": "DART_FILER_MATCH",
                    "confidence": max(0.88, trust_score * 0.92),
                }
            )

        return edges

    def _build_edges_from_llm(
        self,
        *,
        response: LLMExtractionResponse,
        mentions: list[dict[str, Any]],
        direct_company_ids: set[int],
        trust_score: float,
    ) -> list[dict[str, Any]]:
        mention_map = {int(item["company_id"]): item for item in mentions}
        edges: list[dict[str, Any]] = []
        seen: set[tuple[int, str]] = set()

        for company in response.companies:
            if company.company_id <= 0:
                continue
            if company.impact_tier not in {"direct", "indirect", "theme"}:
                continue

            key = (company.company_id, company.impact_tier)
            if key in seen:
                continue
            seen.add(key)

            mention = mention_map.get(company.company_id)
            rule_source = "LLM_OUTPUT"
            if company.company_id in direct_company_ids and company.impact_tier != "direct":
                impact_tier = "direct"
                reason = "DART/company mapping priority"
            else:
                impact_tier = company.impact_tier
                reason = company.reason

            edges.append(
                {
                    "company_id": company.company_id,
                    "impact_tier": impact_tier,
                    "reason": reason,
                    "evidence_text": (mention or {}).get("evidence_text") or reason,
                    "mapping_rule_source": rule_source,
                    "confidence": max(0.0, min(1.0, (company.confidence * 0.7) + (trust_score * 0.3))),
                }
            )

        return edges

    def _build_rule_edges(
        self,
        *,
        row: dict[str, Any],
        mentions: list[dict[str, Any]],
        direct_company_ids: set[int],
        event_type: str,
        trust_score: float,
    ) -> list[dict[str, Any]]:
        normalized_text = normalize_title(self._document_text(row)) or ""

        if not direct_company_ids and mentions:
            subject = mentions[0]
            direct_company_ids.add(int(subject["company_id"]))

        mentioned_company_ids = {int(item["company_id"]) for item in mentions}
        for company_id in sorted(direct_company_ids):
            if company_id in mentioned_company_ids:
                continue
            mentions.append(
                {
                    "company_id": company_id,
                    "company_name": str(company_id),
                    "matched_alias": "",
                    "in_title": False,
                    "evidence_text": self._source_snippet(row),
                }
            )

        has_relationship = any(keyword.casefold() in normalized_text for keyword in RELATIONSHIP_KEYWORDS)
        has_theme = event_type in {"regulation_policy", "macro_theme"} or any(
            keyword.casefold() in normalized_text for keyword in THEME_KEYWORDS
        )

        edges: list[dict[str, Any]] = []
        seen: set[tuple[int, str]] = set()

        for mention in mentions:
            company_id = int(mention["company_id"])
            if company_id in direct_company_ids:
                impact_tier = "direct"
                reason = "filer or explicit subject"
                rule_source = "TITLE_SUBJECT_MATCH"
                confidence = max(0.68, trust_score * 0.82)
            else:
                mention_text = normalize_title(str(mention.get("evidence_text") or "")) or ""
                mention_has_relationship = any(
                    keyword.casefold() in mention_text for keyword in RELATIONSHIP_KEYWORDS
                )
                mention_has_theme = any(keyword.casefold() in mention_text for keyword in THEME_KEYWORDS)

                if mention_has_relationship:
                    impact_tier = "indirect"
                    reason = "relationship keyword match"
                    rule_source = "RELATIONSHIP_KEYWORD_RULE"
                    confidence = max(0.45, trust_score * 0.65)
                elif mention_has_theme:
                    impact_tier = "theme"
                    reason = "theme/policy level mention"
                    rule_source = "THEME_KEYWORD_RULE"
                    confidence = max(0.30, trust_score * 0.55)
                elif has_relationship:
                    impact_tier = "indirect"
                    reason = "relationship keyword match"
                    rule_source = "RELATIONSHIP_KEYWORD_RULE"
                    confidence = max(0.45, trust_score * 0.65)
                elif has_theme:
                    impact_tier = "theme"
                    reason = "theme/policy level mention"
                    rule_source = "THEME_KEYWORD_RULE"
                    confidence = max(0.30, trust_score * 0.55)
                else:
                    impact_tier = "indirect"
                    reason = "co-mentioned company"
                    rule_source = "CO_MENTION_RULE"
                    confidence = max(0.40, trust_score * 0.58)

            key = (company_id, impact_tier)
            if key in seen:
                continue
            seen.add(key)

            edges.append(
                {
                    "company_id": company_id,
                    "impact_tier": impact_tier,
                    "reason": reason,
                    "evidence_text": mention.get("evidence_text") or self._source_snippet(row),
                    "mapping_rule_source": rule_source,
                    "confidence": confidence,
                }
            )

        return edges

    def _upsert_event(
        self,
        connection,
        *,
        row: dict[str, Any],
        event_type: str,
        summary: str,
        sentiment: str,
        source_type: str,
        trust_score: float,
        risk_flags: list[str],
        confidence: float,
        metadata: dict[str, Any],
    ) -> tuple[int, bool]:
        now = utcnow_iso()
        primary_document_id = int(row["id"])
        dedup_key = hashlib.sha256(f"raw_document:{primary_document_id}".encode("utf-8")).hexdigest()

        existing = connection.execute(
            "SELECT id, status FROM events WHERE dedup_key = ?",
            (dedup_key,),
        ).fetchone()

        status = "AUTO_APPROVED"
        if existing is not None and existing["status"] in {"APPROVED", "REJECTED"}:
            status = str(existing["status"])

        publisher_definition = ensure_publisher_definition(
            connection,
            publisher_name=row.get("publisher"),
            publisher_key=row.get("publisher_key"),
        )
        publisher_key = publisher_definition.publisher_key if publisher_definition is not None else None
        occurred_at = effective_document_time(
            document_type=str(row.get("document_type") or ""),
            published_at=row.get("published_at"),
            observed_at=row.get("observed_at"),
            receipt_at=row.get("receipt_at"),
            fallback=now,
        )
        payload = (
            dedup_key,
            primary_document_id,
            event_type,
            event_type_label(event_type),
            summary,
            sentiment,
            source_type,
            str(row.get("provider") or "NAVER_NEWS"),
            row.get("publisher"),
            publisher_key,
            row.get("source_url"),
            row.get("canonical_url"),
            occurred_at,
            trust_score,
            confidence,
            json.dumps(risk_flags, ensure_ascii=False, sort_keys=True),
            status,
            json.dumps(metadata, ensure_ascii=False, sort_keys=True),
            now,
            now,
        )

        if existing is None:
            connection.execute(
                """
                INSERT INTO events (
                    dedup_key,
                    primary_document_id,
                    event_type,
                    event_type_label,
                    summary,
                    sentiment,
                    source_type,
                    source_provider,
                    publisher,
                    publisher_key,
                    source_url,
                    canonical_url,
                    occurred_at,
                    trust_score,
                    confidence,
                    risk_flags_json,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                payload,
            )
            event_id = int(connection.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
            return event_id, True

        event_id = int(existing["id"])
        connection.execute(
            """
            UPDATE events
            SET
                primary_document_id = ?,
                event_type = ?,
                event_type_label = ?,
                summary = ?,
                sentiment = ?,
                source_type = ?,
                source_provider = ?,
                publisher = ?,
                publisher_key = ?,
                source_url = ?,
                canonical_url = ?,
                occurred_at = ?,
                trust_score = ?,
                confidence = ?,
                risk_flags_json = ?,
                status = ?,
                metadata_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                primary_document_id,
                event_type,
                event_type_label(event_type),
                summary,
                sentiment,
                source_type,
                str(row.get("provider") or "NAVER_NEWS"),
                row.get("publisher"),
                publisher_key,
                row.get("source_url"),
                row.get("canonical_url"),
                occurred_at,
                trust_score,
                confidence,
                json.dumps(risk_flags, ensure_ascii=False, sort_keys=True),
                status,
                json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                now,
                event_id,
            ),
        )
        return event_id, False

    def _replace_event_edges(self, connection, *, event_id: int, edges: list[dict[str, Any]]) -> None:
        now = utcnow_iso()
        connection.execute(
            "DELETE FROM event_company_edges WHERE event_id = ?",
            (event_id,),
        )

        for edge in edges:
            connection.execute(
                """
                INSERT INTO event_company_edges (
                    event_id,
                    company_id,
                    impact_tier,
                    reason,
                    evidence_text,
                    mapping_rule_source,
                    confidence,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    int(edge["company_id"]),
                    str(edge["impact_tier"]),
                    str(edge.get("reason") or ""),
                    str(edge.get("evidence_text") or ""),
                    str(edge.get("mapping_rule_source") or ""),
                    max(0.0, min(1.0, float(edge.get("confidence") or 0.0))),
                    now,
                    now,
                ),
            )

    def _upsert_event_extraction(
        self,
        connection,
        *,
        raw_document_id: int,
        event_id: int | None,
        extraction_method: str,
        llm_provider: str | None,
        llm_model: str | None,
        parse_status: str,
        input_hash: str,
        output_payload: dict[str, Any],
        confidence: float | None,
        error_message: str | None,
    ) -> None:
        now = utcnow_iso()
        connection.execute(
            """
            INSERT INTO event_extractions (
                raw_document_id,
                event_id,
                extraction_method,
                llm_provider,
                llm_model,
                parse_status,
                input_hash,
                output_json,
                error_message,
                confidence,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(raw_document_id)
            DO UPDATE SET
                event_id = excluded.event_id,
                extraction_method = excluded.extraction_method,
                llm_provider = excluded.llm_provider,
                llm_model = excluded.llm_model,
                parse_status = excluded.parse_status,
                input_hash = excluded.input_hash,
                output_json = excluded.output_json,
                error_message = excluded.error_message,
                confidence = excluded.confidence,
                updated_at = excluded.updated_at
            """,
            (
                raw_document_id,
                event_id,
                extraction_method,
                llm_provider,
                llm_model,
                parse_status,
                input_hash,
                json.dumps(output_payload, ensure_ascii=False, sort_keys=True),
                error_message,
                confidence,
                now,
                now,
            ),
        )

    def _upsert_review_queue(
        self,
        connection,
        *,
        event_id: int,
        confidence: float,
        threshold: float,
        reason: str,
    ) -> bool:
        now = utcnow_iso()

        if confidence < threshold:
            existing = connection.execute(
                "SELECT id, queue_status FROM event_review_queue WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO event_review_queue (
                        event_id,
                        queue_status,
                        review_reason,
                        review_score,
                        review_threshold,
                        created_at,
                        updated_at
                    ) VALUES (?, 'PENDING', ?, ?, ?, ?, ?)
                    """,
                    (event_id, reason, confidence, threshold, now, now),
                )
            elif str(existing["queue_status"]) == "PENDING":
                connection.execute(
                    """
                    UPDATE event_review_queue
                    SET
                        review_reason = ?,
                        review_score = ?,
                        review_threshold = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (reason, confidence, threshold, now, int(existing["id"])),
                )

            connection.execute(
                "UPDATE events SET status = 'PENDING_REVIEW', updated_at = ? WHERE id = ?",
                (now, event_id),
            )
            return True

        pending_row = connection.execute(
            "SELECT id, queue_status FROM event_review_queue WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if pending_row is not None and str(pending_row["queue_status"]) == "PENDING":
            connection.execute(
                "DELETE FROM event_review_queue WHERE id = ?",
                (int(pending_row["id"]),),
            )

        connection.execute(
            """
            UPDATE events
            SET
                status = CASE
                    WHEN status IN ('APPROVED', 'REJECTED') THEN status
                    ELSE 'AUTO_APPROVED'
                END,
                updated_at = ?
            WHERE id = ?
            """,
            (now, event_id),
        )
        return False

    def _list_events(
        self,
        *,
        limit: int,
        company_id: int | None,
        event_type: str | None,
        impact_tier: str | None,
        min_confidence: float | None,
        source_type: str | None,
    ) -> list[dict[str, Any]]:
        filters: list[str] = []
        params: list[Any] = []

        if company_id is not None:
            filters.append("edge.company_id = ?")
            params.append(company_id)

        normalized_event_type = normalize_event_type(event_type) if event_type else None
        if normalized_event_type:
            filters.append("e.event_type = ?")
            params.append(normalized_event_type)

        if impact_tier:
            candidate = impact_tier.strip().lower()
            if candidate in {"direct", "indirect", "theme"}:
                filters.append("edge.impact_tier = ?")
                params.append(candidate)

        if min_confidence is not None:
            filters.append("e.confidence >= ?")
            params.append(max(0.0, min(1.0, min_confidence)))

        if source_type:
            normalized_source_type = source_type.strip().upper()
            if normalized_source_type in SOURCE_TRUST_SCORES:
                filters.append("e.source_type = ?")
                params.append(normalized_source_type)

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(max(1, limit))

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    e.*,
                    rd.title AS source_title,
                    rd.summary AS source_summary,
                    rd.provider_document_id,
                    rd.report_type,
                    edge.company_id,
                    edge.impact_tier,
                    edge.reason AS edge_reason,
                    edge.evidence_text,
                    edge.mapping_rule_source,
                    edge.confidence AS edge_confidence,
                    c.canonical_name AS company_name,
                    c.primary_stock_code
                FROM events e
                JOIN raw_documents rd ON rd.id = e.primary_document_id
                LEFT JOIN event_company_edges edge ON edge.event_id = e.id
                LEFT JOIN companies c ON c.id = edge.company_id
                {where_clause}
                ORDER BY COALESCE(e.occurred_at, rd.published_at, e.created_at) DESC, e.id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        grouped: dict[int, dict[str, Any]] = {}
        for row in rows:
            event_id = int(row["id"])
            payload = grouped.get(event_id)
            if payload is None:
                payload = {
                    "id": event_id,
                    "event_type": row["event_type"],
                    "event_type_label": row["event_type_label"],
                    "summary": row["summary"],
                    "sentiment": row["sentiment"],
                    "source_type": row["source_type"],
                    "source_provider": row["source_provider"],
                    "publisher": row["publisher"],
                    "source_url": row["source_url"],
                    "canonical_url": row["canonical_url"],
                    "source_title": row["source_title"],
                    "source_summary": row["source_summary"],
                    "provider_document_id": row["provider_document_id"],
                    "report_type": row["report_type"],
                    "occurred_at": row["occurred_at"],
                    "trust_score": row["trust_score"],
                    "confidence": row["confidence"],
                    "status": row["status"],
                    "risk_flags": self._json_load(row["risk_flags_json"]) or [],
                    "metadata": self._json_load(row["metadata_json"]) or {},
                    "companies": [],
                }
                grouped[event_id] = payload

            if row["company_id"] is None:
                continue

            payload["companies"].append(
                {
                    "company_id": int(row["company_id"]),
                    "company_name": row["company_name"],
                    "primary_stock_code": row["primary_stock_code"],
                    "impact_tier": row["impact_tier"],
                    "reason": row["edge_reason"],
                    "evidence_text": row["evidence_text"],
                    "mapping_rule_source": row["mapping_rule_source"],
                    "confidence": row["edge_confidence"],
                }
            )

        return list(grouped.values())

    def _resolve_source_type(self, connection, *, provider: str, document_type: Any) -> tuple[str, float]:
        definitions = list_provider_definitions(connection)
        definition = resolve_provider_definition(
            definitions,
            provider_key=provider,
            document_type=str(document_type or ""),
        )
        source_type = definition.source_type
        if source_type is None:
            if str(document_type or "").upper() == "DISCLOSURE":
                source_type = "DISCLOSURE"
            else:
                source_type = "DISCOVERY_NEWS"
        trust_score = definition.trust_score
        if trust_score is None:
            trust_score = SOURCE_TRUST_SCORES[source_type]
        return source_type, float(trust_score)

    def _make_summary(self, *, row: dict[str, Any]) -> str:
        title = str(row.get("title") or "").strip()
        summary = str(row.get("summary") or "").strip()
        if summary:
            return summary[:280]
        if title:
            return title[:280]
        return "normalized_event"

    def _compose_confidence(
        self,
        *,
        trust_score: float,
        extraction_confidence: float,
        edges: list[dict[str, Any]],
        source_type: str,
        used_llm: bool,
    ) -> float:
        edge_confidence = 0.0
        if edges:
            edge_confidence = sum(float(edge.get("confidence") or 0.0) for edge in edges) / len(edges)

        llm_weight = 0.5 if used_llm else 0.35
        source_weight = 0.3 if source_type == "DISCLOSURE" else 0.25
        edge_weight = 1.0 - llm_weight - source_weight

        score = (
            (extraction_confidence * llm_weight)
            + (trust_score * source_weight)
            + (edge_confidence * edge_weight)
        )
        return max(0.0, min(1.0, score))

    def _build_fallback_risk_flags(
        self,
        *,
        source_type: str,
        edges: list[dict[str, Any]],
        event_type: str,
    ) -> list[str]:
        flags: list[str] = []
        if source_type == "DISCOVERY_NEWS":
            flags.append("discovery_source")
        if not edges:
            flags.append("no_company_mapping")
        if event_type in {"regulation_policy", "macro_theme"}:
            flags.append("theme_level_event")
        return flags

    def _review_reason(self, *, source_type: str, edges: list[dict[str, Any]], confidence: float) -> str:
        if not edges:
            return "no_company_mapping"
        if source_type == "DISCOVERY_NEWS":
            return "low_trust_source"
        if confidence < self.low_confidence_threshold:
            return "low_confidence"
        return "requires_manual_review"

    def _document_text(self, row: dict[str, Any]) -> str:
        parts = [
            str(row.get("title") or "").strip(),
            str(row.get("summary") or "").strip(),
            str(row.get("report_type") or "").strip(),
            str(row.get("publisher") or "").strip(),
        ]
        return "\n".join(part for part in parts if part)

    def _source_snippet(self, row: dict[str, Any]) -> str:
        text = self._document_text(row)
        if not text:
            return ""
        return text[:240]

    def _mention_evidence(self, *, row: dict[str, Any], alias: str) -> str:
        title = str(row.get("title") or "").strip()
        summary = str(row.get("summary") or "").strip()

        if alias and alias in (normalize_title(title) or ""):
            return title[:200]
        if alias and alias in (normalize_title(summary) or ""):
            return summary[:200]
        return self._source_snippet(row)

    def _company_name_from_alias(self, aliases: set[str]) -> str:
        if not aliases:
            return ""
        # Keep deterministic selection for repeatable outputs.
        return sorted(aliases, key=len, reverse=True)[0]

    def _serialize_edge(self, edge: dict[str, Any]) -> dict[str, Any]:
        return {
            "company_id": int(edge["company_id"]),
            "impact_tier": str(edge["impact_tier"]),
            "reason": str(edge.get("reason") or ""),
            "confidence": max(0.0, min(1.0, float(edge.get("confidence") or 0.0))),
        }

    def _start_sync_run(self, connection, *, job_name: str, source_system: str) -> int:
        started_at = utcnow_iso()
        connection.execute(
            """
            INSERT INTO sync_runs (
                job_name,
                source_system,
                status,
                started_at,
                metadata_json
            ) VALUES (?, ?, 'RUNNING', ?, ?)
            """,
            (job_name, source_system, started_at, json.dumps({}, ensure_ascii=False, sort_keys=True)),
        )
        return int(connection.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])

    def _finish_sync_run(
        self,
        connection,
        *,
        run_id: int,
        status: str,
        processed_count: int,
        inserted_count: int,
        updated_count: int,
        failed_count: int,
        metadata: dict[str, Any],
        error_message: str | None = None,
    ) -> None:
        connection.execute(
            """
            UPDATE sync_runs
            SET
                status = ?,
                finished_at = ?,
                processed_count = ?,
                inserted_count = ?,
                updated_count = ?,
                failed_count = ?,
                metadata_json = ?,
                error_message = ?
            WHERE id = ?
            """,
            (
                status,
                utcnow_iso(),
                processed_count,
                inserted_count,
                updated_count,
                failed_count,
                json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                error_message,
                run_id,
            ),
        )

    def _hash_text(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _json_load(self, value: str | None) -> Any:
        if not value:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
