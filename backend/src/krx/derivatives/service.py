from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
from typing import Any

from ...config.env import Settings
from ..company_master.db import get_connection

logger = logging.getLogger(__name__)


def _normalize_key(value: str) -> str:
    return "".join(ch for ch in value.lower().strip() if ch not in {"_", "-", " "})


def _json_load(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, (int, float)):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    try:
        return json.loads(text)
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
    cleaned = text.replace(",", "")
    if cleaned.endswith("%"):
        cleaned = cleaned[:-1].strip()
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    if cleaned in {"-", "--", "N/A", "NA", "null", "None"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    if abs(previous) <= 1e-12:
        return None
    return ((current - previous) / abs(previous)) * 100.0


@dataclass(frozen=True)
class RuleBasedBriefing:
    directional_bias: str
    gap_bias: str
    volatility_bias: str
    confidence_bucket: str
    explanation_ko: str
    components: list[dict[str, Any]]


class DerivativesDashboardService:
    def __init__(self, *, db_path: str, market_scope: str = "KRX") -> None:
        self.db_path = db_path
        self.market_scope = (market_scope or "KRX").strip().upper() or "KRX"

    @classmethod
    def from_settings(cls, settings: Settings) -> "DerivativesDashboardService":
        return cls(db_path=settings.db_path, market_scope=settings.market_briefing_signal_market_scope)

    def get_summary(self, *, date: str | None = None) -> dict[str, Any]:
        requested_date = (date or "").strip() or None

        with get_connection(self.db_path) as connection:
            derivatives_row = self._select_latest_derivatives_row(connection, up_to_date=requested_date)
            resolved_date = derivatives_row["trade_date"] if derivatives_row else None
            briefing = None
            if resolved_date is None:
                briefing = self._select_latest_briefing_row(connection, up_to_date=requested_date)
                if briefing is not None:
                    resolved_date = str(briefing.get("trade_date"))
                else:
                    resolved_date = requested_date

            if briefing is None:
                briefing = self._select_latest_briefing_row(connection, up_to_date=resolved_date)

            previous_derivatives = (
                self._select_previous_derivatives_row(connection, trade_date=resolved_date)
                if resolved_date
                else None
            )
            pre_open_snapshot = (
                self._select_pre_open_snapshot_row(connection, trade_date=resolved_date) if resolved_date else None
            )
            night_snapshot = (
                self._select_night_snapshot_row(connection, trade_date=resolved_date) if resolved_date else None
            )
            components = self._select_components(connection, briefing_id=briefing["id"]) if briefing else []

        requested_date_available = requested_date == resolved_date if requested_date else True

        pcr = self._extract_float_metric(derivatives_row, ("put_call_ratio", "pcr"))
        pcr_previous = self._extract_float_metric(previous_derivatives, ("put_call_ratio", "pcr"))
        implied_volatility = self._extract_float_metric(
            derivatives_row, ("implied_volatility", "iv", "vkospi")
        )
        implied_volatility_previous = self._extract_float_metric(
            previous_derivatives, ("implied_volatility", "iv", "vkospi")
        )
        call_open_interest = self._extract_float_metric(
            derivatives_row, ("call_open_interest", "call_oi", "call_openint")
        )
        put_open_interest = self._extract_float_metric(
            derivatives_row, ("put_open_interest", "put_oi", "put_openint")
        )
        open_interest_total = self._extract_float_metric(
            derivatives_row, ("open_interest_total", "open_interest", "total_open_interest")
        )
        open_interest_total_prev = self._extract_float_metric(
            previous_derivatives, ("open_interest_total", "open_interest", "total_open_interest")
        )
        call_notional = self._extract_float_metric(
            derivatives_row,
            ("call_notional", "call_notional_total", "call_value", "call_amount"),
        )
        put_notional = self._extract_float_metric(
            derivatives_row,
            ("put_notional", "put_notional_total", "put_value", "put_amount"),
        )

        investor_flows = {
            "futures_foreign_net_buy": self._extract_float_metric(
                derivatives_row,
                ("futures_investor_foreign_net_buy", "futures_foreign_net_buy"),
            ),
            "futures_institution_net_buy": self._extract_float_metric(
                derivatives_row,
                ("futures_investor_institution_net_buy", "futures_institution_net_buy"),
            ),
            "futures_individual_net_buy": self._extract_float_metric(
                derivatives_row,
                ("futures_investor_individual_net_buy", "futures_individual_net_buy"),
            ),
            "options_foreign_net_buy": self._extract_float_metric(
                derivatives_row,
                ("options_investor_foreign_net_buy", "options_foreign_net_buy"),
            ),
            "options_institution_net_buy": self._extract_float_metric(
                derivatives_row,
                ("options_investor_institution_net_buy", "options_institution_net_buy"),
            ),
            "options_individual_net_buy": self._extract_float_metric(
                derivatives_row,
                ("options_investor_individual_net_buy", "options_individual_net_buy"),
            ),
        }

        foreign_futures_net_position = investor_flows["futures_foreign_net_buy"]
        pre_open_change_rate = self._extract_float_metric(pre_open_snapshot, ("change_rate", "price_change"))
        night_change_rate = self._extract_float_metric(night_snapshot, ("change_rate", "price_change"))

        pcr_change = _pct_change(pcr, pcr_previous)
        implied_volatility_change = _pct_change(implied_volatility, implied_volatility_previous)

        oi_change = self._extract_float_metric(
            derivatives_row,
            (
                "oi_change",
                "open_interest_change",
                "open_interest_delta",
                "open_interest_change_pct",
            ),
        )
        if oi_change is None:
            oi_change = _pct_change(open_interest_total, open_interest_total_prev)

        participant_summary = self._extract_detail_block(
            derivatives_row,
            (
                "participant_summary",
                "participants",
                "participant_breakdown",
            ),
        )
        if participant_summary is None:
            participant_summary = self._build_participant_summary(investor_flows)

        expiry_or_contract_summary = self._extract_detail_block(
            derivatives_row,
            (
                "expiry_summary",
                "expiry_breakdown",
                "contract_summary",
                "contract_breakdown",
                "option_chain_summary",
                "option_chain",
                "strike_heatmap",
            ),
        )

        rule_based = self._build_rule_based_briefing(
            trade_date=resolved_date,
            pcr=pcr,
            pcr_change=pcr_change,
            call_open_interest=call_open_interest,
            put_open_interest=put_open_interest,
            oi_change=oi_change,
            foreign_futures_flow=foreign_futures_net_position,
            night_change_rate=night_change_rate,
            implied_volatility=implied_volatility,
            implied_volatility_change=implied_volatility_change,
        )

        directional_bias = rule_based.directional_bias
        gap_bias = rule_based.gap_bias
        volatility_bias = rule_based.volatility_bias
        confidence_bucket = rule_based.confidence_bucket
        explanation_text = rule_based.explanation_ko
        briefing_source = "rule_based"

        if briefing is not None:
            directional_bias = str(briefing.get("directional_bias") or directional_bias)
            gap_bias = str(briefing.get("gap_bias") or gap_bias)
            volatility_bias = str(briefing.get("volatility_bias") or volatility_bias)
            confidence_bucket = str(briefing.get("confidence_bucket") or confidence_bucket)
            explanation_text = str(briefing.get("explanation_ko") or explanation_text)
            briefing_source = "market_briefings"

        source_coverage = self._build_source_coverage(
            trade_date=resolved_date,
            derivatives_row=derivatives_row,
            pre_open_snapshot=pre_open_snapshot,
            night_snapshot=night_snapshot,
            briefing=briefing,
            participant_summary=participant_summary,
            expiry_or_contract_summary=expiry_or_contract_summary,
        )

        detail_level = 0
        if derivatives_row is not None:
            detail_level = 1
            has_participant = self._has_value(participant_summary) or any(
                value is not None for value in investor_flows.values()
            )
            if has_participant:
                detail_level = 2
            if self._has_value(expiry_or_contract_summary):
                detail_level = 3

        missing_fields = self._build_missing_fields(
            pcr=pcr,
            pcr_change=pcr_change,
            call_notional=call_notional,
            put_notional=put_notional,
            call_open_interest=call_open_interest,
            put_open_interest=put_open_interest,
            oi_change=oi_change,
            foreign_futures_net_position=foreign_futures_net_position,
            night_change_rate=night_change_rate,
            implied_volatility=implied_volatility,
            directional_bias=directional_bias,
            explanation_text=explanation_text,
            participant_summary=participant_summary,
            expiry_or_contract_summary=expiry_or_contract_summary,
        )

        if derivatives_row is None:
            logger.warning(
                "derivatives_summary_daily_metrics_missing",
                extra={"requested_date": requested_date, "resolved_date": resolved_date},
            )
        if night_snapshot is None:
            logger.info(
                "derivatives_summary_night_snapshot_missing",
                extra={"requested_date": requested_date, "resolved_date": resolved_date},
            )
        if pre_open_snapshot is None:
            logger.info(
                "derivatives_summary_pre_open_snapshot_missing",
                extra={"requested_date": requested_date, "resolved_date": resolved_date},
            )

        return {
            "requested_date": requested_date,
            "date": resolved_date,
            "requested_date_available": requested_date_available,
            "is_latest_fallback": not requested_date_available,
            "source_coverage": source_coverage,
            "pcr": pcr,
            "pcr_change": pcr_change,
            "call_notional": call_notional,
            "put_notional": put_notional,
            "call_open_interest": call_open_interest,
            "put_open_interest": put_open_interest,
            "open_interest_total": open_interest_total,
            "oi_change": oi_change,
            "investor_flows": investor_flows,
            "foreign_futures_net_position": foreign_futures_net_position,
            "pre_open_futures": {
                "signal": self._night_signal(pre_open_change_rate),
                "change_rate": pre_open_change_rate,
                "price": self._extract_float_metric(pre_open_snapshot, ("price",)),
                "price_change": self._extract_float_metric(pre_open_snapshot, ("price_change",)),
                "instrument_code": self._extract_text_metric(pre_open_snapshot, ("instrument_code",)),
                "instrument_name": self._extract_text_metric(pre_open_snapshot, ("instrument_name",)),
                "snapshot_time": pre_open_snapshot.get("snapshot_time") if pre_open_snapshot else None,
                "source_name": pre_open_snapshot.get("source_name") if pre_open_snapshot else None,
                "source_url": pre_open_snapshot.get("source_url") if pre_open_snapshot else None,
            },
            "night_futures": {
                "signal": self._night_signal(night_change_rate),
                "change_rate": night_change_rate,
                "price": self._extract_float_metric(night_snapshot, ("price",)),
                "price_change": self._extract_float_metric(night_snapshot, ("price_change",)),
                "instrument_code": self._extract_text_metric(night_snapshot, ("instrument_code",)),
                "instrument_name": self._extract_text_metric(night_snapshot, ("instrument_name",)),
                "snapshot_time": night_snapshot.get("snapshot_time") if night_snapshot else None,
                "source_name": night_snapshot.get("source_name") if night_snapshot else None,
                "source_url": night_snapshot.get("source_url") if night_snapshot else None,
            },
            "implied_volatility": implied_volatility,
            "implied_volatility_change": implied_volatility_change,
            "directional_bias": directional_bias,
            "gap_bias": gap_bias,
            "volatility_bias": volatility_bias,
            "confidence_bucket": confidence_bucket,
            "explanation_text": explanation_text,
            "briefing_source": briefing_source,
            "participant_summary": participant_summary,
            "expiry_or_contract_summary": expiry_or_contract_summary,
            "detail_level": detail_level,
            "components": components if components else rule_based.components,
            "last_updated_at": self._latest_timestamp(
                derivatives_row,
                pre_open_snapshot,
                night_snapshot,
                briefing,
            ),
            "missing_fields": missing_fields,
        }

    def get_trends(self, *, preset: str = "20d", date: str | None = None) -> dict[str, Any]:
        requested_date = (date or "").strip() or None
        session_count = self._parse_preset_sessions(preset)

        with get_connection(self.db_path) as connection:
            rows = self._select_derivatives_trend_rows(
                connection,
                up_to_date=requested_date,
                session_count=session_count,
            )

        items = [
            {
                "date": row.get("trade_date"),
                "pcr": self._extract_float_metric(row, ("put_call_ratio", "pcr")),
                "call_open_interest": self._extract_float_metric(
                    row, ("call_open_interest", "call_oi", "call_openint")
                ),
                "put_open_interest": self._extract_float_metric(
                    row, ("put_open_interest", "put_oi", "put_openint")
                ),
                "open_interest_total": self._extract_float_metric(
                    row, ("open_interest_total", "open_interest", "total_open_interest")
                ),
                "implied_volatility": self._extract_float_metric(
                    row, ("implied_volatility", "iv", "vkospi")
                ),
                "source_name": row.get("source_name"),
            }
            for row in rows
        ]

        items.sort(key=lambda item: str(item.get("date") or ""))

        return {
            "preset": f"{session_count}d",
            "date": items[-1]["date"] if items else requested_date,
            "items": items,
            "missing_fields": self._trend_missing_fields(items),
        }

    def get_investor_flow(self, *, preset: str = "20d", date: str | None = None) -> dict[str, Any]:
        requested_date = (date or "").strip() or None
        session_count = self._parse_preset_sessions(preset)

        with get_connection(self.db_path) as connection:
            rows = self._select_derivatives_trend_rows(
                connection,
                up_to_date=requested_date,
                session_count=session_count,
            )

        items: list[dict[str, Any]] = []
        for row in rows:
            items.append(
                {
                    "date": row.get("trade_date"),
                    "futures_foreign_net_buy": self._extract_float_metric(
                        row, ("futures_investor_foreign_net_buy", "futures_foreign_net_buy")
                    ),
                    "futures_institution_net_buy": self._extract_float_metric(
                        row, ("futures_investor_institution_net_buy", "futures_institution_net_buy")
                    ),
                    "futures_individual_net_buy": self._extract_float_metric(
                        row, ("futures_investor_individual_net_buy", "futures_individual_net_buy")
                    ),
                    "options_foreign_net_buy": self._extract_float_metric(
                        row, ("options_investor_foreign_net_buy", "options_foreign_net_buy")
                    ),
                    "options_institution_net_buy": self._extract_float_metric(
                        row, ("options_investor_institution_net_buy", "options_institution_net_buy")
                    ),
                    "options_individual_net_buy": self._extract_float_metric(
                        row, ("options_investor_individual_net_buy", "options_individual_net_buy")
                    ),
                    "source_name": row.get("source_name"),
                }
            )

        items.sort(key=lambda item: str(item.get("date") or ""))

        missing_fields: list[str] = []
        if items and all(item.get("futures_foreign_net_buy") is None for item in items):
            missing_fields.append("futures_investor_foreign_net_buy")
        if items and all(item.get("options_foreign_net_buy") is None for item in items):
            missing_fields.append("options_investor_foreign_net_buy")

        return {
            "preset": f"{session_count}d",
            "date": items[-1]["date"] if items else requested_date,
            "items": items,
            "missing_fields": missing_fields,
        }

    def get_briefing(self, *, date: str | None = None) -> dict[str, Any]:
        summary = self.get_summary(date=date)

        return {
            "requested_date": summary["requested_date"],
            "date": summary["date"],
            "directional_bias": summary["directional_bias"],
            "gap_bias": summary["gap_bias"],
            "volatility_bias": summary["volatility_bias"],
            "confidence_bucket": summary["confidence_bucket"],
            "explanation_text": summary["explanation_text"],
            "briefing_source": summary["briefing_source"],
            "components": summary["components"],
            "source_coverage": summary["source_coverage"],
            "last_updated_at": summary["last_updated_at"],
            "missing_fields": summary["missing_fields"],
        }

    def get_coverage(self, *, date: str | None = None) -> dict[str, Any]:
        summary = self.get_summary(date=date)
        return {
            "requested_date": summary["requested_date"],
            "date": summary["date"],
            "requested_date_available": summary["requested_date_available"],
            "is_latest_fallback": summary["is_latest_fallback"],
            "source_coverage": summary["source_coverage"],
            "detail_level": summary["detail_level"],
            "missing_fields": summary["missing_fields"],
            "last_updated_at": summary["last_updated_at"],
        }

    def _parse_preset_sessions(self, preset: str) -> int:
        normalized = (preset or "20d").strip().lower()
        match = re.fullmatch(r"(\d{1,3})d", normalized)
        if not match:
            return 20
        sessions = int(match.group(1))
        return max(5, min(sessions, 120))

    def _select_latest_derivatives_row(self, connection, *, up_to_date: str | None) -> dict[str, Any] | None:
        filters: list[str] = []
        params: list[Any] = []
        if up_to_date:
            filters.append("trade_date <= ?")
            params.append(up_to_date)

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        row = connection.execute(
            f"""
            WITH ranked AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (
                        PARTITION BY trade_date
                        ORDER BY
                            CASE
                                WHEN source_name = 'KRX_DERIVATIVES_REFERENCE' THEN 0
                                WHEN source_name = 'KRX_DERIVATIVES_MANUAL' THEN 1
                                ELSE 2
                            END,
                            id DESC
                    ) AS row_rank
                FROM derivatives_daily_metrics
                {where_clause}
            )
            SELECT *
            FROM ranked
            WHERE row_rank = 1
            ORDER BY trade_date DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
        return self._deserialize_derivatives_row(row)

    def _select_previous_derivatives_row(self, connection, *, trade_date: str | None) -> dict[str, Any] | None:
        if not trade_date:
            return None
        row = connection.execute(
            """
            WITH ranked AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (
                        PARTITION BY trade_date
                        ORDER BY
                            CASE
                                WHEN source_name = 'KRX_DERIVATIVES_REFERENCE' THEN 0
                                WHEN source_name = 'KRX_DERIVATIVES_MANUAL' THEN 1
                                ELSE 2
                            END,
                            id DESC
                    ) AS row_rank
                FROM derivatives_daily_metrics
                WHERE trade_date < ?
            )
            SELECT *
            FROM ranked
            WHERE row_rank = 1
            ORDER BY trade_date DESC
            LIMIT 1
            """,
            (trade_date,),
        ).fetchone()
        return self._deserialize_derivatives_row(row)

    def _select_derivatives_trend_rows(
        self,
        connection,
        *,
        up_to_date: str | None,
        session_count: int,
    ) -> list[dict[str, Any]]:
        filters: list[str] = []
        params: list[Any] = []
        if up_to_date:
            filters.append("trade_date <= ?")
            params.append(up_to_date)

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(session_count)

        rows = connection.execute(
            f"""
            WITH ranked AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (
                        PARTITION BY trade_date
                        ORDER BY
                            CASE
                                WHEN source_name = 'KRX_DERIVATIVES_REFERENCE' THEN 0
                                WHEN source_name = 'KRX_DERIVATIVES_MANUAL' THEN 1
                                ELSE 2
                            END,
                            id DESC
                    ) AS row_rank
                FROM derivatives_daily_metrics
                {where_clause}
            )
            SELECT *
            FROM ranked
            WHERE row_rank = 1
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [self._deserialize_derivatives_row(row) for row in rows]

    def _select_night_snapshot_row(self, connection, *, trade_date: str) -> dict[str, Any] | None:
        row = connection.execute(
            """
            SELECT *
            FROM market_intraday_snapshots
            WHERE trade_date = ? AND session_type = 'NIGHT_SESSION'
            ORDER BY
                CASE
                    WHEN source_name = 'KIS_NIGHT_FUTURES' THEN 0
                    ELSE 1
                END,
                snapshot_time DESC,
                id DESC
            LIMIT 1
            """,
            (trade_date,),
        ).fetchone()
        return self._deserialize_snapshot_row(row)

    def _select_pre_open_snapshot_row(self, connection, *, trade_date: str) -> dict[str, Any] | None:
        row = connection.execute(
            """
            SELECT *
            FROM market_intraday_snapshots
            WHERE trade_date = ? AND session_type = 'PRE_OPEN'
            ORDER BY
                CASE
                    WHEN source_name = 'KIS_DOMESTIC_DERIVATIVES' THEN 0
                    ELSE 1
                END,
                CASE
                    WHEN instrument_name LIKE '%KOSPI200%' THEN 0
                    WHEN instrument_code LIKE '101%' THEN 1
                    ELSE 2
                END,
                snapshot_time DESC,
                id DESC
            LIMIT 1
            """,
            (trade_date,),
        ).fetchone()
        return self._deserialize_snapshot_row(row)

    def _select_latest_briefing_row(self, connection, *, up_to_date: str | None) -> dict[str, Any] | None:
        filters = ["market_scope = ?"]
        params: list[Any] = [self.market_scope]
        if up_to_date:
            filters.append("trade_date <= ?")
            params.append(up_to_date)

        where_clause = f"WHERE {' AND '.join(filters)}"
        row = connection.execute(
            f"""
            SELECT *
            FROM market_briefings
            {where_clause}
            ORDER BY trade_date DESC, id DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
        return self._deserialize_briefing_row(row)

    def _latest_briefing_trade_date(self, connection) -> str | None:
        row = connection.execute(
            """
            SELECT trade_date
            FROM market_briefings
            WHERE market_scope = ?
            ORDER BY trade_date DESC, id DESC
            LIMIT 1
            """,
            (self.market_scope,),
        ).fetchone()
        if row is None:
            return None
        return str(row["trade_date"])

    def _select_components(self, connection, *, briefing_id: int) -> list[dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT *
            FROM market_signal_components
            WHERE briefing_id = ?
            ORDER BY ABS(score) DESC, id ASC
            """,
            (briefing_id,),
        ).fetchall()

        items: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["threshold"] = _json_load(payload.pop("threshold_json", None))
            payload["metadata"] = _json_load(payload.pop("metadata_json", None))
            payload["data_available"] = bool(payload.get("data_available", 0))
            items.append(payload)
        return items

    def _deserialize_derivatives_row(self, row) -> dict[str, Any] | None:
        if row is None:
            return None
        payload = dict(row)
        payload["additional_metrics"] = _json_load(payload.pop("additional_metrics_json", None)) or {}
        payload["raw_payload"] = _json_load(payload.pop("raw_payload_json", None))
        payload.pop("row_rank", None)
        return payload

    def _deserialize_snapshot_row(self, row) -> dict[str, Any] | None:
        if row is None:
            return None
        payload = dict(row)
        payload["additional_metrics"] = _json_load(payload.pop("additional_metrics_json", None)) or {}
        payload["raw_payload"] = _json_load(payload.pop("raw_payload_json", None))
        return payload

    def _deserialize_briefing_row(self, row) -> dict[str, Any] | None:
        if row is None:
            return None
        payload = dict(row)
        payload["json_payload"] = _json_load(payload.get("json_payload"))
        payload["notification_payload"] = _json_load(payload.pop("notification_payload_json", None))
        payload["rule_config"] = _json_load(payload.pop("rule_config_json", None))
        payload["input_snapshot"] = _json_load(payload.pop("input_snapshot_json", None))
        return payload

    def _extract_float_metric(self, row: dict[str, Any] | None, aliases: tuple[str, ...]) -> float | None:
        value = self._extract_metric_value(row, aliases)
        return _as_float(value)

    def _extract_text_metric(self, row: dict[str, Any] | None, aliases: tuple[str, ...]) -> str | None:
        value = self._extract_metric_value(row, aliases)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _extract_metric_value(self, row: dict[str, Any] | None, aliases: tuple[str, ...]) -> Any:
        if row is None:
            return None

        containers: list[dict[str, Any]] = [row]
        additional = row.get("additional_metrics")
        if isinstance(additional, dict):
            containers.append(additional)

        normalized_aliases = {_normalize_key(alias): alias for alias in aliases}
        for container in containers:
            for key, value in container.items():
                if _normalize_key(str(key)) in normalized_aliases:
                    if value is None:
                        continue
                    return value
        return None

    def _extract_detail_block(
        self,
        row: dict[str, Any] | None,
        aliases: tuple[str, ...],
    ) -> Any:
        value = self._extract_metric_value(row, aliases)
        if isinstance(value, (dict, list)):
            return value
        return None

    def _build_participant_summary(self, investor_flows: dict[str, float | None]) -> list[dict[str, Any]] | None:
        participants = [
            (
                "외국인",
                investor_flows.get("futures_foreign_net_buy"),
                investor_flows.get("options_foreign_net_buy"),
            ),
            (
                "기관",
                investor_flows.get("futures_institution_net_buy"),
                investor_flows.get("options_institution_net_buy"),
            ),
            (
                "개인",
                investor_flows.get("futures_individual_net_buy"),
                investor_flows.get("options_individual_net_buy"),
            ),
        ]

        items = []
        for name, futures_value, options_value in participants:
            if futures_value is None and options_value is None:
                continue
            items.append(
                {
                    "participant": name,
                    "futures_net_buy": futures_value,
                    "options_net_buy": options_value,
                }
            )
        return items or None

    def _build_rule_based_briefing(
        self,
        *,
        trade_date: str | None,
        pcr: float | None,
        pcr_change: float | None,
        call_open_interest: float | None,
        put_open_interest: float | None,
        oi_change: float | None,
        foreign_futures_flow: float | None,
        night_change_rate: float | None,
        implied_volatility: float | None,
        implied_volatility_change: float | None,
    ) -> RuleBasedBriefing:
        score = 0.0
        volatility_score = 0.0
        observed_signals = 0
        components: list[dict[str, Any]] = []

        def add_component(component_key: str, label: str, raw_value: Any, delta_score: float, note: str) -> None:
            nonlocal score, observed_signals
            score += delta_score
            observed_signals += 1
            components.append(
                {
                    "component_key": component_key,
                    "component_label": label,
                    "raw_value": raw_value,
                    "score": round(delta_score, 4),
                    "explanation_ko": note,
                    "source_table": "derivatives_daily_metrics"
                    if component_key != "night_futures_gap_signal"
                    else "market_intraday_snapshots",
                    "data_available": True,
                }
            )

        if pcr is not None:
            if pcr <= 0.95:
                add_component(
                    "put_call_ratio_pressure",
                    "Put/Call 비율 압력",
                    pcr,
                    1.0,
                    f"Put/Call 비율 {pcr:.3f}는 콜 우위로 해석했습니다.",
                )
            elif pcr >= 1.05:
                add_component(
                    "put_call_ratio_pressure",
                    "Put/Call 비율 압력",
                    pcr,
                    -1.0,
                    f"Put/Call 비율 {pcr:.3f}는 풋 우위로 해석했습니다.",
                )
            else:
                add_component(
                    "put_call_ratio_pressure",
                    "Put/Call 비율 압력",
                    pcr,
                    0.0,
                    f"Put/Call 비율 {pcr:.3f}는 중립 범위로 해석했습니다.",
                )

        if pcr_change is not None:
            pcr_delta_score = 0.0
            if pcr_change <= -2.0:
                pcr_delta_score = 0.35
            elif pcr_change >= 2.0:
                pcr_delta_score = -0.35
            add_component(
                "put_call_change",
                "Put/Call 변화율",
                pcr_change,
                pcr_delta_score,
                f"Put/Call 전일 대비 변화율 {pcr_change:.2f}%를 반영했습니다.",
            )

        if call_open_interest is not None and put_open_interest is not None:
            oi_delta_score = 0.0
            if call_open_interest > put_open_interest:
                oi_delta_score = 0.45
            elif call_open_interest < put_open_interest:
                oi_delta_score = -0.45
            add_component(
                "open_interest_balance",
                "콜/풋 OI 균형",
                {"call_open_interest": call_open_interest, "put_open_interest": put_open_interest},
                oi_delta_score,
                "콜/풋 미결제약정 상대 강도를 반영했습니다.",
            )

        if oi_change is not None:
            directional_hint = 1.0 if score >= 0 else -1.0
            oi_delta_score = 0.0
            if oi_change >= 4.0:
                oi_delta_score = 0.25 * directional_hint
                volatility_score += 0.35
            elif oi_change <= -4.0:
                oi_delta_score = -0.25 * directional_hint
                volatility_score -= 0.2
            add_component(
                "open_interest_change_pressure",
                "미결제약정 변화 압력",
                oi_change,
                oi_delta_score,
                f"미결제약정 변화율 {oi_change:.2f}%를 반영했습니다.",
            )

        if foreign_futures_flow is not None:
            flow_score = 0.0
            if foreign_futures_flow >= 500.0:
                flow_score = 0.8
            elif foreign_futures_flow <= -500.0:
                flow_score = -0.8
            add_component(
                "investor_futures_flow_pressure",
                "외국인 선물 순매수 압력",
                foreign_futures_flow,
                flow_score,
                f"외국인 선물 순매수 {foreign_futures_flow:.1f}를 반영했습니다.",
            )

        gap_bias = "flat"
        if night_change_rate is not None:
            gap_score = 0.0
            if night_change_rate >= 0.2:
                gap_bias = "gap_up"
                gap_score = 0.7
            elif night_change_rate <= -0.2:
                gap_bias = "gap_down"
                gap_score = -0.7
            if abs(night_change_rate) >= 0.6:
                volatility_score += 0.25
            add_component(
                "night_futures_gap_signal",
                "야간선물 갭 시그널",
                night_change_rate,
                gap_score,
                f"야간선물 변동률 {night_change_rate:.2f}%를 반영했습니다.",
            )

        if implied_volatility is not None:
            iv_score = 0.0
            if implied_volatility >= 22.0:
                volatility_score += 0.65
                iv_score = -0.2
            elif implied_volatility <= 16.0:
                volatility_score -= 0.45
                iv_score = 0.2
            add_component(
                "implied_volatility_pressure",
                "내재변동성 압력",
                implied_volatility,
                iv_score,
                f"내재변동성 {implied_volatility:.2f} 레벨을 반영했습니다.",
            )

        if implied_volatility_change is not None:
            observed_signals += 1
            if implied_volatility_change >= 3.5:
                volatility_score += 0.9
            elif implied_volatility_change <= -3.5:
                volatility_score -= 0.7
            components.append(
                {
                    "component_key": "implied_volatility_change",
                    "component_label": "내재변동성 변화율",
                    "raw_value": implied_volatility_change,
                    "score": 0.0,
                    "explanation_ko": f"내재변동성 변화율 {implied_volatility_change:.2f}%를 반영했습니다.",
                    "source_table": "derivatives_daily_metrics",
                    "data_available": True,
                }
            )

        directional_bias = "neutral"
        if score >= 1.0:
            directional_bias = "bullish"
        elif score <= -1.0:
            directional_bias = "bearish"

        volatility_bias = "stable"
        if volatility_score >= 0.8:
            volatility_bias = "rising"
        elif volatility_score <= -0.8:
            volatility_bias = "falling"

        coverage_ratio = observed_signals / 7.0
        abs_score = abs(score)
        confidence_bucket = "low"
        if abs_score >= 2.0 and coverage_ratio >= 0.75:
            confidence_bucket = "high"
        elif abs_score >= 1.0 and coverage_ratio >= 0.5:
            confidence_bucket = "medium"

        directional_label = {
            "bullish": "상방 우위",
            "bearish": "하방 우위",
            "neutral": "중립",
        }[directional_bias]
        gap_label = {
            "gap_up": "갭상승 가능성",
            "gap_down": "갭하락 가능성",
            "flat": "갭 중립",
        }[gap_bias]
        volatility_label = {
            "rising": "변동성 확대",
            "stable": "변동성 안정",
            "falling": "변동성 완화",
        }[volatility_bias]
        trade_date_text = trade_date or "최근 세션"
        explanation_ko = (
            f"{trade_date_text} 파생 지표 기준으로 방향성은 {directional_label}, "
            f"갭 해석은 {gap_label}, 변동성은 {volatility_label}로 해석했습니다. "
            f"(신뢰도 {confidence_bucket}) 본 해석은 정보 제공 목적이며 투자 성과를 보장하지 않습니다."
        )

        return RuleBasedBriefing(
            directional_bias=directional_bias,
            gap_bias=gap_bias,
            volatility_bias=volatility_bias,
            confidence_bucket=confidence_bucket,
            explanation_ko=explanation_ko,
            components=components,
        )

    def _build_source_coverage(
        self,
        *,
        trade_date: str | None,
        derivatives_row: dict[str, Any] | None,
        pre_open_snapshot: dict[str, Any] | None,
        night_snapshot: dict[str, Any] | None,
        briefing: dict[str, Any] | None,
        participant_summary: Any,
        expiry_or_contract_summary: Any,
    ) -> dict[str, Any]:
        sections = [
            {
                "key": "daily_metrics",
                "label": "파생 일간 요약",
                "status": "available" if derivatives_row else "missing",
                "source_name": derivatives_row.get("source_name") if derivatives_row else None,
                "updated_at": derivatives_row.get("updated_at") if derivatives_row else None,
            },
            {
                "key": "investor_flow",
                "label": "투자자 선물/옵션 수급",
                "status": "available" if self._has_value(participant_summary) else "missing",
                "source_name": derivatives_row.get("source_name") if derivatives_row else None,
                "updated_at": derivatives_row.get("updated_at") if derivatives_row else None,
            },
            {
                "key": "pre_open_futures",
                "label": "개장 전 선물 스냅샷",
                "status": "available" if pre_open_snapshot else "missing",
                "source_name": pre_open_snapshot.get("source_name") if pre_open_snapshot else None,
                "updated_at": pre_open_snapshot.get("updated_at") if pre_open_snapshot else None,
            },
            {
                "key": "night_futures",
                "label": "야간선물 스냅샷",
                "status": "available" if night_snapshot else "missing",
                "source_name": night_snapshot.get("source_name") if night_snapshot else None,
                "updated_at": night_snapshot.get("updated_at") if night_snapshot else None,
            },
            {
                "key": "briefing",
                "label": "방향성 해석",
                "status": "available" if briefing else "rule_based",
                "source_name": "MARKET_BRIEFINGS" if briefing else "DETERMINISTIC_RULES",
                "updated_at": briefing.get("updated_at") if briefing else None,
            },
            {
                "key": "contract_breakdown",
                "label": "만기/계약 상세",
                "status": "available" if self._has_value(expiry_or_contract_summary) else "missing",
                "source_name": derivatives_row.get("source_name") if derivatives_row else None,
                "updated_at": derivatives_row.get("updated_at") if derivatives_row else None,
            },
        ]

        available_count = sum(
            1 for section in sections if section["status"] in {"available", "rule_based"}
        )
        source_names = sorted(
            {
                section["source_name"]
                for section in sections
                if section.get("source_name")
            }
        )
        return {
            "trade_date": trade_date,
            "coverage_ratio": round(available_count / len(sections), 4) if sections else 0.0,
            "sections": sections,
            "source_names": source_names,
        }

    def _build_missing_fields(
        self,
        *,
        pcr: float | None,
        pcr_change: float | None,
        call_notional: float | None,
        put_notional: float | None,
        call_open_interest: float | None,
        put_open_interest: float | None,
        oi_change: float | None,
        foreign_futures_net_position: float | None,
        night_change_rate: float | None,
        implied_volatility: float | None,
        directional_bias: str | None,
        explanation_text: str | None,
        participant_summary: Any,
        expiry_or_contract_summary: Any,
    ) -> list[str]:
        missing: list[str] = []
        if pcr is None:
            missing.append("pcr")
        if pcr_change is None:
            missing.append("pcr_change")
        if call_notional is None:
            missing.append("call_notional")
        if put_notional is None:
            missing.append("put_notional")
        if call_open_interest is None:
            missing.append("call_open_interest")
        if put_open_interest is None:
            missing.append("put_open_interest")
        if oi_change is None:
            missing.append("oi_change")
        if foreign_futures_net_position is None:
            missing.append("foreign_futures_net_position")
        if night_change_rate is None:
            missing.append("night_futures_change_rate")
        if implied_volatility is None:
            missing.append("implied_volatility")
        if not directional_bias:
            missing.append("directional_bias")
        if not explanation_text:
            missing.append("explanation_text")
        if not self._has_value(participant_summary):
            missing.append("participant_summary")
        if not self._has_value(expiry_or_contract_summary):
            missing.append("expiry_or_contract_summary")
        return missing

    def _trend_missing_fields(self, items: list[dict[str, Any]]) -> list[str]:
        if not items:
            return [
                "pcr",
                "call_open_interest",
                "put_open_interest",
                "implied_volatility",
            ]

        missing: list[str] = []
        if all(item.get("pcr") is None for item in items):
            missing.append("pcr")
        if all(item.get("call_open_interest") is None for item in items):
            missing.append("call_open_interest")
        if all(item.get("put_open_interest") is None for item in items):
            missing.append("put_open_interest")
        if all(item.get("implied_volatility") is None for item in items):
            missing.append("implied_volatility")
        return missing

    def _night_signal(self, change_rate: float | None) -> str | None:
        if change_rate is None:
            return None
        if change_rate >= 0.2:
            return "gap_up"
        if change_rate <= -0.2:
            return "gap_down"
        return "flat"

    def _latest_timestamp(self, *rows: dict[str, Any] | None) -> str | None:
        timestamps: list[str] = []
        for row in rows:
            if row is None:
                continue
            for key in ("updated_at", "generated_at", "snapshot_time", "trade_date"):
                value = row.get(key)
                if isinstance(value, str) and value.strip():
                    timestamps.append(value.strip())
                    break
        if not timestamps:
            return None
        return max(timestamps)

    def _has_value(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, dict, set)):
            return len(value) > 0
        return True
