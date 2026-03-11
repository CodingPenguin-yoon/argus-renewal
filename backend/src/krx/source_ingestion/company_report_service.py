from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
import logging
from statistics import mean, pstdev
import time
from typing import Any
from uuid import uuid4

from ..company_master.db import get_connection, utcnow_iso
from ..company_master.normalize import normalize_stock_code
from .report_llm import (
    CompanyReportLLMRequest,
    CompanyReportNarrativeProvider,
    DisabledCompanyReportNarrativeProvider,
)

logger = logging.getLogger(__name__)

_ALLOWED_REPORT_RUN_MODES = {"SCHEDULED", "MANUAL", "BACKFILL", "RERUN_FAILED", "RERUN_SINGLE"}
_ALLOWED_RUN_STATUS = {"RUNNING", "SUCCESS", "PARTIAL_SUCCESS", "FAILED", "SKIPPED"}

_SECTION_KEYS: tuple[tuple[str, str], ...] = (
    ("one_line_status", "한줄 상태"),
    ("recent_key_events", "최근 핵심 이벤트"),
    ("flow_summary", "수급/플로우 요약"),
    ("technical_context_summary", "기술적/맥락 요약"),
    ("bull_points", "Bull 포인트"),
    ("bear_points", "Bear 포인트"),
    ("watch_items", "다음 세션/주간 체크포인트"),
)


@dataclass(frozen=True)
class CompanyReportRunOutcome:
    run_id: int
    batch_run_key: str
    universe_key: str
    company_id: int
    trade_date: str
    status: str
    report_id: int | None
    generation_method: str
    llm_provider: str | None
    llm_model: str | None
    error_message: str | None = None


@dataclass(frozen=True)
class CompanyReportBatchOutcome:
    batch_run_key: str
    universe_key: str
    trade_date: str
    run_mode: str
    total_count: int
    success_count: int
    partial_success_count: int
    failed_count: int
    skipped_count: int
    items: list[dict[str, Any]]
    error_message: str | None = None


