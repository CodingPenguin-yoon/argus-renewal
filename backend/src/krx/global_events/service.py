from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
import json
import logging
import sqlite3
from typing import Any
from zoneinfo import ZoneInfo

from ..company_master.db import get_connection, utcnow_iso
from .adapters import candidate_to_payload
from .impact_llm import (
    DisabledGlobalEventImpactProvider,
    GlobalEventImpactProvider,
    GlobalEventImpactRequest,
)
from .models import (
    GlobalEventCoverageSnapshot,
    GlobalEventReleaseAdapter,
    GlobalEventReleaseCandidate,
    GlobalEventScheduleAdapter,
    GlobalEventScheduleCandidate,
    GlobalEventVendorAdapter,
    GlobalEventsSyncResult,
)

logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")


def _json_dump(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_load(value: str | None) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _fmt_number(value: float | None, unit: str | None) -> str | None:
    if value is None:
        return None
    if unit == "pct":
        sign = "+" if value > 0 else ""
        return f"{sign}{value:.2f}%"
    if unit == "k_jobs":
        sign = "+" if value > 0 else ""
        return f"{sign}{value:.1f}k"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}"


def _coverage_status(available_count: int, expected_count: int) -> tuple[str, float]:
    if expected_count <= 0:
        return "full", 1.0
    ratio = round(min(max(available_count / expected_count, 0.0), 1.0), 4)
    if ratio >= 0.999:
        return "full", ratio
    if ratio > 0:
        return "partial", ratio
    return "empty", ratio


