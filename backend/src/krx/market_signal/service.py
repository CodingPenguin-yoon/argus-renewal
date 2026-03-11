from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
from typing import Any

from ...config.env import Settings
from ..company_master.db import get_connection
from ..derivatives.service import DerivativesDashboardService

logger = logging.getLogger(__name__)


def _normalize_key(value: str) -> str:
    return "".join(ch for ch in value.lower().strip() if ch not in {"_", "-", " "})


def _json_load(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list, int, float)):
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


def _sign(value: float | None, *, threshold: float = 0.0) -> int:
    if value is None:
        return 0
    if value > threshold:
        return 1
    if value < -threshold:
        return -1
    return 0


def _format_number(value: float | None, fraction_digits: int = 0) -> str:
    if value is None:
        return "-"
    return f"{value:,.{fraction_digits}f}"


def _format_signed_number(value: float | None, fraction_digits: int = 0) -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{_format_number(value, fraction_digits)}"


def _format_signed_percent(value: float | None, fraction_digits: int = 2) -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{_format_number(value, fraction_digits)}%"


def _format_notional_krw(value: float | None) -> str:
    if value is None:
        return "-"
    abs_value = abs(value)
    if abs_value >= 1_000_000_000_000:
        return f"{_format_signed_number(value / 1_000_000_000_000, 2)}조"
    if abs_value >= 100_000_000:
        return f"{_format_signed_number(value / 100_000_000, 1)}억"
    return _format_signed_number(value, 0)


def _format_ratio(value: float | None, fraction_digits: int = 2) -> str:
    if value is None:
        return "-"
    return _format_number(value, fraction_digits)


def _source_coverage_state(ratio: float) -> str:
    if ratio >= 0.9999:
        return "full"
    if ratio > 0:
        return "partial"
    return "missing"


def _coverage_badge_payload(available_count: int, expected_count: int, source_names: list[str]) -> dict[str, Any]:
    ratio = round(available_count / expected_count, 4) if expected_count else 0.0
    return {
        "state": _source_coverage_state(ratio),
        "coverage_ratio": ratio,
        "label": f"소스 {available_count}/{expected_count}",
        "source_names": source_names,
    }


def _metric_payload(
    *,
    key: str,
    label: str,
    raw_value: Any,
    formatted_value: str,
    source_table: str | None,
    source_name: str | None,
    source_url: str | None,
    source_record_id: str | None,
    trade_date: str | None,
    metric_key: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "raw_value": raw_value,
        "formatted_value": formatted_value,
        "provenance": {
            "source_table": source_table,
            "source_name": source_name,
            "source_url": source_url,
            "source_record_id": source_record_id,
            "trade_date": trade_date,
            "metric_key": metric_key,
        },
    }


def _card_payload(
    *,
    key: str,
    title: str,
    tone: str,
    interpretation_line: str,
    detail_text: str | None,
    trend_badge: dict[str, Any] | None,
    source_coverage: dict[str, Any],
    supporting_metrics: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "tone": tone,
        "interpretation_line": interpretation_line,
        "detail_text": detail_text,
        "trend_badge": trend_badge,
        "source_coverage": source_coverage,
        "supporting_metrics": supporting_metrics,
    }


@dataclass(frozen=True)
class TrendWindow:
    current: float | None
    previous: float | None
    average: float | None


