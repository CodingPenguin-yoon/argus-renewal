from __future__ import annotations

import dataclasses
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional


SENSITIVE_KEYS = {
    "access_token",
    "app_key",
    "app_secret",
    "appkey",
    "appsecret",
    "authorization",
    "client_secret",
    "kis_app_key",
    "kis_app_secret",
    "secret",
    "token",
}


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class PersistedProviderBatch:
    run_id: int
    provider_key: str
    status: str
    observed_count: int
    sample_ids: list[int]
    derivatives_snapshot_ids: list[int]
    option_chain_snapshot_ids: list[int]
    market_reaction_snapshot_ids: list[int]
    news_trigger_ids: list[int]


class ArgusV2Storage:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def start_provider_run(
        self,
        *,
        provider_key: str,
        provider_label: str | None = None,
        endpoint: str | None = None,
        started_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO argus_v2_provider_runs (
                provider_key,
                provider_label,
                endpoint,
                status,
                started_at,
                metadata_json
            )
            VALUES (?, ?, ?, 'running', ?, ?)
            """,
            (
                provider_key,
                provider_label,
                endpoint,
                started_at or utcnow_iso(),
                _json_dumps(metadata or {}),
            ),
        )
        return int(cursor.lastrowid)

    def finish_provider_run(
        self,
        *,
        run_id: int,
        status: str,
        observed_count: int,
        expected_count: int | None = None,
        missing_fields: list[str] | None = None,
        error: str | None = None,
        finished_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.connection.execute(
            """
            UPDATE argus_v2_provider_runs
            SET status = ?,
                finished_at = ?,
                observed_count = ?,
                expected_count = ?,
                missing_fields_json = ?,
                error = ?,
                metadata_json = ?
            WHERE id = ?
            """,
            (
                status,
                finished_at or utcnow_iso(),
                observed_count,
                expected_count,
                _json_dumps(missing_fields or []),
                error,
                _json_dumps(metadata or {}),
                run_id,
            ),
        )

    def save_provider_sample(
        self,
        *,
        run_id: int,
        sample_kind: str,
        payload: Any,
        source_url: str | None = None,
        created_at: str | None = None,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO argus_v2_provider_samples (
                run_id,
                sample_kind,
                source_url,
                payload_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                sample_kind,
                source_url,
                _json_dumps(_redact_sensitive(payload)),
                created_at or utcnow_iso(),
            ),
        )
        return int(cursor.lastrowid)

    def save_derivatives_snapshot(self, *, run_id: int, record: Any, raw_sample_id: int | None = None) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO argus_v2_derivatives_snapshots (
                run_id,
                raw_sample_id,
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
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                raw_sample_id,
                _attr(record, "trade_date"),
                _attr(record, "snapshot_time"),
                _attr(record, "session_type"),
                _attr(record, "source_name"),
                _attr(record, "instrument_code"),
                _attr(record, "instrument_name"),
                _attr(record, "price"),
                _attr(record, "price_change"),
                _attr(record, "change_rate"),
                _attr(record, "volume"),
                _attr(record, "open_interest"),
                _attr(record, "put_call_ratio"),
                _attr(record, "implied_volatility"),
                _json_dumps(_attr(record, "additional_metrics") or {}),
                _attr(record, "source_url"),
                _attr(record, "source_record_id"),
                utcnow_iso(),
            ),
        )
        return int(cursor.lastrowid)

    def save_option_chain_snapshot(self, *, run_id: int, record: Any, raw_sample_id: int | None = None) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO argus_v2_option_chain_snapshots (
                run_id,
                raw_sample_id,
                trade_date,
                snapshot_time,
                market_scope,
                underlying_code,
                underlying_name,
                underlying_price,
                expiry_date,
                contract_month,
                source_name,
                source_url,
                source_record_id,
                atm_strike,
                expected_level_count,
                observed_level_count,
                freshness_state,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                raw_sample_id,
                _attr(record, "trade_date"),
                _attr(record, "snapshot_time"),
                _attr(record, "market_scope") or "KRX",
                _attr(record, "underlying_code") or "KOSPI200",
                _attr(record, "underlying_name"),
                _attr(record, "underlying_price"),
                _attr(record, "expiry_date"),
                _attr(record, "contract_month"),
                _attr(record, "source_name"),
                _attr(record, "source_url"),
                _attr(record, "source_record_id"),
                _attr(record, "atm_strike"),
                _attr(record, "expected_level_count"),
                _attr(record, "observed_level_count") or len(_attr(record, "levels") or []),
                _attr(record, "freshness_state") or "missing",
                utcnow_iso(),
            ),
        )
        snapshot_id = int(cursor.lastrowid)

        for level in _attr(record, "levels") or []:
            self.connection.execute(
                """
                INSERT INTO argus_v2_option_chain_levels (
                    snapshot_id,
                    strike_price,
                    moneyness,
                    call_last_price,
                    call_change_rate,
                    call_volume,
                    call_open_interest,
                    call_open_interest_change,
                    call_implied_volatility,
                    put_last_price,
                    put_change_rate,
                    put_volume,
                    put_open_interest,
                    put_open_interest_change,
                    put_implied_volatility,
                    total_open_interest,
                    net_call_put_oi,
                    call_put_oi_ratio,
                    pressure_side,
                    metadata_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    _attr(level, "strike_price"),
                    _attr(level, "moneyness") or "UNKNOWN",
                    _attr(level, "call_last_price"),
                    _attr(level, "call_change_rate"),
                    _attr(level, "call_volume"),
                    _attr(level, "call_open_interest"),
                    _attr(level, "call_open_interest_change"),
                    _attr(level, "call_implied_volatility"),
                    _attr(level, "put_last_price"),
                    _attr(level, "put_change_rate"),
                    _attr(level, "put_volume"),
                    _attr(level, "put_open_interest"),
                    _attr(level, "put_open_interest_change"),
                    _attr(level, "put_implied_volatility"),
                    _attr(level, "total_open_interest"),
                    _attr(level, "net_call_put_oi"),
                    _attr(level, "call_put_oi_ratio"),
                    _attr(level, "pressure_side") or "UNKNOWN",
                    _json_dumps(_attr(level, "metadata") or {}),
                    utcnow_iso(),
                ),
            )

        return snapshot_id

    def save_market_reaction_snapshot(self, *, run_id: int, record: Any, raw_sample_id: int | None = None) -> int:
        kospi_point = _attr(record, "kospi_change_rate")
        kosdaq_point = _attr(record, "kosdaq_change_rate")
        futures_point = _attr(record, "kospi200_futures_change_rate")
        spot_foreign_point = _attr(record, "spot_foreign_net_buy")
        spot_institution_point = _attr(record, "spot_institution_net_buy")
        spot_individual_point = _attr(record, "spot_individual_net_buy")
        snapshot_time = (
            _attr(record, "snapshot_time")
            or _point_attr(kospi_point, "observed_at")
            or _point_attr(kosdaq_point, "observed_at")
            or _point_attr(futures_point, "observed_at")
            or _point_attr(spot_foreign_point, "observed_at")
            or _point_attr(spot_institution_point, "observed_at")
            or _point_attr(spot_individual_point, "observed_at")
            or utcnow_iso()
        )
        source_name = (
            _attr(record, "source_name")
            or _point_attr(kospi_point, "source")
            or _point_attr(kosdaq_point, "source")
            or _point_attr(futures_point, "source")
            or _point_attr(spot_foreign_point, "source")
            or _point_attr(spot_institution_point, "source")
            or _point_attr(spot_individual_point, "source")
            or "argus_v2.market_reaction"
        )

        cursor = self.connection.execute(
            """
            INSERT INTO argus_v2_market_reaction_snapshots (
                run_id,
                raw_sample_id,
                trade_date,
                snapshot_time,
                source_name,
                kospi_change_rate,
                kosdaq_change_rate,
                kospi200_futures_change_rate,
                advancing_count,
                declining_count,
                spot_foreign_net_buy,
                spot_institution_net_buy,
                spot_individual_net_buy,
                summary,
                freshness_state,
                source_url,
                source_record_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                raw_sample_id,
                _attr(record, "trade_date") or str(snapshot_time)[:10],
                snapshot_time,
                source_name,
                _point_value(kospi_point),
                _point_value(kosdaq_point),
                _point_value(futures_point),
                _point_value(_attr(record, "advancing_count")),
                _point_value(_attr(record, "declining_count")),
                _point_value(spot_foreign_point),
                _point_value(spot_institution_point),
                _point_value(spot_individual_point),
                _attr(record, "summary") or "",
                _attr(record, "freshness_state") or _point_attr(kospi_point, "freshness") or "partial",
                _attr(record, "source_url"),
                _attr(record, "source_record_id"),
                utcnow_iso(),
            ),
        )
        snapshot_id = int(cursor.lastrowid)

        for role, sector_items in (
            ("strong", _attr(record, "strong_sectors") or []),
            ("weak", _attr(record, "weak_sectors") or []),
        ):
            for sector in sector_items:
                sector_source = _attr(sector, "source") or source_name
                self.connection.execute(
                    """
                    INSERT INTO argus_v2_market_reaction_sectors (
                        snapshot_id,
                        role,
                        name,
                        change_rate,
                        reason,
                        tone,
                        source_name,
                        observed_at,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        role,
                        _attr(sector, "name"),
                        _attr(sector, "change_rate"),
                        _attr(sector, "reason") or "",
                        _attr(sector, "tone") or ("positive" if role == "strong" else "negative"),
                        sector_source,
                        _attr(sector, "observed_at") or snapshot_time,
                        utcnow_iso(),
                    ),
                )

        return snapshot_id

    def save_news_trigger(self, *, run_id: int, record: Any, raw_sample_id: int | None = None) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO argus_v2_news_triggers (
                run_id,
                raw_sample_id,
                external_id,
                title,
                summary,
                impact,
                source_name,
                published_at,
                connection_strength,
                freshness_state,
                source_url,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                raw_sample_id,
                _attr(record, "id") or _attr(record, "external_id") or _attr(record, "source_record_id") or "",
                _attr(record, "title"),
                _attr(record, "summary") or "",
                _attr(record, "impact") or "neutral",
                _attr(record, "source") or _attr(record, "source_name") or "argus_v2.news_triggers",
                _attr(record, "published_at") or _attr(record, "observed_at"),
                _attr(record, "connection_strength") or "unclear",
                _attr(record, "freshness") or _attr(record, "freshness_state") or "partial",
                _attr(record, "source_url"),
                utcnow_iso(),
            ),
        )
        return int(cursor.lastrowid)

    def save_provider_batch(
        self,
        *,
        provider_key: str,
        batch: Any,
        provider_label: str | None = None,
        endpoint: str | None = None,
        started_at: str | None = None,
    ) -> PersistedProviderBatch:
        records = list(_attr(batch, "records") or [])
        metadata = dict(_attr(batch, "metadata") or {})
        disabled_reason = _attr(batch, "disabled_reason")
        expected_count = _pick_expected_count(records=records, metadata=metadata)

        run_id = self.start_provider_run(
            provider_key=provider_key,
            provider_label=provider_label,
            endpoint=endpoint,
            started_at=started_at,
            metadata=metadata,
        )

        sample_ids: list[int] = []
        derivatives_snapshot_ids: list[int] = []
        option_chain_snapshot_ids: list[int] = []
        market_reaction_snapshot_ids: list[int] = []
        news_trigger_ids: list[int] = []

        for record in records:
            raw_payload = _attr(record, "raw_payload")
            raw_sample_id: int | None = None
            if raw_payload is not None:
                raw_sample_id = self.save_provider_sample(
                    run_id=run_id,
                    sample_kind=_sample_kind(record),
                    payload=raw_payload,
                    source_url=_attr(record, "source_url"),
                )
                sample_ids.append(raw_sample_id)

            if _is_option_chain_snapshot(record):
                option_chain_snapshot_ids.append(
                    self.save_option_chain_snapshot(
                        run_id=run_id,
                        record=record,
                        raw_sample_id=raw_sample_id,
                    )
                )
            elif _is_derivatives_snapshot(record):
                derivatives_snapshot_ids.append(
                    self.save_derivatives_snapshot(
                        run_id=run_id,
                        record=record,
                        raw_sample_id=raw_sample_id,
                    )
                )
            elif _is_market_reaction_snapshot(record):
                market_reaction_snapshot_ids.append(
                    self.save_market_reaction_snapshot(
                        run_id=run_id,
                        record=record,
                        raw_sample_id=raw_sample_id,
                    )
                )
            elif _is_news_trigger(record):
                news_trigger_ids.append(
                    self.save_news_trigger(
                        run_id=run_id,
                        record=record,
                        raw_sample_id=raw_sample_id,
                    )
                )

        observed_count = _observed_count(records)
        status = _batch_status(
            disabled_reason=disabled_reason,
            observed_count=observed_count,
            expected_count=expected_count,
        )
        self.finish_provider_run(
            run_id=run_id,
            status=status,
            observed_count=observed_count,
            expected_count=expected_count,
            missing_fields=[str(disabled_reason)] if disabled_reason else [],
            metadata=metadata,
        )

        return PersistedProviderBatch(
            run_id=run_id,
            provider_key=provider_key,
            status=status,
            observed_count=observed_count,
            sample_ids=sample_ids,
            derivatives_snapshot_ids=derivatives_snapshot_ids,
            option_chain_snapshot_ids=option_chain_snapshot_ids,
            market_reaction_snapshot_ids=market_reaction_snapshot_ids,
            news_trigger_ids=news_trigger_ids,
        )

    def get_latest_derivatives_snapshot(self) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT *
            FROM argus_v2_derivatives_snapshots
            ORDER BY snapshot_time DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        return _row_to_dict(row)

    def get_latest_option_chain_snapshot(self) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT *
            FROM argus_v2_option_chain_snapshots
            ORDER BY snapshot_time DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None

        snapshot = _row_to_dict(row) or {}
        levels = self.connection.execute(
            """
            SELECT *
            FROM argus_v2_option_chain_levels
            WHERE snapshot_id = ?
            ORDER BY strike_price ASC
            """,
            (snapshot["id"],),
        ).fetchall()
        snapshot["levels"] = [_row_to_dict(level) for level in levels]
        return snapshot

    def get_previous_option_chain_snapshot(self, *, latest_snapshot: dict[str, Any]) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT *
            FROM argus_v2_option_chain_snapshots
            WHERE id != ?
              AND underlying_code = ?
              AND expiry_date = ?
              AND snapshot_time < ?
            ORDER BY snapshot_time DESC, id DESC
            LIMIT 1
            """,
            (
                latest_snapshot["id"],
                latest_snapshot["underlying_code"],
                latest_snapshot["expiry_date"],
                latest_snapshot["snapshot_time"],
            ),
        ).fetchone()
        if row is None:
            return None

        snapshot = _row_to_dict(row) or {}
        levels = self.connection.execute(
            """
            SELECT *
            FROM argus_v2_option_chain_levels
            WHERE snapshot_id = ?
            ORDER BY strike_price ASC
            """,
            (snapshot["id"],),
        ).fetchall()
        snapshot["levels"] = [_row_to_dict(level) for level in levels]
        return snapshot

    def get_latest_provider_runs(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT runs.*
            FROM argus_v2_provider_runs AS runs
            JOIN (
                SELECT provider_key, MAX(id) AS latest_id
                FROM argus_v2_provider_runs
                GROUP BY provider_key
            ) AS latest
                ON runs.id = latest.latest_id
            ORDER BY runs.provider_key
            """
        ).fetchall()
        return [_row_to_dict(row) or {} for row in rows]

    def get_latest_market_reaction_snapshot(self) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT *
            FROM argus_v2_market_reaction_snapshots
            ORDER BY snapshot_time DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None

        snapshot = _row_to_dict(row) or {}
        sectors = self.connection.execute(
            """
            SELECT *
            FROM argus_v2_market_reaction_sectors
            WHERE snapshot_id = ?
            ORDER BY id ASC
            """,
            (snapshot["id"],),
        ).fetchall()
        snapshot["strong_sectors"] = []
        snapshot["weak_sectors"] = []
        for sector in sectors:
            item = _row_to_dict(sector) or {}
            if item.get("role") == "strong":
                snapshot["strong_sectors"].append(item)
            elif item.get("role") == "weak":
                snapshot["weak_sectors"].append(item)
        return snapshot

    def get_latest_news_triggers(self, *, limit: int = 5) -> list[dict[str, Any]]:
        window_limit = max(limit * 5, limit)
        rows = self.connection.execute(
            """
            SELECT triggers.*, samples.payload_json AS raw_payload_json
            FROM argus_v2_news_triggers AS triggers
            LEFT JOIN argus_v2_provider_samples AS samples
                ON samples.id = triggers.raw_sample_id
            ORDER BY COALESCE(triggers.published_at, triggers.created_at) DESC, triggers.id DESC
            LIMIT ?
            """,
            (window_limit,),
        ).fetchall()
        items = [_row_to_dict(row) or {} for row in rows]
        items.sort(
            key=lambda item: (
                _news_relevance_from_sample(item.get("raw_payload_json")),
                str(item.get("published_at") or item.get("created_at") or ""),
                int(item.get("id") or 0),
            ),
            reverse=True,
        )
        return items[:limit]