class GlobalEventsService:
    def __init__(
        self,
        *,
        db_path: str,
        schedule_adapters: list[GlobalEventScheduleAdapter],
        release_adapters: list[GlobalEventReleaseAdapter],
        vendor_adapter: GlobalEventVendorAdapter | None = None,
        impact_provider: GlobalEventImpactProvider | None = None,
        sync_enabled: bool = True,
        release_lookback_days: int = 120,
    ) -> None:
        self.db_path = db_path
        self.schedule_adapters = schedule_adapters
        self.release_adapters = release_adapters
        self.vendor_adapter = vendor_adapter
        self.impact_provider = impact_provider or DisabledGlobalEventImpactProvider()
        self.sync_enabled = sync_enabled
        self.release_lookback_days = max(1, release_lookback_days)

    def sync(self, *, start_date: date, end_date: date) -> GlobalEventsSyncResult:
        started_at = utcnow_iso()
        if not self.sync_enabled:
            return GlobalEventsSyncResult(
                status="SKIPPED_DISABLED",
                started_at=started_at,
                finished_at=utcnow_iso(),
                schedule_upserted=0,
                release_upserted=0,
                impacts_upserted=0,
                provider_results=[],
                error_message="global_events_sync_disabled",
            )

        provider_results: list[dict[str, Any]] = []
        schedule_candidates: list[GlobalEventScheduleCandidate] = []
        release_candidates: list[GlobalEventReleaseCandidate] = []
        coverage_snapshots: list[GlobalEventCoverageSnapshot] = []
        seen_keys_by_source: dict[str, set[str]] = defaultdict(set)
        schedule_upserted = 0
        release_upserted = 0
        impacts_upserted = 0
        failed_count = 0

        logger.info(
            "global_event_sync_start",
            extra={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )

        for adapter in self.schedule_adapters:
            try:
                items, coverage = adapter.fetch(start_date=start_date, end_date=end_date)
                schedule_candidates.extend(items)
                coverage_snapshots.append(coverage)
                seen_keys_by_source[adapter.source_key].update(item.event_key for item in items)
                provider_results.append(
                    {
                        "source_key": adapter.source_key,
                        "source_kind": "schedule",
                        "status": coverage.status,
                        "item_count": len(items),
                        "note": coverage.note,
                    }
                )
            except Exception as error:  # noqa: BLE001
                failed_count += 1
                logger.warning(
                    "global_event_schedule_adapter_failed",
                    extra={"source_key": adapter.source_key, "error": str(error)},
                )
                coverage_snapshots.append(
                    self._missing_coverage(
                        source_key=adapter.source_key,
                        source_name=adapter.source_name,
                        source_kind="schedule",
                        source_url=adapter.source_url,
                        is_required=adapter.is_required,
                        note=str(error),
                    )
                )
                provider_results.append(
                    {
                        "source_key": adapter.source_key,
                        "source_kind": "schedule",
                        "status": "missing",
                        "item_count": 0,
                        "note": str(error),
                    }
                )

        if self.vendor_adapter is not None:
            try:
                batch = self.vendor_adapter.fetch(start_date=start_date, end_date=end_date)
                schedule_candidates.extend(batch.schedules)
                release_candidates.extend(batch.releases)
                coverage_snapshots.append(batch.coverage)
                seen_keys_by_source[self.vendor_adapter.source_key].update(item.event_key for item in batch.schedules)
                provider_results.append(
                    {
                        "source_key": self.vendor_adapter.source_key,
                        "source_kind": "vendor",
                        "status": batch.coverage.status,
                        "item_count": len(batch.schedules) + len(batch.releases),
                        "note": batch.coverage.note,
                    }
                )
            except Exception as error:  # noqa: BLE001
                failed_count += 1
                logger.warning(
                    "global_event_vendor_adapter_failed",
                    extra={"source_key": self.vendor_adapter.source_key, "error": str(error)},
                )
                coverage_snapshots.append(
                    self._missing_coverage(
                        source_key=self.vendor_adapter.source_key,
                        source_name=self.vendor_adapter.source_name,
                        source_kind="vendor",
                        source_url=self.vendor_adapter.source_url,
                        is_required=self.vendor_adapter.is_required,
                        note=str(error),
                    )
                )
                provider_results.append(
                    {
                        "source_key": self.vendor_adapter.source_key,
                        "source_kind": "vendor",
                        "status": "missing",
                        "item_count": 0,
                        "note": str(error),
                    }
                )

        with get_connection(self.db_path) as connection:
            for candidate in schedule_candidates:
                schedule_upserted += self._upsert_schedule(connection, candidate)

            for source_key, seen_keys in seen_keys_by_source.items():
                self._mark_removed_events(
                    connection,
                    source_key=source_key,
                    start_date=start_date,
                    end_date=end_date,
                    seen_event_keys=seen_keys,
                )

            release_scope_start = start_date - timedelta(days=self.release_lookback_days)
            release_scope_events = self._select_schedule_rows(connection, start_date=release_scope_start, end_date=end_date)

            for adapter in self.release_adapters:
                try:
                    items, coverage = adapter.fetch(events=release_scope_events)
                    release_candidates.extend(items)
                    coverage_snapshots.append(coverage)
                    provider_results.append(
                        {
                            "source_key": adapter.source_key,
                            "source_kind": "release",
                            "status": coverage.status,
                            "item_count": len(items),
                            "note": coverage.note,
                        }
                    )
                except Exception as error:  # noqa: BLE001
                    failed_count += 1
                    logger.warning(
                        "global_event_release_adapter_failed",
                        extra={"source_key": adapter.source_key, "error": str(error)},
                    )
                    coverage_snapshots.append(
                        self._missing_coverage(
                            source_key=adapter.source_key,
                            source_name=adapter.source_name,
                            source_kind="release",
                            source_url=adapter.source_url,
                            is_required=adapter.is_required,
                            note=str(error),
                        )
                    )
                    provider_results.append(
                        {
                            "source_key": adapter.source_key,
                            "source_kind": "release",
                            "status": "missing",
                            "item_count": 0,
                            "note": str(error),
                        }
                    )

            for candidate in release_candidates:
                release_upserted += self._upsert_release(connection, candidate)

            impact_rows = self._select_rows_for_impact(connection, start_date=start_date - timedelta(days=1), end_date=end_date)
            for row in impact_rows:
                impacts_upserted += self._upsert_impact(connection, row)

            for coverage in coverage_snapshots:
                self._upsert_coverage(connection, coverage)

        status = "SUCCESS"
        if failed_count and (schedule_upserted or release_upserted or impacts_upserted):
            status = "PARTIAL_SUCCESS"
        elif failed_count and not (schedule_upserted or release_upserted or impacts_upserted):
            status = "FAILED"

        result = GlobalEventsSyncResult(
            status=status,
            started_at=started_at,
            finished_at=utcnow_iso(),
            schedule_upserted=schedule_upserted,
            release_upserted=release_upserted,
            impacts_upserted=impacts_upserted,
            provider_results=provider_results,
            error_message=None if status != "FAILED" else "global_event_sync_failed",
        )

        logger.info(
            "global_event_sync_complete",
            extra={
                "status": result.status,
                "schedule_upserted": schedule_upserted,
                "release_upserted": release_upserted,
                "impacts_upserted": impacts_upserted,
                "provider_results": provider_results,
            },
        )
        return result

    def get_upcoming(self, *, window_hours: int = 24) -> dict[str, Any]:
        now_kst = datetime.now(_KST)
        end_kst = now_kst + timedelta(hours=max(1, window_hours))
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    s.*,
                    r.metric_code,
                    r.release_state,
                    r.unit,
                    r.previous_value,
                    r.previous_display,
                    r.forecast_value,
                    r.forecast_display,
                    r.actual_value,
                    r.actual_display,
                    r.surprise_value,
                    r.surprise_display,
                    r.source_name AS release_source_name,
                    r.source_url AS release_source_url,
                    r.source_record_id,
                    r.actual_released_at,
                    r.provenance_json AS release_provenance_json,
                    i.summary_ko,
                    i.tone,
                    i.impact_channels_json,
                    i.generation_method,
                    i.provider_name,
                    i.model_name,
                    i.provenance_json AS impact_provenance_json
                FROM global_event_schedule s
                LEFT JOIN global_event_releases r ON r.schedule_id = s.id
                LEFT JOIN global_event_impacts i ON i.schedule_id = s.id AND i.status = 'active'
                WHERE s.status != 'cancelled'
                  AND (
                    (s.event_time_precision = 'time' AND s.sort_at_kst >= ? AND s.sort_at_kst < ?)
                    OR
                    (s.event_time_precision = 'date' AND s.event_date_kst >= ? AND s.event_date_kst <= ?)
                  )
                ORDER BY s.sort_at_kst ASC, s.id ASC
                """,
                (
                    now_kst.replace(microsecond=0).isoformat(),
                    end_kst.replace(microsecond=0).isoformat(),
                    now_kst.date().isoformat(),
                    end_kst.date().isoformat(),
                ),
            ).fetchall()
        return {
            "window": f"{window_hours}h",
            "updated_at": self._latest_row_timestamp(rows),
            "items": [self._serialize_event(row) for row in rows],
        }

    def get_week(self, *, anchor: date | None = None) -> dict[str, Any]:
        anchor_date = anchor or datetime.now(_KST).date()
        week_start = anchor_date - timedelta(days=anchor_date.weekday())
        week_end = week_start + timedelta(days=6)
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    s.*,
                    r.metric_code,
                    r.release_state,
                    r.unit,
                    r.previous_value,
                    r.previous_display,
                    r.forecast_value,
                    r.forecast_display,
                    r.actual_value,
                    r.actual_display,
                    r.surprise_value,
                    r.surprise_display,
                    r.source_name AS release_source_name,
                    r.source_url AS release_source_url,
                    r.source_record_id,
                    r.actual_released_at,
                    r.provenance_json AS release_provenance_json,
                    i.summary_ko,
                    i.tone,
                    i.impact_channels_json,
                    i.generation_method,
                    i.provider_name,
                    i.model_name,
                    i.provenance_json AS impact_provenance_json
                FROM global_event_schedule s
                LEFT JOIN global_event_releases r ON r.schedule_id = s.id
                LEFT JOIN global_event_impacts i ON i.schedule_id = s.id AND i.status = 'active'
                WHERE s.status != 'cancelled'
                  AND s.event_date_kst >= ?
                  AND s.event_date_kst <= ?
                ORDER BY s.sort_at_kst ASC, s.id ASC
                """,
                (week_start.isoformat(), week_end.isoformat()),
            ).fetchall()
        return {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "updated_at": self._latest_row_timestamp(rows),
            "items": [self._serialize_event(row) for row in rows],
        }

    def get_highlight(self, *, anchor: date | None = None, limit: int = 6) -> dict[str, Any]:
        payload = self.get_week(anchor=anchor)
        items = payload["items"]
        ranked = sorted(
            items,
            key=lambda item: (
                {"high": 0, "medium": 1, "low": 2}.get(item.get("importance") or "medium", 1),
                item.get("event_time_kst") or item.get("event_date_kst") or "9999-12-31",
            ),
        )
        payload["items"] = ranked[: max(1, limit)]
        return payload

    def get_coverage(self) -> dict[str, Any]:
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM global_event_source_coverage
                ORDER BY is_required DESC, source_kind ASC, source_key ASC
                """
            ).fetchall()

        if not rows:
            return {
                "state": "empty",
                "coverage_ratio": 0,
                "available_sources": 0,
                "expected_sources": 0,
                "summary": "글로벌 이벤트 동기화 이력이 아직 없습니다.",
                "updated_at": None,
                "items": [],
            }

        required_rows = [row for row in rows if int(row["is_required"] or 0) == 1]
        available_required = sum(1 for row in required_rows if row["status"] == "available")
        status, ratio = _coverage_status(available_required, len(required_rows))
        return {
            "state": status,
            "coverage_ratio": ratio,
            "available_sources": available_required,
            "expected_sources": len(required_rows),
            "summary": self._coverage_summary(status=status, available=available_required, expected=len(required_rows)),
            "updated_at": self._latest_row_timestamp(rows),
            "items": [
                {
                    "source_key": row["source_key"],
                    "source_name": row["source_name"],
                    "source_kind": row["source_kind"],
                    "is_required": bool(row["is_required"]),
                    "status": row["status"],
                    "available_count": int(row["available_count"] or 0),
                    "expected_count": int(row["expected_count"] or 0),
                    "coverage_ratio": float(row["coverage_ratio"] or 0.0),
                    "event_types": _json_load(row["event_types_json"]) or [],
                    "last_synced_at": row["last_synced_at"],
                    "last_success_at": row["last_success_at"],
                    "source_url": row["source_url"],
                    "note": row["note"],
                    "metadata": _json_load(row["metadata_json"]) or {},
                }
                for row in rows
            ],
        }

    def _upsert_schedule(self, connection: sqlite3.Connection, candidate: GlobalEventScheduleCandidate) -> int:
        payload = candidate_to_payload(candidate)
        now = utcnow_iso()
        existing = connection.execute(
            "SELECT id, event_time_kst, status FROM global_event_schedule WHERE event_key = ?",
            (candidate.event_key,),
        ).fetchone()

        status = payload["status"]
        previous_event_time_kst = None
        revision_note = None
        created_at = now
        if existing is not None:
            created_row = connection.execute(
                "SELECT created_at FROM global_event_schedule WHERE id = ?",
                (existing["id"],),
            ).fetchone()
            created_at = created_row["created_at"] if created_row is not None else now
            if existing["event_time_kst"] != payload["event_time_kst"] and existing["event_time_kst"] and payload["event_time_kst"]:
                status = "revised"
                previous_event_time_kst = existing["event_time_kst"]
                revision_note = "schedule_time_updated"
            elif existing["status"] == "released":
                status = "released"

        connection.execute(
            """
            INSERT INTO global_event_schedule (
                event_key,
                source_key,
                source_event_id,
                event_type,
                title,
                category,
                country,
                market_scope,
                event_date_kst,
                event_time_kst,
                event_time_utc,
                event_time_precision,
                sort_at_kst,
                source_timezone,
                reference_period,
                status,
                importance,
                importance_source,
                why_it_matters_ko,
                source_name,
                source_url,
                revision_note,
                previous_event_time_kst,
                source_updated_at,
                last_seen_at,
                provenance_json,
                raw_payload_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_key) DO UPDATE SET
                source_key = excluded.source_key,
                source_event_id = excluded.source_event_id,
                event_type = excluded.event_type,
                title = excluded.title,
                category = excluded.category,
                country = excluded.country,
                market_scope = excluded.market_scope,
                event_date_kst = excluded.event_date_kst,
                event_time_kst = excluded.event_time_kst,
                event_time_utc = excluded.event_time_utc,
                event_time_precision = excluded.event_time_precision,
                sort_at_kst = excluded.sort_at_kst,
                source_timezone = excluded.source_timezone,
                reference_period = excluded.reference_period,
                status = excluded.status,
                importance = excluded.importance,
                importance_source = excluded.importance_source,
                why_it_matters_ko = excluded.why_it_matters_ko,
                source_name = excluded.source_name,
                source_url = excluded.source_url,
                revision_note = excluded.revision_note,
                previous_event_time_kst = excluded.previous_event_time_kst,
                source_updated_at = excluded.source_updated_at,
                last_seen_at = excluded.last_seen_at,
                provenance_json = excluded.provenance_json,
                raw_payload_json = excluded.raw_payload_json,
                updated_at = excluded.updated_at
            """,
            (
                candidate.event_key,
                candidate.source_key,
                candidate.source_event_id,
                candidate.event_type,
                candidate.title,
                candidate.category,
                candidate.country,
                "KRX",
                payload["event_date_kst"],
                payload["event_time_kst"],
                payload["event_time_utc"],
                candidate.event_time_precision,
                payload["sort_at_kst"],
                candidate.source_timezone,
                candidate.reference_period,
                status,
                candidate.importance,
                candidate.importance_source,
                candidate.why_it_matters_ko,
                candidate.source_name,
                candidate.source_url,
                revision_note,
                previous_event_time_kst,
                candidate.source_updated_at,
                now,
                _json_dump(candidate.provenance),
                _json_dump(candidate.raw_payload),
                created_at,
                now,
            ),
        )
        return 1

    def _mark_removed_events(
        self,
        connection: sqlite3.Connection,
        *,
        source_key: str,
        start_date: date,
        end_date: date,
        seen_event_keys: set[str],
    ) -> None:
        placeholders = ",".join("?" for _ in seen_event_keys) if seen_event_keys else None
        base_query = """
            UPDATE global_event_schedule
            SET status = 'cancelled',
                revision_note = 'source_schedule_removed',
                updated_at = ?
            WHERE source_key = ?
              AND event_date_kst >= ?
              AND event_date_kst <= ?
              AND status != 'released'
        """
        params: list[Any] = [utcnow_iso(), source_key, start_date.isoformat(), end_date.isoformat()]
        if placeholders:
            base_query += f" AND event_key NOT IN ({placeholders})"
            params.extend(sorted(seen_event_keys))
        connection.execute(base_query, params)

    def _select_schedule_rows(self, connection: sqlite3.Connection, *, start_date: date, end_date: date) -> list[dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT *
            FROM global_event_schedule
            WHERE status != 'cancelled'
              AND event_date_kst >= ?
              AND event_date_kst <= ?
            ORDER BY event_date_kst ASC, sort_at_kst ASC
            """,
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchall()
        return [dict(row) for row in rows]

    def _upsert_release(self, connection: sqlite3.Connection, candidate: GlobalEventReleaseCandidate) -> int:
        schedule = connection.execute(
            "SELECT id, status FROM global_event_schedule WHERE event_key = ?",
            (candidate.event_key,),
        ).fetchone()
        if schedule is None:
            logger.info(
                "global_event_release_schedule_missing",
                extra={"event_key": candidate.event_key, "metric_code": candidate.metric_code},
            )
            return 0

        schedule_id = int(schedule["id"])
        now = utcnow_iso()
        existing = connection.execute(
            "SELECT * FROM global_event_releases WHERE schedule_id = ?",
            (schedule_id,),
        ).fetchone()

        existing_provenance = _json_load(existing["provenance_json"]) if existing else {}
        merged_provenance = self._merge_release_provenance(existing_provenance, candidate)

        previous_value = candidate.previous_value if candidate.previous_value is not None else _as_float(existing["previous_value"]) if existing else None
        forecast_value = candidate.forecast_value if candidate.forecast_value is not None else _as_float(existing["forecast_value"]) if existing else None
        actual_value = candidate.actual_value if candidate.actual_value is not None else _as_float(existing["actual_value"]) if existing else None
        surprise_value = candidate.surprise_value
        if surprise_value is None and actual_value is not None and forecast_value is not None:
            surprise_value = round(actual_value - forecast_value, 4)
        if surprise_value is None and existing is not None:
            surprise_value = _as_float(existing["surprise_value"])

        release_state = self._resolve_release_state(
            candidate_release_state=candidate.release_state,
            existing=existing,
            forecast_value=forecast_value,
            actual_value=actual_value,
        )
        created_at = existing["created_at"] if existing is not None else now

        connection.execute(
            """
            INSERT INTO global_event_releases (
                schedule_id,
                metric_code,
                unit,
                release_state,
                previous_value,
                previous_display,
                forecast_value,
                forecast_display,
                actual_value,
                actual_display,
                surprise_value,
                surprise_display,
                source_name,
                source_url,
                source_record_id,
                actual_released_at,
                provenance_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(schedule_id) DO UPDATE SET
                metric_code = excluded.metric_code,
                unit = excluded.unit,
                release_state = excluded.release_state,
                previous_value = excluded.previous_value,
                previous_display = excluded.previous_display,
                forecast_value = excluded.forecast_value,
                forecast_display = excluded.forecast_display,
                actual_value = excluded.actual_value,
                actual_display = excluded.actual_display,
                surprise_value = excluded.surprise_value,
                surprise_display = excluded.surprise_display,
                source_name = excluded.source_name,
                source_url = excluded.source_url,
                source_record_id = excluded.source_record_id,
                actual_released_at = excluded.actual_released_at,
                provenance_json = excluded.provenance_json,
                updated_at = excluded.updated_at
            """,
            (
                schedule_id,
                candidate.metric_code or (existing["metric_code"] if existing else "headline"),
                candidate.unit or (existing["unit"] if existing else None),
                release_state,
                previous_value,
                candidate.previous_display
                or (existing["previous_display"] if existing and existing["previous_display"] else None)
                or _fmt_number(previous_value, candidate.unit or (existing["unit"] if existing else None)),
                forecast_value,
                candidate.forecast_display
                or (existing["forecast_display"] if existing and existing["forecast_display"] else None)
                or _fmt_number(forecast_value, candidate.unit or (existing["unit"] if existing else None)),
                actual_value,
                candidate.actual_display
                or (existing["actual_display"] if existing and existing["actual_display"] else None)
                or _fmt_number(actual_value, candidate.unit or (existing["unit"] if existing else None)),
                surprise_value,
                candidate.surprise_display
                or (existing["surprise_display"] if existing and existing["surprise_display"] else None)
                or _fmt_number(surprise_value, candidate.unit or (existing["unit"] if existing else None)),
                candidate.source_name or (existing["source_name"] if existing else None),
                candidate.source_url or (existing["source_url"] if existing else None),
                candidate.source_record_id or (existing["source_record_id"] if existing else None),
                candidate.actual_released_at or (existing["actual_released_at"] if existing else None),
                _json_dump(merged_provenance),
                created_at,
                now,
            ),
        )

        if actual_value is not None and schedule["status"] != "cancelled":
            connection.execute(
                """
                UPDATE global_event_schedule
                SET status = 'released',
                    updated_at = ?
                WHERE id = ?
                """,
                (now, schedule_id),
            )
        return 1

    def _resolve_release_state(
        self,
        *,
        candidate_release_state: str,
        existing: sqlite3.Row | None,
        forecast_value: float | None,
        actual_value: float | None,
    ) -> str:
        if actual_value is not None:
            if existing is not None and existing["actual_value"] is not None and _as_float(existing["actual_value"]) != actual_value:
                return "revised"
            return "released"
        if forecast_value is not None:
            return "forecast_pending"
        if candidate_release_state:
            return candidate_release_state
        return "actual_pending"

    def _merge_release_provenance(self, existing: Any, candidate: GlobalEventReleaseCandidate) -> dict[str, Any]:
        payload: dict[str, Any] = existing if isinstance(existing, dict) else {}
        sources = payload.get("sources")
        if not isinstance(sources, list):
            sources = []
        source_entry = {
            "source_name": candidate.source_name,
            "source_url": candidate.source_url,
            "source_record_id": candidate.source_record_id,
            "metric_code": candidate.metric_code,
            "actual_released_at": candidate.actual_released_at,
        }
        if source_entry not in sources:
            sources.append(source_entry)
        payload["sources"] = sources
        if candidate.provenance:
            payload["latest"] = candidate.provenance
        return payload

    def _select_rows_for_impact(self, connection: sqlite3.Connection, *, start_date: date, end_date: date) -> list[sqlite3.Row]:
        return connection.execute(
            """
            SELECT
                s.*,
                r.metric_code,
                r.release_state,
                r.unit,
                r.previous_value,
                r.previous_display,
                r.forecast_value,
                r.forecast_display,
                r.actual_value,
                r.actual_display,
                r.surprise_value,
                r.surprise_display,
                r.provenance_json AS release_provenance_json
            FROM global_event_schedule s
            LEFT JOIN global_event_releases r ON r.schedule_id = s.id
            WHERE s.status != 'cancelled'
              AND s.event_date_kst >= ?
              AND s.event_date_kst <= ?
            ORDER BY s.sort_at_kst ASC
            """,
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchall()

    def _upsert_impact(self, connection: sqlite3.Connection, row: sqlite3.Row) -> int:
        impact = self._build_impact_candidate(row)
        now = utcnow_iso()
        existing = connection.execute(
            "SELECT created_at FROM global_event_impacts WHERE schedule_id = ?",
            (row["id"],),
        ).fetchone()
        created_at = existing["created_at"] if existing is not None else now
        connection.execute(
            """
            INSERT INTO global_event_impacts (
                schedule_id,
                event_key,
                summary_ko,
                tone,
                impact_channels_json,
                generation_method,
                provider_name,
                model_name,
                status,
                provenance_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(schedule_id) DO UPDATE SET
                event_key = excluded.event_key,
                summary_ko = excluded.summary_ko,
                tone = excluded.tone,
                impact_channels_json = excluded.impact_channels_json,
                generation_method = excluded.generation_method,
                provider_name = excluded.provider_name,
                model_name = excluded.model_name,
                status = excluded.status,
                provenance_json = excluded.provenance_json,
                updated_at = excluded.updated_at
            """,
            (
                row["id"],
                impact["event_key"],
                impact["summary_ko"],
                impact["tone"],
                _json_dump(impact["impact_channels"]),
                impact["generation_method"],
                impact["provider_name"],
                impact["model_name"],
                "active",
                _json_dump(impact["provenance"]),
                created_at,
                now,
            ),
        )
        return 1

    def _build_impact_candidate(self, row: sqlite3.Row) -> dict[str, Any]:
        release = {
            "metric_code": row["metric_code"],
            "release_state": row["release_state"],
            "unit": row["unit"],
            "previous_value": _as_float(row["previous_value"]),
            "forecast_value": _as_float(row["forecast_value"]),
            "actual_value": _as_float(row["actual_value"]),
            "surprise_value": _as_float(row["surprise_value"]),
            "previous_display": row["previous_display"],
            "forecast_display": row["forecast_display"],
            "actual_display": row["actual_display"],
            "surprise_display": row["surprise_display"],
        }

        if not isinstance(self.impact_provider, DisabledGlobalEventImpactProvider):
            request = GlobalEventImpactRequest(
                event_key=row["event_key"],
                title=row["title"],
                category=row["category"],
                country=row["country"],
                why_it_matters_ko=row["why_it_matters_ko"],
                status=row["status"],
                importance=row["importance"],
                release=release,
                provenance={"schedule": _json_load(row["provenance_json"]) or {}, "release": _json_load(row["release_provenance_json"]) or {}},
            )
            try:
                response = self.impact_provider.generate_impact(request)
                if response is not None:
                    return {
                        "event_key": row["event_key"],
                        "summary_ko": response.summary_ko,
                        "tone": response.tone,
                        "impact_channels": response.impact_channels,
                        "generation_method": "llm",
                        "provider_name": self.impact_provider.provider_name,
                        "model_name": self.impact_provider.model_name(),
                        "provenance": response.raw_output,
                    }
            except Exception as error:  # noqa: BLE001
                logger.warning(
                    "global_event_impact_llm_failed",
                    extra={"event_key": row["event_key"], "error": str(error)},
                )

        return self._build_rule_based_impact(row, release)

    def _build_rule_based_impact(self, row: sqlite3.Row, release: dict[str, Any]) -> dict[str, Any]:
        event_type = str(row["event_type"])
        title = str(row["title"])
        channels = ["USD/KRW", "외국인 수급", "반도체/성장주"]
        summary = str(row["why_it_matters_ko"])
        tone = "neutral"
        actual = release.get("actual_value")
        forecast = release.get("forecast_value")
        previous = release.get("previous_value")

        if event_type in {"CPI", "PCE"}:
            if actual is not None and forecast is not None and actual > forecast:
                tone = "hawkish"
                summary = "물가가 예상보다 높아 금리 인하 지연 위험이 커졌고, 달러 강세와 함께 성장주·반도체 변동성이 확대될 수 있습니다."
            elif actual is not None and forecast is not None and actual < forecast:
                tone = "dovish"
                summary = "물가가 예상보다 낮아 금리 부담이 완화되면서 원화 압력 완화와 성장주 반등 기대가 커질 수 있습니다."
            elif actual is not None and previous is not None and actual > previous:
                tone = "hawkish"
                summary = "물가 둔화 속도가 기대보다 느려져 금리 기대 재조정과 환율 민감도가 다시 커질 수 있습니다."
            else:
                tone = "mixed"
                summary = "물가 결과에 따라 연준 경로와 달러 방향이 재조정될 수 있어 한국 성장주와 외국인 수급이 민감하게 반응할 수 있습니다."
        elif event_type == "PAYROLLS":
            if actual is not None and forecast is not None and actual > forecast:
                tone = "hawkish"
                summary = "고용이 예상보다 강해 금리 인하 기대가 늦춰질 수 있고, 달러 강세와 함께 한국 증시 외국인 수급 민감도가 높아질 수 있습니다."
            elif actual is not None and forecast is not None and actual < forecast:
                tone = "risk_off"
                summary = "고용이 예상보다 약해 경기둔화 우려가 부각될 수 있어 수출주와 경기민감주 변동성이 커질 수 있습니다."
            elif actual is not None and previous is not None and actual > previous:
                tone = "hawkish"
                summary = "고용 모멘텀이 예상보다 단단해 장단기 금리와 달러가 반응하면 한국 증시 밸류에이션 민감주가 흔들릴 수 있습니다."
            else:
                tone = "mixed"
                summary = "고용 발표는 연준 경로와 위험선호를 동시에 흔들 수 있어 원화, 반도체, 외국인 수급을 함께 봐야 합니다."
        elif event_type in {"FOMC", "ECB", "BOJ"}:
            tone = "hawkish" if actual is not None and previous is not None and actual > previous else "mixed"
            summary = "중앙은행 톤이 매파적으로 기울면 달러 강세와 환율 압력이 커지고, 비둘기파적이면 성장주와 외국인 수급 부담이 완화될 수 있습니다."
            channels = ["USD/KRW", "국채금리", "외국인 수급"]
        elif event_type == "EARNINGS":
            tone = "risk_on" if actual is not None and forecast is not None and actual > forecast else "mixed"
            summary = "대형 기술주 실적과 가이던스는 AI 투자 심리를 통해 국내 반도체와 장비주 밸류에이션을 직접 흔들 수 있습니다."
            channels = ["반도체", "AI 공급망", "위험선호"]
        elif event_type == "OIL":
            tone = "risk_off"
            summary = "유가 상방 이벤트는 인플레이션 기대와 원가 부담을 동시에 자극해 항공·화학·정유 업종의 차별화를 키울 수 있습니다."
            channels = ["유가", "원/달러", "항공/정유/화학"]
        else:
            summary = f"{title} 결과는 달러, 금리, 위험선호를 통해 한국 증시에 파급될 수 있습니다."

        return {
            "event_key": row["event_key"],
            "summary_ko": summary,
            "tone": tone,
            "impact_channels": channels,
            "generation_method": "rule_based",
            "provider_name": None,
            "model_name": None,
            "provenance": {"rule": event_type, "release": release},
        }

    def _upsert_coverage(self, connection: sqlite3.Connection, coverage: GlobalEventCoverageSnapshot) -> None:
        now = utcnow_iso()
        existing = connection.execute(
            "SELECT created_at FROM global_event_source_coverage WHERE source_key = ?",
            (coverage.source_key,),
        ).fetchone()
        created_at = existing["created_at"] if existing is not None else now
        connection.execute(
            """
            INSERT INTO global_event_source_coverage (
                source_key,
                source_name,
                source_kind,
                is_required,
                status,
                available_count,
                expected_count,
                coverage_ratio,
                event_types_json,
                last_synced_at,
                last_success_at,
                source_url,
                note,
                metadata_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_key) DO UPDATE SET
                source_name = excluded.source_name,
                source_kind = excluded.source_kind,
                is_required = excluded.is_required,
                status = excluded.status,
                available_count = excluded.available_count,
                expected_count = excluded.expected_count,
                coverage_ratio = excluded.coverage_ratio,
                event_types_json = excluded.event_types_json,
                last_synced_at = excluded.last_synced_at,
                last_success_at = excluded.last_success_at,
                source_url = excluded.source_url,
                note = excluded.note,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            """,
            (
                coverage.source_key,
                coverage.source_name,
                coverage.source_kind,
                1 if coverage.is_required else 0,
                coverage.status,
                coverage.available_count,
                coverage.expected_count,
                coverage.coverage_ratio,
                _json_dump(coverage.event_types),
                coverage.last_synced_at,
                coverage.last_success_at,
                coverage.source_url,
                coverage.note,
                _json_dump(coverage.metadata),
                created_at,
                now,
            ),
        )

    def _serialize_event(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["event_key"],
            "event_key": row["event_key"],
            "title": row["title"],
            "event_type": row["event_type"],
            "category": row["category"],
            "country": row["country"],
            "status": row["status"],
            "importance": row["importance"],
            "importance_source": row["importance_source"],
            "event_date_kst": row["event_date_kst"],
            "event_time_kst": row["event_time_kst"],
            "event_time_precision": row["event_time_precision"],
            "previous_event_time_kst": row["previous_event_time_kst"],
            "revision_note": row["revision_note"],
            "why_it_matters_ko": row["why_it_matters_ko"],
            "source": {
                "key": row["source_key"],
                "name": row["source_name"],
                "url": row["source_url"],
                "updated_at": row["source_updated_at"],
            },
            "release": {
                "metric_code": row["metric_code"],
                "state": row["release_state"] or ("actual_pending" if row["event_time_kst"] else "scheduled"),
                "unit": row["unit"],
                "previous": row["previous_display"],
                "forecast": row["forecast_display"],
                "actual": row["actual_display"],
                "surprise": row["surprise_display"],
                "previous_value": _as_float(row["previous_value"]),
                "forecast_value": _as_float(row["forecast_value"]),
                "actual_value": _as_float(row["actual_value"]),
                "surprise_value": _as_float(row["surprise_value"]),
                "source_name": row["release_source_name"],
                "source_url": row["release_source_url"],
                "source_record_id": row["source_record_id"],
                "actual_released_at": row["actual_released_at"],
            },
            "impact": {
                "summary_ko": row["summary_ko"],
                "tone": row["tone"],
                "impact_channels": _json_load(row["impact_channels_json"]) or [],
                "generation_method": row["generation_method"],
                "provider_name": row["provider_name"],
                "model_name": row["model_name"],
            }
            if row["summary_ko"]
            else None,
            "provenance": {
                "schedule": _json_load(row["provenance_json"]) or {},
                "release": _json_load(row["release_provenance_json"]) or {},
                "impact": _json_load(row["impact_provenance_json"]) or {},
            },
            "updated_at": self._latest_value([row["updated_at"], row["actual_released_at"]]),
        }

    def _coverage_summary(self, *, status: str, available: int, expected: int) -> str:
        if expected <= 0:
            return "표시 대상 소스가 아직 없습니다."
        if status == "full":
            return f"필수 소스 {available}/{expected}가 모두 준비되었습니다."
        if status == "partial":
            return f"필수 소스 {available}/{expected}만 반영되어 일부 일정·실적·예상치가 비어 있을 수 있습니다."
        return "필수 소스 동기화가 아직 비어 있어 빈 상태가 보일 수 있습니다."

    def _latest_row_timestamp(self, rows: list[Any]) -> str | None:
        timestamps: list[str] = []
        for row in rows:
            if isinstance(row, sqlite3.Row):
                timestamps.extend([value for value in [row["updated_at"], row.get("actual_released_at") if hasattr(row, "get") else None] if value])
                continue
            if isinstance(row, dict):
                timestamps.extend([value for value in [row.get("updated_at"), row.get("actual_released_at")] if value])
        return max(timestamps) if timestamps else None

    def _latest_value(self, values: list[str | None]) -> str | None:
        filtered = [value for value in values if value]
        return max(filtered) if filtered else None

    def _missing_coverage(
        self,
        *,
        source_key: str,
        source_name: str,
        source_kind: str,
        source_url: str | None,
        is_required: bool,
        note: str,
    ) -> GlobalEventCoverageSnapshot:
        return GlobalEventCoverageSnapshot(
            source_key=source_key,
            source_name=source_name,
            source_kind=source_kind,
            is_required=is_required,
            status="missing",
            available_count=0,
            expected_count=1 if is_required else 0,
            coverage_ratio=0.0,
            event_types=[],
            last_synced_at=utcnow_iso(),
            last_success_at=None,
            source_url=source_url,
            note=note,
            metadata={},
        )