class MarketSignalService:
    def __init__(self, *, db_path: str, market_scope: str = "KRX") -> None:
        self.db_path = db_path
        self.market_scope = (market_scope or "KRX").strip().upper() or "KRX"
        self.derivatives_service = DerivativesDashboardService(
            db_path=db_path,
            market_scope=self.market_scope,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> "MarketSignalService":
        return cls(
            db_path=settings.db_path,
            market_scope=settings.market_briefing_signal_market_scope,
        )

    def get_summary(self, *, date: str | None = None) -> dict[str, Any]:
        requested_date = (date or "").strip() or None
        derivatives_summary = self.derivatives_service.get_summary(date=requested_date)
        resolved_date = derivatives_summary.get("date")

        with get_connection(self.db_path) as connection:
            if resolved_date is None:
                current_daily = self._select_latest_daily_factor_row(connection, up_to_date=requested_date)
                resolved_date = current_daily.get("trade_date") if current_daily else requested_date
            current_daily = (
                self._select_latest_daily_factor_row(connection, up_to_date=resolved_date)
                if resolved_date
                else None
            )
            current_daily_trade_date = current_daily.get("trade_date") if current_daily else resolved_date
            previous_daily = (
                self._select_previous_daily_factor_row(connection, trade_date=current_daily_trade_date)
                if current_daily_trade_date
                else None
            )
            daily_trend_rows = (
                self._select_daily_factor_trend_rows(
                    connection,
                    up_to_date=current_daily_trade_date,
                    session_count=20,
                )
                if current_daily_trade_date
                else []
            )

        requested_date_available = requested_date == resolved_date if requested_date else True
        last_updated_at = self._latest_timestamp(
            derivatives_summary.get("last_updated_at"),
            current_daily.get("updated_at") if current_daily else None,
        )

        foreign_flow = self._extract_float_metric(current_daily, ("investor_foreign_net_buy",))
        institution_flow = self._extract_float_metric(current_daily, ("investor_institution_net_buy",))
        individual_flow = self._extract_float_metric(current_daily, ("investor_individual_net_buy",))
        program_net_total = self._extract_float_metric(current_daily, ("program_net_total",))
        credit_balance_total = self._extract_float_metric(current_daily, ("credit_balance_total", "margin_loan_balance"))

        previous_foreign_flow = self._extract_float_metric(previous_daily, ("investor_foreign_net_buy",))
        previous_institution_flow = self._extract_float_metric(previous_daily, ("investor_institution_net_buy",))
        previous_program_net_total = self._extract_float_metric(previous_daily, ("program_net_total",))
        previous_credit_balance_total = self._extract_float_metric(
            previous_daily, ("credit_balance_total", "margin_loan_balance")
        )

        big_money_values = [value for value in (foreign_flow, institution_flow) if value is not None]
        previous_big_money_values = [
            value
            for value in (previous_foreign_flow, previous_institution_flow)
            if value is not None
        ]
        big_money_flow = sum(big_money_values) if big_money_values else None
        previous_big_money_flow = (
            sum(previous_big_money_values) if previous_big_money_values else None
        )
        credit_change_pct = _pct_change(credit_balance_total, previous_credit_balance_total)
        program_change = (
            None
            if program_net_total is None or previous_program_net_total is None
            else program_net_total - previous_program_net_total
        )

        overall_sections = self._build_overall_coverage_sections(
            current_daily=current_daily,
            derivatives_summary=derivatives_summary,
        )
        source_coverage = self._build_source_coverage_payload(
            trade_date=resolved_date,
            sections=overall_sections,
        )

        today_card = self._build_today_conclusion_card(
            current_daily=current_daily,
            derivatives_summary=derivatives_summary,
            big_money_flow=big_money_flow,
            previous_big_money_flow=previous_big_money_flow,
            program_net_total=program_net_total,
        )
        flow_card = self._build_fund_flow_card(
            current_daily=current_daily,
            foreign_flow=foreign_flow,
            institution_flow=institution_flow,
            individual_flow=individual_flow,
            big_money_flow=big_money_flow,
            previous_big_money_flow=previous_big_money_flow,
            program_net_total=program_net_total,
            program_change=program_change,
            credit_balance_total=credit_balance_total,
            credit_change_pct=credit_change_pct,
        )
        derivatives_card = self._build_derivatives_card(
            derivatives_summary=derivatives_summary,
        )
        checkpoints_card = self._build_checkpoints_card(
            current_daily=current_daily,
            derivatives_summary=derivatives_summary,
            credit_change_pct=credit_change_pct,
            daily_trend_rows=daily_trend_rows,
            source_coverage=source_coverage,
            last_updated_at=last_updated_at,
        )

        explanation_source = str(derivatives_summary.get("briefing_source") or "rule_based")
        explanation_text = str(derivatives_summary.get("explanation_text") or today_card["interpretation_line"])

        if source_coverage["state"] != "full":
            logger.info(
                "market_signal_summary_partial_coverage",
                extra={
                    "requested_date": requested_date,
                    "resolved_date": resolved_date,
                    "coverage_ratio": source_coverage["coverage_ratio"],
                    "source_names": source_coverage["source_names"],
                },
            )

        return {
            "requested_date": requested_date,
            "date": resolved_date,
            "requested_date_available": requested_date_available,
            "is_latest_fallback": not requested_date_available,
            "interpretation_line": today_card["interpretation_line"],
            "explanation_text": explanation_text,
            "explanation_source": explanation_source,
            "directional_bias": derivatives_summary.get("directional_bias", "neutral"),
            "gap_bias": derivatives_summary.get("gap_bias", "flat"),
            "volatility_bias": derivatives_summary.get("volatility_bias", "stable"),
            "confidence_bucket": derivatives_summary.get("confidence_bucket", "low"),
            "source_coverage": source_coverage,
            "cards": [today_card, flow_card, derivatives_card, checkpoints_card],
            "last_updated_at": last_updated_at,
            "missing_fields": self._build_missing_fields(
                current_daily=current_daily,
                derivatives_summary=derivatives_summary,
            ),
        }

    def get_trends(self, *, preset: str = "20d", date: str | None = None) -> dict[str, Any]:
        requested_date = (date or "").strip() or None
        session_count = self._parse_preset_sessions(preset)

        with get_connection(self.db_path) as connection:
            daily_rows = self._select_daily_factor_trend_rows(
                connection,
                up_to_date=requested_date,
                session_count=session_count,
            )
            night_rows = self._select_night_snapshot_trend_rows(
                connection,
                up_to_date=requested_date,
                session_count=session_count,
            )

        derivatives_trends = self.derivatives_service.get_trends(preset=f"{session_count}d", date=requested_date)
        derivatives_by_date = {
            str(item.get("date")): item
            for item in derivatives_trends.get("items", [])
            if item.get("date")
        }
        night_by_date = {
            str(item.get("trade_date")): item
            for item in night_rows
            if item.get("trade_date")
        }

        dates = sorted(
            {
                *[str(row.get("trade_date")) for row in daily_rows if row.get("trade_date")],
                *[str(item.get("date")) for item in derivatives_trends.get("items", []) if item.get("date")],
                *[str(row.get("trade_date")) for row in night_rows if row.get("trade_date")],
            }
        )

        items: list[dict[str, Any]] = []
        previous_credit: float | None = None
        for date_key in dates:
            daily_row = next((row for row in daily_rows if row.get("trade_date") == date_key), None)
            derivatives_row = derivatives_by_date.get(date_key)
            night_row = night_by_date.get(date_key)
            current_credit = self._extract_float_metric(daily_row, ("credit_balance_total", "margin_loan_balance"))
            items.append(
                {
                    "date": date_key,
                    "foreign_net_buy": self._extract_float_metric(daily_row, ("investor_foreign_net_buy",)),
                    "institution_net_buy": self._extract_float_metric(
                        daily_row, ("investor_institution_net_buy",)
                    ),
                    "individual_net_buy": self._extract_float_metric(daily_row, ("investor_individual_net_buy",)),
                    "program_net_total": self._extract_float_metric(daily_row, ("program_net_total",)),
                    "credit_balance_total": current_credit,
                    "credit_balance_change_pct": _pct_change(current_credit, previous_credit),
                    "futures_foreign_net_buy": _as_float(
                        derivatives_row.get("futures_foreign_net_buy") if derivatives_row else None
                    ),
                    "pcr": _as_float(derivatives_row.get("pcr") if derivatives_row else None),
                    "implied_volatility": _as_float(
                        derivatives_row.get("implied_volatility") if derivatives_row else None
                    ),
                    "night_futures_change_rate": self._extract_float_metric(night_row, ("change_rate", "price_change")),
                    "source_names": sorted(
                        {
                            value
                            for value in (
                                daily_row.get("source_name") if daily_row else None,
                                derivatives_row.get("source_name") if derivatives_row else None,
                                night_row.get("source_name") if night_row else None,
                            )
                            if value
                        }
                    ),
                }
            )
            if current_credit is not None:
                previous_credit = current_credit

        missing_fields: list[str] = []
        if items and all(item.get("foreign_net_buy") is None for item in items):
            missing_fields.append("foreign_net_buy")
        if items and all(item.get("program_net_total") is None for item in items):
            missing_fields.append("program_net_total")
        if items and all(item.get("credit_balance_total") is None for item in items):
            missing_fields.append("credit_balance_total")
        if items and all(item.get("futures_foreign_net_buy") is None for item in items):
            missing_fields.append("futures_foreign_net_buy")
        if items and all(item.get("pcr") is None for item in items):
            missing_fields.append("pcr")
        if items and all(item.get("night_futures_change_rate") is None for item in items):
            missing_fields.append("night_futures_change_rate")

        return {
            "preset": f"{session_count}d",
            "date": items[-1]["date"] if items else requested_date,
            "items": items,
            "missing_fields": missing_fields,
        }

    def get_components(self, *, date: str | None = None) -> dict[str, Any]:
        summary = self.get_summary(date=date)
        requested_date = summary.get("requested_date")
        resolved_date = summary.get("date")
        derivatives_summary = self.derivatives_service.get_summary(date=resolved_date)

        with get_connection(self.db_path) as connection:
            current_daily = (
                self._select_latest_daily_factor_row(connection, up_to_date=resolved_date)
                if resolved_date
                else None
            )
            previous_daily = (
                self._select_previous_daily_factor_row(
                    connection,
                    trade_date=current_daily.get("trade_date") if current_daily else resolved_date,
                )
                if resolved_date
                else None
            )

        credit_now = self._extract_float_metric(current_daily, ("credit_balance_total", "margin_loan_balance"))
        credit_prev = self._extract_float_metric(previous_daily, ("credit_balance_total", "margin_loan_balance"))
        items = [
            self._synthetic_component(
                key="spot_flow",
                label="현물 수급",
                component_group="fund_flow",
                raw_value=self._extract_float_metric(current_daily, ("investor_foreign_net_buy",)),
                reference_value=self._extract_float_metric(current_daily, ("investor_institution_net_buy",)),
                delta_value=self._extract_float_metric(current_daily, ("investor_individual_net_buy",)),
                explanation=self._spot_flow_component_line(current_daily),
                source_table="market_daily_factors",
                source_row=current_daily,
                source_metric_key="investor_foreign_net_buy/investor_institution_net_buy/investor_individual_net_buy",
                score=self._spot_flow_score(current_daily),
            ),
            self._synthetic_component(
                key="program_trading",
                label="프로그램 매매",
                component_group="fund_flow",
                raw_value=self._extract_float_metric(current_daily, ("program_net_total",)),
                reference_value=self._extract_float_metric(current_daily, ("program_buy_total",)),
                delta_value=self._extract_float_metric(current_daily, ("program_sell_total",)),
                explanation=self._program_component_line(current_daily),
                source_table="market_daily_factors",
                source_row=current_daily,
                source_metric_key="program_net_total/program_buy_total/program_sell_total",
                score=self._program_score(current_daily),
            ),
            self._synthetic_component(
                key="credit_balance",
                label="신용잔고",
                component_group="fund_flow",
                raw_value=credit_now,
                reference_value=credit_prev,
                delta_value=_pct_change(credit_now, credit_prev),
                explanation=self._credit_component_line(credit_now=credit_now, credit_prev=credit_prev),
                source_table="market_daily_factors",
                source_row=current_daily,
                source_metric_key="credit_balance_total/margin_loan_balance",
                score=self._credit_score(credit_now=credit_now, credit_prev=credit_prev),
            ),
        ]

        for component in derivatives_summary.get("components", []) or []:
            items.append(
                {
                    "component_key": component.get("component_key"),
                    "component_label": component.get("component_label"),
                    "component_group": component.get("component_group") or "derivatives",
                    "raw_value": component.get("raw_value"),
                    "reference_value": component.get("reference_value"),
                    "delta_value": component.get("delta_value"),
                    "score": component.get("score"),
                    "data_available": bool(component.get("data_available")),
                    "explanation_ko": component.get("explanation_ko"),
                    "source_table": component.get("source_table"),
                    "source_name": component.get("source_name"),
                    "source_url": component.get("source_url"),
                    "source_record_id": component.get("source_record_id"),
                    "source_metric_key": component.get("source_metric_key"),
                    "metadata": component.get("metadata"),
                    "threshold": component.get("threshold"),
                }
            )

        items.sort(
            key=lambda item: abs(_as_float(item.get("score")) or 0.0),
            reverse=True,
        )

        return {
            "requested_date": requested_date,
            "date": resolved_date,
            "requested_date_available": summary.get("requested_date_available", True),
            "is_latest_fallback": summary.get("is_latest_fallback", False),
            "items": items,
            "source_coverage": summary.get("source_coverage"),
            "last_updated_at": summary.get("last_updated_at"),
        }

    def _build_today_conclusion_card(
        self,
        *,
        current_daily: dict[str, Any] | None,
        derivatives_summary: dict[str, Any],
        big_money_flow: float | None,
        previous_big_money_flow: float | None,
        program_net_total: float | None,
    ) -> dict[str, Any]:
        spot_sign = _sign(big_money_flow, threshold=150.0)
        derivatives_sign = {
            "bullish": 1,
            "bearish": -1,
            "neutral": 0,
        }.get(str(derivatives_summary.get("directional_bias") or "neutral"), 0)

        if spot_sign > 0 and derivatives_sign > 0:
            tone = "positive"
            interpretation_line = "큰손들의 베팅은 지금 상방 쪽으로 함께 기울고 있습니다."
        elif spot_sign < 0 and derivatives_sign < 0:
            tone = "negative"
            interpretation_line = "큰손들의 베팅은 지금 방어적이거나 하방 쪽으로 기울고 있습니다."
        elif spot_sign == 0 and derivatives_sign == 0:
            tone = "neutral"
            interpretation_line = "현물과 파생 모두 아직 한쪽으로 강하게 기운 신호는 아닙니다."
        else:
            tone = "neutral"
            interpretation_line = "현물과 파생이 엇갈려 큰손 베팅을 한 방향으로 단정하기 어렵습니다."

        trend_badge = self._overall_trend_badge(
            big_money_flow=big_money_flow,
            previous_big_money_flow=previous_big_money_flow,
            derivatives_summary=derivatives_summary,
        )
        source_names = sorted(
            {
                value
                for value in (
                    current_daily.get("source_name") if current_daily else None,
                    *list(derivatives_summary.get("source_coverage", {}).get("source_names", [])),
                )
                if value
            }
        )
        supporting_metrics = [
            _metric_payload(
                key="spot_big_money_flow",
                label="외국인+기관 현물",
                raw_value=big_money_flow,
                formatted_value=_format_notional_krw(big_money_flow),
                source_table="market_daily_factors",
                source_name=current_daily.get("source_name") if current_daily else None,
                source_url=current_daily.get("source_url") if current_daily else None,
                source_record_id=current_daily.get("source_record_id") if current_daily else None,
                trade_date=current_daily.get("trade_date") if current_daily else None,
                metric_key="investor_foreign_net_buy/investor_institution_net_buy",
            ),
            _metric_payload(
                key="foreign_futures_net",
                label="외국인 선물",
                raw_value=derivatives_summary.get("foreign_futures_net_position"),
                formatted_value=_format_signed_number(
                    _as_float(derivatives_summary.get("foreign_futures_net_position")),
                    0,
                ),
                source_table="derivatives_daily_metrics",
                source_name=self._source_name_from_derivatives_summary(derivatives_summary),
                source_url=self._source_url_from_derivatives_summary_component(
                    derivatives_summary,
                    "investor_futures_flow_pressure",
                ),
                source_record_id=None,
                trade_date=derivatives_summary.get("date"),
                metric_key="futures_investor_foreign_net_buy",
            ),
            _metric_payload(
                key="program_net_total",
                label="프로그램 순매수",
                raw_value=program_net_total,
                formatted_value=_format_notional_krw(program_net_total),
                source_table="market_daily_factors",
                source_name=current_daily.get("source_name") if current_daily else None,
                source_url=current_daily.get("source_url") if current_daily else None,
                source_record_id=current_daily.get("source_record_id") if current_daily else None,
                trade_date=current_daily.get("trade_date") if current_daily else None,
                metric_key="program_net_total",
            ),
        ]
        return _card_payload(
            key="today_conclusion",
            title="오늘 시장 결론",
            tone=tone,
            interpretation_line=interpretation_line,
            detail_text=str(derivatives_summary.get("explanation_text") or "") or None,
            trend_badge=trend_badge,
            source_coverage=_coverage_badge_payload(
                available_count=sum(
                    1
                    for value in (
                        current_daily is not None,
                        derivatives_summary.get("source_coverage", {}).get("coverage_ratio", 0) > 0,
                        derivatives_summary.get("night_futures", {}).get("change_rate") is not None,
                    )
                    if value
                ),
                expected_count=3,
                source_names=source_names,
            ),
            supporting_metrics=supporting_metrics,
        )

    def _build_fund_flow_card(
        self,
        *,
        current_daily: dict[str, Any] | None,
        foreign_flow: float | None,
        institution_flow: float | None,
        individual_flow: float | None,
        big_money_flow: float | None,
        previous_big_money_flow: float | None,
        program_net_total: float | None,
        program_change: float | None,
        credit_balance_total: float | None,
        credit_change_pct: float | None,
    ) -> dict[str, Any]:
        big_money_sign = _sign(big_money_flow, threshold=150.0)
        program_sign = _sign(program_net_total, threshold=100.0)
        credit_sign = _sign(credit_change_pct, threshold=0.25)

        if big_money_sign > 0 and program_sign >= 0:
            tone = "positive"
            interpretation_line = "현물 자금은 외국인·기관 쪽 유입이 우세해 받쳐주는 흐름입니다."
        elif big_money_sign < 0 and program_sign <= 0:
            tone = "negative"
            interpretation_line = "현물 자금은 외국인·기관 이탈과 프로그램 매도 우위가 겹칩니다."
        elif big_money_sign == 0 and program_sign == 0:
            tone = "neutral"
            interpretation_line = "현물 수급은 아직 뚜렷한 주도 자금이 보이지 않는 중립 구간입니다."
        else:
            tone = "neutral"
            interpretation_line = "현물 수급은 주체별 방향이 갈려 장중 확인이 더 필요합니다."

        if credit_sign > 0 and tone != "negative":
            interpretation_line += " 신용잔고는 위험 선호가 조금 살아나는 쪽입니다."
        elif credit_sign < 0 and tone != "positive":
            interpretation_line += " 신용잔고는 레버리지 확장보다 정리 쪽에 가깝습니다."

        trend_badge = self._fund_flow_trend_badge(
            big_money_flow=big_money_flow,
            previous_big_money_flow=previous_big_money_flow,
            program_change=program_change,
        )
        supporting_metrics = [
            _metric_payload(
                key="foreign_flow",
                label="외국인",
                raw_value=foreign_flow,
                formatted_value=_format_notional_krw(foreign_flow),
                source_table="market_daily_factors",
                source_name=current_daily.get("source_name") if current_daily else None,
                source_url=current_daily.get("source_url") if current_daily else None,
                source_record_id=current_daily.get("source_record_id") if current_daily else None,
                trade_date=current_daily.get("trade_date") if current_daily else None,
                metric_key="investor_foreign_net_buy",
            ),
            _metric_payload(
                key="institution_flow",
                label="기관",
                raw_value=institution_flow,
                formatted_value=_format_notional_krw(institution_flow),
                source_table="market_daily_factors",
                source_name=current_daily.get("source_name") if current_daily else None,
                source_url=current_daily.get("source_url") if current_daily else None,
                source_record_id=current_daily.get("source_record_id") if current_daily else None,
                trade_date=current_daily.get("trade_date") if current_daily else None,
                metric_key="investor_institution_net_buy",
            ),
            _metric_payload(
                key="credit_balance",
                label="신용잔고",
                raw_value=credit_balance_total,
                formatted_value=(
                    f"{_format_number(credit_balance_total / 100_000_000, 0)}억"
                    if credit_balance_total is not None
                    else "-"
                ),
                source_table="market_daily_factors",
                source_name=current_daily.get("source_name") if current_daily else None,
                source_url=current_daily.get("source_url") if current_daily else None,
                source_record_id=current_daily.get("source_record_id") if current_daily else None,
                trade_date=current_daily.get("trade_date") if current_daily else None,
                metric_key="credit_balance_total",
            ),
        ]
        return _card_payload(
            key="fund_flow",
            title="자금 흐름",
            tone=tone,
            interpretation_line=interpretation_line,
            detail_text=(
                f"개인 수급은 {_format_notional_krw(individual_flow)}이고 "
                f"프로그램 변화는 {_format_notional_krw(program_net_total)}입니다."
                if individual_flow is not None or program_net_total is not None
                else None
            ),
            trend_badge=trend_badge,
            source_coverage=_coverage_badge_payload(
                available_count=sum(
                    1
                    for value in (
                        foreign_flow is not None or institution_flow is not None or individual_flow is not None,
                        program_net_total is not None,
                        credit_balance_total is not None,
                    )
                    if value
                ),
                expected_count=3,
                source_names=(
                    [current_daily.get("source_name")]
                    if current_daily and current_daily.get("source_name")
                    else []
                ),
            ),
            supporting_metrics=supporting_metrics,
        )

    def _build_derivatives_card(self, *, derivatives_summary: dict[str, Any]) -> dict[str, Any]:
        directional_bias = str(derivatives_summary.get("directional_bias") or "neutral")
        gap_bias = str(derivatives_summary.get("gap_bias") or "flat")
        volatility_bias = str(derivatives_summary.get("volatility_bias") or "stable")
        tone = {
            "bullish": "positive",
            "bearish": "negative",
            "neutral": "neutral",
        }.get(directional_bias, "neutral")

        if directional_bias == "bullish":
            interpretation_line = "선물·옵션 쪽은 상방 베팅이 우세합니다."
        elif directional_bias == "bearish":
            interpretation_line = "선물·옵션 쪽은 방어적이거나 하방 베팅이 우세합니다."
        else:
            interpretation_line = "선물·옵션 쪽은 아직 한 방향 확신이 강하지 않습니다."

        if gap_bias == "gap_up":
            interpretation_line += " 야간선물은 상단 출발 가능성을 열어둡니다."
        elif gap_bias == "gap_down":
            interpretation_line += " 야간선물은 약한 출발 가능성을 시사합니다."

        if volatility_bias == "rising":
            interpretation_line += " 다만 변동성 확대 신호는 경계가 필요합니다."
        elif volatility_bias == "falling":
            interpretation_line += " 변동성은 이전보다 진정되는 흐름입니다."

        trend_badge = self._derivatives_trend_badge(derivatives_summary=derivatives_summary)
        supporting_metrics = [
            _metric_payload(
                key="pcr",
                label="PCR",
                raw_value=derivatives_summary.get("pcr"),
                formatted_value=_format_ratio(_as_float(derivatives_summary.get("pcr")), 2),
                source_table="derivatives_daily_metrics",
                source_name=self._source_name_from_derivatives_summary(derivatives_summary),
                source_url=self._source_url_from_derivatives_summary_component(
                    derivatives_summary,
                    "put_call_ratio_pressure",
                ),
                source_record_id=None,
                trade_date=derivatives_summary.get("date"),
                metric_key="put_call_ratio",
            ),
            _metric_payload(
                key="foreign_futures_net",
                label="외국인 선물",
                raw_value=derivatives_summary.get("foreign_futures_net_position"),
                formatted_value=_format_signed_number(
                    _as_float(derivatives_summary.get("foreign_futures_net_position")),
                    0,
                ),
                source_table="derivatives_daily_metrics",
                source_name=self._source_name_from_derivatives_summary(derivatives_summary),
                source_url=self._source_url_from_derivatives_summary_component(
                    derivatives_summary,
                    "investor_futures_flow_pressure",
                ),
                source_record_id=None,
                trade_date=derivatives_summary.get("date"),
                metric_key="futures_investor_foreign_net_buy",
            ),
            _metric_payload(
                key="night_futures_change",
                label="야간선물",
                raw_value=derivatives_summary.get("night_futures", {}).get("change_rate"),
                formatted_value=_format_signed_percent(
                    _as_float(derivatives_summary.get("night_futures", {}).get("change_rate")),
                    2,
                ),
                source_table="market_intraday_snapshots",
                source_name=derivatives_summary.get("night_futures", {}).get("source_name"),
                source_url=derivatives_summary.get("night_futures", {}).get("source_url"),
                source_record_id=None,
                trade_date=derivatives_summary.get("date"),
                metric_key="change_rate",
            ),
        ]
        return _card_payload(
            key="futures_options",
            title="선물·옵션 신호",
            tone=tone,
            interpretation_line=interpretation_line,
            detail_text=(
                f"IV는 {_format_ratio(_as_float(derivatives_summary.get('implied_volatility')), 2)}, "
                f"신뢰도는 {self._confidence_bucket_label(str(derivatives_summary.get('confidence_bucket') or 'low'))}입니다."
            ),
            trend_badge=trend_badge,
            source_coverage=_coverage_badge_payload(
                available_count=sum(
                    1
                    for value in (
                        derivatives_summary.get("pcr") is not None,
                        derivatives_summary.get("foreign_futures_net_position") is not None,
                        derivatives_summary.get("night_futures", {}).get("change_rate") is not None,
                    )
                    if value
                ),
                expected_count=3,
                source_names=list(derivatives_summary.get("source_coverage", {}).get("source_names", [])),
            ),
            supporting_metrics=supporting_metrics,
        )

    def _build_checkpoints_card(
        self,
        *,
        current_daily: dict[str, Any] | None,
        derivatives_summary: dict[str, Any],
        credit_change_pct: float | None,
        daily_trend_rows: list[dict[str, Any]],
        source_coverage: dict[str, Any],
        last_updated_at: str | None,
    ) -> dict[str, Any]:
        top_components = sorted(
            derivatives_summary.get("components", []) or [],
            key=lambda item: abs(_as_float(item.get("score")) or 0.0),
            reverse=True,
        )
        strongest_component = top_components[0] if top_components else None
        missing_count = len(source_coverage.get("sections", [])) - int(
            round(source_coverage.get("coverage_ratio", 0.0) * len(source_coverage.get("sections", [])))
        )

        if strongest_component is not None:
            strongest_label = str(strongest_component.get("component_label") or "핵심 요인")
            interpretation_line = f"오늘은 {strongest_label}와 프로그램 수급 지속 여부를 먼저 확인할 구간입니다."
        else:
            interpretation_line = "오늘은 데이터 공백보다 실제 체결 강도와 프로그램 수급 지속 여부를 먼저 확인해야 합니다."

        if derivatives_summary.get("night_futures", {}).get("change_rate") is not None:
            interpretation_line += " 야간선물 방향이 장 초반 심리를 좌우할 가능성이 큽니다."
        elif missing_count > 0:
            interpretation_line += " 일부 소스가 비어 있어 장중 재확인이 필요합니다."

        trend_badge = self._checkpoint_trend_badge(
            derivatives_summary=derivatives_summary,
            missing_count=max(missing_count, 0),
        )
        latest_big_money = self._trend_window(
            rows=daily_trend_rows,
            aliases=("investor_foreign_net_buy", "investor_institution_net_buy"),
        )
        supporting_metrics = [
            _metric_payload(
                key="top_component",
                label="최대 압력",
                raw_value=strongest_component.get("score") if strongest_component else None,
                formatted_value=str(strongest_component.get("component_label") or "-") if strongest_component else "-",
                source_table=strongest_component.get("source_table") if strongest_component else None,
                source_name=strongest_component.get("source_name") if strongest_component else None,
                source_url=strongest_component.get("source_url") if strongest_component else None,
                source_record_id=strongest_component.get("source_record_id") if strongest_component else None,
                trade_date=derivatives_summary.get("date"),
                metric_key=str(strongest_component.get("source_metric_key") or "") if strongest_component else "",
            ),
            _metric_payload(
                key="credit_change",
                label="신용잔고 변화",
                raw_value=credit_change_pct,
                formatted_value=_format_signed_percent(credit_change_pct, 2),
                source_table="market_daily_factors",
                source_name=current_daily.get("source_name") if current_daily else None,
                source_url=current_daily.get("source_url") if current_daily else None,
                source_record_id=current_daily.get("source_record_id") if current_daily else None,
                trade_date=current_daily.get("trade_date") if current_daily else None,
                metric_key="credit_balance_total",
            ),
            _metric_payload(
                key="last_updated_at",
                label="기준 시각",
                raw_value=last_updated_at,
                formatted_value=last_updated_at or "-",
                source_table=None,
                source_name=None,
                source_url=None,
                source_record_id=None,
                trade_date=derivatives_summary.get("date"),
                metric_key="last_updated_at",
            ),
        ]
        detail_text = None
        if latest_big_money.average is not None and latest_big_money.current is not None:
            detail_text = (
                f"최근 20세션 평균 대비 큰손 현물 유입은 "
                f"{_format_notional_krw(latest_big_money.current - latest_big_money.average)} 차이입니다."
            )
        return _card_payload(
            key="checkpoints",
            title="오늘 체크포인트",
            tone="neutral" if missing_count == 0 else "negative",
            interpretation_line=interpretation_line,
            detail_text=detail_text,
            trend_badge=trend_badge,
            source_coverage=_coverage_badge_payload(
                available_count=max(
                    len(source_coverage.get("sections", [])) - max(missing_count, 0),
                    0,
                ),
                expected_count=max(len(source_coverage.get("sections", [])), 1),
                source_names=list(source_coverage.get("source_names", [])),
            ),
            supporting_metrics=supporting_metrics,
        )

    def _build_overall_coverage_sections(
        self,
        *,
        current_daily: dict[str, Any] | None,
        derivatives_summary: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return [
            {
                "key": "spot_flow",
                "label": "현물 수급",
                "status": (
                    "available"
                    if any(
                        self._extract_float_metric(current_daily, (alias,)) is not None
                        for alias in (
                            "investor_foreign_net_buy",
                            "investor_institution_net_buy",
                            "investor_individual_net_buy",
                        )
                    )
                    else "missing"
                ),
                "source_name": current_daily.get("source_name") if current_daily else None,
                "updated_at": current_daily.get("updated_at") if current_daily else None,
            },
            {
                "key": "program_trading",
                "label": "프로그램 매매",
                "status": (
                    "available"
                    if self._extract_float_metric(current_daily, ("program_net_total",)) is not None
                    else "missing"
                ),
                "source_name": current_daily.get("source_name") if current_daily else None,
                "updated_at": current_daily.get("updated_at") if current_daily else None,
            },
            {
                "key": "credit_balance",
                "label": "신용잔고",
                "status": (
                    "available"
                    if self._extract_float_metric(
                        current_daily, ("credit_balance_total", "margin_loan_balance")
                    )
                    is not None
                    else "missing"
                ),
                "source_name": current_daily.get("source_name") if current_daily else None,
                "updated_at": current_daily.get("updated_at") if current_daily else None,
            },
            {
                "key": "derivatives",
                "label": "선물·옵션",
                "status": (
                    "available"
                    if derivatives_summary.get("source_coverage", {}).get("coverage_ratio", 0) > 0
                    else "missing"
                ),
                "source_name": self._source_name_from_derivatives_summary(derivatives_summary),
                "updated_at": derivatives_summary.get("last_updated_at"),
            },
            {
                "key": "night_futures",
                "label": "야간선물",
                "status": (
                    "available"
                    if derivatives_summary.get("night_futures", {}).get("change_rate") is not None
                    else "missing"
                ),
                "source_name": derivatives_summary.get("night_futures", {}).get("source_name"),
                "updated_at": derivatives_summary.get("night_futures", {}).get("snapshot_time"),
            },
            {
                "key": "interpretation",
                "label": "해석 레이어",
                "status": (
                    "available"
                    if derivatives_summary.get("briefing_source") == "market_briefings"
                    else "rule_based"
                ),
                "source_name": (
                    "MARKET_BRIEFINGS"
                    if derivatives_summary.get("briefing_source") == "market_briefings"
                    else "DETERMINISTIC_RULES"
                ),
                "updated_at": derivatives_summary.get("last_updated_at"),
            },
        ]

    def _build_source_coverage_payload(
        self,
        *,
        trade_date: str | None,
        sections: list[dict[str, Any]],
    ) -> dict[str, Any]:
        available_count = sum(
            1 for section in sections if section.get("status") in {"available", "rule_based"}
        )
        source_names = sorted(
            {
                str(section.get("source_name"))
                for section in sections
                if section.get("source_name")
            }
        )
        coverage = _coverage_badge_payload(
            available_count=available_count,
            expected_count=len(sections),
            source_names=source_names,
        )
        coverage["trade_date"] = trade_date
        coverage["sections"] = sections
        coverage["source_names"] = source_names
        return coverage

    def _build_missing_fields(
        self,
        *,
        current_daily: dict[str, Any] | None,
        derivatives_summary: dict[str, Any],
    ) -> list[str]:
        missing = list(derivatives_summary.get("missing_fields", []))
        if self._extract_float_metric(current_daily, ("investor_foreign_net_buy",)) is None:
            missing.append("investor_foreign_net_buy")
        if self._extract_float_metric(current_daily, ("investor_institution_net_buy",)) is None:
            missing.append("investor_institution_net_buy")
        if self._extract_float_metric(current_daily, ("program_net_total",)) is None:
            missing.append("program_net_total")
        if self._extract_float_metric(
            current_daily, ("credit_balance_total", "margin_loan_balance")
        ) is None:
            missing.append("credit_balance_total")
        return sorted(set(missing))

    def _source_name_from_derivatives_summary(self, summary: dict[str, Any]) -> str | None:
        source_names = summary.get("source_coverage", {}).get("source_names", [])
        if isinstance(source_names, list) and source_names:
            return str(source_names[0])
        return None

    def _source_url_from_derivatives_summary_component(
        self,
        summary: dict[str, Any],
        component_key: str,
    ) -> str | None:
        for item in summary.get("components", []) or []:
            if str(item.get("component_key")) == component_key:
                value = item.get("source_url")
                if value:
                    return str(value)
        return summary.get("night_futures", {}).get("source_url")

    def _confidence_bucket_label(self, value: str) -> str:
        mapping = {
            "high": "높음",
            "medium": "중간",
            "low": "낮음",
        }
        return mapping.get(value, "낮음")

    def _overall_trend_badge(
        self,
        *,
        big_money_flow: float | None,
        previous_big_money_flow: float | None,
        derivatives_summary: dict[str, Any],
    ) -> dict[str, Any] | None:
        derivatives_sign = {
            "bullish": 1,
            "bearish": -1,
            "neutral": 0,
        }.get(str(derivatives_summary.get("directional_bias") or "neutral"), 0)
        flow_delta = (
            None
            if big_money_flow is None or previous_big_money_flow is None
            else big_money_flow - previous_big_money_flow
        )
        if flow_delta is not None and flow_delta >= 300:
            return {"label": "상방 신호 강화", "tone": "positive"}
        if flow_delta is not None and flow_delta <= -300:
            return {"label": "방어 신호 강화", "tone": "negative"}
        if _sign(big_money_flow, threshold=150.0) != 0 and derivatives_sign != 0:
            if _sign(big_money_flow, threshold=150.0) == derivatives_sign:
                return {"label": "현물·파생 정합", "tone": "positive" if derivatives_sign > 0 else "negative"}
            return {"label": "현물·파생 엇갈림", "tone": "neutral"}
        return {"label": "신호 혼조", "tone": "neutral"}

    def _fund_flow_trend_badge(
        self,
        *,
        big_money_flow: float | None,
        previous_big_money_flow: float | None,
        program_change: float | None,
    ) -> dict[str, Any] | None:
        delta = (
            None
            if big_money_flow is None or previous_big_money_flow is None
            else big_money_flow - previous_big_money_flow
        )
        if delta is not None and delta >= 300:
            return {"label": "유입 강화", "tone": "positive"}
        if delta is not None and delta <= -300:
            return {"label": "이탈 확대", "tone": "negative"}
        if program_change is not None and program_change >= 150:
            return {"label": "프로그램 개선", "tone": "positive"}
        if program_change is not None and program_change <= -150:
            return {"label": "프로그램 약화", "tone": "negative"}
        return {"label": "주체 혼조", "tone": "neutral"}

    def _derivatives_trend_badge(self, *, derivatives_summary: dict[str, Any]) -> dict[str, Any] | None:
        pcr_change = _as_float(derivatives_summary.get("pcr_change"))
        night_change_rate = _as_float(derivatives_summary.get("night_futures", {}).get("change_rate"))
        volatility_bias = str(derivatives_summary.get("volatility_bias") or "stable")
        if pcr_change is not None and pcr_change <= -2.0:
            return {"label": "콜 우위 강화", "tone": "positive"}
        if pcr_change is not None and pcr_change >= 2.0:
            return {"label": "풋 우위 강화", "tone": "negative"}
        if night_change_rate is not None and night_change_rate >= 0.4:
            return {"label": "야간 상방", "tone": "positive"}
        if night_change_rate is not None and night_change_rate <= -0.4:
            return {"label": "야간 약세", "tone": "negative"}
        if volatility_bias == "rising":
            return {"label": "변동성 경계", "tone": "negative"}
        return {"label": "중립 유지", "tone": "neutral"}

    def _checkpoint_trend_badge(
        self,
        *,
        derivatives_summary: dict[str, Any],
        missing_count: int,
    ) -> dict[str, Any] | None:
        if missing_count > 0:
            return {"label": "데이터 보강 필요", "tone": "negative"}
        if str(derivatives_summary.get("volatility_bias") or "stable") == "rising":
            return {"label": "변동성 확인", "tone": "negative"}
        if str(derivatives_summary.get("gap_bias") or "flat") != "flat":
            return {"label": "시가 갭 주의", "tone": "neutral"}
        return {"label": "정상 체크", "tone": "neutral"}

    def _trend_window(self, *, rows: list[dict[str, Any]], aliases: tuple[str, ...]) -> TrendWindow:
        values: list[float] = []
        for row in rows:
            if len(aliases) == 2:
                combined_values = [
                    value
                    for value in (
                        self._extract_float_metric(row, (aliases[0],)),
                        self._extract_float_metric(row, (aliases[1],)),
                    )
                    if value is not None
                ]
                if combined_values:
                    values.append(sum(combined_values))
            else:
                value = self._extract_float_metric(row, aliases)
                if value is not None:
                    values.append(value)
        return TrendWindow(
            current=values[-1] if values else None,
            previous=values[-2] if len(values) >= 2 else None,
            average=(sum(values) / len(values)) if values else None,
        )

    def _spot_flow_score(self, row: dict[str, Any] | None) -> float:
        foreign = self._extract_float_metric(row, ("investor_foreign_net_buy",)) or 0.0
        institution = self._extract_float_metric(row, ("investor_institution_net_buy",)) or 0.0
        return round((foreign + institution) / 1000.0, 4)

    def _program_score(self, row: dict[str, Any] | None) -> float:
        program = self._extract_float_metric(row, ("program_net_total",)) or 0.0
        return round(program / 1000.0, 4)

    def _credit_score(self, *, credit_now: float | None, credit_prev: float | None) -> float:
        return round((_pct_change(credit_now, credit_prev) or 0.0) / 2.0, 4)

    def _spot_flow_component_line(self, row: dict[str, Any] | None) -> str:
        foreign = self._extract_float_metric(row, ("investor_foreign_net_buy",))
        institution = self._extract_float_metric(row, ("investor_institution_net_buy",))
        individual = self._extract_float_metric(row, ("investor_individual_net_buy",))
        if foreign is None and institution is None and individual is None:
            return "현물 주체별 수급 데이터가 없어 방향을 확정하지 않았습니다."
        return (
            f"외국인 {_format_notional_krw(foreign)}, 기관 {_format_notional_krw(institution)}, "
            f"개인 {_format_notional_krw(individual)} 흐름을 반영했습니다."
        )

    def _program_component_line(self, row: dict[str, Any] | None) -> str:
        value = self._extract_float_metric(row, ("program_net_total",))
        if value is None:
            return "프로그램 매매 데이터가 없어 체결 압력을 분리하지 못했습니다."
        if value > 0:
            return f"프로그램 순매수 {_format_notional_krw(value)}로 수급 보강 신호입니다."
        if value < 0:
            return f"프로그램 순매도 {_format_notional_krw(value)}로 장중 부담 요인입니다."
        return "프로그램 매매는 중립 수준입니다."

    def _credit_component_line(self, *, credit_now: float | None, credit_prev: float | None) -> str:
        delta_pct = _pct_change(credit_now, credit_prev)
        if credit_now is None:
            return "신용잔고 데이터가 없어 레버리지 방향은 중립으로 처리했습니다."
        if delta_pct is None:
            return f"신용잔고는 {_format_number(credit_now / 100_000_000, 0)}억 수준입니다."
        if delta_pct >= 0.25:
            return f"신용잔고가 전일 대비 {_format_signed_percent(delta_pct, 2)} 늘어 위험 선호가 강해졌습니다."
        if delta_pct <= -0.25:
            return f"신용잔고가 전일 대비 {_format_signed_percent(delta_pct, 2)} 줄어 레버리지 축소가 진행 중입니다."
        return f"신용잔고 변화율은 {_format_signed_percent(delta_pct, 2)}로 중립권입니다."

    def _synthetic_component(
        self,
        *,
        key: str,
        label: str,
        component_group: str,
        raw_value: float | None,
        reference_value: float | None,
        delta_value: float | None,
        explanation: str,
        source_table: str,
        source_row: dict[str, Any] | None,
        source_metric_key: str,
        score: float,
    ) -> dict[str, Any]:
        return {
            "component_key": key,
            "component_label": label,
            "component_group": component_group,
            "raw_value": raw_value,
            "reference_value": reference_value,
            "delta_value": delta_value,
            "score": score,
            "data_available": source_row is not None and raw_value is not None,
            "explanation_ko": explanation,
            "source_table": source_table,
            "source_name": source_row.get("source_name") if source_row else None,
            "source_url": source_row.get("source_url") if source_row else None,
            "source_record_id": source_row.get("source_record_id") if source_row else None,
            "source_metric_key": source_metric_key,
            "metadata": None,
            "threshold": None,
        }

    def _select_latest_daily_factor_row(self, connection, *, up_to_date: str | None) -> dict[str, Any] | None:
        filters = ["market_scope = ?"]
        params: list[Any] = [self.market_scope]
        if up_to_date:
            filters.append("trade_date <= ?")
            params.append(up_to_date)
        where_clause = f"WHERE {' AND '.join(filters)}"
        row = connection.execute(
            f"""
            WITH ranked AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (
                        PARTITION BY trade_date
                        ORDER BY
                            CASE
                                WHEN source_name = 'KIS_MARKET_BREADTH' THEN 0
                                ELSE 1
                            END,
                            id DESC
                    ) AS row_rank
                FROM market_daily_factors
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
        return self._deserialize_daily_factor_row(row)

    def _select_previous_daily_factor_row(self, connection, *, trade_date: str | None) -> dict[str, Any] | None:
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
                                WHEN source_name = 'KIS_MARKET_BREADTH' THEN 0
                                ELSE 1
                            END,
                            id DESC
                    ) AS row_rank
                FROM market_daily_factors
                WHERE market_scope = ? AND trade_date < ?
            )
            SELECT *
            FROM ranked
            WHERE row_rank = 1
            ORDER BY trade_date DESC
            LIMIT 1
            """,
            (self.market_scope, trade_date),
        ).fetchone()
        return self._deserialize_daily_factor_row(row)

    def _select_daily_factor_trend_rows(
        self,
        connection,
        *,
        up_to_date: str | None,
        session_count: int,
    ) -> list[dict[str, Any]]:
        filters = ["market_scope = ?"]
        params: list[Any] = [self.market_scope]
        if up_to_date:
            filters.append("trade_date <= ?")
            params.append(up_to_date)
        where_clause = f"WHERE {' AND '.join(filters)}"
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
                                WHEN source_name = 'KIS_MARKET_BREADTH' THEN 0
                                ELSE 1
                            END,
                            id DESC
                    ) AS row_rank
                FROM market_daily_factors
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
        items = [self._deserialize_daily_factor_row(row) for row in rows]
        items.sort(key=lambda item: str(item.get("trade_date") or ""))
        return items

    def _select_night_snapshot_trend_rows(
        self,
        connection,
        *,
        up_to_date: str | None,
        session_count: int,
    ) -> list[dict[str, Any]]:
        filters = ["session_type = 'NIGHT_SESSION'"]
        params: list[Any] = []
        if up_to_date:
            filters.append("trade_date <= ?")
            params.append(up_to_date)
        where_clause = f"WHERE {' AND '.join(filters)}"
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
                                WHEN source_name = 'KIS_NIGHT_FUTURES' THEN 0
                                ELSE 1
                            END,
                            snapshot_time DESC,
                            id DESC
                    ) AS row_rank
                FROM market_intraday_snapshots
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
        items = [self._deserialize_snapshot_row(row) for row in rows]
        items.sort(key=lambda item: str(item.get("trade_date") or ""))
        return items

    def _deserialize_daily_factor_row(self, row) -> dict[str, Any] | None:
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
        payload.pop("row_rank", None)
        return payload

    def _extract_metric_value(self, row: dict[str, Any] | None, aliases: tuple[str, ...]) -> Any:
        if row is None:
            return None

        containers: list[dict[str, Any]] = [row]
        additional = row.get("additional_metrics")
        if isinstance(additional, dict):
            containers.append(additional)

        normalized_aliases = {_normalize_key(alias) for alias in aliases}
        for container in containers:
            for key, value in container.items():
                if _normalize_key(str(key)) in normalized_aliases:
                    if value is None:
                        continue
                    return value
        return None

    def _extract_float_metric(self, row: dict[str, Any] | None, aliases: tuple[str, ...]) -> float | None:
        return _as_float(self._extract_metric_value(row, aliases))

    def _latest_timestamp(self, *timestamps: str | None) -> str | None:
        values = [value.strip() for value in timestamps if isinstance(value, str) and value.strip()]
        if not values:
            return None
        return max(values)

    def _parse_preset_sessions(self, preset: str) -> int:
        normalized = (preset or "20d").strip().lower()
        match = re.fullmatch(r"(\d{1,3})d", normalized)
        if not match:
            return 20
        sessions = int(match.group(1))
        return max(5, min(sessions, 120))