class CompanyReportService:
    def __init__(
        self,
        *,
        db_path: str,
        llm_provider: CompanyReportNarrativeProvider | None = None,
        pipeline_enabled: bool = True,
        market_scope: str = "KRX",
        default_universe_key: str = "KRX_LARGE_CAP_CORE",
        default_universe_name: str = "KRX Large Cap Core",
        default_universe_target_size: int = 25,
        seed_stock_codes: list[str] | None = None,
        event_lookback_days: int = 7,
        disclosure_lookback_days: int = 14,
        price_lookback_days: int = 7,
    ) -> None:
        self.db_path = db_path
        self.pipeline_enabled = pipeline_enabled
        self.market_scope = (market_scope or "KRX").strip().upper() or "KRX"
        self.default_universe_key = (default_universe_key or "KRX_LARGE_CAP_CORE").strip() or "KRX_LARGE_CAP_CORE"
        self.default_universe_name = (
            (default_universe_name or "KRX Large Cap Core").strip() or "KRX Large Cap Core"
        )
        self.default_universe_target_size = max(1, default_universe_target_size)
        self.seed_stock_codes = [
            code
            for code in [normalize_stock_code(value) for value in (seed_stock_codes or [])]
            if code is not None
        ]
        self.event_lookback_days = max(1, event_lookback_days)
        self.disclosure_lookback_days = max(1, disclosure_lookback_days)
        self.price_lookback_days = max(1, price_lookback_days)
        self.llm_provider = llm_provider or DisabledCompanyReportNarrativeProvider()

    def ensure_universe(
        self,
        *,
        universe_key: str | None = None,
        universe_name: str | None = None,
        description: str | None = None,
        target_size: int | None = None,
        selection_mode: str = "MANUAL",
        selection_config: dict[str, Any] | None = None,
        created_by: str = "system",
    ) -> dict[str, Any]:
        normalized_key = (universe_key or self.default_universe_key).strip()
        normalized_name = (universe_name or self.default_universe_name).strip()
        normalized_target_size = target_size or self.default_universe_target_size

        with get_connection(self.db_path) as connection:
            universe_id = self._upsert_universe(
                connection,
                universe_key=normalized_key,
                universe_name=normalized_name,
                description=description,
                selection_mode=selection_mode,
                selection_config=selection_config,
                target_size=normalized_target_size,
                created_by=created_by,
            )
            return self._load_universe(connection, universe_id=universe_id)

    def sync_universe_members(
        self,
        *,
        universe_key: str | None = None,
        stock_codes: list[str] | None = None,
        company_ids: list[int] | None = None,
        replace: bool = True,
        member_source: str = "MANUAL",
        note: str | None = None,
        created_by: str = "system",
    ) -> dict[str, Any]:
        normalized_key = (universe_key or self.default_universe_key).strip()
        requested_company_ids = sorted({int(value) for value in (company_ids or []) if int(value) > 0})

        normalized_stock_codes = [
            code
            for code in [normalize_stock_code(value) for value in (stock_codes or [])]
            if code is not None
        ]
        normalized_stock_codes = sorted(set(normalized_stock_codes))

        with get_connection(self.db_path) as connection:
            universe = self._load_universe_by_key(connection, universe_key=normalized_key)
            if universe is None:
                universe_id = self._upsert_universe(
                    connection,
                    universe_key=normalized_key,
                    universe_name=self.default_universe_name,
                    description="KRX large-cap company report coverage",
                    selection_mode="MIXED",
                    selection_config={"member_source": member_source},
                    target_size=self.default_universe_target_size,
                    created_by=created_by,
                )
                universe = self._load_universe(connection, universe_id=universe_id)

            resolved_company_ids, missing_codes = self._resolve_company_ids_by_stock_codes(
                connection,
                stock_codes=normalized_stock_codes,
            )
            target_company_ids = sorted(set(requested_company_ids + resolved_company_ids))

            now = utcnow_iso()
            if replace:
                connection.execute(
                    """
                    UPDATE report_universe_members
                    SET
                        member_status = 'INACTIVE',
                        removed_at = ?,
                        updated_at = ?
                    WHERE universe_id = ? AND member_status = 'ACTIVE'
                    """,
                    (now, now, universe["id"]),
                )

            for company_id in target_company_ids:
                connection.execute(
                    """
                    INSERT INTO report_universe_members (
                        universe_id,
                        company_id,
                        member_status,
                        member_source,
                        note,
                        added_at,
                        removed_at,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, 'ACTIVE', ?, ?, ?, NULL, ?, ?)
                    ON CONFLICT(universe_id, company_id)
                    DO UPDATE SET
                        member_status = 'ACTIVE',
                        member_source = excluded.member_source,
                        note = excluded.note,
                        added_at = excluded.added_at,
                        removed_at = NULL,
                        updated_at = excluded.updated_at
                    """,
                    (
                        universe["id"],
                        company_id,
                        member_source,
                        note,
                        now,
                        now,
                        now,
                    ),
                )

            active_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM report_universe_members
                WHERE universe_id = ? AND member_status = 'ACTIVE'
                """,
                (universe["id"],),
            ).fetchone()["count"]

        return {
            "universe_key": normalized_key,
            "replace": replace,
            "requested_company_count": len(requested_company_ids),
            "requested_stock_code_count": len(normalized_stock_codes),
            "resolved_company_count": len(target_company_ids),
            "missing_stock_codes": missing_codes,
            "active_member_count": int(active_count),
        }

    def list_universes(self, *, limit: int = 20, include_inactive: bool = False) -> list[dict[str, Any]]:
        filters: list[str] = []
        params: list[Any] = []
        if not include_inactive:
            filters.append("u.is_active = 1")

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    u.*,
                    COALESCE(member_counts.active_count, 0) AS active_member_count,
                    COALESCE(member_counts.total_count, 0) AS total_member_count
                FROM report_universes u
                LEFT JOIN (
                    SELECT
                        universe_id,
                        SUM(CASE WHEN member_status = 'ACTIVE' THEN 1 ELSE 0 END) AS active_count,
                        COUNT(*) AS total_count
                    FROM report_universe_members
                    GROUP BY universe_id
                ) member_counts ON member_counts.universe_id = u.id
                {where_clause}
                ORDER BY u.updated_at DESC, u.id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        return [self._deserialize_universe_row(dict(row)) for row in rows]

    def list_universe_members(
        self,
        *,
        universe_key: str | None = None,
        include_inactive: bool = False,
        limit: int = 300,
    ) -> list[dict[str, Any]]:
        normalized_key = (universe_key or self.default_universe_key).strip()

        with get_connection(self.db_path) as connection:
            universe = self._load_universe_by_key(connection, universe_key=normalized_key)
            if universe is None:
                return []

            filters = ["m.universe_id = ?"]
            params: list[Any] = [universe["id"]]
            if not include_inactive:
                filters.append("m.member_status = 'ACTIVE'")

            params.append(limit)
            where_clause = f"WHERE {' AND '.join(filters)}"
            rows = connection.execute(
                f"""
                SELECT
                    m.id AS member_id,
                    m.member_status,
                    m.member_source,
                    m.weight,
                    m.note,
                    m.added_at,
                    m.removed_at,
                    c.id AS company_id,
                    c.canonical_name,
                    c.primary_stock_code,
                    c.market,
                    c.market_classification,
                    c.listing_status,
                    c.is_listed
                FROM report_universe_members m
                JOIN companies c ON c.id = m.company_id
                {where_clause}
                ORDER BY c.canonical_name ASC, c.id ASC
                LIMIT ?
                """,
                params,
            ).fetchall()

        return [dict(row) for row in rows]

    def generate_nightly_reports(
        self,
        *,
        trade_date: date,
        universe_key: str | None = None,
        mode: str = "SCHEDULED",
        company_ids: list[int] | None = None,
        max_companies: int | None = None,
        rerun_map: dict[int, int] | None = None,
    ) -> CompanyReportBatchOutcome:
        normalized_mode = self._normalize_run_mode(mode)
        trade_date_iso = trade_date.isoformat()
        target_universe_key = (universe_key or self.default_universe_key).strip()

        if not self.pipeline_enabled:
            return CompanyReportBatchOutcome(
                batch_run_key=self._build_batch_run_key(
                    trade_date_iso=trade_date_iso,
                    universe_key=target_universe_key,
                    run_mode=normalized_mode,
                ),
                universe_key=target_universe_key,
                trade_date=trade_date_iso,
                run_mode=normalized_mode,
                total_count=0,
                success_count=0,
                partial_success_count=0,
                failed_count=0,
                skipped_count=0,
                items=[],
                error_message="company_report_pipeline_disabled",
            )

        universe = self._ensure_universe_for_generation(universe_key=target_universe_key)
        members = self.list_universe_members(universe_key=target_universe_key, include_inactive=False, limit=1000)

        target_company_ids: list[int]
        if company_ids:
            allow_set = {int(value) for value in company_ids if int(value) > 0}
            target_company_ids = [int(member["company_id"]) for member in members if int(member["company_id"]) in allow_set]
        else:
            target_company_ids = [int(member["company_id"]) for member in members]

        if max_companies is not None and max_companies > 0:
            target_company_ids = target_company_ids[: max_companies]

        batch_run_key = self._build_batch_run_key(
            trade_date_iso=trade_date_iso,
            universe_key=target_universe_key,
            run_mode=normalized_mode,
        )

        results: list[CompanyReportRunOutcome] = []
        for company_id in target_company_ids:
            rerun_of_run_id = None
            if rerun_map is not None:
                rerun_of_run_id = rerun_map.get(company_id)
            result = self.generate_single_company_report(
                company_id=company_id,
                trade_date=trade_date,
                universe_key=target_universe_key,
                mode=normalized_mode,
                batch_run_key=batch_run_key,
                rerun_of_run_id=rerun_of_run_id,
            )
            results.append(result)

        success_count = sum(1 for item in results if item.status == "SUCCESS")
        partial_success_count = sum(1 for item in results if item.status == "PARTIAL_SUCCESS")
        failed_count = sum(1 for item in results if item.status == "FAILED")
        skipped_count = sum(1 for item in results if item.status == "SKIPPED")

        return CompanyReportBatchOutcome(
            batch_run_key=batch_run_key,
            universe_key=universe["universe_key"],
            trade_date=trade_date_iso,
            run_mode=normalized_mode,
            total_count=len(target_company_ids),
            success_count=success_count,
            partial_success_count=partial_success_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            items=[self._run_outcome_to_payload(item) for item in results],
        )

    def generate_single_company_report(
        self,
        *,
        company_id: int,
        trade_date: date,
        universe_key: str | None = None,
        mode: str = "RERUN_SINGLE",
        batch_run_key: str | None = None,
        rerun_of_run_id: int | None = None,
    ) -> CompanyReportRunOutcome:
        normalized_mode = self._normalize_run_mode(mode)
        trade_date_iso = trade_date.isoformat()
        target_universe_key = (universe_key or self.default_universe_key).strip()

        universe = self._ensure_universe_for_generation(universe_key=target_universe_key)

        # Ensure single-company rerun can proceed even if membership is temporarily missing.
        self.sync_universe_members(
            universe_key=target_universe_key,
            company_ids=[company_id],
            replace=False,
            member_source="MANUAL",
            note="auto-attached-by-rerun",
        )

        effective_batch_key = batch_run_key or self._build_batch_run_key(
            trade_date_iso=trade_date_iso,
            universe_key=target_universe_key,
            run_mode=normalized_mode,
        )

        with get_connection(self.db_path) as connection:
            run_id = self._start_company_report_run(
                connection,
                batch_run_key=effective_batch_key,
                universe_id=int(universe["id"]),
                company_id=company_id,
                trade_date_iso=trade_date_iso,
                run_mode=normalized_mode,
                rerun_of_run_id=rerun_of_run_id,
            )

            started_monotonic = time.monotonic()
            report_id: int | None = None
            status = "FAILED"
            generation_method = "RULE_BASED"
            llm_provider_name: str | None = None
            llm_model_name: str | None = None
            source_coverage: dict[str, Any] | None = None

            try:
                company_row = self._load_company_row(connection, company_id=company_id)
                if company_row is None:
                    raise ValueError(f"company not found: {company_id}")

                input_payload, source_coverage, feature_snapshot = self._assemble_report_input(
                    connection,
                    company_row=company_row,
                    trade_date_iso=trade_date_iso,
                )

                (
                    status,
                    generation_method,
                    llm_provider_name,
                    llm_model_name,
                    report_payload,
                    markdown_body,
                    sections,
                ) = self._generate_report_output(
                    company_row=company_row,
                    trade_date_iso=trade_date_iso,
                    input_payload=input_payload,
                    source_coverage=source_coverage,
                )

                report_id = self._upsert_company_report(
                    connection,
                    universe_id=int(universe["id"]),
                    company_id=company_id,
                    trade_date_iso=trade_date_iso,
                    run_mode=normalized_mode,
                    status=status,
                    generation_method=generation_method,
                    llm_provider=llm_provider_name,
                    llm_model=llm_model_name,
                    input_payload=input_payload,
                    report_payload=report_payload,
                    markdown_body=markdown_body,
                    source_coverage=source_coverage,
                    feature_snapshot=feature_snapshot,
                )
                self._upsert_report_sections(connection, report_id=report_id, sections=sections)

                elapsed_ms = int((time.monotonic() - started_monotonic) * 1000)
                self._finish_company_report_run(
                    connection,
                    run_id=run_id,
                    status=status,
                    report_id=report_id,
                    elapsed_ms=elapsed_ms,
                    source_coverage=source_coverage,
                    error_message=None,
                    metadata={
                        "generation_method": generation_method,
                        "llm_provider": llm_provider_name,
                        "llm_model": llm_model_name,
                    },
                )

                logger.info(
                    "company_report_generated",
                    extra={
                        "run_id": run_id,
                        "batch_run_key": effective_batch_key,
                        "universe_key": universe["universe_key"],
                        "company_id": company_id,
                        "trade_date": trade_date_iso,
                        "status": status,
                        "generation_method": generation_method,
                    },
                )
            except Exception as error:  # noqa: BLE001
                elapsed_ms = int((time.monotonic() - started_monotonic) * 1000)
                message = str(error)
                self._finish_company_report_run(
                    connection,
                    run_id=run_id,
                    status="FAILED",
                    report_id=None,
                    elapsed_ms=elapsed_ms,
                    source_coverage=source_coverage,
                    error_message=message,
                    metadata={"generation_method": generation_method},
                )
                logger.exception(
                    "company_report_generation_failed",
                    extra={
                        "run_id": run_id,
                        "batch_run_key": effective_batch_key,
                        "universe_key": universe["universe_key"],
                        "company_id": company_id,
                        "trade_date": trade_date_iso,
                        "error": message,
                    },
                )
                return CompanyReportRunOutcome(
                    run_id=run_id,
                    batch_run_key=effective_batch_key,
                    universe_key=universe["universe_key"],
                    company_id=company_id,
                    trade_date=trade_date_iso,
                    status="FAILED",
                    report_id=None,
                    generation_method=generation_method,
                    llm_provider=llm_provider_name,
                    llm_model=llm_model_name,
                    error_message=message,
                )

        return CompanyReportRunOutcome(
            run_id=run_id,
            batch_run_key=effective_batch_key,
            universe_key=universe["universe_key"],
            company_id=company_id,
            trade_date=trade_date_iso,
            status=status,
            report_id=report_id,
            generation_method=generation_method,
            llm_provider=llm_provider_name,
            llm_model=llm_model_name,
        )

    def rerun_failed_subset(
        self,
        *,
        trade_date: date,
        universe_key: str | None = None,
        reference_batch_run_key: str | None = None,
    ) -> CompanyReportBatchOutcome:
        trade_date_iso = trade_date.isoformat()
        target_universe_key = (universe_key or self.default_universe_key).strip()
        universe = self._ensure_universe_for_generation(universe_key=target_universe_key)

        with get_connection(self.db_path) as connection:
            batch_run_key = reference_batch_run_key
            if not batch_run_key:
                row = connection.execute(
                    """
                    SELECT batch_run_key
                    FROM company_report_runs
                    WHERE universe_id = ? AND trade_date = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (universe["id"], trade_date_iso),
                ).fetchone()
                if row is None:
                    return CompanyReportBatchOutcome(
                        batch_run_key="",
                        universe_key=target_universe_key,
                        trade_date=trade_date_iso,
                        run_mode="RERUN_FAILED",
                        total_count=0,
                        success_count=0,
                        partial_success_count=0,
                        failed_count=0,
                        skipped_count=0,
                        items=[],
                        error_message="reference_batch_not_found",
                    )
                batch_run_key = str(row["batch_run_key"])

            rows = connection.execute(
                """
                SELECT id, company_id
                FROM company_report_runs
                WHERE universe_id = ?
                  AND trade_date = ?
                  AND batch_run_key = ?
                  AND status = 'FAILED'
                  AND company_id IS NOT NULL
                ORDER BY id ASC
                """,
                (universe["id"], trade_date_iso, batch_run_key),
            ).fetchall()

        rerun_map = {int(row["company_id"]): int(row["id"]) for row in rows}
        if not rerun_map:
            return CompanyReportBatchOutcome(
                batch_run_key="",
                universe_key=target_universe_key,
                trade_date=trade_date_iso,
                run_mode="RERUN_FAILED",
                total_count=0,
                success_count=0,
                partial_success_count=0,
                failed_count=0,
                skipped_count=0,
                items=[],
                error_message="no_failed_rows_in_reference_batch",
            )

        return self.generate_nightly_reports(
            trade_date=trade_date,
            universe_key=target_universe_key,
            mode="RERUN_FAILED",
            company_ids=list(rerun_map.keys()),
            rerun_map=rerun_map,
        )

    def list_report_runs(
        self,
        *,
        limit: int,
        universe_key: str | None = None,
        batch_run_key: str | None = None,
        trade_date: str | None = None,
        status: str | None = None,
        company_id: int | None = None,
    ) -> list[dict[str, Any]]:
        filters: list[str] = []
        params: list[Any] = []

        if universe_key:
            filters.append("u.universe_key = ?")
            params.append(universe_key.strip())
        if batch_run_key:
            filters.append("r.batch_run_key = ?")
            params.append(batch_run_key.strip())
        if trade_date:
            filters.append("r.trade_date = ?")
            params.append(trade_date.strip())
        if status:
            normalized_status = status.strip().upper()
            if normalized_status not in _ALLOWED_RUN_STATUS:
                raise ValueError("invalid status")
            filters.append("r.status = ?")
            params.append(normalized_status)
        if company_id is not None:
            filters.append("r.company_id = ?")
            params.append(company_id)

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    r.*,
                    u.universe_key,
                    c.canonical_name,
                    c.primary_stock_code
                FROM company_report_runs r
                JOIN report_universes u ON u.id = r.universe_id
                LEFT JOIN companies c ON c.id = r.company_id
                {where_clause}
                ORDER BY r.id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        items: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["source_coverage"] = self._json_load(payload.pop("source_coverage_json", None))
            payload["metadata"] = self._json_load(payload.pop("metadata_json", None))
            items.append(payload)
        return items

    def get_latest_report_for_company(
        self,
        *,
        company_id: int,
        universe_key: str | None = None,
        trade_date: str | None = None,
    ) -> dict[str, Any] | None:
        filters = ["r.company_id = ?"]
        params: list[Any] = [company_id]

        if universe_key:
            filters.append("u.universe_key = ?")
            params.append(universe_key.strip())
        if trade_date:
            filters.append("r.trade_date <= ?")
            params.append(trade_date.strip())

        where_clause = f"WHERE {' AND '.join(filters)}"

        with get_connection(self.db_path) as connection:
            row = connection.execute(
                f"""
                SELECT r.*, u.universe_key, u.universe_name, c.canonical_name, c.primary_stock_code
                FROM company_reports r
                JOIN report_universes u ON u.id = r.universe_id
                JOIN companies c ON c.id = r.company_id
                {where_clause}
                ORDER BY r.trade_date DESC, r.id DESC
                LIMIT 1
                """,
                params,
            ).fetchone()

            if row is None:
                return None

            report = self._deserialize_report_row(dict(row))
            report["sections"] = self._list_sections_for_report(connection, report_id=int(report["id"]))
            return report

    def list_report_history_for_company(
        self,
        *,
        company_id: int,
        universe_key: str | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        filters = ["r.company_id = ?"]
        params: list[Any] = [company_id]

        if universe_key:
            filters.append("u.universe_key = ?")
            params.append(universe_key.strip())

        params.append(limit)
        where_clause = f"WHERE {' AND '.join(filters)}"

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT r.*, u.universe_key, u.universe_name, c.canonical_name, c.primary_stock_code
                FROM company_reports r
                JOIN report_universes u ON u.id = r.universe_id
                JOIN companies c ON c.id = r.company_id
                {where_clause}
                ORDER BY r.trade_date DESC, r.id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        return [self._deserialize_report_row(dict(row)) for row in rows]

    def list_latest_reports_for_universe(
        self,
        *,
        universe_key: str | None = None,
        trade_date: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        target_universe_key = (universe_key or self.default_universe_key).strip()
        params: list[Any] = [target_universe_key]

        date_filter_sql = ""
        if trade_date:
            date_filter_sql = "AND r.trade_date <= ?"
            params.append(trade_date.strip())

        params.append(limit)

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                f"""
                WITH ranked AS (
                    SELECT
                        r.*,
                        u.universe_key,
                        u.universe_name,
                        c.canonical_name,
                        c.primary_stock_code,
                        ROW_NUMBER() OVER (
                            PARTITION BY r.company_id
                            ORDER BY r.trade_date DESC, r.id DESC
                        ) AS row_no
                    FROM company_reports r
                    JOIN report_universes u ON u.id = r.universe_id
                    JOIN companies c ON c.id = r.company_id
                    WHERE u.universe_key = ?
                    {date_filter_sql}
                )
                SELECT *
                FROM ranked
                WHERE row_no = 1
                ORDER BY trade_date DESC, id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        return [self._deserialize_report_row(dict(row)) for row in rows]

    def import_company_daily_prices(
        self,
        *,
        company_id: int,
        items: list[dict[str, Any]],
        source_name: str = "MANUAL_IMPORT",
        source_url: str | None = None,
    ) -> dict[str, Any]:
        processed = 0
        upserted = 0
        failed = 0
        now = utcnow_iso()

        with get_connection(self.db_path) as connection:
            company_row = self._load_company_row(connection, company_id=company_id)
            if company_row is None:
                raise ValueError(f"company not found: {company_id}")

            for item in items:
                processed += 1
                trade_date = self._normalize_date_string(
                    self._pick_first(item, "trade_date", "date", "dt")
                )
                if trade_date is None:
                    failed += 1
                    continue

                payload = dict(item)
                connection.execute(
                    """
                    INSERT INTO company_daily_prices (
                        company_id,
                        trade_date,
                        open_price,
                        high_price,
                        low_price,
                        close_price,
                        adjusted_close,
                        volume,
                        turnover,
                        change_rate,
                        source_name,
                        source_url,
                        source_record_id,
                        raw_payload_json,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(company_id, trade_date, source_name)
                    DO UPDATE SET
                        open_price = excluded.open_price,
                        high_price = excluded.high_price,
                        low_price = excluded.low_price,
                        close_price = excluded.close_price,
                        adjusted_close = excluded.adjusted_close,
                        volume = excluded.volume,
                        turnover = excluded.turnover,
                        change_rate = excluded.change_rate,
                        source_url = excluded.source_url,
                        source_record_id = excluded.source_record_id,
                        raw_payload_json = excluded.raw_payload_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        company_id,
                        trade_date,
                        self._as_float(self._pick_first(item, "open_price", "open")),
                        self._as_float(self._pick_first(item, "high_price", "high")),
                        self._as_float(self._pick_first(item, "low_price", "low")),
                        self._as_float(self._pick_first(item, "close_price", "close")),
                        self._as_float(self._pick_first(item, "adjusted_close", "adj_close")),
                        self._as_float(self._pick_first(item, "volume", "vol")),
                        self._as_float(self._pick_first(item, "turnover", "amount")),
                        self._as_float(self._pick_first(item, "change_rate", "pct_change", "return_pct")),
                        source_name,
                        source_url or self._pick_first(item, "source_url", "url"),
                        str(self._pick_first(item, "source_record_id", "record_id", "id") or ""),
                        self._json_dump(payload),
                        now,
                        now,
                    ),
                )
                upserted += 1

        return {
            "company_id": company_id,
            "processed_count": processed,
            "upserted_count": upserted,
            "failed_count": failed,
            "source_name": source_name,
        }

    def list_company_daily_prices(self, *, company_id: int, limit: int = 100) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM company_daily_prices
                WHERE company_id = ?
                ORDER BY trade_date DESC, id DESC
                LIMIT ?
                """,
                (company_id, limit),
            ).fetchall()

        items: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["raw_payload"] = self._json_load(payload.pop("raw_payload_json", None))
            items.append(payload)
        return items

    def import_company_investor_flows(
        self,
        *,
        company_id: int,
        items: list[dict[str, Any]],
        source_name: str = "MANUAL_IMPORT",
        source_url: str | None = None,
    ) -> dict[str, Any]:
        processed = 0
        upserted = 0
        failed = 0
        now = utcnow_iso()

        with get_connection(self.db_path) as connection:
            company_row = self._load_company_row(connection, company_id=company_id)
            if company_row is None:
                raise ValueError(f"company not found: {company_id}")

            for item in items:
                processed += 1
                trade_date = self._normalize_date_string(
                    self._pick_first(item, "trade_date", "date", "dt")
                )
                if trade_date is None:
                    failed += 1
                    continue

                payload = dict(item)
                connection.execute(
                    """
                    INSERT INTO company_investor_flows (
                        company_id,
                        trade_date,
                        foreign_net_buy,
                        institution_net_buy,
                        individual_net_buy,
                        program_net_buy,
                        source_name,
                        source_url,
                        source_record_id,
                        raw_payload_json,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(company_id, trade_date, source_name)
                    DO UPDATE SET
                        foreign_net_buy = excluded.foreign_net_buy,
                        institution_net_buy = excluded.institution_net_buy,
                        individual_net_buy = excluded.individual_net_buy,
                        program_net_buy = excluded.program_net_buy,
                        source_url = excluded.source_url,
                        source_record_id = excluded.source_record_id,
                        raw_payload_json = excluded.raw_payload_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        company_id,
                        trade_date,
                        self._as_float(
                            self._pick_first(item, "foreign_net_buy", "investor_foreign_net_buy", "foreign")
                        ),
                        self._as_float(
                            self._pick_first(
                                item,
                                "institution_net_buy",
                                "investor_institution_net_buy",
                                "institution",
                            )
                        ),
                        self._as_float(
                            self._pick_first(item, "individual_net_buy", "investor_individual_net_buy", "individual")
                        ),
                        self._as_float(self._pick_first(item, "program_net_buy", "program_net_total", "program")),
                        source_name,
                        source_url or self._pick_first(item, "source_url", "url"),
                        str(self._pick_first(item, "source_record_id", "record_id", "id") or ""),
                        self._json_dump(payload),
                        now,
                        now,
                    ),
                )
                upserted += 1

        return {
            "company_id": company_id,
            "processed_count": processed,
            "upserted_count": upserted,
            "failed_count": failed,
            "source_name": source_name,
        }

    def list_company_investor_flows(self, *, company_id: int, limit: int = 100) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM company_investor_flows
                WHERE company_id = ?
                ORDER BY trade_date DESC, id DESC
                LIMIT ?
                """,
                (company_id, limit),
            ).fetchall()

        items: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["raw_payload"] = self._json_load(payload.pop("raw_payload_json", None))
            items.append(payload)
        return items

    def import_company_financial_snapshots(
        self,
        *,
        company_id: int,
        items: list[dict[str, Any]],
        source_name: str = "MANUAL_IMPORT",
        source_url: str | None = None,
    ) -> dict[str, Any]:
        processed = 0
        upserted = 0
        failed = 0
        now = utcnow_iso()

        with get_connection(self.db_path) as connection:
            company_row = self._load_company_row(connection, company_id=company_id)
            if company_row is None:
                raise ValueError(f"company not found: {company_id}")

            for item in items:
                processed += 1
                snapshot_date = self._normalize_date_string(
                    self._pick_first(item, "snapshot_date", "as_of_date", "trade_date", "date")
                )
                if snapshot_date is None:
                    failed += 1
                    continue

                payload = dict(item)
                connection.execute(
                    """
                    INSERT INTO company_financial_snapshots (
                        company_id,
                        snapshot_date,
                        fiscal_period,
                        market_cap,
                        per,
                        pbr,
                        roe,
                        eps,
                        bps,
                        dividend_yield,
                        revenue,
                        operating_income,
                        net_income,
                        debt_ratio,
                        currency,
                        source_name,
                        source_url,
                        source_record_id,
                        raw_payload_json,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(company_id, snapshot_date, source_name)
                    DO UPDATE SET
                        fiscal_period = excluded.fiscal_period,
                        market_cap = excluded.market_cap,
                        per = excluded.per,
                        pbr = excluded.pbr,
                        roe = excluded.roe,
                        eps = excluded.eps,
                        bps = excluded.bps,
                        dividend_yield = excluded.dividend_yield,
                        revenue = excluded.revenue,
                        operating_income = excluded.operating_income,
                        net_income = excluded.net_income,
                        debt_ratio = excluded.debt_ratio,
                        currency = excluded.currency,
                        source_url = excluded.source_url,
                        source_record_id = excluded.source_record_id,
                        raw_payload_json = excluded.raw_payload_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        company_id,
                        snapshot_date,
                        self._pick_first(item, "fiscal_period", "period"),
                        self._as_float(self._pick_first(item, "market_cap", "market_capitalization", "mkt_cap")),
                        self._as_float(self._pick_first(item, "per")),
                        self._as_float(self._pick_first(item, "pbr")),
                        self._as_float(self._pick_first(item, "roe")),
                        self._as_float(self._pick_first(item, "eps")),
                        self._as_float(self._pick_first(item, "bps")),
                        self._as_float(self._pick_first(item, "dividend_yield", "div_yield")),
                        self._as_float(self._pick_first(item, "revenue", "sales")),
                        self._as_float(self._pick_first(item, "operating_income", "op_income")),
                        self._as_float(self._pick_first(item, "net_income", "net_profit")),
                        self._as_float(self._pick_first(item, "debt_ratio")),
                        self._pick_first(item, "currency"),
                        source_name,
                        source_url or self._pick_first(item, "source_url", "url"),
                        str(self._pick_first(item, "source_record_id", "record_id", "id") or ""),
                        self._json_dump(payload),
                        now,
                        now,
                    ),
                )
                upserted += 1

        return {
            "company_id": company_id,
            "processed_count": processed,
            "upserted_count": upserted,
            "failed_count": failed,
            "source_name": source_name,
        }

    def list_company_financial_snapshots(self, *, company_id: int, limit: int = 50) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM company_financial_snapshots
                WHERE company_id = ?
                ORDER BY snapshot_date DESC, id DESC
                LIMIT ?
                """,
                (company_id, limit),
            ).fetchall()

        items: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["raw_payload"] = self._json_load(payload.pop("raw_payload_json", None))
            items.append(payload)
        return items

    def _ensure_universe_for_generation(self, *, universe_key: str) -> dict[str, Any]:
        with get_connection(self.db_path) as connection:
            universe = self._load_universe_by_key(connection, universe_key=universe_key)
            if universe is None:
                universe_id = self._upsert_universe(
                    connection,
                    universe_key=universe_key,
                    universe_name=self.default_universe_name,
                    description="KRX large-cap company report coverage",
                    selection_mode="MIXED",
                    selection_config={"source": "auto_create"},
                    target_size=self.default_universe_target_size,
                    created_by="system",
                )
                universe = self._load_universe(connection, universe_id=universe_id)

        members = self.list_universe_members(universe_key=universe_key, include_inactive=False, limit=1)
        if not members and self.seed_stock_codes:
            self.sync_universe_members(
                universe_key=universe_key,
                stock_codes=self.seed_stock_codes,
                replace=True,
                member_source="ENV_SEED",
                note="seeded from COMPANY_REPORT_SEED_STOCK_CODES",
            )

        with get_connection(self.db_path) as connection:
            refreshed = self._load_universe_by_key(connection, universe_key=universe_key)
            if refreshed is None:
                raise RuntimeError(f"failed to resolve universe: {universe_key}")
            return refreshed

    def _generate_report_output(
        self,
        *,
        company_row: dict[str, Any],
        trade_date_iso: str,
        input_payload: dict[str, Any],
        source_coverage: dict[str, Any],
    ) -> tuple[str, str, str | None, str | None, dict[str, Any], str, list[dict[str, Any]]]:
        fallback_payload = self._build_fallback_report(company_row=company_row, input_payload=input_payload)
        fallback_payload["source_coverage"] = source_coverage

        llm_provider_name: str | None = None
        llm_model_name: str | None = None
        generation_method = "RULE_BASED"
        status = "SUCCESS"

        llm_response_payload: dict[str, Any] | None = None
        llm_error: str | None = None

        enabled, _reason = self.llm_provider.is_enabled()
        if enabled:
            llm_provider_name = getattr(self.llm_provider, "provider_name", "unknown")
            llm_model_name = self.llm_provider.model_name()
            try:
                response = self.llm_provider.generate_report(
                    CompanyReportLLMRequest(
                        company_id=int(company_row["id"]),
                        trade_date=trade_date_iso,
                        company_profile={
                            "company_id": int(company_row["id"]),
                            "canonical_name": company_row.get("canonical_name"),
                            "primary_stock_code": company_row.get("primary_stock_code"),
                            "market_classification": company_row.get("market_classification"),
                        },
                        input_payload=input_payload,
                    )
                )

                if response is not None:
                    llm_response_payload = {
                        "one_line_status": self._sanitize_text(response.one_line_status),
                        "recent_key_events": [self._sanitize_text(item) for item in response.recent_key_events],
                        "flow_summary": self._sanitize_text(response.flow_summary),
                        "technical_context_summary": self._sanitize_text(response.technical_context_summary),
                        "bull_points": [self._sanitize_text(item) for item in response.bull_points],
                        "bear_points": [self._sanitize_text(item) for item in response.bear_points],
                        "watch_items": [self._sanitize_text(item) for item in response.watch_items],
                        "confidence": {
                            "score": response.confidence_score,
                            "bucket": response.confidence_bucket,
                            "rationale": self._sanitize_text(response.confidence_rationale),
                        },
                        "source_coverage": source_coverage,
                        "meta": {
                            "provider": llm_provider_name,
                            "model": llm_model_name,
                            "raw_output": response.raw_output,
                        },
                    }
                    generation_method = "LLM"
            except Exception as error:  # noqa: BLE001
                llm_error = str(error)
                generation_method = "HYBRID"
                status = "PARTIAL_SUCCESS"
                logger.warning(
                    "company_report_llm_fallback",
                    extra={
                        "company_id": company_row.get("id"),
                        "trade_date": trade_date_iso,
                        "error": llm_error,
                    },
                )

        effective_payload = llm_response_payload or fallback_payload
        if llm_response_payload is None and generation_method == "HYBRID":
            effective_payload.setdefault("meta", {})
            effective_payload["meta"]["llm_error"] = llm_error

        sections = self._payload_to_sections(effective_payload)
        markdown = self._build_markdown_report(
            company_name=str(company_row.get("canonical_name") or "회사"),
            stock_code=company_row.get("primary_stock_code"),
            trade_date_iso=trade_date_iso,
            payload=effective_payload,
            sections=sections,
        )

        if not llm_provider_name:
            llm_provider_name = "disabled"

        return (
            status,
            generation_method,
            llm_provider_name,
            llm_model_name,
            effective_payload,
            markdown,
            sections,
        )

    def _assemble_report_input(
        self,
        connection,
        *,
        company_row: dict[str, Any],
        trade_date_iso: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        company_id = int(company_row["id"])
        stock_code = normalize_stock_code(company_row.get("primary_stock_code"))

        price_rows = self._load_price_rows(
            connection,
            company_id=company_id,
            stock_code=stock_code,
            trade_date_iso=trade_date_iso,
        )
        price_context = self._build_price_context(price_rows=price_rows)

        flow_rows = self._load_investor_flow_rows(
            connection,
            company_id=company_id,
            trade_date_iso=trade_date_iso,
        )
        flow_context = self._build_flow_context(flow_rows=flow_rows)

        event_rows = self._load_company_event_rows(
            connection,
            company_id=company_id,
            trade_date_iso=trade_date_iso,
        )
        event_context, event_recency_hours = self._build_event_context(
            event_rows=event_rows,
            trade_date_iso=trade_date_iso,
        )

        disclosure_rows = self._load_disclosure_rows(
            connection,
            company_id=company_id,
            trade_date_iso=trade_date_iso,
        )
        disclosure_context = self._build_disclosure_context(disclosure_rows=disclosure_rows)

        financial_snapshot = self._load_financial_snapshot(
            connection,
            company_id=company_id,
            trade_date_iso=trade_date_iso,
        )

        source_coverage = self._build_source_coverage(
            price_context=price_context,
            flow_context=flow_context,
            event_context=event_context,
            disclosure_context=disclosure_context,
            financial_snapshot=financial_snapshot,
        )

        feature_snapshot = {
            "momentum_score": price_context["summary"].get("momentum_score"),
            "volatility_score": price_context["summary"].get("volatility_score"),
            "price_trend_label": price_context["summary"].get("trend_label"),
            "event_recency_hours": event_recency_hours,
            "recent_event_count": len(event_context),
            "recent_disclosure_count": len(disclosure_context),
            "flow_foreign_avg": flow_context["summary"].get("foreign_net_buy_avg"),
            "flow_institution_avg": flow_context["summary"].get("institution_net_buy_avg"),
        }

        payload = {
            "as_of_trade_date": trade_date_iso,
            "company": {
                "company_id": company_id,
                "canonical_name": company_row.get("canonical_name"),
                "primary_stock_code": stock_code,
                "market": company_row.get("market"),
                "market_classification": company_row.get("market_classification"),
                "listing_status": company_row.get("listing_status"),
            },
            "price_context": price_context,
            "investor_flow_context": flow_context,
            "event_context": event_context,
            "disclosure_context": disclosure_context,
            "financial_snapshot": financial_snapshot,
            "derived_features": feature_snapshot,
            "source_coverage": source_coverage,
        }

        return payload, source_coverage, feature_snapshot

    def _build_fallback_report(self, *, company_row: dict[str, Any], input_payload: dict[str, Any]) -> dict[str, Any]:
        features = input_payload.get("derived_features") or {}
        source_coverage = input_payload.get("source_coverage") or {}
        event_context = input_payload.get("event_context") or []
        disclosure_context = input_payload.get("disclosure_context") or []
        flow_summary = (input_payload.get("investor_flow_context") or {}).get("summary") or {}
        price_summary = (input_payload.get("price_context") or {}).get("summary") or {}

        momentum = self._as_float(features.get("momentum_score"))
        volatility = self._as_float(features.get("volatility_score"))
        event_recency_hours = self._as_float(features.get("event_recency_hours"))

        trend_label = str(price_summary.get("trend_label") or "unknown")
        event_count = len(event_context)
        disclosure_count = len(disclosure_context)

        coverage_ratio = self._as_float(source_coverage.get("coverage_ratio")) or 0.0
        confidence_score = self._estimate_confidence_score(
            coverage_ratio=coverage_ratio,
            event_count=event_count,
            has_price=bool(price_summary.get("available")),
            has_flow=bool(flow_summary.get("available")),
        )
        confidence_bucket = self._confidence_bucket(confidence_score)

        if trend_label == "up" and event_count > 0:
            one_line_status = "단기 모멘텀은 우호적이며 최근 이벤트 추적이 필요합니다."
        elif trend_label == "down" and event_count > 0:
            one_line_status = "단기 변동성 확대 구간으로 이벤트 리스크 점검이 필요합니다."
        elif coverage_ratio < 0.45:
            one_line_status = "가용 데이터가 제한적이어서 보수적 모니터링이 필요한 구간입니다."
        else:
            one_line_status = "수급·이벤트 혼조 구간으로 팩트 업데이트 중심 추적이 필요합니다."

        recent_key_events = [
            self._sanitize_text(str(item.get("summary") or item.get("event_type_label") or ""))
            for item in event_context[:4]
            if str(item.get("summary") or item.get("event_type_label") or "").strip()
        ]
        if not recent_key_events:
            recent_key_events = [
                self._sanitize_text(str(item.get("title") or ""))
                for item in disclosure_context[:3]
                if str(item.get("title") or "").strip()
            ]
        if not recent_key_events:
            recent_key_events = ["최근 주요 이벤트 데이터가 제한적입니다."]

        flow_parts: list[str] = []
        foreign_latest = self._as_float(flow_summary.get("foreign_net_buy_latest"))
        institution_latest = self._as_float(flow_summary.get("institution_net_buy_latest"))
        program_latest = self._as_float(flow_summary.get("program_net_total_latest"))
        flow_scope = str(flow_summary.get("flow_scope") or "").upper()

        if foreign_latest is not None:
            flow_parts.append(f"외국인 순매수(최근): {self._fmt_signed_number(foreign_latest)}")
        if institution_latest is not None:
            flow_parts.append(f"기관 순매수(최근): {self._fmt_signed_number(institution_latest)}")
        if program_latest is not None:
            flow_parts.append(f"프로그램 순매수(최근): {self._fmt_signed_number(program_latest)}")

        if flow_parts:
            flow_summary_text = ", ".join(flow_parts)
        else:
            flow_summary_text = "수급 데이터가 제한적이며 시장 전반 흐름 확인이 필요합니다."

        if flow_scope == "MARKET_LEVEL":
            flow_summary_text = f"{flow_summary_text} (시장 레벨 수급 기준)"

        technical_parts: list[str] = []
        if momentum is not None:
            technical_parts.append(f"모멘텀(최근 {self.price_lookback_days}일 평균 변화율): {momentum:.3f}")
        if volatility is not None:
            technical_parts.append(f"변동성(변화율 표준편차): {volatility:.3f}")
        if event_recency_hours is not None:
            technical_parts.append(f"최근 이벤트 경과 시간: {event_recency_hours:.1f}시간")
        if not technical_parts:
            technical_parts.append("기술적 요약에 필요한 시세 데이터가 제한적입니다.")

        bull_points: list[str] = []
        bear_points: list[str] = []

        if momentum is not None and momentum > 0:
            bull_points.append("단기 모멘텀이 플러스 구간에 머물고 있습니다.")
        if foreign_latest is not None and foreign_latest > 0:
            bull_points.append("외국인 수급이 순매수 방향으로 관측됩니다.")
        if event_count > 0:
            positive_events = [
                item
                for item in event_context
                if str(item.get("sentiment") or "").lower() in {"positive", "mixed"}
            ]
            if positive_events:
                bull_points.append("최근 이벤트 중 우호적 시그널이 관찰됩니다.")

        if momentum is not None and momentum < 0:
            bear_points.append("단기 모멘텀이 약세 구간에 위치합니다.")
        if volatility is not None and volatility > 1.0:
            bear_points.append("변동성 지표가 높아 단기 노이즈 확대 가능성이 있습니다.")
        if institution_latest is not None and institution_latest < 0:
            bear_points.append("기관 수급이 순매도 방향으로 나타납니다.")
        negative_events = [
            item
            for item in event_context
            if str(item.get("sentiment") or "").lower() in {"negative", "mixed"}
        ]
        if negative_events:
            bear_points.append("최근 이벤트 중 하방 리스크 요인이 포함되어 있습니다.")

        if not bull_points:
            bull_points = ["추가 데이터 유입 시 우호 시그널 재평가가 필요합니다."]
        if not bear_points:
            bear_points = ["명확한 하방 신호는 제한적이나 이벤트 변동성 점검이 필요합니다."]

        watch_items: list[str] = [
            "다음 거래일 외국인/기관 순매수 방향 전환 여부 확인",
            "신규 공시 접수 여부 및 이벤트 유형 변화 확인",
            "장 초반 변동성 확대 구간에서 거래대금/호가 균형 점검",
        ]
        if disclosure_count == 0:
            watch_items.append("최근 공시 부재 구간이므로 공시 업데이트 발생 여부 모니터링")

        return {
            "one_line_status": self._sanitize_text(one_line_status),
            "recent_key_events": [self._sanitize_text(item) for item in recent_key_events[:4]],
            "flow_summary": self._sanitize_text(flow_summary_text),
            "technical_context_summary": self._sanitize_text("; ".join(technical_parts)),
            "bull_points": [self._sanitize_text(item) for item in bull_points[:4]],
            "bear_points": [self._sanitize_text(item) for item in bear_points[:4]],
            "watch_items": [self._sanitize_text(item) for item in watch_items[:4]],
            "confidence": {
                "score": confidence_score,
                "bucket": confidence_bucket,
                "rationale": self._sanitize_text(
                    f"coverage_ratio={coverage_ratio:.2f}, event_count={event_count}, disclosure_count={disclosure_count}"
                ),
            },
            "source_coverage": source_coverage,
            "meta": {
                "generator": "rule_based_fallback",
                "company_id": int(company_row["id"]),
                "company_name": company_row.get("canonical_name"),
            },
        }

    def _payload_to_sections(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []
        for order, (section_key, section_title) in enumerate(_SECTION_KEYS, start=1):
            value = payload.get(section_key)
            if isinstance(value, list):
                normalized = [self._sanitize_text(str(item)) for item in value if str(item).strip()]
                markdown = "\n".join(f"- {item}" for item in normalized) if normalized else "- 데이터 없음"
                content_json = normalized
            else:
                text = self._sanitize_text(str(value or "데이터 없음").strip())
                markdown = text
                content_json = {"text": text}

            sections.append(
                {
                    "section_key": section_key,
                    "section_title": section_title,
                    "section_order": order,
                    "content_markdown": markdown,
                    "content_json": content_json,
                }
            )
        return sections

    def _build_markdown_report(
        self,
        *,
        company_name: str,
        stock_code: str | None,
        trade_date_iso: str,
        payload: dict[str, Any],
        sections: list[dict[str, Any]],
    ) -> str:
        title = f"# {company_name} ({stock_code or '-'}) 리포트 - {trade_date_iso}"
        lines = [
            title,
            "",
            "> 본 리포트는 저장된 데이터 기반의 정보 요약이며 투자 판단의 단독 근거로 사용될 수 없습니다.",
            "",
        ]

        for section in sections:
            lines.append(f"## {section['section_title']}")
            lines.append(str(section["content_markdown"]))
            lines.append("")

        confidence = payload.get("confidence") if isinstance(payload.get("confidence"), dict) else {}
        source_coverage = payload.get("source_coverage") if isinstance(payload.get("source_coverage"), dict) else {}
        lines.extend(
            [
                "## 메타데이터",
                f"- confidence_score: {self._fmt_float(confidence.get('score'))}",
                f"- confidence_bucket: {confidence.get('bucket') or 'unknown'}",
                f"- source_coverage_ratio: {self._fmt_float(source_coverage.get('coverage_ratio'))}",
                "",
            ]
        )

        return "\n".join(lines).strip()

    def _start_company_report_run(
        self,
        connection,
        *,
        batch_run_key: str,
        universe_id: int,
        company_id: int,
        trade_date_iso: str,
        run_mode: str,
        rerun_of_run_id: int | None,
    ) -> int:
        now = utcnow_iso()
        previous = connection.execute(
            """
            SELECT MAX(attempt_no) AS attempt_no
            FROM company_report_runs
            WHERE universe_id = ? AND company_id = ? AND trade_date = ?
            """,
            (universe_id, company_id, trade_date_iso),
        ).fetchone()
        attempt_no = int(previous["attempt_no"] or 0) + 1

        connection.execute(
            """
            INSERT INTO company_report_runs (
                batch_run_key,
                universe_id,
                company_id,
                trade_date,
                run_mode,
                status,
                attempt_no,
                rerun_of_run_id,
                report_id,
                started_at,
                finished_at,
                elapsed_ms,
                source_coverage_json,
                error_message,
                metadata_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, 'RUNNING', ?, ?, NULL, ?, NULL, NULL, NULL, NULL, NULL, ?, ?)
            """,
            (
                batch_run_key,
                universe_id,
                company_id,
                trade_date_iso,
                run_mode,
                attempt_no,
                rerun_of_run_id,
                now,
                now,
                now,
            ),
        )
        row = connection.execute("SELECT last_insert_rowid() AS id").fetchone()
        return int(row["id"])

    def _finish_company_report_run(
        self,
        connection,
        *,
        run_id: int,
        status: str,
        report_id: int | None,
        elapsed_ms: int,
        source_coverage: dict[str, Any] | None,
        error_message: str | None,
        metadata: dict[str, Any] | None,
    ) -> None:
        normalized_status = status.strip().upper()
        if normalized_status not in _ALLOWED_RUN_STATUS:
            raise ValueError(f"unsupported company report run status: {status}")

        now = utcnow_iso()
        connection.execute(
            """
            UPDATE company_report_runs
            SET
                status = ?,
                report_id = ?,
                finished_at = ?,
                elapsed_ms = ?,
                source_coverage_json = ?,
                error_message = ?,
                metadata_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                normalized_status,
                report_id,
                now,
                max(0, elapsed_ms),
                self._json_dump(source_coverage),
                error_message,
                self._json_dump(metadata),
                now,
                run_id,
            ),
        )

    def _upsert_company_report(
        self,
        connection,
        *,
        universe_id: int,
        company_id: int,
        trade_date_iso: str,
        run_mode: str,
        status: str,
        generation_method: str,
        llm_provider: str | None,
        llm_model: str | None,
        input_payload: dict[str, Any],
        report_payload: dict[str, Any],
        markdown_body: str,
        source_coverage: dict[str, Any],
        feature_snapshot: dict[str, Any],
    ) -> int:
        now = utcnow_iso()

        confidence = report_payload.get("confidence") if isinstance(report_payload.get("confidence"), dict) else {}
        confidence_score = self._as_float(confidence.get("score"))
        confidence_bucket = str(confidence.get("bucket") or "").lower().strip()
        if confidence_bucket not in {"low", "medium", "high"}:
            confidence_bucket = self._confidence_bucket(confidence_score or 0.0)

        source_event_count = len(input_payload.get("event_context") or [])
        source_disclosure_count = len(input_payload.get("disclosure_context") or [])

        connection.execute(
            """
            INSERT INTO company_reports (
                universe_id,
                company_id,
                trade_date,
                run_mode,
                status,
                generation_method,
                llm_provider,
                llm_model,
                input_payload_json,
                report_payload_json,
                markdown_body,
                source_coverage_json,
                confidence_score,
                confidence_bucket,
                feature_snapshot_json,
                source_event_count,
                source_disclosure_count,
                metadata_json,
                generated_at,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(universe_id, company_id, trade_date)
            DO UPDATE SET
                run_mode = excluded.run_mode,
                status = excluded.status,
                generation_method = excluded.generation_method,
                llm_provider = excluded.llm_provider,
                llm_model = excluded.llm_model,
                input_payload_json = excluded.input_payload_json,
                report_payload_json = excluded.report_payload_json,
                markdown_body = excluded.markdown_body,
                source_coverage_json = excluded.source_coverage_json,
                confidence_score = excluded.confidence_score,
                confidence_bucket = excluded.confidence_bucket,
                feature_snapshot_json = excluded.feature_snapshot_json,
                source_event_count = excluded.source_event_count,
                source_disclosure_count = excluded.source_disclosure_count,
                metadata_json = excluded.metadata_json,
                generated_at = excluded.generated_at,
                updated_at = excluded.updated_at
            """,
            (
                universe_id,
                company_id,
                trade_date_iso,
                run_mode,
                status,
                generation_method,
                llm_provider,
                llm_model,
                self._json_dump(input_payload),
                self._json_dump(report_payload),
                markdown_body,
                self._json_dump(source_coverage),
                confidence_score,
                confidence_bucket,
                self._json_dump(feature_snapshot),
                source_event_count,
                source_disclosure_count,
                self._json_dump({"report_version": 1}),
                now,
                now,
                now,
            ),
        )

        row = connection.execute(
            """
            SELECT id
            FROM company_reports
            WHERE universe_id = ? AND company_id = ? AND trade_date = ?
            """,
            (universe_id, company_id, trade_date_iso),
        ).fetchone()
        return int(row["id"])

    def _upsert_report_sections(self, connection, *, report_id: int, sections: list[dict[str, Any]]) -> None:
        now = utcnow_iso()
        for section in sections:
            connection.execute(
                """
                INSERT INTO company_report_sections (
                    report_id,
                    section_key,
                    section_title,
                    section_order,
                    content_markdown,
                    content_json,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(report_id, section_key)
                DO UPDATE SET
                    section_title = excluded.section_title,
                    section_order = excluded.section_order,
                    content_markdown = excluded.content_markdown,
                    content_json = excluded.content_json,
                    updated_at = excluded.updated_at
                """,
                (
                    report_id,
                    section["section_key"],
                    section["section_title"],
                    section["section_order"],
                    section["content_markdown"],
                    self._json_dump(section["content_json"]),
                    now,
                    now,
                ),
            )

    def _load_price_rows(
        self,
        connection,
        *,
        company_id: int,
        stock_code: str | None,
        trade_date_iso: str,
    ) -> list[dict[str, Any]]:
        start_date = (date.fromisoformat(trade_date_iso) - timedelta(days=self.price_lookback_days - 1)).isoformat()

        company_rows = connection.execute(
            """
            SELECT
                trade_date,
                open_price,
                high_price,
                low_price,
                close_price,
                adjusted_close,
                volume,
                turnover,
                change_rate,
                source_name,
                source_url,
                source_record_id
            FROM company_daily_prices
            WHERE company_id = ?
              AND trade_date >= ?
              AND trade_date <= ?
            ORDER BY trade_date DESC, id DESC
            """,
            (company_id, start_date, trade_date_iso),
        ).fetchall()

        if company_rows:
            return [
                {
                    "trade_date": row["trade_date"],
                    "snapshot_time": f"{row['trade_date']}T15:30:00+09:00",
                    "instrument_code": stock_code,
                    "instrument_name": None,
                    "open_price": row["open_price"],
                    "high_price": row["high_price"],
                    "low_price": row["low_price"],
                    "close_price": row["close_price"],
                    "adjusted_close": row["adjusted_close"],
                    "price": row["close_price"],
                    "price_change": None,
                    "change_rate": row["change_rate"],
                    "volume": row["volume"],
                    "turnover": row["turnover"],
                    "source_name": row["source_name"],
                    "source_url": row["source_url"],
                    "source_record_id": row["source_record_id"],
                    "source_table": "company_daily_prices",
                }
                for row in company_rows
            ]

        if not stock_code:
            return []

        candidates = [stock_code, f"{stock_code}.KS", f"A{stock_code}"]
        placeholders = ",".join("?" for _ in candidates)
        params: list[Any] = [start_date, trade_date_iso, *candidates]

        rows = connection.execute(
            f"""
            SELECT
                trade_date,
                snapshot_time,
                instrument_code,
                instrument_name,
                price,
                price_change,
                change_rate,
                volume,
                source_name,
                source_url,
                source_record_id
            FROM market_intraday_snapshots
            WHERE trade_date >= ?
              AND trade_date <= ?
              AND instrument_code IN ({placeholders})
            ORDER BY trade_date DESC, snapshot_time DESC, id DESC
            """,
            params,
        ).fetchall()

        return [{**dict(row), "source_table": "market_intraday_snapshots"} for row in rows]

    def _build_price_context(self, *, price_rows: list[dict[str, Any]]) -> dict[str, Any]:
        latest_by_date: dict[str, dict[str, Any]] = {}
        for row in price_rows:
            trade_date = str(row.get("trade_date") or "")
            if not trade_date:
                continue
            if trade_date not in latest_by_date:
                latest_by_date[trade_date] = row

        ordered_dates = sorted(latest_by_date.keys(), reverse=True)
        observations = [latest_by_date[key] for key in ordered_dates][: self.price_lookback_days]

        change_rates: list[float] = []
        previous_close: float | None = None
        for item in sorted(observations, key=lambda value: str(value.get("trade_date") or "")):
            raw_change_rate = self._as_float(item.get("change_rate"))
            if raw_change_rate is not None:
                change_rates.append(raw_change_rate)
            else:
                close_price = (
                    self._as_float(item.get("adjusted_close"))
                    or self._as_float(item.get("close_price"))
                    or self._as_float(item.get("price"))
                )
                open_price = self._as_float(item.get("open_price"))
                inferred_change_rate: float | None = None
                if close_price is not None and open_price is not None and open_price != 0:
                    inferred_change_rate = ((close_price - open_price) / open_price) * 100.0
                elif close_price is not None and previous_close is not None and previous_close != 0:
                    inferred_change_rate = ((close_price - previous_close) / previous_close) * 100.0

                if inferred_change_rate is not None:
                    change_rates.append(inferred_change_rate)

                if close_price is not None:
                    previous_close = close_price

        momentum_score = round(mean(change_rates), 4) if change_rates else None
        volatility_score = round(pstdev(change_rates), 4) if len(change_rates) >= 2 else None

        trend_label = "unknown"
        if momentum_score is not None:
            if momentum_score > 0.2:
                trend_label = "up"
            elif momentum_score < -0.2:
                trend_label = "down"
            else:
                trend_label = "flat"

        normalized_observations: list[dict[str, Any]] = []
        for row in observations:
            close_price = (
                self._as_float(row.get("adjusted_close"))
                or self._as_float(row.get("close_price"))
                or self._as_float(row.get("price"))
            )
            normalized_observations.append(
                {
                    "trade_date": row.get("trade_date"),
                    "snapshot_time": row.get("snapshot_time"),
                    "instrument_code": row.get("instrument_code"),
                    "open_price": self._as_float(row.get("open_price")),
                    "high_price": self._as_float(row.get("high_price")),
                    "low_price": self._as_float(row.get("low_price")),
                    "close_price": self._as_float(row.get("close_price")),
                    "adjusted_close": self._as_float(row.get("adjusted_close")),
                    "price": close_price,
                    "price_change": self._as_float(row.get("price_change")),
                    "change_rate": self._as_float(row.get("change_rate")),
                    "volume": self._as_float(row.get("volume")),
                    "turnover": self._as_float(row.get("turnover")),
                    "source_name": row.get("source_name"),
                    "source_url": row.get("source_url"),
                    "source_record_id": row.get("source_record_id"),
                    "source_table": row.get("source_table"),
                }
            )

        source_table = normalized_observations[0]["source_table"] if normalized_observations else None
        return {
            "observations": normalized_observations,
            "summary": {
                "available": len(normalized_observations) > 0,
                "observation_count": len(normalized_observations),
                "momentum_score": momentum_score,
                "volatility_score": volatility_score,
                "trend_label": trend_label,
                "source_table": source_table,
            },
        }

    def _load_investor_flow_rows(
        self,
        connection,
        *,
        company_id: int,
        trade_date_iso: str,
    ) -> list[dict[str, Any]]:
        start_date = (date.fromisoformat(trade_date_iso) - timedelta(days=self.price_lookback_days - 1)).isoformat()

        company_rows = connection.execute(
            """
            SELECT
                trade_date,
                source_name,
                foreign_net_buy AS investor_foreign_net_buy,
                institution_net_buy AS investor_institution_net_buy,
                individual_net_buy AS investor_individual_net_buy,
                program_net_buy AS program_net_total,
                source_url,
                source_record_id
            FROM company_investor_flows
            WHERE company_id = ?
              AND trade_date >= ?
              AND trade_date <= ?
            ORDER BY trade_date DESC, id DESC
            """,
            (company_id, start_date, trade_date_iso),
        ).fetchall()
        if company_rows:
            return [
                {
                    **dict(row),
                    "flow_scope": "COMPANY_LEVEL",
                    "source_table": "company_investor_flows",
                }
                for row in company_rows
            ]

        rows = connection.execute(
            """
            SELECT
                trade_date,
                source_name,
                investor_foreign_net_buy,
                investor_institution_net_buy,
                investor_individual_net_buy,
                program_net_total,
                source_url,
                source_record_id
            FROM market_daily_factors
            WHERE market_scope = ?
              AND trade_date >= ?
              AND trade_date <= ?
            ORDER BY trade_date DESC, id DESC
            """,
            (self.market_scope, start_date, trade_date_iso),
        ).fetchall()
        return [
            {
                **dict(row),
                "flow_scope": "MARKET_LEVEL",
                "source_table": "market_daily_factors",
            }
            for row in rows
        ]

    def _build_flow_context(self, *, flow_rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not flow_rows:
            return {
                "rows": [],
                "summary": {
                    "available": False,
                    "flow_scope": None,
                    "source_table": None,
                    "foreign_net_buy_latest": None,
                    "foreign_net_buy_avg": None,
                    "institution_net_buy_latest": None,
                    "institution_net_buy_avg": None,
                    "program_net_total_latest": None,
                },
            }

        latest = flow_rows[0]
        foreign_series = [
            self._as_float(row.get("investor_foreign_net_buy"))
            for row in flow_rows
            if self._as_float(row.get("investor_foreign_net_buy")) is not None
        ]
        institution_series = [
            self._as_float(row.get("investor_institution_net_buy"))
            for row in flow_rows
            if self._as_float(row.get("investor_institution_net_buy")) is not None
        ]

        normalized_rows = [
            {
                "trade_date": row.get("trade_date"),
                "source_name": row.get("source_name"),
                "investor_foreign_net_buy": self._as_float(row.get("investor_foreign_net_buy")),
                "investor_institution_net_buy": self._as_float(row.get("investor_institution_net_buy")),
                "investor_individual_net_buy": self._as_float(row.get("investor_individual_net_buy")),
                "program_net_total": self._as_float(row.get("program_net_total")),
                "source_url": row.get("source_url"),
                "source_record_id": row.get("source_record_id"),
                "flow_scope": row.get("flow_scope"),
                "source_table": row.get("source_table"),
            }
            for row in flow_rows[: self.price_lookback_days]
        ]

        return {
            "rows": normalized_rows,
            "summary": {
                "available": True,
                "flow_scope": latest.get("flow_scope"),
                "source_table": latest.get("source_table"),
                "foreign_net_buy_latest": self._as_float(latest.get("investor_foreign_net_buy")),
                "foreign_net_buy_avg": round(mean(foreign_series), 3) if foreign_series else None,
                "institution_net_buy_latest": self._as_float(latest.get("investor_institution_net_buy")),
                "institution_net_buy_avg": round(mean(institution_series), 3) if institution_series else None,
                "program_net_total_latest": self._as_float(latest.get("program_net_total")),
            },
        }

    def _load_company_event_rows(
        self,
        connection,
        *,
        company_id: int,
        trade_date_iso: str,
    ) -> list[dict[str, Any]]:
        start_date = (date.fromisoformat(trade_date_iso) - timedelta(days=self.event_lookback_days - 1)).isoformat()
        rows = connection.execute(
            """
            SELECT
                e.id,
                e.event_type,
                e.event_type_label,
                e.summary,
                e.sentiment,
                e.source_type,
                e.source_provider,
                e.source_url,
                e.canonical_url,
                e.occurred_at,
                e.confidence,
                e.trust_score,
                edge.impact_tier,
                edge.reason AS impact_reason,
                rd.provider_document_id,
                rd.title AS source_title,
                rd.summary AS source_summary,
                rd.publisher AS source_publisher
            FROM event_company_edges edge
            JOIN events e ON e.id = edge.event_id
            LEFT JOIN raw_documents rd ON rd.id = e.primary_document_id
            WHERE edge.company_id = ?
              AND substr(COALESCE(e.occurred_at, e.created_at), 1, 10) >= ?
              AND substr(COALESCE(e.occurred_at, e.created_at), 1, 10) <= ?
              AND e.status IN ('AUTO_APPROVED', 'APPROVED', 'PENDING_REVIEW')
            ORDER BY COALESCE(e.occurred_at, e.created_at) DESC, e.id DESC
            LIMIT 30
            """,
            (company_id, start_date, trade_date_iso),
        ).fetchall()
        return [dict(row) for row in rows]

    def _build_event_context(
        self,
        *,
        event_rows: list[dict[str, Any]],
        trade_date_iso: str,
    ) -> tuple[list[dict[str, Any]], float | None]:
        items: list[dict[str, Any]] = []
        latest_occurred_at: str | None = None

        for row in event_rows[:12]:
            occurred_at = row.get("occurred_at")
            if latest_occurred_at is None and isinstance(occurred_at, str) and occurred_at.strip():
                latest_occurred_at = occurred_at

            items.append(
                {
                    "event_id": row.get("id"),
                    "event_type": row.get("event_type"),
                    "event_type_label": row.get("event_type_label"),
                    "summary": row.get("summary"),
                    "sentiment": row.get("sentiment"),
                    "impact_tier": row.get("impact_tier"),
                    "impact_reason": row.get("impact_reason"),
                    "confidence": self._as_float(row.get("confidence")),
                    "trust_score": self._as_float(row.get("trust_score")),
                    "source_type": row.get("source_type"),
                    "source_provider": row.get("source_provider"),
                    "source_url": row.get("source_url"),
                    "canonical_url": row.get("canonical_url"),
                    "provider_document_id": row.get("provider_document_id"),
                    "source_title": row.get("source_title"),
                    "source_summary": row.get("source_summary"),
                    "occurred_at": occurred_at,
                }
            )

        event_recency_hours: float | None = None
        if latest_occurred_at:
            latest_dt = self._parse_iso_datetime(latest_occurred_at)
            if latest_dt is not None:
                anchor_kst = datetime.fromisoformat(f"{trade_date_iso}T15:30:00+09:00")
                anchor_utc = anchor_kst.astimezone(timezone.utc)
                delta = anchor_utc - latest_dt
                event_recency_hours = round(max(0.0, delta.total_seconds() / 3600.0), 2)

        return items, event_recency_hours

    def _load_disclosure_rows(
        self,
        connection,
        *,
        company_id: int,
        trade_date_iso: str,
    ) -> list[dict[str, Any]]:
        start_date = (date.fromisoformat(trade_date_iso) - timedelta(days=self.disclosure_lookback_days - 1)).isoformat()
        rows = connection.execute(
            """
            SELECT
                id,
                provider_document_id,
                title,
                summary,
                report_type,
                source_url,
                canonical_url,
                published_at,
                receipt_at,
                publisher
            FROM raw_documents
            WHERE provider = 'DART'
              AND document_type = 'DISCLOSURE'
              AND company_id = ?
              AND substr(COALESCE(receipt_at, published_at, created_at), 1, 10) >= ?
              AND substr(COALESCE(receipt_at, published_at, created_at), 1, 10) <= ?
            ORDER BY COALESCE(receipt_at, published_at, created_at) DESC, id DESC
            LIMIT 20
            """,
            (company_id, start_date, trade_date_iso),
        ).fetchall()
        return [dict(row) for row in rows]

    def _build_disclosure_context(self, *, disclosure_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "document_id": row.get("id"),
                "provider_document_id": row.get("provider_document_id"),
                "title": row.get("title"),
                "summary": row.get("summary"),
                "report_type": row.get("report_type"),
                "source_url": row.get("source_url"),
                "canonical_url": row.get("canonical_url"),
                "published_at": row.get("published_at"),
                "receipt_at": row.get("receipt_at"),
                "publisher": row.get("publisher"),
            }
            for row in disclosure_rows[:10]
        ]

    def _load_financial_snapshot(
        self,
        connection,
        *,
        company_id: int,
        trade_date_iso: str,
    ) -> dict[str, Any] | None:
        snapshot_row = connection.execute(
            """
            SELECT
                snapshot_date,
                fiscal_period,
                market_cap,
                per,
                pbr,
                roe,
                eps,
                bps,
                dividend_yield,
                revenue,
                operating_income,
                net_income,
                debt_ratio,
                currency,
                source_name,
                source_url,
                source_record_id
            FROM company_financial_snapshots
            WHERE company_id = ?
              AND snapshot_date <= ?
            ORDER BY snapshot_date DESC, id DESC
            LIMIT 1
            """,
            (company_id, trade_date_iso),
        ).fetchone()
        if snapshot_row is not None:
            row = dict(snapshot_row)
            return {
                "snapshot_date": row.get("snapshot_date"),
                "fiscal_period": row.get("fiscal_period"),
                "market_cap": self._as_float(row.get("market_cap")),
                "per": self._as_float(row.get("per")),
                "pbr": self._as_float(row.get("pbr")),
                "roe": self._as_float(row.get("roe")),
                "eps": self._as_float(row.get("eps")),
                "bps": self._as_float(row.get("bps")),
                "dividend_yield": self._as_float(row.get("dividend_yield")),
                "revenue": self._as_float(row.get("revenue")),
                "operating_income": self._as_float(row.get("operating_income")),
                "net_income": self._as_float(row.get("net_income")),
                "debt_ratio": self._as_float(row.get("debt_ratio")),
                "currency": row.get("currency"),
                "source_name": row.get("source_name"),
                "source_url": row.get("source_url"),
                "source_record_id": row.get("source_record_id"),
                "source_table": "company_financial_snapshots",
            }

        row = connection.execute(
            """
            SELECT source_metadata_json, source_url, source_record_id, updated_at
            FROM company_source_mappings
            WHERE company_id = ? AND source_system = 'KIS'
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (company_id,),
        ).fetchone()

        if row is None:
            return None

        metadata = self._json_load(row["source_metadata_json"])
        if not isinstance(metadata, dict):
            metadata = {}

        normalized_map = {str(key).lower(): value for key, value in metadata.items()}

        def pick(*candidates: str):
            for key in candidates:
                if key.lower() in normalized_map:
                    return normalized_map[key.lower()]
            return None

        snapshot = {
            "market_cap": pick("market_cap", "market_capitalization", "mkt_cap", "시가총액"),
            "per": pick("per"),
            "pbr": pick("pbr"),
            "roe": pick("roe"),
            "eps": pick("eps"),
            "bps": pick("bps"),
            "dividend_yield": pick("dividend_yield", "div_yield"),
            "source_name": "KIS_MAPPING_METADATA",
            "source_url": row["source_url"],
            "source_record_id": row["source_record_id"],
            "updated_at": row["updated_at"],
            "source_table": "company_source_mappings",
        }

        populated = {key: value for key, value in snapshot.items() if value not in {None, ""}}
        if len(populated) <= 3:
            return None
        return snapshot

    def _build_source_coverage(
        self,
        *,
        price_context: dict[str, Any],
        flow_context: dict[str, Any],
        event_context: list[dict[str, Any]],
        disclosure_context: list[dict[str, Any]],
        financial_snapshot: dict[str, Any] | None,
    ) -> dict[str, Any]:
        has_price = bool((price_context.get("summary") or {}).get("available"))
        has_flow = bool((flow_context.get("summary") or {}).get("available"))
        has_events = len(event_context) > 0
        has_disclosures = len(disclosure_context) > 0
        has_financial = financial_snapshot is not None

        available_count = sum([has_price, has_flow, has_events, has_disclosures, has_financial])
        coverage_ratio = round(available_count / 5.0, 3)

        return {
            "price_context": {
                "available": has_price,
                "observation_count": int((price_context.get("summary") or {}).get("observation_count") or 0),
                "source_table": (price_context.get("summary") or {}).get("source_table"),
            },
            "investor_flow": {
                "available": has_flow,
                "row_count": len(flow_context.get("rows") or []),
                "flow_scope": (flow_context.get("summary") or {}).get("flow_scope"),
                "source_table": (flow_context.get("summary") or {}).get("source_table"),
            },
            "events": {
                "available": has_events,
                "row_count": len(event_context),
                "latest_event_at": (event_context[0].get("occurred_at") if event_context else None),
            },
            "disclosures": {
                "available": has_disclosures,
                "row_count": len(disclosure_context),
            },
            "financial_snapshot": {
                "available": has_financial,
                "source_table": (financial_snapshot or {}).get("source_table"),
            },
            "coverage_ratio": coverage_ratio,
        }

    def _upsert_universe(
        self,
        connection,
        *,
        universe_key: str,
        universe_name: str,
        description: str | None,
        selection_mode: str,
        selection_config: dict[str, Any] | None,
        target_size: int,
        created_by: str,
    ) -> int:
        normalized_selection_mode = selection_mode.strip().upper()
        if normalized_selection_mode not in {"MANUAL", "FILTER", "MIXED"}:
            raise ValueError("selection_mode must be one of MANUAL, FILTER, MIXED")

        now = utcnow_iso()
        connection.execute(
            """
            INSERT INTO report_universes (
                universe_key,
                universe_name,
                market_scope,
                description,
                selection_mode,
                selection_config_json,
                target_size,
                is_active,
                created_by,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            ON CONFLICT(universe_key)
            DO UPDATE SET
                universe_name = excluded.universe_name,
                market_scope = excluded.market_scope,
                description = excluded.description,
                selection_mode = excluded.selection_mode,
                selection_config_json = excluded.selection_config_json,
                target_size = excluded.target_size,
                is_active = 1,
                updated_at = excluded.updated_at
            """,
            (
                universe_key,
                universe_name,
                self.market_scope,
                description,
                normalized_selection_mode,
                self._json_dump(selection_config),
                max(1, target_size),
                created_by,
                now,
                now,
            ),
        )

        row = connection.execute(
            "SELECT id FROM report_universes WHERE universe_key = ?",
            (universe_key,),
        ).fetchone()
        return int(row["id"])

    def _load_universe_by_key(self, connection, *, universe_key: str) -> dict[str, Any] | None:
        row = connection.execute(
            "SELECT * FROM report_universes WHERE universe_key = ?",
            (universe_key,),
        ).fetchone()
        if row is None:
            return None
        return self._deserialize_universe_row(dict(row))

    def _load_universe(self, connection, *, universe_id: int) -> dict[str, Any]:
        row = connection.execute(
            "SELECT * FROM report_universes WHERE id = ?",
            (universe_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"universe not found: {universe_id}")
        return self._deserialize_universe_row(dict(row))

    def _resolve_company_ids_by_stock_codes(
        self,
        connection,
        *,
        stock_codes: list[str],
    ) -> tuple[list[int], list[str]]:
        if not stock_codes:
            return [], []

        placeholders = ",".join("?" for _ in stock_codes)
        rows = connection.execute(
            f"""
            SELECT id, primary_stock_code
            FROM companies
            WHERE primary_stock_code IN ({placeholders})
              AND market = ?
              AND is_listed = 1
            """,
            [*stock_codes, "KR"],
        ).fetchall()

        resolved = {str(row["primary_stock_code"]): int(row["id"]) for row in rows}
        missing = [code for code in stock_codes if code not in resolved]
        company_ids = [resolved[code] for code in stock_codes if code in resolved]
        return company_ids, missing

    def _load_company_row(self, connection, *, company_id: int) -> dict[str, Any] | None:
        row = connection.execute(
            """
            SELECT
                id,
                canonical_name,
                primary_stock_code,
                market,
                market_classification,
                listing_status,
                is_listed
            FROM companies
            WHERE id = ?
            """,
            (company_id,),
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def _list_sections_for_report(self, connection, *, report_id: int) -> list[dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT section_key, section_title, section_order, content_markdown, content_json
            FROM company_report_sections
            WHERE report_id = ?
            ORDER BY section_order ASC
            """,
            (report_id,),
        ).fetchall()

        items: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["content"] = self._json_load(payload.pop("content_json", None))
            items.append(payload)
        return items

    def _deserialize_universe_row(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = dict(row)
        payload["selection_config"] = self._json_load(payload.pop("selection_config_json", None))
        return payload

    def _deserialize_report_row(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = dict(row)
        payload["input_payload"] = self._json_load(payload.pop("input_payload_json", None))
        payload["report_payload"] = self._json_load(payload.pop("report_payload_json", None))
        payload["source_coverage"] = self._json_load(payload.pop("source_coverage_json", None))
        payload["feature_snapshot"] = self._json_load(payload.pop("feature_snapshot_json", None))
        payload["metadata"] = self._json_load(payload.pop("metadata_json", None))
        return payload

    def _build_batch_run_key(self, *, trade_date_iso: str, universe_key: str, run_mode: str) -> str:
        suffix = uuid4().hex[:8]
        return f"{trade_date_iso}:{universe_key}:{run_mode.lower()}:{suffix}"

    def _normalize_run_mode(self, value: str) -> str:
        normalized = (value or "MANUAL").strip().upper()
        if normalized not in _ALLOWED_REPORT_RUN_MODES:
            raise ValueError(
                "run_mode must be one of SCHEDULED, MANUAL, BACKFILL, RERUN_FAILED, RERUN_SINGLE"
            )
        return normalized

    def _estimate_confidence_score(
        self,
        *,
        coverage_ratio: float,
        event_count: int,
        has_price: bool,
        has_flow: bool,
    ) -> float:
        score = 0.0
        score += min(max(coverage_ratio, 0.0), 1.0) * 0.45
        score += min(event_count / 4.0, 1.0) * 0.25
        score += 0.15 if has_price else 0.0
        score += 0.15 if has_flow else 0.0
        return round(min(score, 1.0), 3)

    def _confidence_bucket(self, score: float) -> str:
        if score >= 0.75:
            return "high"
        if score >= 0.45:
            return "medium"
        return "low"

    def _run_outcome_to_payload(self, outcome: CompanyReportRunOutcome) -> dict[str, Any]:
        return {
            "run_id": outcome.run_id,
            "batch_run_key": outcome.batch_run_key,
            "universe_key": outcome.universe_key,
            "company_id": outcome.company_id,
            "trade_date": outcome.trade_date,
            "status": outcome.status,
            "report_id": outcome.report_id,
            "generation_method": outcome.generation_method,
            "llm_provider": outcome.llm_provider,
            "llm_model": outcome.llm_model,
            "error_message": outcome.error_message,
        }

    def _sanitize_text(self, value: str) -> str:
        text = value.strip()
        replacements = {
            "매수": "판단",
            "매도": "판단",
            "투자 추천": "정보 요약",
            "목표주가": "가격 관찰",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    def _fmt_signed_number(self, value: float) -> str:
        rounded = round(value, 2)
        prefix = "+" if rounded > 0 else ""
        return f"{prefix}{rounded}"

    def _fmt_float(self, value: Any) -> str:
        parsed = self._as_float(value)
        if parsed is None:
            return "N/A"
        return f"{parsed:.3f}"

    def _as_float(self, value: Any) -> float | None:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _parse_iso_datetime(self, value: str) -> datetime | None:
        candidate = (value or "").strip()
        if not candidate:
            return None
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.astimezone(timezone.utc)
        return parsed

    @staticmethod
    def _pick_first(payload: dict[str, Any], *keys: str):
        for key in keys:
            if key not in payload:
                continue
            value = payload[key]
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            return value
        return None

    @staticmethod
    def _normalize_date_string(value: Any) -> str | None:
        if value is None:
            return None
        candidate = str(value).strip()
        if not candidate:
            return None

        try:
            if "T" in candidate:
                return datetime.fromisoformat(candidate.replace("Z", "+00:00")).date().isoformat()
            return date.fromisoformat(candidate[:10]).isoformat()
        except ValueError:
            return None

    @staticmethod
    def _json_dump(payload: Any) -> str | None:
        if payload is None:
            return None
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _json_load(payload: str | None) -> Any:
        if payload is None:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None