def _batch_status(*, disabled_reason: str | None, observed_count: int, expected_count: int | None) -> str:
    if disabled_reason:
        return "skipped"
    if expected_count == 0 and observed_count == 0:
        return "success"
    if observed_count <= 0:
        return "failed"
    if expected_count is not None and observed_count < expected_count:
        return "partial"
    return "success"


def _pick_expected_count(*, records: list[Any], metadata: dict[str, Any]) -> int | None:
    for key in ("expected_level_count", "expected_count"):
        value = metadata.get(key)
        if isinstance(value, int) and value >= 0:
            return value
    for record in records:
        value = _attr(record, "expected_level_count")
        if isinstance(value, int) and value > 0:
            return value
    return None


def _observed_count(records: list[Any]) -> int:
    option_records = [record for record in records if _is_option_chain_snapshot(record)]
    if option_records:
        return sum(
            int(_attr(record, "observed_level_count") or len(_attr(record, "levels") or []))
            for record in option_records
        )

    derivatives_count = sum(1 for record in records if _is_derivatives_snapshot(record))
    if derivatives_count:
        return derivatives_count

    reaction_count = sum(1 for record in records if _is_market_reaction_snapshot(record))
    if reaction_count:
        return reaction_count

    trigger_count = sum(1 for record in records if _is_news_trigger(record))
    if trigger_count:
        return trigger_count

    total = 0
    for record in records:
        value = _attr(record, "observed_count")
        if isinstance(value, int) and value > 0:
            total += value
    return total


