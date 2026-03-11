from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import csv
import json
import logging
from pathlib import Path
from typing import Any

from .db import get_connection, utcnow_iso
from .normalize import normalize_company_name, normalize_stock_code

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncResult:
    run_id: int
    status: str
    processed_count: int
    inserted_count: int
    updated_count: int
    failed_count: int


@dataclass(frozen=True)
class MergeResult:
    run_id: int
    status: str
    processed_count: int
    mapped_count: int
    unresolved_count: int
    conflict_count: int
    created_company_count: int


@dataclass(frozen=True)
class SingleSourceDecision:
    company_id: int | None
    created: bool
    mapping_status: str
    mapping_source: str
    mapping_confidence: float
    needs_review: int
    review_reason: str | None


class CompanyMasterService:
    def __init__(self, *, db_path: str) -> None:
        self.db_path = db_path

    def sync_dart(self, records: list[Any]) -> SyncResult:
        with get_connection(self.db_path) as connection:
            run_id = self._start_sync_run(
                connection,
                job_name="company_master_sync_dart",
                source_system="DART",
            )
            processed_count = 0
            inserted_count = 0
            updated_count = 0
            failed_count = 0

            try:
                for record in records:
                    processed_count += 1
                    try:
                        inserted, updated = self._upsert_source_mapping(
                            connection,
                            source_system="DART",
                            source_record_id=record.corp_code,
                            source_name=record.corp_name,
                            source_name_en=record.corp_eng_name,
                            source_stock_code=record.stock_code,
                            source_market="KR",
                            listing_status="LISTED" if record.stock_code else "UNLISTED",
                            market_classification=None,
                            modify_date=record.modify_date,
                            source_url=record.source_url,
                            source_metadata={
                                "provider": "DART",
                                "modify_date": record.modify_date,
                            },
                            source_snippet=f"{record.corp_code}:{record.corp_name}",
                            run_id=run_id,
                        )
                        inserted_count += int(inserted)
                        updated_count += int(updated)
                    except Exception as error:  # noqa: BLE001
                        failed_count += 1
                        logger.exception(
                            "dart_record_upsert_failed",
                            extra={"corp_code": getattr(record, "corp_code", None), "error": str(error)},
                        )

                self._finish_sync_run(
                    connection,
                    run_id=run_id,
                    status="SUCCESS",
                    processed_count=processed_count,
                    inserted_count=inserted_count,
                    updated_count=updated_count,
                    failed_count=failed_count,
                )
                return SyncResult(
                    run_id=run_id,
                    status="SUCCESS",
                    processed_count=processed_count,
                    inserted_count=inserted_count,
                    updated_count=updated_count,
                    failed_count=failed_count,
                )
            except Exception as error:  # noqa: BLE001
                self._finish_sync_run(
                    connection,
                    run_id=run_id,
                    status="FAILED",
                    processed_count=processed_count,
                    inserted_count=inserted_count,
                    updated_count=updated_count,
                    failed_count=failed_count,
                    error_message=str(error),
                )
                raise

    def sync_kis(self, records: list[Any]) -> SyncResult:
        with get_connection(self.db_path) as connection:
            run_id = self._start_sync_run(
                connection,
                job_name="company_master_sync_kis",
                source_system="KIS",
            )
            processed_count = 0
            inserted_count = 0
            updated_count = 0
            failed_count = 0

            try:
                for record in records:
                    processed_count += 1
                    try:
                        inserted, updated = self._upsert_source_mapping(
                            connection,
                            source_system="KIS",
                            source_record_id=record.symbol,
                            source_name=record.name,
                            source_name_en=None,
                            source_stock_code=record.symbol,
                            source_market=record.market,
                            listing_status=record.listing_status or "UNKNOWN",
                            market_classification=record.market_classification,
                            modify_date=None,
                            source_url=record.source_url,
                            source_metadata={
                                "provider": "KIS",
                                "market": record.market,
                                "listing_status": record.listing_status,
                                "market_classification": record.market_classification,
                            },
                            source_snippet=f"{record.symbol}:{record.name}",
                            run_id=run_id,
                        )
                        inserted_count += int(inserted)
                        updated_count += int(updated)
                    except Exception as error:  # noqa: BLE001
                        failed_count += 1
                        logger.exception(
                            "kis_record_upsert_failed",
                            extra={"symbol": getattr(record, "symbol", None), "error": str(error)},
                        )

                self._finish_sync_run(
                    connection,
                    run_id=run_id,
                    status="SUCCESS",
                    processed_count=processed_count,
                    inserted_count=inserted_count,
                    updated_count=updated_count,
                    failed_count=failed_count,
                )
                return SyncResult(
                    run_id=run_id,
                    status="SUCCESS",
                    processed_count=processed_count,
                    inserted_count=inserted_count,
                    updated_count=updated_count,
                    failed_count=failed_count,
                )
            except Exception as error:  # noqa: BLE001
                self._finish_sync_run(
                    connection,
                    run_id=run_id,
                    status="FAILED",
                    processed_count=processed_count,
                    inserted_count=inserted_count,
                    updated_count=updated_count,
                    failed_count=failed_count,
                    error_message=str(error),
                )
                raise

    def build_mapping(self) -> MergeResult:
        with get_connection(self.db_path) as connection:
            run_id = self._start_sync_run(
                connection,
                job_name="company_master_build_mapping",
                source_system="MERGE",
            )

            self._reset_mapping_state(connection)

            source_rows = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT *
                    FROM company_source_mappings
                    ORDER BY source_system, id
                    """
                ).fetchall()
            ]
            processed_count = len(source_rows)

            overrides = {
                (row["source_system"], row["source_record_id"]): dict(row)
                for row in connection.execute(
                    """
                    SELECT *
                    FROM company_manual_overrides
                    """
                ).fetchall()
            }

            handled_mapping_ids: set[int] = set()
            used_kis_ids: set[int] = set()
            created_company_count = 0

            try:
                for row in source_rows:
                    override = overrides.get((row["source_system"], row["source_record_id"]))
                    if override is None:
                        continue

                    if override["action"] == "SKIP":
                        self._set_mapping_state(
                            connection,
                            mapping_id=row["id"],
                            company_id=None,
                            mapping_status="SKIPPED",
                            mapping_source="MANUAL_OVERRIDE",
                            mapping_confidence=1.0,
                            needs_review=1,
                            review_reason=override["note"] or "manual_skip",
                        )
                        handled_mapping_ids.add(row["id"])
                        continue

                    if override["action"] == "REVIEW":
                        self._set_mapping_state(
                            connection,
                            mapping_id=row["id"],
                            company_id=None,
                            mapping_status="CONFLICT",
                            mapping_source="MANUAL_OVERRIDE",
                            mapping_confidence=0.0,
                            needs_review=1,
                            review_reason=override["note"] or "manual_review",
                        )
                        handled_mapping_ids.add(row["id"])
                        continue

                    if override["action"] == "MAP":
                        try:
                            company_id, created = self._resolve_manual_override_company(
                                connection=connection,
                                source_row=row,
                                override=override,
                            )
                            created_company_count += int(created)
                            self._set_mapping_state(
                                connection,
                                mapping_id=row["id"],
                                company_id=company_id,
                                mapping_status="MAPPED",
                                mapping_source="MANUAL_OVERRIDE",
                                mapping_confidence=1.0,
                                needs_review=0,
                                review_reason=None,
                            )
                        except Exception as error:  # noqa: BLE001
                            self._set_mapping_state(
                                connection,
                                mapping_id=row["id"],
                                company_id=None,
                                mapping_status="CONFLICT",
                                mapping_source="MANUAL_OVERRIDE",
                                mapping_confidence=0.0,
                                needs_review=1,
                                review_reason=f"invalid_manual_override:{error}",
                            )
                        handled_mapping_ids.add(row["id"])
                        if row["source_system"] == "KIS":
                            used_kis_ids.add(row["id"])

                dart_rows = [
                    row
                    for row in source_rows
                    if row["source_system"] == "DART" and row["id"] not in handled_mapping_ids
                ]
                kis_rows = [
                    row
                    for row in source_rows
                    if row["source_system"] == "KIS" and row["id"] not in handled_mapping_ids
                ]

                kis_by_stock_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
                kis_by_normalized_name: dict[str, list[dict[str, Any]]] = defaultdict(list)

                for row in kis_rows:
                    stock_code = normalize_stock_code(row["source_stock_code"])
                    if stock_code:
                        kis_by_stock_code[stock_code].append(row)

                    normalized_name = normalize_company_name(row["source_name"])
                    if normalized_name:
                        kis_by_normalized_name[normalized_name].append(row)

                for dart_row in dart_rows:
                    dart_id = dart_row["id"]
                    if dart_id in handled_mapping_ids:
                        continue

                    matched = False
                    stock_code = normalize_stock_code(dart_row["source_stock_code"])
                    if stock_code:
                        candidates = self._available_candidates(
                            kis_by_stock_code.get(stock_code, []),
                            handled_mapping_ids,
                            used_kis_ids,
                        )
                        if len(candidates) == 1:
                            company_id, created = self._ensure_company_for_pair(
                                connection=connection,
                                dart_row=dart_row,
                                kis_row=candidates[0],
                                mapping_source="STOCK_CODE_EXACT",
                                mapping_confidence=1.0,
                            )
                            created_company_count += int(created)
                            self._set_pair_mapping(
                                connection=connection,
                                dart_row=dart_row,
                                kis_row=candidates[0],
                                company_id=company_id,
                                mapping_source="STOCK_CODE_EXACT",
                                mapping_confidence=1.0,
                            )
                            handled_mapping_ids.add(dart_id)
                            handled_mapping_ids.add(candidates[0]["id"])
                            used_kis_ids.add(candidates[0]["id"])
                            matched = True
                        elif len(candidates) > 1:
                            self._mark_ambiguous(
                                connection=connection,
                                rows=[dart_row, *candidates],
                                reason="ambiguous_stock_code_match",
                                mapping_source="AMBIGUOUS_STOCK_CODE",
                                handled_mapping_ids=handled_mapping_ids,
                            )
                            matched = True

                    if matched:
                        continue

                    normalized_name = normalize_company_name(dart_row["source_name"])
                    if normalized_name:
                        candidates = self._available_candidates(
                            kis_by_normalized_name.get(normalized_name, []),
                            handled_mapping_ids,
                            used_kis_ids,
                        )
                        if len(candidates) == 1:
                            company_id, created = self._ensure_company_for_pair(
                                connection=connection,
                                dart_row=dart_row,
                                kis_row=candidates[0],
                                mapping_source="NORMALIZED_NAME",
                                mapping_confidence=0.75,
                            )
                            created_company_count += int(created)
                            self._set_pair_mapping(
                                connection=connection,
                                dart_row=dart_row,
                                kis_row=candidates[0],
                                company_id=company_id,
                                mapping_source="NORMALIZED_NAME",
                                mapping_confidence=0.75,
                            )
                            handled_mapping_ids.add(dart_id)
                            handled_mapping_ids.add(candidates[0]["id"])
                            used_kis_ids.add(candidates[0]["id"])
                            continue

                        if len(candidates) > 1:
                            self._mark_ambiguous(
                                connection=connection,
                                rows=[dart_row, *candidates],
                                reason="ambiguous_normalized_name_match",
                                mapping_source="AMBIGUOUS_NAME",
                                handled_mapping_ids=handled_mapping_ids,
                            )

                remaining_kis_rows = [
                    row
                    for row in source_rows
                    if row["source_system"] == "KIS" and row["id"] not in handled_mapping_ids
                ]
                for row in remaining_kis_rows:
                    decision = self._ensure_company_for_single_source(
                        connection=connection,
                        row=row,
                        fallback_mapping_source="KIS_ONLY",
                        fallback_confidence=0.6,
                    )
                    created_company_count += int(decision.created)
                    self._set_mapping_state(
                        connection,
                        mapping_id=row["id"],
                        company_id=decision.company_id,
                        mapping_status=decision.mapping_status,
                        mapping_source=decision.mapping_source,
                        mapping_confidence=decision.mapping_confidence,
                        needs_review=decision.needs_review,
                        review_reason=decision.review_reason,
                    )
                    handled_mapping_ids.add(row["id"])

                remaining_dart_rows = [
                    row
                    for row in source_rows
                    if row["source_system"] == "DART" and row["id"] not in handled_mapping_ids
                ]
                for row in remaining_dart_rows:
                    decision = self._ensure_company_for_single_source(
                        connection=connection,
                        row=row,
                        fallback_mapping_source="DART_ONLY",
                        fallback_confidence=0.6,
                    )
                    created_company_count += int(decision.created)
                    self._set_mapping_state(
                        connection,
                        mapping_id=row["id"],
                        company_id=decision.company_id,
                        mapping_status=decision.mapping_status,
                        mapping_source=decision.mapping_source,
                        mapping_confidence=decision.mapping_confidence,
                        needs_review=decision.needs_review,
                        review_reason=decision.review_reason,
                    )
                    handled_mapping_ids.add(row["id"])

                mapped_count = self._count_rows(connection, "MAPPED")
                unresolved_count = self._count_unresolved_rows(connection)
                conflict_count = self._count_rows(connection, "CONFLICT")

                self._finish_sync_run(
                    connection,
                    run_id=run_id,
                    status="SUCCESS",
                    processed_count=processed_count,
                    inserted_count=created_company_count,
                    updated_count=mapped_count,
                    failed_count=0,
                )

                return MergeResult(
                    run_id=run_id,
                    status="SUCCESS",
                    processed_count=processed_count,
                    mapped_count=mapped_count,
                    unresolved_count=unresolved_count,
                    conflict_count=conflict_count,
                    created_company_count=created_company_count,
                )
            except Exception as error:  # noqa: BLE001
                self._finish_sync_run(
                    connection,
                    run_id=run_id,
                    status="FAILED",
                    processed_count=processed_count,
                    inserted_count=created_company_count,
                    updated_count=0,
                    failed_count=1,
                    error_message=str(error),
                )
                raise

    def export_unresolved_mappings(self, output_path: str) -> int:
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    source_system,
                    source_record_id,
                    source_name,
                    source_stock_code,
                    source_market,
                    listing_status,
                    mapping_status,
                    mapping_source,
                    mapping_confidence,
                    needs_review,
                    review_reason,
                    updated_at
                FROM company_source_mappings
                WHERE mapping_status != 'MAPPED' OR needs_review = 1
                ORDER BY updated_at DESC, id DESC
                """
            ).fetchall()

            destination = Path(output_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=[
                        "source_system",
                        "source_record_id",
                        "source_name",
                        "source_stock_code",
                        "source_market",
                        "listing_status",
                        "mapping_status",
                        "mapping_source",
                        "mapping_confidence",
                        "needs_review",
                        "review_reason",
                        "updated_at",
                    ],
                )
                writer.writeheader()
                for row in rows:
                    writer.writerow(dict(row))

            return len(rows)

    def get_mapping_summary(self, *, recent_limit: int = 20) -> dict[str, Any]:
        with get_connection(self.db_path) as connection:
            total_mapped = connection.execute(
                "SELECT COUNT(*) AS count FROM company_source_mappings WHERE mapping_status = 'MAPPED'"
            ).fetchone()["count"]
            unresolved = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM company_source_mappings
                WHERE mapping_status != 'MAPPED' OR needs_review = 1
                """
            ).fetchone()["count"]
            conflicting = connection.execute(
                "SELECT COUNT(*) AS count FROM company_source_mappings WHERE mapping_status = 'CONFLICT'"
            ).fetchone()["count"]

            duplicate_groups = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT source_system, source_stock_code, COUNT(*) AS duplicate_count
                    FROM company_source_mappings
                    WHERE source_stock_code IS NOT NULL AND source_stock_code != ''
                    GROUP BY source_system, source_stock_code
                    HAVING COUNT(*) > 1
                    ORDER BY duplicate_count DESC, source_system
                    """
                ).fetchall()
            ]

            recently_changed = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT
                        source_system,
                        source_record_id,
                        source_name,
                        source_stock_code,
                        company_id,
                        mapping_status,
                        mapping_source,
                        mapping_confidence,
                        needs_review,
                        review_reason,
                        COALESCE(mapped_at, updated_at) AS changed_at
                    FROM company_source_mappings
                    ORDER BY changed_at DESC, id DESC
                    LIMIT ?
                    """,
                    (recent_limit,),
                ).fetchall()
            ]

            return {
                "total_mapped": total_mapped,
                "unresolved": unresolved,
                "conflicting_rows": conflicting,
                "duplicate_groups": duplicate_groups,
                "recently_changed_mappings": recently_changed,
            }

    def get_unresolved_mappings(self, *, limit: int = 200) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as connection:
            return [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT
                        source_system,
                        source_record_id,
                        source_name,
                        source_stock_code,
                        source_market,
                        listing_status,
                        mapping_status,
                        mapping_source,
                        mapping_confidence,
                        needs_review,
                        review_reason,
                        updated_at
                    FROM company_source_mappings
                    WHERE mapping_status != 'MAPPED' OR needs_review = 1
                    ORDER BY updated_at DESC, id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            ]

    def list_manual_overrides(self, *, limit: int = 200) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as connection:
            return [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT
                        id,
                        source_system,
                        source_record_id,
                        target_company_id,
                        force_canonical_key,
                        force_canonical_name,
                        action,
                        note,
                        created_by,
                        created_at,
                        updated_at
                    FROM company_manual_overrides
                    ORDER BY updated_at DESC, id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            ]

    def upsert_manual_override(
        self,
        *,
        source_system: str,
        source_record_id: str,
        action: str,
        target_company_id: int | None = None,
        force_canonical_key: str | None = None,
        force_canonical_name: str | None = None,
        note: str | None = None,
        created_by: str = "operator",
    ) -> dict[str, Any]:
        normalized_source_system = source_system.upper().strip()
        normalized_action = action.upper().strip()
        if normalized_source_system not in {"DART", "KIS"}:
            raise ValueError("source_system must be DART or KIS")
        if normalized_action not in {"MAP", "SKIP", "REVIEW"}:
            raise ValueError("action must be MAP, SKIP, REVIEW")

        now = utcnow_iso()
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO company_manual_overrides (
                    source_system,
                    source_record_id,
                    target_company_id,
                    force_canonical_key,
                    force_canonical_name,
                    action,
                    note,
                    created_by,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_system, source_record_id)
                DO UPDATE SET
                    target_company_id = excluded.target_company_id,
                    force_canonical_key = excluded.force_canonical_key,
                    force_canonical_name = excluded.force_canonical_name,
                    action = excluded.action,
                    note = excluded.note,
                    created_by = excluded.created_by,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized_source_system,
                    source_record_id,
                    target_company_id,
                    force_canonical_key,
                    force_canonical_name,
                    normalized_action,
                    note,
                    created_by,
                    now,
                    now,
                ),
            )
            row = connection.execute(
                """
                SELECT
                    id,
                    source_system,
                    source_record_id,
                    target_company_id,
                    force_canonical_key,
                    force_canonical_name,
                    action,
                    note,
                    created_by,
                    created_at,
                    updated_at
                FROM company_manual_overrides
                WHERE source_system = ? AND source_record_id = ?
                """,
                (normalized_source_system, source_record_id),
            ).fetchone()
            return dict(row)

    def delete_manual_override(self, *, source_system: str, source_record_id: str) -> bool:
        normalized_source_system = source_system.upper().strip()
        if normalized_source_system not in {"DART", "KIS"}:
            raise ValueError("source_system must be DART or KIS")

        with get_connection(self.db_path) as connection:
            result = connection.execute(
                """
                DELETE FROM company_manual_overrides
                WHERE source_system = ? AND source_record_id = ?
                """,
                (normalized_source_system, source_record_id),
            )
            return result.rowcount > 0

    def _count_rows(self, connection, status: str) -> int:
        return connection.execute(
            "SELECT COUNT(*) AS count FROM company_source_mappings WHERE mapping_status = ?",
            (status,),
        ).fetchone()["count"]

    def _count_unresolved_rows(self, connection) -> int:
        return connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM company_source_mappings
            WHERE mapping_status != 'MAPPED' OR needs_review = 1
            """
        ).fetchone()["count"]

    def _available_candidates(
        self,
        candidates: list[dict[str, Any]],
        handled_mapping_ids: set[int],
        used_kis_ids: set[int],
    ) -> list[dict[str, Any]]:
        return [
            row
            for row in candidates
            if row["id"] not in handled_mapping_ids and row["id"] not in used_kis_ids
        ]

    def _mark_ambiguous(
        self,
        *,
        connection,
        rows: list[dict[str, Any]],
        reason: str,
        mapping_source: str,
        handled_mapping_ids: set[int],
    ) -> None:
        for row in rows:
            if row["id"] in handled_mapping_ids:
                continue
            self._set_mapping_state(
                connection,
                mapping_id=row["id"],
                company_id=None,
                mapping_status="CONFLICT",
                mapping_source=mapping_source,
                mapping_confidence=0.0,
                needs_review=1,
                review_reason=reason,
            )
            handled_mapping_ids.add(row["id"])

    def _set_pair_mapping(
        self,
        *,
        connection,
        dart_row: dict[str, Any],
        kis_row: dict[str, Any],
        company_id: int,
        mapping_source: str,
        mapping_confidence: float,
    ) -> None:
        self._set_mapping_state(
            connection,
            mapping_id=dart_row["id"],
            company_id=company_id,
            mapping_status="MAPPED",
            mapping_source=mapping_source,
            mapping_confidence=mapping_confidence,
            needs_review=0,
            review_reason=None,
        )
        self._set_mapping_state(
            connection,
            mapping_id=kis_row["id"],
            company_id=company_id,
            mapping_status="MAPPED",
            mapping_source=mapping_source,
            mapping_confidence=mapping_confidence,
            needs_review=0,
            review_reason=None,
        )

    def _resolve_manual_override_company(
        self,
        *,
        connection,
        source_row: dict[str, Any],
        override: dict[str, Any],
    ) -> tuple[int, bool]:
        if override["target_company_id"] is not None:
            target = connection.execute(
                "SELECT id FROM companies WHERE id = ?",
                (override["target_company_id"],),
            ).fetchone()
            if target is None:
                raise ValueError(
                    f"manual override target_company_id does not exist: {override['target_company_id']}"
                )
            return target["id"], False

        canonical_key = override["force_canonical_key"] or self._derive_company_key(source_row)
        canonical_name = override["force_canonical_name"] or source_row["source_name"]
        return self._upsert_company(
            connection=connection,
            canonical_key=canonical_key,
            canonical_name=canonical_name,
            canonical_name_en=source_row.get("source_name_en"),
            primary_stock_code=normalize_stock_code(source_row.get("source_stock_code")),
            market=source_row.get("source_market"),
            listing_status=source_row.get("listing_status"),
            instrument_type="EQUITY",
            market_classification=source_row.get("market_classification"),
            mapping_source="MANUAL_OVERRIDE",
            mapping_confidence=1.0,
            needs_review=False,
            review_reason=None,
        )

    def _ensure_company_for_pair(
        self,
        *,
        connection,
        dart_row: dict[str, Any],
        kis_row: dict[str, Any],
        mapping_source: str,
        mapping_confidence: float,
    ) -> tuple[int, bool]:
        stock_code = normalize_stock_code(dart_row.get("source_stock_code")) or normalize_stock_code(
            kis_row.get("source_stock_code")
        )

        existing_by_stock = None
        if stock_code:
            existing_by_stock = connection.execute(
                "SELECT id FROM companies WHERE primary_stock_code = ?",
                (stock_code,),
            ).fetchone()

        canonical_key = self._derive_company_key(dart_row)
        if existing_by_stock is not None:
            existing_company_id = existing_by_stock["id"]
            self._update_existing_company(
                connection=connection,
                company_id=existing_company_id,
                canonical_name=dart_row.get("source_name") or kis_row.get("source_name"),
                canonical_name_en=dart_row.get("source_name_en"),
                primary_stock_code=stock_code,
                market=kis_row.get("source_market") or dart_row.get("source_market"),
                listing_status=kis_row.get("listing_status") or dart_row.get("listing_status"),
                instrument_type="EQUITY",
                market_classification=kis_row.get("market_classification"),
                mapping_source=mapping_source,
                mapping_confidence=mapping_confidence,
                needs_review=False,
                review_reason=None,
            )
            return existing_company_id, False

        return self._upsert_company(
            connection=connection,
            canonical_key=canonical_key,
            canonical_name=dart_row.get("source_name") or kis_row.get("source_name"),
            canonical_name_en=dart_row.get("source_name_en"),
            primary_stock_code=stock_code,
            market=kis_row.get("source_market") or dart_row.get("source_market"),
            listing_status=kis_row.get("listing_status") or dart_row.get("listing_status"),
            instrument_type="EQUITY",
            market_classification=kis_row.get("market_classification"),
            mapping_source=mapping_source,
            mapping_confidence=mapping_confidence,
            needs_review=False,
            review_reason=None,
        )

    def _ensure_company_for_single_source(
        self,
        *,
        connection,
        row: dict[str, Any],
        fallback_mapping_source: str,
        fallback_confidence: float,
    ) -> SingleSourceDecision:
        stock_code = normalize_stock_code(row.get("source_stock_code"))

        if stock_code:
            by_stock = connection.execute(
                "SELECT id FROM companies WHERE primary_stock_code = ?",
                (stock_code,),
            ).fetchone()
            if by_stock is not None:
                self._update_existing_company(
                    connection=connection,
                    company_id=by_stock["id"],
                    canonical_name=row.get("source_name"),
                    canonical_name_en=row.get("source_name_en"),
                    primary_stock_code=stock_code,
                    market=row.get("source_market"),
                    listing_status=row.get("listing_status"),
                    instrument_type="EQUITY",
                    market_classification=row.get("market_classification"),
                    mapping_source="ATTACH_STOCK_CODE",
                    mapping_confidence=0.85,
                    needs_review=False,
                    review_reason=None,
                )
                return SingleSourceDecision(
                    company_id=by_stock["id"],
                    created=False,
                    mapping_status="MAPPED",
                    mapping_source="ATTACH_STOCK_CODE",
                    mapping_confidence=0.85,
                    needs_review=0,
                    review_reason=None,
                )

        company_id, created = self._upsert_company(
            connection=connection,
            canonical_key=self._derive_company_key(row),
            canonical_name=row.get("source_name"),
            canonical_name_en=row.get("source_name_en"),
            primary_stock_code=stock_code,
            market=row.get("source_market"),
            listing_status=row.get("listing_status"),
            instrument_type="EQUITY",
            market_classification=row.get("market_classification"),
            mapping_source=fallback_mapping_source,
            mapping_confidence=fallback_confidence,
            needs_review=False,
            review_reason=None,
        )
        return SingleSourceDecision(
            company_id=company_id,
            created=created,
            mapping_status="MAPPED",
            mapping_source=fallback_mapping_source,
            mapping_confidence=fallback_confidence,
            needs_review=0,
            review_reason=None,
        )

    def _derive_company_key(self, row: dict[str, Any]) -> str:
        source_system = row.get("source_system")
        source_record_id = row.get("source_record_id")
        stock_code = normalize_stock_code(row.get("source_stock_code"))
        normalized_name = normalize_company_name(row.get("source_name"))

        if source_system == "DART" and source_record_id:
            return f"dart:{source_record_id}"
        if source_system == "KIS" and stock_code:
            return f"stock:{stock_code}"
        if source_system == "KIS" and source_record_id:
            return f"kis:{source_record_id}"
        if stock_code:
            return f"stock:{stock_code}"
        if normalized_name:
            return f"name:{normalized_name}"
        return f"fallback:{source_system}:{source_record_id}"

    def _upsert_company(
        self,
        *,
        connection,
        canonical_key: str,
        canonical_name: str,
        canonical_name_en: str | None,
        primary_stock_code: str | None,
        market: str | None,
        listing_status: str | None,
        instrument_type: str,
        market_classification: str | None,
        mapping_source: str,
        mapping_confidence: float,
        needs_review: bool,
        review_reason: str | None,
    ) -> tuple[int, bool]:
        existing = connection.execute(
            "SELECT id FROM companies WHERE canonical_key = ?",
            (canonical_key,),
        ).fetchone()

        if existing is None and primary_stock_code:
            existing = connection.execute(
                "SELECT id FROM companies WHERE primary_stock_code = ?",
                (primary_stock_code,),
            ).fetchone()

        if existing is not None:
            company_id = existing["id"]
            self._update_existing_company(
                connection=connection,
                company_id=company_id,
                canonical_name=canonical_name,
                canonical_name_en=canonical_name_en,
                primary_stock_code=primary_stock_code,
                market=market,
                listing_status=listing_status,
                instrument_type=instrument_type,
                market_classification=market_classification,
                mapping_source=mapping_source,
                mapping_confidence=mapping_confidence,
                needs_review=needs_review,
                review_reason=review_reason,
            )
            return company_id, False

        now = utcnow_iso()
        connection.execute(
            """
            INSERT INTO companies (
                canonical_key,
                canonical_name,
                canonical_name_en,
                normalized_name,
                primary_stock_code,
                market,
                listing_status,
                instrument_type,
                market_classification,
                is_listed,
                needs_review,
                review_reason,
                last_mapping_source,
                last_mapping_confidence,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                canonical_key,
                canonical_name,
                canonical_name_en,
                normalize_company_name(canonical_name),
                primary_stock_code,
                market,
                listing_status,
                instrument_type,
                market_classification,
                int(self._is_listed(listing_status)),
                int(needs_review),
                review_reason,
                mapping_source,
                mapping_confidence,
                now,
                now,
            ),
        )
        return int(connection.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]), True

    def _update_existing_company(
        self,
        *,
        connection,
        company_id: int,
        canonical_name: str | None,
        canonical_name_en: str | None,
        primary_stock_code: str | None,
        market: str | None,
        listing_status: str | None,
        instrument_type: str,
        market_classification: str | None,
        mapping_source: str,
        mapping_confidence: float,
        needs_review: bool,
        review_reason: str | None,
    ) -> None:
        existing = dict(
            connection.execute(
                "SELECT * FROM companies WHERE id = ?",
                (company_id,),
            ).fetchone()
        )

        next_name = canonical_name or existing["canonical_name"]
        next_name_en = canonical_name_en or existing["canonical_name_en"]
        next_stock_code = primary_stock_code or existing["primary_stock_code"]
        next_market = market or existing["market"]
        next_listing_status = listing_status or existing["listing_status"]
        next_market_classification = market_classification or existing["market_classification"]

        connection.execute(
            """
            UPDATE companies
            SET
                canonical_name = ?,
                canonical_name_en = ?,
                normalized_name = ?,
                primary_stock_code = ?,
                market = ?,
                listing_status = ?,
                instrument_type = ?,
                market_classification = ?,
                is_listed = ?,
                needs_review = ?,
                review_reason = ?,
                last_mapping_source = ?,
                last_mapping_confidence = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                next_name,
                next_name_en,
                normalize_company_name(next_name),
                next_stock_code,
                next_market,
                next_listing_status,
                instrument_type,
                next_market_classification,
                int(self._is_listed(next_listing_status)),
                int(needs_review),
                review_reason,
                mapping_source,
                mapping_confidence,
                utcnow_iso(),
                company_id,
            ),
        )

    def _is_listed(self, listing_status: str | None) -> bool:
        if listing_status is None:
            return True

        normalized = listing_status.strip().upper()
        delisted_tokens = {"DELISTED", "UNLISTED", "SUSPENDED", "TERMINATED", "폐지"}
        return normalized not in delisted_tokens

    def _reset_mapping_state(self, connection) -> None:
        connection.execute(
            """
            UPDATE company_source_mappings
            SET
                company_id = NULL,
                mapping_status = 'UNMAPPED',
                mapping_source = NULL,
                mapping_confidence = NULL,
                needs_review = 0,
                review_reason = NULL,
                mapped_at = NULL,
                updated_at = ?
            """,
            (utcnow_iso(),),
        )

    def _set_mapping_state(
        self,
        connection,
        *,
        mapping_id: int,
        company_id: int | None,
        mapping_status: str,
        mapping_source: str,
        mapping_confidence: float,
        needs_review: int,
        review_reason: str | None,
    ) -> None:
        mapped_at = utcnow_iso() if mapping_status == "MAPPED" else None
        connection.execute(
            """
            UPDATE company_source_mappings
            SET
                company_id = ?,
                mapping_status = ?,
                mapping_source = ?,
                mapping_confidence = ?,
                needs_review = ?,
                review_reason = ?,
                mapped_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                company_id,
                mapping_status,
                mapping_source,
                mapping_confidence,
                int(needs_review),
                review_reason,
                mapped_at,
                utcnow_iso(),
                mapping_id,
            ),
        )

    def _upsert_source_mapping(
        self,
        connection,
        *,
        source_system: str,
        source_record_id: str,
        source_name: str,
        source_name_en: str | None,
        source_stock_code: str | None,
        source_market: str | None,
        listing_status: str | None,
        market_classification: str | None,
        modify_date: str | None,
        source_url: str | None,
        source_metadata: dict[str, Any],
        source_snippet: str,
        run_id: int,
    ) -> tuple[bool, bool]:
        now = utcnow_iso()
        normalized_stock_code = normalize_stock_code(source_stock_code)
        metadata_json = json.dumps(source_metadata, ensure_ascii=False, sort_keys=True)

        existing = connection.execute(
            """
            SELECT *
            FROM company_source_mappings
            WHERE source_system = ? AND source_record_id = ?
            """,
            (source_system, source_record_id),
        ).fetchone()

        if existing is None:
            connection.execute(
                """
                INSERT INTO company_source_mappings (
                    source_system,
                    source_record_id,
                    source_name,
                    source_name_en,
                    source_stock_code,
                    source_market,
                    listing_status,
                    market_classification,
                    modify_date,
                    source_url,
                    source_metadata_json,
                    source_snippet,
                    last_seen_run_id,
                    mapping_status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'UNMAPPED', ?, ?)
                """,
                (
                    source_system,
                    source_record_id,
                    source_name,
                    source_name_en,
                    normalized_stock_code,
                    source_market,
                    listing_status,
                    market_classification,
                    modify_date,
                    source_url,
                    metadata_json,
                    source_snippet,
                    run_id,
                    now,
                    now,
                ),
            )
            return True, False

        existing_data = dict(existing)
        changed_columns = [
            ("source_name", source_name),
            ("source_name_en", source_name_en),
            ("source_stock_code", normalized_stock_code),
            ("source_market", source_market),
            ("listing_status", listing_status),
            ("market_classification", market_classification),
            ("modify_date", modify_date),
            ("source_url", source_url),
            ("source_metadata_json", metadata_json),
            ("source_snippet", source_snippet),
        ]
        has_changes = any(existing_data[column] != value for column, value in changed_columns)

        if has_changes:
            connection.execute(
                """
                UPDATE company_source_mappings
                SET
                    source_name = ?,
                    source_name_en = ?,
                    source_stock_code = ?,
                    source_market = ?,
                    listing_status = ?,
                    market_classification = ?,
                    modify_date = ?,
                    source_url = ?,
                    source_metadata_json = ?,
                    source_snippet = ?,
                    last_seen_run_id = ?,
                    company_id = NULL,
                    mapping_status = 'UNMAPPED',
                    mapping_source = NULL,
                    mapping_confidence = NULL,
                    needs_review = 0,
                    review_reason = NULL,
                    mapped_at = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    source_name,
                    source_name_en,
                    normalized_stock_code,
                    source_market,
                    listing_status,
                    market_classification,
                    modify_date,
                    source_url,
                    metadata_json,
                    source_snippet,
                    run_id,
                    now,
                    existing_data["id"],
                ),
            )
            return False, True

        connection.execute(
            """
            UPDATE company_source_mappings
            SET
                last_seen_run_id = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (run_id, now, existing_data["id"]),
        )
        return False, False

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
            )
            VALUES (?, ?, 'RUNNING', ?, ?)
            """,
            (
                job_name,
                source_system,
                started_at,
                json.dumps({"job_name": job_name, "source_system": source_system}, ensure_ascii=False),
            ),
        )
        row = connection.execute("SELECT last_insert_rowid() AS id").fetchone()
        return int(row["id"])

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
                error_message,
                run_id,
            ),
        )
