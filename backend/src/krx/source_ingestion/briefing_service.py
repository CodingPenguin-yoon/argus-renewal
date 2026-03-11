from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import logging
import time
from typing import Any, Callable

from ..company_master.db import get_connection, utcnow_iso
from .briefing_models import (
    BriefingProviderBatch,
    BriefingInputRunResult,
    DerivativesDailyMetricRecord,
    GlobalInputProvider,
    MarketDailyFactorRecord,
    MarketIntradaySnapshotRecord,
)
from .providers import (
    KisDomesticDerivativesService,
    KisMarketBreadthService,
    KisNightFuturesService,
    KrxDerivativesReferenceService,
)

logger = logging.getLogger(__name__)

ProviderFetcher = Callable[[], Any]


class MarketBriefingInputService:
    def __init__(
        self,
        *,
        db_path: str,
        kis_market_breadth_service: KisMarketBreadthService,
        kis_domestic_derivatives_service: KisDomesticDerivativesService,
        kis_night_futures_service: KisNightFuturesService,
        krx_derivatives_reference_service: KrxDerivativesReferenceService,
        global_input_providers: list[GlobalInputProvider] | None = None,
    ) -> None:
        self.db_path = db_path
        self.kis_market_breadth_service = kis_market_breadth_service
        self.kis_domestic_derivatives_service = kis_domestic_derivatives_service
        self.kis_night_futures_service = kis_night_futures_service
        self.krx_derivatives_reference_service = krx_derivatives_reference_service
        self.global_input_providers = global_input_providers or []

    def collect_end_of_day_factors(
        self,
        *,
        trade_date: date,
        mode: str = "SCHEDULED",
    ) -> BriefingInputRunResult:
        provider_specs = [
            (
                "KIS_MARKET_BREADTH",
                "MARKET_DAILY_FACTORS",
                lambda: self.kis_market_breadth_service.fetch_market_daily_factors(trade_date=trade_date),
            ),
            (
                "KRX_DERIVATIVES_REFERENCE",
                "DERIVATIVES_DAILY_METRICS",
                lambda: self.krx_derivatives_reference_service.fetch_daily_metrics(trade_date=trade_date),
            ),
        ]
        return self._execute_provider_run(
            job_name="market_briefing_collect_end_of_day",
            mode=mode,
            trade_date=trade_date,
            provider_specs=provider_specs,
            metadata={"collector": "end_of_day"},
        )

    def collect_night_session_snapshots(
        self,
        *,
        trade_date: date,
        snapshot_time: datetime | None = None,
        mode: str = "SCHEDULED",
    ) -> BriefingInputRunResult:
        snapshot_at = snapshot_time or datetime.now(timezone.utc)
        provider_specs = [
            (
                "KIS_NIGHT_FUTURES",
                "MARKET_INTRADAY_SNAPSHOTS",
                lambda: self.kis_night_futures_service.fetch_night_session_snapshots(
                    trade_date=trade_date,
                    snapshot_time=snapshot_at,
                ),
            ),
        ]
        return self._execute_provider_run(
            job_name="market_briefing_collect_night_session",
            mode=mode,
            trade_date=trade_date,
            provider_specs=provider_specs,
            metadata={"collector": "night_session", "snapshot_time": snapshot_at.isoformat()},
        )

    def collect_pre_open_snapshots(
        self,
        *,
        trade_date: date,
        snapshot_time: datetime | None = None,
        mode: str = "SCHEDULED",
    ) -> BriefingInputRunResult:
        snapshot_at = snapshot_time or datetime.now(timezone.utc)

        provider_specs: list[tuple[str, str, ProviderFetcher]] = [
            (
                "KIS_DOMESTIC_DERIVATIVES",
                "MARKET_INTRADAY_SNAPSHOTS",
                lambda: self.kis_domestic_derivatives_service.fetch_pre_open_snapshots(
                    trade_date=trade_date,
                    snapshot_time=snapshot_at,
                ),
            ),
        ]

        for index, provider in enumerate(self.global_input_providers):
            provider_specs.append(
                (
                    f"GLOBAL_INPUT_PROVIDER_{index + 1}",
                    "MARKET_INTRADAY_SNAPSHOTS",
                    lambda provider=provider: provider.fetch_pre_open_inputs(
                        trade_date=trade_date,
                        snapshot_at=snapshot_at,
                    ),
                )
            )

        return self._execute_provider_run(
            job_name="market_briefing_collect_pre_open",
            mode=mode,
            trade_date=trade_date,
            provider_specs=provider_specs,
            metadata={"collector": "pre_open", "snapshot_time": snapshot_at.isoformat()},
        )

    def backfill_by_date_range(
        self,
        *,
        start_date: date,
        end_date: date,
        include_end_of_day: bool,
        include_night_session: bool,
        include_pre_open: bool,
    ) -> list[BriefingInputRunResult]:
        if end_date < start_date:
            raise ValueError("end_date must be greater than or equal to start_date")

        results: list[BriefingInputRunResult] = []
        cursor = start_date
        while cursor <= end_date:
            if include_end_of_day:
                results.append(self.collect_end_of_day_factors(trade_date=cursor, mode="BACKFILL"))
            if include_night_session:
                results.append(self.collect_night_session_snapshots(trade_date=cursor, mode="BACKFILL"))
            if include_pre_open:
                results.append(self.collect_pre_open_snapshots(trade_date=cursor, mode="BACKFILL"))
            cursor += timedelta(days=1)

        return results

    def manual_import_krx_derivatives_reference(
        self,
        *,
        trade_date: date,
        input_path: str,
    ) -> BriefingInputRunResult:
        provider_specs = [
            (
                "KRX_DERIVATIVES_MANUAL",
                "MANUAL_IMPORT",
                lambda: self._manual_krx_import_fetcher(trade_date=trade_date, input_path=input_path),
            )
        ]
        return self._execute_provider_run(
            job_name="market_briefing_manual_import_krx_derivatives",
            mode="MANUAL",
            trade_date=trade_date,
            provider_specs=provider_specs,
            metadata={"collector": "manual_import", "input_path": input_path},
        )

    def list_runs(
        self,
        *,
        limit: int,
        status: str | None = None,
        job_name: str | None = None,
    ) -> list[dict[str, Any]]:
        filters = []
        params: list[Any] = []
        if status:
            filters.append("status = ?")
            params.append(status)
        if job_name:
            filters.append("job_name = ?")
            params.append(job_name)

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM briefing_input_runs
                {where_clause}
                ORDER BY id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["metadata"] = self._json_load(payload.pop("metadata_json", None))
            results.append(payload)
        return results

    def list_provider_health_checks(
        self,
        *,
        limit: int,
        run_id: int | None = None,
        provider_name: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        filters = []
        params: list[Any] = []
        if run_id is not None:
            filters.append("run_id = ?")
            params.append(run_id)
        if provider_name:
            filters.append("provider_name = ?")
            params.append(provider_name)
        if status:
            filters.append("status = ?")
            params.append(status)

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM provider_health_checks
                {where_clause}
                ORDER BY id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["metadata"] = self._json_load(payload.pop("metadata_json", None))
            results.append(payload)
        return results

    def list_market_daily_factors(
        self,
        *,
        limit: int,
        trade_date: str | None = None,
        source_name: str | None = None,
    ) -> list[dict[str, Any]]:
        filters = []
        params: list[Any] = []
        if trade_date:
            filters.append("trade_date = ?")
            params.append(trade_date)
        if source_name:
            filters.append("source_name = ?")
            params.append(source_name)
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM market_daily_factors
                {where_clause}
                ORDER BY trade_date DESC, id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        return [self._deserialize_json_fields(dict(row)) for row in rows]

    def list_market_intraday_snapshots(
        self,
        *,
        limit: int,
        trade_date: str | None = None,
        session_type: str | None = None,
        source_name: str | None = None,
    ) -> list[dict[str, Any]]:
        filters = []
        params: list[Any] = []
        if trade_date:
            filters.append("trade_date = ?")
            params.append(trade_date)
        if session_type:
            filters.append("session_type = ?")
            params.append(session_type)
        if source_name:
            filters.append("source_name = ?")
            params.append(source_name)
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM market_intraday_snapshots
                {where_clause}
                ORDER BY trade_date DESC, snapshot_time DESC, id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        return [self._deserialize_json_fields(dict(row)) for row in rows]

    def list_derivatives_daily_metrics(
        self,
        *,
        limit: int,
        trade_date: str | None = None,
        source_name: str | None = None,
    ) -> list[dict[str, Any]]:
        filters = []
        params: list[Any] = []
        if trade_date:
            filters.append("trade_date = ?")
            params.append(trade_date)
        if source_name:
            filters.append("source_name = ?")
            params.append(source_name)
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM derivatives_daily_metrics
                {where_clause}
                ORDER BY trade_date DESC, id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        return [self._deserialize_json_fields(dict(row)) for row in rows]

    def _manual_krx_import_fetcher(self, *, trade_date: date, input_path: str):
        records = self.krx_derivatives_reference_service.load_manual_records(
            trade_date=trade_date,
            input_path=input_path,
        )
        return BriefingProviderBatch(
            records=records,
            metadata={"input_path": input_path, "record_count": len(records)},
            disabled_reason=None,
            retry_count=0,
        )

    def _execute_provider_run(
        self,
        *,
        job_name: str,
        mode: str,
        trade_date: date,
        provider_specs: list[tuple[str, str, ProviderFetcher]],
        metadata: dict[str, Any],
    ) -> BriefingInputRunResult:
        with get_connection(self.db_path) as connection:
            run_id = self._start_run(
                connection,
                job_name=job_name,
                mode=mode,
                trade_date=trade_date,
                start_date=trade_date,
                end_date=trade_date,
                metadata=metadata,
            )

            processed_provider_count = 0
            success_provider_count = 0
            failed_provider_count = 0
            skipped_provider_count = 0
            inserted_count = 0
            updated_count = 0
            provider_results: list[dict[str, Any]] = []

            try:
                for provider_name, provider_scope, fetcher in provider_specs:
                    processed_provider_count += 1
                    started = time.perf_counter()
                    try:
                        batch = fetcher()
                        latency_ms = int((time.perf_counter() - started) * 1000)

                        if getattr(batch, "disabled_reason", None):
                            skipped_provider_count += 1
                            payload = {
                                "provider_name": provider_name,
                                "provider_scope": provider_scope,
                                "status": "SKIPPED_DISABLED",
                                "latency_ms": latency_ms,
                                "retry_count": int(getattr(batch, "retry_count", 0)),
                                "inserted_count": 0,
                                "updated_count": 0,
                                "error_message": None,
                                "metadata": {
                                    **(getattr(batch, "metadata", {}) or {}),
                                    "disabled_reason": batch.disabled_reason,
                                },
                            }
                            provider_results.append(payload)
                            self._record_provider_health_check(connection, run_id=run_id, payload=payload)
                            continue

                        provider_inserted = 0
                        provider_updated = 0
                        for record in getattr(batch, "records", []):
                            inserted, updated = self._persist_record(
                                connection,
                                run_id=run_id,
                                record=record,
                            )
                            provider_inserted += int(inserted)
                            provider_updated += int(updated)

                        inserted_count += provider_inserted
                        updated_count += provider_updated
                        success_provider_count += 1

                        payload = {
                            "provider_name": provider_name,
                            "provider_scope": provider_scope,
                            "status": "SUCCESS",
                            "latency_ms": latency_ms,
                            "retry_count": int(getattr(batch, "retry_count", 0)),
                            "inserted_count": provider_inserted,
                            "updated_count": provider_updated,
                            "error_message": None,
                            "metadata": getattr(batch, "metadata", {}) or {},
                        }
                        provider_results.append(payload)
                        self._record_provider_health_check(connection, run_id=run_id, payload=payload)
                    except Exception as error:  # noqa: BLE001
                        failed_provider_count += 1
                        latency_ms = int((time.perf_counter() - started) * 1000)
                        logger.exception(
                            "market_briefing_provider_failed",
                            extra={
                                "run_id": run_id,
                                "job_name": job_name,
                                "provider_name": provider_name,
                                "provider_scope": provider_scope,
                                "error": str(error),
                            },
                        )
                        payload = {
                            "provider_name": provider_name,
                            "provider_scope": provider_scope,
                            "status": "FAILED",
                            "latency_ms": latency_ms,
                            "retry_count": 0,
                            "inserted_count": 0,
                            "updated_count": 0,
                            "error_message": str(error),
                            "metadata": {},
                        }
                        provider_results.append(payload)
                        self._record_provider_health_check(connection, run_id=run_id, payload=payload)

                status = self._resolve_run_status(
                    success_provider_count=success_provider_count,
                    failed_provider_count=failed_provider_count,
                    skipped_provider_count=skipped_provider_count,
                )

                self._finish_run(
                    connection,
                    run_id=run_id,
                    status=status,
                    processed_provider_count=processed_provider_count,
                    success_provider_count=success_provider_count,
                    failed_provider_count=failed_provider_count,
                    skipped_provider_count=skipped_provider_count,
                    inserted_count=inserted_count,
                    updated_count=updated_count,
                    metadata={
                        **metadata,
                        "provider_results": provider_results,
                    },
                    error_message=None,
                )

                return BriefingInputRunResult(
                    run_id=run_id,
                    status=status,
                    job_name=job_name,
                    mode=mode,
                    trade_date=trade_date.isoformat(),
                    start_date=trade_date.isoformat(),
                    end_date=trade_date.isoformat(),
                    processed_provider_count=processed_provider_count,
                    success_provider_count=success_provider_count,
                    failed_provider_count=failed_provider_count,
                    skipped_provider_count=skipped_provider_count,
                    inserted_count=inserted_count,
                    updated_count=updated_count,
                    provider_results=provider_results,
                )
            except Exception as error:  # noqa: BLE001
                self._finish_run(
                    connection,
                    run_id=run_id,
                    status="FAILED",
                    processed_provider_count=processed_provider_count,
                    success_provider_count=success_provider_count,
                    failed_provider_count=failed_provider_count,
                    skipped_provider_count=skipped_provider_count,
                    inserted_count=inserted_count,
                    updated_count=updated_count,
                    metadata={**metadata, "provider_results": provider_results},
                    error_message=str(error),
                )
                raise

    def _resolve_run_status(
        self,
        *,
        success_provider_count: int,
        failed_provider_count: int,
        skipped_provider_count: int,
    ) -> str:
        if failed_provider_count > 0 and success_provider_count == 0:
            return "FAILED"
        if failed_provider_count > 0:
            return "PARTIAL_SUCCESS"
        if success_provider_count == 0 and skipped_provider_count > 0:
            return "SKIPPED_DISABLED"
        return "SUCCESS"

    def _persist_record(
        self,
        connection,
        *,
        run_id: int,
        record: Any,
    ) -> tuple[bool, bool]:
        if isinstance(record, MarketDailyFactorRecord):
            return self._upsert_market_daily_factor(connection, run_id=run_id, record=record)
        if isinstance(record, MarketIntradaySnapshotRecord):
            return self._upsert_market_intraday_snapshot(connection, run_id=run_id, record=record)
        if isinstance(record, DerivativesDailyMetricRecord):
            return self._upsert_derivatives_daily_metric(connection, run_id=run_id, record=record)
        raise TypeError(f"Unsupported record type: {type(record)!r}")

    def _upsert_market_daily_factor(
        self,
        connection,
        *,
        run_id: int,
        record: MarketDailyFactorRecord,
    ) -> tuple[bool, bool]:
        existing = connection.execute(
            """
            SELECT id
            FROM market_daily_factors
            WHERE trade_date = ? AND source_name = ? AND market_scope = ?
            """,
            (record.trade_date, record.source_name, record.market_scope),
        ).fetchone()

        now = utcnow_iso()
        additional_metrics_json = json.dumps(record.additional_metrics, ensure_ascii=False, sort_keys=True)
        raw_payload_json = (
            json.dumps(record.raw_payload, ensure_ascii=False, sort_keys=True)
            if record.raw_payload is not None
            else None
        )

        if existing is None:
            connection.execute(
                """
                INSERT INTO market_daily_factors (
                    trade_date,
                    source_name,
                    market_scope,
                    investor_individual_net_buy,
                    investor_foreign_net_buy,
                    investor_institution_net_buy,
                    investor_other_net_buy,
                    investor_bank_net_buy,
                    investor_pension_net_buy,
                    program_buy_total,
                    program_sell_total,
                    program_net_total,
                    credit_balance_total,
                    margin_loan_balance,
                    stock_financing_balance,
                    securities_lending_balance,
                    additional_metrics_json,
                    source_url,
                    source_record_id,
                    raw_payload_json,
                    run_id,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.trade_date,
                    record.source_name,
                    record.market_scope,
                    record.investor_individual_net_buy,
                    record.investor_foreign_net_buy,
                    record.investor_institution_net_buy,
                    record.investor_other_net_buy,
                    record.investor_bank_net_buy,
                    record.investor_pension_net_buy,
                    record.program_buy_total,
                    record.program_sell_total,
                    record.program_net_total,
                    record.credit_balance_total,
                    record.margin_loan_balance,
                    record.stock_financing_balance,
                    record.securities_lending_balance,
                    additional_metrics_json,
                    record.source_url,
                    record.source_record_id,
                    raw_payload_json,
                    run_id,
                    now,
                    now,
                ),
            )
            return True, False

        connection.execute(
            """
            UPDATE market_daily_factors
            SET
                investor_individual_net_buy = ?,
                investor_foreign_net_buy = ?,
                investor_institution_net_buy = ?,
                investor_other_net_buy = ?,
                investor_bank_net_buy = ?,
                investor_pension_net_buy = ?,
                program_buy_total = ?,
                program_sell_total = ?,
                program_net_total = ?,
                credit_balance_total = ?,
                margin_loan_balance = ?,
                stock_financing_balance = ?,
                securities_lending_balance = ?,
                additional_metrics_json = ?,
                source_url = ?,
                source_record_id = ?,
                raw_payload_json = ?,
                run_id = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                record.investor_individual_net_buy,
                record.investor_foreign_net_buy,
                record.investor_institution_net_buy,
                record.investor_other_net_buy,
                record.investor_bank_net_buy,
                record.investor_pension_net_buy,
                record.program_buy_total,
                record.program_sell_total,
                record.program_net_total,
                record.credit_balance_total,
                record.margin_loan_balance,
                record.stock_financing_balance,
                record.securities_lending_balance,
                additional_metrics_json,
                record.source_url,
                record.source_record_id,
                raw_payload_json,
                run_id,
                now,
                int(existing["id"]),
            ),
        )
        return False, True

    def _upsert_market_intraday_snapshot(
        self,
        connection,
        *,
        run_id: int,
        record: MarketIntradaySnapshotRecord,
    ) -> tuple[bool, bool]:
        existing = connection.execute(
            """
            SELECT id
            FROM market_intraday_snapshots
            WHERE
                trade_date = ?
                AND snapshot_time = ?
                AND session_type = ?
                AND source_name = ?
                AND instrument_code = ?
            """,
            (
                record.trade_date,
                record.snapshot_time,
                record.session_type,
                record.source_name,
                record.instrument_code,
            ),
        ).fetchone()

        now = utcnow_iso()
        additional_metrics_json = json.dumps(record.additional_metrics, ensure_ascii=False, sort_keys=True)
        raw_payload_json = (
            json.dumps(record.raw_payload, ensure_ascii=False, sort_keys=True)
            if record.raw_payload is not None
            else None
        )

        if existing is None:
            connection.execute(
                """
                INSERT INTO market_intraday_snapshots (
                    trade_date,
                    snapshot_time,
                    session_type,
                    source_name,
                    instrument_code,
                    instrument_name,
                    price,
                    price_change,
                    change_rate,
                    volume,
                    open_interest,
                    put_call_ratio,
                    implied_volatility,
                    additional_metrics_json,
                    source_url,
                    source_record_id,
                    raw_payload_json,
                    run_id,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.trade_date,
                    record.snapshot_time,
                    record.session_type,
                    record.source_name,
                    record.instrument_code,
                    record.instrument_name,
                    record.price,
                    record.price_change,
                    record.change_rate,
                    record.volume,
                    record.open_interest,
                    record.put_call_ratio,
                    record.implied_volatility,
                    additional_metrics_json,
                    record.source_url,
                    record.source_record_id,
                    raw_payload_json,
                    run_id,
                    now,
                    now,
                ),
            )
            return True, False

        connection.execute(
            """
            UPDATE market_intraday_snapshots
            SET
                instrument_name = ?,
                price = ?,
                price_change = ?,
                change_rate = ?,
                volume = ?,
                open_interest = ?,
                put_call_ratio = ?,
                implied_volatility = ?,
                additional_metrics_json = ?,
                source_url = ?,
                source_record_id = ?,
                raw_payload_json = ?,
                run_id = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                record.instrument_name,
                record.price,
                record.price_change,
                record.change_rate,
                record.volume,
                record.open_interest,
                record.put_call_ratio,
                record.implied_volatility,
                additional_metrics_json,
                record.source_url,
                record.source_record_id,
                raw_payload_json,
                run_id,
                now,
                int(existing["id"]),
            ),
        )
        return False, True

    def _upsert_derivatives_daily_metric(
        self,
        connection,
        *,
        run_id: int,
        record: DerivativesDailyMetricRecord,
    ) -> tuple[bool, bool]:
        existing = connection.execute(
            """
            SELECT id
            FROM derivatives_daily_metrics
            WHERE trade_date = ? AND source_name = ? AND metric_scope = ?
            """,
            (record.trade_date, record.source_name, record.metric_scope),
        ).fetchone()

        now = utcnow_iso()
        additional_metrics_json = json.dumps(record.additional_metrics, ensure_ascii=False, sort_keys=True)
        raw_payload_json = (
            json.dumps(record.raw_payload, ensure_ascii=False, sort_keys=True)
            if record.raw_payload is not None
            else None
        )

        if existing is None:
            connection.execute(
                """
                INSERT INTO derivatives_daily_metrics (
                    trade_date,
                    source_name,
                    metric_scope,
                    put_call_ratio,
                    implied_volatility,
                    open_interest_total,
                    call_open_interest,
                    put_open_interest,
                    futures_investor_foreign_net_buy,
                    futures_investor_institution_net_buy,
                    futures_investor_individual_net_buy,
                    options_investor_foreign_net_buy,
                    options_investor_institution_net_buy,
                    options_investor_individual_net_buy,
                    futures_volume_total,
                    options_volume_total,
                    additional_metrics_json,
                    source_url,
                    source_record_id,
                    raw_payload_json,
                    run_id,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.trade_date,
                    record.source_name,
                    record.metric_scope,
                    record.put_call_ratio,
                    record.implied_volatility,
                    record.open_interest_total,
                    record.call_open_interest,
                    record.put_open_interest,
                    record.futures_investor_foreign_net_buy,
                    record.futures_investor_institution_net_buy,
                    record.futures_investor_individual_net_buy,
                    record.options_investor_foreign_net_buy,
                    record.options_investor_institution_net_buy,
                    record.options_investor_individual_net_buy,
                    record.futures_volume_total,
                    record.options_volume_total,
                    additional_metrics_json,
                    record.source_url,
                    record.source_record_id,
                    raw_payload_json,
                    run_id,
                    now,
                    now,
                ),
            )
            return True, False

        connection.execute(
            """
            UPDATE derivatives_daily_metrics
            SET
                put_call_ratio = ?,
                implied_volatility = ?,
                open_interest_total = ?,
                call_open_interest = ?,
                put_open_interest = ?,
                futures_investor_foreign_net_buy = ?,
                futures_investor_institution_net_buy = ?,
                futures_investor_individual_net_buy = ?,
                options_investor_foreign_net_buy = ?,
                options_investor_institution_net_buy = ?,
                options_investor_individual_net_buy = ?,
                futures_volume_total = ?,
                options_volume_total = ?,
                additional_metrics_json = ?,
                source_url = ?,
                source_record_id = ?,
                raw_payload_json = ?,
                run_id = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                record.put_call_ratio,
                record.implied_volatility,
                record.open_interest_total,
                record.call_open_interest,
                record.put_open_interest,
                record.futures_investor_foreign_net_buy,
                record.futures_investor_institution_net_buy,
                record.futures_investor_individual_net_buy,
                record.options_investor_foreign_net_buy,
                record.options_investor_institution_net_buy,
                record.options_investor_individual_net_buy,
                record.futures_volume_total,
                record.options_volume_total,
                additional_metrics_json,
                record.source_url,
                record.source_record_id,
                raw_payload_json,
                run_id,
                now,
                int(existing["id"]),
            ),
        )
        return False, True

    def _start_run(
        self,
        connection,
        *,
        job_name: str,
        mode: str,
        trade_date: date | None,
        start_date: date | None,
        end_date: date | None,
        metadata: dict[str, Any],
    ) -> int:
        started_at = utcnow_iso()
        connection.execute(
            """
            INSERT INTO briefing_input_runs (
                job_name,
                mode,
                trade_date,
                start_date,
                end_date,
                status,
                started_at,
                metadata_json
            ) VALUES (?, ?, ?, ?, ?, 'RUNNING', ?, ?)
            """,
            (
                job_name,
                mode,
                trade_date.isoformat() if trade_date else None,
                start_date.isoformat() if start_date else None,
                end_date.isoformat() if end_date else None,
                started_at,
                json.dumps(metadata, ensure_ascii=False, sort_keys=True),
            ),
        )
        row = connection.execute("SELECT last_insert_rowid() AS id").fetchone()
        return int(row["id"])

    def _finish_run(
        self,
        connection,
        *,
        run_id: int,
        status: str,
        processed_provider_count: int,
        success_provider_count: int,
        failed_provider_count: int,
        skipped_provider_count: int,
        inserted_count: int,
        updated_count: int,
        metadata: dict[str, Any],
        error_message: str | None,
    ) -> None:
        connection.execute(
            """
            UPDATE briefing_input_runs
            SET
                status = ?,
                finished_at = ?,
                processed_provider_count = ?,
                success_provider_count = ?,
                failed_provider_count = ?,
                skipped_provider_count = ?,
                inserted_count = ?,
                updated_count = ?,
                metadata_json = ?,
                error_message = ?
            WHERE id = ?
            """,
            (
                status,
                utcnow_iso(),
                processed_provider_count,
                success_provider_count,
                failed_provider_count,
                skipped_provider_count,
                inserted_count,
                updated_count,
                json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                error_message,
                run_id,
            ),
        )

    def _record_provider_health_check(self, connection, *, run_id: int, payload: dict[str, Any]) -> None:
        connection.execute(
            """
            INSERT INTO provider_health_checks (
                run_id,
                provider_name,
                provider_scope,
                status,
                checked_at,
                latency_ms,
                retry_count,
                inserted_count,
                updated_count,
                metadata_json,
                error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, provider_name, provider_scope)
            DO UPDATE SET
                status = excluded.status,
                checked_at = excluded.checked_at,
                latency_ms = excluded.latency_ms,
                retry_count = excluded.retry_count,
                inserted_count = excluded.inserted_count,
                updated_count = excluded.updated_count,
                metadata_json = excluded.metadata_json,
                error_message = excluded.error_message
            """,
            (
                run_id,
                payload["provider_name"],
                payload["provider_scope"],
                payload["status"],
                utcnow_iso(),
                payload.get("latency_ms"),
                int(payload.get("retry_count") or 0),
                int(payload.get("inserted_count") or 0),
                int(payload.get("updated_count") or 0),
                json.dumps(payload.get("metadata") or {}, ensure_ascii=False, sort_keys=True),
                payload.get("error_message"),
            ),
        )

    def _json_load(self, value: str | None) -> Any:
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None

    def _deserialize_json_fields(self, payload: dict[str, Any]) -> dict[str, Any]:
        if "additional_metrics_json" in payload:
            payload["additional_metrics"] = self._json_load(payload.pop("additional_metrics_json"))
        if "raw_payload_json" in payload:
            payload["raw_payload"] = self._json_load(payload.pop("raw_payload_json"))
        if "metadata_json" in payload:
            payload["metadata"] = self._json_load(payload.pop("metadata_json"))
        return payload