def _is_derivatives_snapshot(record: Any) -> bool:
    return bool(_attr(record, "instrument_code") and _attr(record, "snapshot_time"))


def _is_option_chain_snapshot(record: Any) -> bool:
    return bool(_attr(record, "levels") is not None and _attr(record, "expiry_date"))


def _is_market_reaction_snapshot(record: Any) -> bool:
    return bool(
        _attr(record, "kospi_change_rate") is not None
        or _attr(record, "kosdaq_change_rate") is not None
        or _attr(record, "spot_foreign_net_buy") is not None
        or _attr(record, "spot_institution_net_buy") is not None
        or _attr(record, "spot_individual_net_buy") is not None
        or _attr(record, "strong_sectors") is not None
        or _attr(record, "weak_sectors") is not None
    )


def _is_news_trigger(record: Any) -> bool:
    return bool(_attr(record, "title") and _attr(record, "impact"))


def _sample_kind(record: Any) -> str:
    if _is_option_chain_snapshot(record):
        return "option_chain_snapshot"
    if _is_derivatives_snapshot(record):
        return "derivatives_snapshot"
    if _is_market_reaction_snapshot(record):
        return "market_reaction_snapshot"
    if _is_news_trigger(record):
        return "news_trigger"
    return record.__class__.__name__


def _attr(item: Any, name: str) -> Any:
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)


def _point_attr(point: Any, name: str) -> Any:
    return _attr(point, name)


def _point_value(point: Any) -> float | int | str | None:
    value = _attr(point, "value")
    if value is not None:
        return value
    if isinstance(point, (float, int, str)) or point is None:
        return point
    return None


def _row_to_dict(row: Optional[sqlite3.Row]) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def _json_dumps(payload: Any) -> str:
    return json.dumps(_json_ready(payload), ensure_ascii=False, sort_keys=True)


def _json_ready(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return _json_ready(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _redact_sensitive(value: Any) -> Any:
    ready = _json_ready(value)
    if isinstance(ready, dict):
        redacted: dict[str, Any] = {}
        for key, item in ready.items():
            if key.lower() in SENSITIVE_KEYS:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_sensitive(item)
        return redacted
    if isinstance(ready, list):
        return [_redact_sensitive(item) for item in ready]
    return ready


def _news_relevance_from_sample(payload_json: Any) -> int:
    if not isinstance(payload_json, str) or not payload_json:
        return 0
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict):
        return 0
    value = payload.get("_argus_ai_relevance_score")
    return int(value) if isinstance(value, int) else 0
