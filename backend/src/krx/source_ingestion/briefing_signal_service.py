from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import logging
from typing import Any

from ..company_master.db import get_connection, utcnow_iso

logger = logging.getLogger(__name__)


DEFAULT_SIGNAL_RULES: dict[str, Any] = {
    "classification": {
        "directional_bullish_cutoff": 1.0,
        "directional_bearish_cutoff": -1.0,
        "gap_up_cutoff_pct": 0.2,
        "gap_down_cutoff_pct": -0.2,
        "volatility_rising_cutoff": 1.0,
        "volatility_falling_cutoff": -1.0,
        "outcome_up_cutoff_pct": 0.15,
        "outcome_down_cutoff_pct": -0.15,
        "outcome_iv_rising_delta": 0.7,
        "outcome_iv_falling_delta": -0.7,
        "confidence_medium_min_score": 1.2,
        "confidence_high_min_score": 2.5,
        "confidence_medium_min_coverage": 0.5,
        "confidence_high_min_coverage": 0.75,
    },
    "components": {
        "investor_futures_flow_pressure": {
            "weight": 1.25,
            "bullish_threshold": 300.0,
            "bearish_threshold": -300.0,
            "scale": 1800.0,
        },
        "open_interest_change_pressure": {
            "weight": 0.8,
            "flat_change_pct": 2.0,
            "scale_change_pct": 12.0,
            "put_call_bearish_threshold": 1.03,
            "put_call_bullish_threshold": 0.97,
            "volatility_weight": 0.35,
        },
        "put_call_ratio_pressure": {
            "weight": 1.1,
            "bullish_threshold": 0.9,
            "bearish_threshold": 1.1,
            "scale": 0.35,
        },
        "implied_volatility_pressure": {
            "weight": 0.95,
            "low_threshold": 16.0,
            "high_threshold": 22.0,
            "scale": 8.0,
            "volatility_weight": 1.0,
        },
        "credit_balance_trend_pressure": {
            "weight": 0.6,
            "bullish_change_pct": 0.25,
            "bearish_change_pct": -0.25,
            "scale_change_pct": 1.5,
        },
        "night_futures_gap_signal": {
            "weight": 1.15,
            "gap_up_pct": 0.2,
            "gap_down_pct": -0.2,
            "scale_pct": 1.5,
            "volatility_weight": 0.3,
        },
        "global_risk_input": {
            "weight": 0.8,
            "risk_off_threshold": 0.3,
            "risk_on_threshold": -0.3,
            "scale": 1.5,
            "volatility_weight": 0.5,
        },
    },
}

MANDATORY_COMPONENT_KEYS = (
    "investor_futures_flow_pressure",
    "open_interest_change_pressure",
    "put_call_ratio_pressure",
    "implied_volatility_pressure",
    "credit_balance_trend_pressure",
    "night_futures_gap_signal",
)


@dataclass(frozen=True)
class SignalComponentResult:
    component_key: str
    component_label: str
    component_group: str
    raw_value: float | None
    reference_value: float | None
    delta_value: float | None
    score: float
    volatility_score: float
    weight: float
    data_available: bool
    source_table: str | None
    source_name: str | None
    source_url: str | None
    source_record_id: str | None
    source_metric_key: str | None
    thresholds: dict[str, Any]
    metadata: dict[str, Any]
    explanation_ko: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "component_key": self.component_key,
            "component_label": self.component_label,
            "component_group": self.component_group,
            "raw_value": self.raw_value,
            "reference_value": self.reference_value,
            "delta_value": self.delta_value,
            "score": round(self.score, 4),
            "volatility_score": round(self.volatility_score, 4),
            "weight": self.weight,
            "data_available": self.data_available,
            "source_table": self.source_table,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "source_record_id": self.source_record_id,
            "source_metric_key": self.source_metric_key,
            "thresholds": self.thresholds,
            "metadata": self.metadata,
            "explanation_ko": self.explanation_ko,
        }


@dataclass(frozen=True)
class MarketBriefingGenerationResult:
    briefing_id: int
    trade_date: str
    market_scope: str
    directional_bias: str
    gap_bias: str
    volatility_bias: str
    confidence_bucket: str
    total_score: float
    volatility_score: float
    explanation_ko: str
    json_payload: dict[str, Any]
    markdown_summary: str
    notification_payload: dict[str, Any] | None
    components: list[dict[str, Any]]
    generated_at: str


@dataclass(frozen=True)
class MarketBriefingBacktestResult:
    backtest_id: int
    briefing_id: int
    trade_date: str
    evaluation_date: str
    predicted_directional_bias: str
    actual_directional_bias: str
    predicted_gap_bias: str
    actual_gap_bias: str
    predicted_volatility_bias: str
    actual_volatility_bias: str
    directional_hit: bool | None
    gap_hit: bool | None
    volatility_hit: bool | None
    hit_rate: float | None
    confusion_summary: dict[str, Any]
    score_distribution: dict[str, int]
    metrics: dict[str, Any]


class MarketBriefingSignalService:
    def __init__(
        self,
        *,
        db_path: str,
        signal_enabled: bool = True,
        market_scope: str = "KRX",
        rules_json: str | None = None,
    ) -> None:
        self.db_path = db_path
        self.signal_enabled = signal_enabled
        self.market_scope = (market_scope or "KRX").strip().upper() or "KRX"
        self.rules = self._load_rules(rules_json)

    def generate_briefing(
        self,
        *,
        trade_date: date,
        mode: str = "MANUAL",
    ) -> MarketBriefingGenerationResult:
        if not self.signal_enabled:
            raise RuntimeError("market_briefing_signal_disabled")

        mode_normalized = self._normalize_mode(mode)
        trade_date_iso = trade_date.isoformat()

        with get_connection(self.db_path) as connection:
            inputs = self._load_signal_inputs(connection, trade_date_iso=trade_date_iso)
            components = self._score_components(trade_date=trade_date, inputs=inputs)

            total_score = sum(component.score for component in components)
            volatility_score = sum(component.volatility_score for component in components)
            directional_bias = self._directional_bias(total_score)
            gap_bias = self._gap_bias_from_components(components)
            volatility_bias = self._volatility_bias(volatility_score)
            confidence_bucket = self._confidence_bucket(total_score=total_score, components=components)
            explanation_ko = self._build_korean_explanation(
                trade_date=trade_date,
                directional_bias=directional_bias,
                gap_bias=gap_bias,
                volatility_bias=volatility_bias,
                total_score=total_score,
                confidence_bucket=confidence_bucket,
                components=components,
            )

            components_payload = [component.to_payload() for component in components]
            generated_at = utcnow_iso()
            json_payload = {
                "trade_date": trade_date_iso,
                "market_scope": self.market_scope,
                "directional_bias": directional_bias,
                "gap_bias": gap_bias,
                "volatility_bias": volatility_bias,
                "confidence_bucket": confidence_bucket,
                "total_score": round(total_score, 4),
                "volatility_score": round(volatility_score, 4),
                "components": components_payload,
                "explanation_ko": explanation_ko,
                "generated_at": generated_at,
                "disclaimer": "본 브리핑은 정보 제공 목적이며 투자 성과를 보장하지 않습니다.",
            }
            markdown_summary = self._build_markdown_summary(
                trade_date=trade_date,
                directional_bias=directional_bias,
                gap_bias=gap_bias,
                volatility_bias=volatility_bias,
                confidence_bucket=confidence_bucket,
                total_score=total_score,
                volatility_score=volatility_score,
                components=components,
                explanation_ko=explanation_ko,
            )
            notification_payload = self._build_notification_payload(
                trade_date=trade_date,
                directional_bias=directional_bias,
                gap_bias=gap_bias,
                volatility_bias=volatility_bias,
                total_score=total_score,
                confidence_bucket=confidence_bucket,
            )

            input_snapshot = {
                "market_daily_factors": inputs["daily_current"],
                "market_daily_factors_previous": inputs["daily_previous"],
                "derivatives_daily_metrics": inputs["derivatives_current"],
                "derivatives_daily_metrics_previous": inputs["derivatives_previous"],
                "night_futures_snapshot": inputs["night_snapshot"],
                "global_risk_snapshot": inputs["global_snapshot"],
            }

            briefing_id = self._upsert_market_briefing(
                connection,
                trade_date_iso=trade_date_iso,
                run_mode=mode_normalized,
                directional_bias=directional_bias,
                gap_bias=gap_bias,
                volatility_bias=volatility_bias,
                confidence_bucket=confidence_bucket,
                total_score=total_score,
                volatility_score=volatility_score,
                explanation_ko=explanation_ko,
                json_payload=json_payload,
                markdown_summary=markdown_summary,
                notification_payload=notification_payload,
                input_snapshot=input_snapshot,
            )
            self._upsert_signal_components(
                connection,
                briefing_id=briefing_id,
                trade_date_iso=trade_date_iso,
                components=components,
            )

        logger.info(
            "market_briefing_generated",
            extra={
                "briefing_id": briefing_id,
                "trade_date": trade_date_iso,
                "mode": mode_normalized,
                "directional_bias": directional_bias,
                "gap_bias": gap_bias,
                "volatility_bias": volatility_bias,
                "total_score": round(total_score, 4),
                "volatility_score": round(volatility_score, 4),
                "confidence_bucket": confidence_bucket,
            },
        )

        return MarketBriefingGenerationResult(
            briefing_id=briefing_id,
            trade_date=trade_date_iso,
            market_scope=self.market_scope,
            directional_bias=directional_bias,
            gap_bias=gap_bias,
            volatility_bias=volatility_bias,
            confidence_bucket=confidence_bucket,
            total_score=round(total_score, 4),
            volatility_score=round(volatility_score, 4),
            explanation_ko=explanation_ko,
            json_payload=json_payload,
            markdown_summary=markdown_summary,
            notification_payload=notification_payload,
            components=components_payload,
            generated_at=generated_at,
        )

    def list_briefings(
        self,
        *,
        limit: int,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        filters: list[str] = ["market_scope = ?"]
        params: list[Any] = [self.market_scope]

        if start_date:
            filters.append("trade_date >= ?")
            params.append(start_date)
        if end_date:
            filters.append("trade_date <= ?")
            params.append(end_date)

        where_clause = f"WHERE {' AND '.join(filters)}"
        params.append(limit)

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    id,
                    trade_date,
                    market_scope,
                    run_mode,
                    directional_bias,
                    gap_bias,
                    volatility_bias,
                    confidence_bucket,
                    total_score,
                    volatility_score,
                    explanation_ko,
                    generated_at,
                    created_at,
                    updated_at
                FROM market_briefings
                {where_clause}
                ORDER BY trade_date DESC, id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def get_latest_briefing(self, *, trade_date: str | None = None) -> dict[str, Any] | None:
        filters: list[str] = ["market_scope = ?"]
        params: list[Any] = [self.market_scope]
        if trade_date:
            filters.append("trade_date <= ?")
            params.append(trade_date)

        where_clause = f"WHERE {' AND '.join(filters)}"
        with get_connection(self.db_path) as connection:
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

        if row is None:
            return None
        return self._deserialize_briefing_row(dict(row))

    def get_briefing_detail(self, *, trade_date: str) -> dict[str, Any] | None:
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM market_briefings
                WHERE trade_date = ? AND market_scope = ?
                LIMIT 1
                """,
                (trade_date, self.market_scope),
            ).fetchone()
            if row is None:
                return None

            payload = self._deserialize_briefing_row(dict(row))
            components = self._list_components_by_briefing_id(connection, briefing_id=int(row["id"]))
            backtests = self._list_backtests_by_briefing_id(connection, briefing_id=int(row["id"]))
            payload["components"] = components
            payload["backtests"] = backtests
        return payload

    def list_components_by_date(self, *, trade_date: str) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT id
                FROM market_briefings
                WHERE trade_date = ? AND market_scope = ?
                LIMIT 1
                """,
                (trade_date, self.market_scope),
            ).fetchone()
            if row is None:
                return []
            return self._list_components_by_briefing_id(connection, briefing_id=int(row["id"]))

    def backtest_briefing(
        self,
        *,
        trade_date: date,
    ) -> MarketBriefingBacktestResult:
        trade_date_iso = trade_date.isoformat()

        with get_connection(self.db_path) as connection:
            briefing_row = connection.execute(
                """
                SELECT *
                FROM market_briefings
                WHERE trade_date = ? AND market_scope = ?
                LIMIT 1
                """,
                (trade_date_iso, self.market_scope),
            ).fetchone()
            if briefing_row is None:
                raise ValueError(f"briefing_not_found:{trade_date_iso}")

            evaluation_date = self._resolve_next_evaluation_date(connection, trade_date_iso=trade_date_iso)
            if evaluation_date is None:
                raise ValueError(f"evaluation_date_not_found:{trade_date_iso}")

            briefing = dict(briefing_row)
            actual_outcome = self._resolve_actual_outcome(connection, evaluation_date=evaluation_date)

            directional_hit = self._to_hit(
                predicted=str(briefing["directional_bias"]),
                actual=actual_outcome["directional_bias"],
            )
            gap_hit = self._to_hit(
                predicted=str(briefing["gap_bias"]),
                actual=actual_outcome["gap_bias"],
            )
            volatility_hit = self._to_hit(
                predicted=str(briefing["volatility_bias"]),
                actual=actual_outcome["volatility_bias"],
            )

            backtest_id = self._upsert_backtest(
                connection,
                briefing_id=int(briefing["id"]),
                trade_date_iso=trade_date_iso,
                evaluation_date=evaluation_date,
                predicted_directional_bias=str(briefing["directional_bias"]),
                actual_directional_bias=actual_outcome["directional_bias"],
                predicted_gap_bias=str(briefing["gap_bias"]),
                actual_gap_bias=actual_outcome["gap_bias"],
                predicted_volatility_bias=str(briefing["volatility_bias"]),
                actual_volatility_bias=actual_outcome["volatility_bias"],
                directional_hit=directional_hit,
                gap_hit=gap_hit,
                volatility_hit=volatility_hit,
            )

            confusion_summary = self._build_confusion_summary(connection)
            score_distribution = self._build_score_distribution(connection)
            hit_rate = self._compute_hit_rate(connection)
            metrics = {
                "evaluated_count": self._count_evaluated_backtests(connection),
                "hit_rate": hit_rate,
                "directional_hits": self._count_hits(connection, "directional_hit"),
                "gap_hits": self._count_hits(connection, "gap_hit"),
                "volatility_hits": self._count_hits(connection, "volatility_hit"),
                "score_distribution": score_distribution,
                "confusion_summary": confusion_summary,
                "actual_outcome": actual_outcome,
            }

            connection.execute(
                """
                UPDATE market_signal_backtests
                SET
                    hit_rate = ?,
                    confusion_summary_json = ?,
                    score_distribution_json = ?,
                    metrics_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    hit_rate,
                    json.dumps(confusion_summary, ensure_ascii=False, sort_keys=True),
                    json.dumps(score_distribution, ensure_ascii=False, sort_keys=True),
                    json.dumps(metrics, ensure_ascii=False, sort_keys=True),
                    utcnow_iso(),
                    backtest_id,
                ),
            )

        logger.info(
            "market_briefing_backtest_saved",
            extra={
                "backtest_id": backtest_id,
                "trade_date": trade_date_iso,
                "evaluation_date": evaluation_date,
                "predicted_directional_bias": str(briefing_row["directional_bias"]),
                "actual_directional_bias": actual_outcome["directional_bias"],
                "predicted_gap_bias": str(briefing_row["gap_bias"]),
                "actual_gap_bias": actual_outcome["gap_bias"],
                "predicted_volatility_bias": str(briefing_row["volatility_bias"]),
                "actual_volatility_bias": actual_outcome["volatility_bias"],
                "hit_rate": hit_rate,
            },
        )

        return MarketBriefingBacktestResult(
            backtest_id=backtest_id,
            briefing_id=int(briefing_row["id"]),
            trade_date=trade_date_iso,
            evaluation_date=evaluation_date,
            predicted_directional_bias=str(briefing_row["directional_bias"]),
            actual_directional_bias=actual_outcome["directional_bias"],
            predicted_gap_bias=str(briefing_row["gap_bias"]),
            actual_gap_bias=actual_outcome["gap_bias"],
            predicted_volatility_bias=str(briefing_row["volatility_bias"]),
            actual_volatility_bias=actual_outcome["volatility_bias"],
            directional_hit=directional_hit,
            gap_hit=gap_hit,
            volatility_hit=volatility_hit,
            hit_rate=hit_rate,
            confusion_summary=confusion_summary,
            score_distribution=score_distribution,
            metrics=metrics,
        )

    def backtest_date_range(self, *, start_date: date, end_date: date) -> list[MarketBriefingBacktestResult]:
        if end_date < start_date:
            raise ValueError("end_date must be greater than or equal to start_date")

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT trade_date
                FROM market_briefings
                WHERE market_scope = ? AND trade_date >= ? AND trade_date <= ?
                ORDER BY trade_date ASC
                """,
                (self.market_scope, start_date.isoformat(), end_date.isoformat()),
            ).fetchall()

        results: list[MarketBriefingBacktestResult] = []
        for row in rows:
            try:
                results.append(self.backtest_briefing(trade_date=date.fromisoformat(str(row["trade_date"]))))
            except ValueError as error:
                logger.info(
                    "market_briefing_backtest_skipped",
                    extra={"trade_date": str(row["trade_date"]), "reason": str(error)},
                )
        return results

    def _load_signal_inputs(self, connection, *, trade_date_iso: str) -> dict[str, dict[str, Any] | None]:
        derivatives_current = self._select_derivatives_row(connection, trade_date_iso=trade_date_iso)
        derivatives_previous = self._select_previous_derivatives_row(connection, trade_date_iso=trade_date_iso)
        daily_current = self._select_daily_factor_row(connection, trade_date_iso=trade_date_iso)
        daily_previous = self._select_previous_daily_factor_row(connection, trade_date_iso=trade_date_iso)
        night_snapshot = self._select_night_snapshot_row(connection, trade_date_iso=trade_date_iso)
        global_snapshot = self._select_global_snapshot_row(connection, trade_date_iso=trade_date_iso)
        return {
            "derivatives_current": derivatives_current,
            "derivatives_previous": derivatives_previous,
            "daily_current": daily_current,
            "daily_previous": daily_previous,
            "night_snapshot": night_snapshot,
            "global_snapshot": global_snapshot,
        }

    def _score_components(self, *, trade_date: date, inputs: dict[str, dict[str, Any] | None]) -> list[SignalComponentResult]:
        derivatives_current = inputs["derivatives_current"] or {}
        derivatives_previous = inputs["derivatives_previous"] or {}
        daily_current = inputs["daily_current"] or {}
        daily_previous = inputs["daily_previous"] or {}
        night_snapshot = inputs["night_snapshot"] or {}
        global_snapshot = inputs["global_snapshot"] or {}

        flow_component = self._score_investor_futures_flow(derivatives_current)
        open_interest_component = self._score_open_interest_change(
            derivatives_current=derivatives_current,
            derivatives_previous=derivatives_previous,
            fallback_flow_raw=flow_component.raw_value,
        )
        put_call_component = self._score_put_call_ratio(derivatives_current)
        iv_component = self._score_implied_volatility(derivatives_current)
        credit_component = self._score_credit_trend(
            daily_current=daily_current,
            daily_previous=daily_previous,
        )
        night_gap_component = self._score_night_futures_gap(night_snapshot)
        global_risk_component = self._score_global_risk(global_snapshot)

        components = [
            flow_component,
            open_interest_component,
            put_call_component,
            iv_component,
            credit_component,
            night_gap_component,
            global_risk_component,
        ]

        logger.info(
            "market_briefing_components_scored",
            extra={
                "trade_date": trade_date.isoformat(),
                "component_scores": {component.component_key: round(component.score, 4) for component in components},
                "volatility_scores": {
                    component.component_key: round(component.volatility_score, 4) for component in components
                },
            },
        )
        return components

    def _score_investor_futures_flow(self, derivatives_current: dict[str, Any]) -> SignalComponentResult:
        rules = self._component_rules("investor_futures_flow_pressure")
        foreign = self._as_float(derivatives_current.get("futures_investor_foreign_net_buy"))
        institution = self._as_float(derivatives_current.get("futures_investor_institution_net_buy"))

        if foreign is None and institution is None:
            return self._missing_component(
                component_key="investor_futures_flow_pressure",
                component_label="투자자 선물 수급 압력",
                component_group="directional",
                weight=float(rules.get("weight", 1.0)),
                thresholds=rules,
                explanation_ko="선물 투자자 수급 데이터가 없어 수급 압력을 중립(0점)으로 처리했습니다.",
                source_table="derivatives_daily_metrics",
                source_name=self._as_text(derivatives_current.get("source_name")),
                source_url=self._as_text(derivatives_current.get("source_url")),
                source_record_id=self._as_text(derivatives_current.get("source_record_id")),
                source_metric_key="futures_investor_foreign_net_buy/futures_investor_institution_net_buy",
            )

        raw_value = (foreign or 0.0) + (institution or 0.0)
        score_raw = self._score_high_bullish(
            raw_value,
            bullish_threshold=float(rules.get("bullish_threshold", 300.0)),
            bearish_threshold=float(rules.get("bearish_threshold", -300.0)),
            scale=float(rules.get("scale", 1800.0)),
        )
        score = score_raw * float(rules.get("weight", 1.0))
        explanation_ko = (
            f"외국인/기관 선물 순매수 합계가 {raw_value:.1f}로 집계되어 "
            f"방향 점수 {score:.2f}점을 반영했습니다."
        )
        return SignalComponentResult(
            component_key="investor_futures_flow_pressure",
            component_label="투자자 선물 수급 압력",
            component_group="directional",
            raw_value=raw_value,
            reference_value=None,
            delta_value=None,
            score=score,
            volatility_score=0.0,
            weight=float(rules.get("weight", 1.0)),
            data_available=True,
            source_table="derivatives_daily_metrics",
            source_name=self._as_text(derivatives_current.get("source_name")),
            source_url=self._as_text(derivatives_current.get("source_url")),
            source_record_id=self._as_text(derivatives_current.get("source_record_id")),
            source_metric_key="futures_investor_foreign_net_buy/futures_investor_institution_net_buy",
            thresholds=rules,
            metadata={"foreign_net_buy": foreign, "institution_net_buy": institution},
            explanation_ko=explanation_ko,
        )

    def _score_open_interest_change(
        self,
        *,
        derivatives_current: dict[str, Any],
        derivatives_previous: dict[str, Any],
        fallback_flow_raw: float | None,
    ) -> SignalComponentResult:
        rules = self._component_rules("open_interest_change_pressure")
        current_oi = self._as_float(derivatives_current.get("open_interest_total"))
        previous_oi = self._as_float(derivatives_previous.get("open_interest_total"))

        if current_oi is None or previous_oi is None:
            return self._missing_component(
                component_key="open_interest_change_pressure",
                component_label="미결제약정 변화 압력",
                component_group="directional",
                weight=float(rules.get("weight", 1.0)),
                thresholds=rules,
                explanation_ko="미결제약정 전일 비교 데이터가 없어 0점으로 처리했습니다.",
                source_table="derivatives_daily_metrics",
                source_name=self._as_text(derivatives_current.get("source_name")),
                source_url=self._as_text(derivatives_current.get("source_url")),
                source_record_id=self._as_text(derivatives_current.get("source_record_id")),
                source_metric_key="open_interest_total",
            )

        delta_pct = self._pct_change(current_oi, previous_oi)
        if delta_pct is None:
            return self._missing_component(
                component_key="open_interest_change_pressure",
                component_label="미결제약정 변화 압력",
                component_group="directional",
                weight=float(rules.get("weight", 1.0)),
                thresholds=rules,
                explanation_ko="미결제약정 변화율 계산이 불가능해 0점으로 처리했습니다.",
                source_table="derivatives_daily_metrics",
                source_name=self._as_text(derivatives_current.get("source_name")),
                source_url=self._as_text(derivatives_current.get("source_url")),
                source_record_id=self._as_text(derivatives_current.get("source_record_id")),
                source_metric_key="open_interest_total",
            )

        magnitude = 0.0
        flat_change_pct = float(rules.get("flat_change_pct", 2.0))
        if abs(delta_pct) >= flat_change_pct:
            magnitude = self._clamp(abs(delta_pct) / max(float(rules.get("scale_change_pct", 12.0)), 0.01), 0.0, 2.0)

        put_call_ratio = self._as_float(derivatives_current.get("put_call_ratio"))
        direction_hint = 1.0
        if put_call_ratio is not None:
            if put_call_ratio >= float(rules.get("put_call_bearish_threshold", 1.03)):
                direction_hint = -1.0
            elif put_call_ratio <= float(rules.get("put_call_bullish_threshold", 0.97)):
                direction_hint = 1.0
            else:
                direction_hint = 1.0 if (fallback_flow_raw or 0.0) >= 0 else -1.0
        elif (fallback_flow_raw or 0.0) < 0:
            direction_hint = -1.0

        trend_sign = 1.0 if delta_pct >= 0 else -1.0
        score = magnitude * direction_hint * trend_sign * float(rules.get("weight", 1.0))
        volatility_score = magnitude * trend_sign * float(rules.get("volatility_weight", 0.35))

        explanation_ko = (
            f"미결제약정이 전일 대비 {delta_pct:.2f}% 변동했고 "
            f"Put/Call 비율 힌트({put_call_ratio if put_call_ratio is not None else 'N/A'})를 반영해 "
            f"점수 {score:.2f}점을 부여했습니다."
        )

        return SignalComponentResult(
            component_key="open_interest_change_pressure",
            component_label="미결제약정 변화 압력",
            component_group="directional",
            raw_value=current_oi,
            reference_value=previous_oi,
            delta_value=delta_pct,
            score=score,
            volatility_score=volatility_score,
            weight=float(rules.get("weight", 1.0)),
            data_available=True,
            source_table="derivatives_daily_metrics",
            source_name=self._as_text(derivatives_current.get("source_name")),
            source_url=self._as_text(derivatives_current.get("source_url")),
            source_record_id=self._as_text(derivatives_current.get("source_record_id")),
            source_metric_key="open_interest_total",
            thresholds=rules,
            metadata={"put_call_ratio_hint": put_call_ratio, "delta_pct": delta_pct},
            explanation_ko=explanation_ko,
        )

    def _score_put_call_ratio(self, derivatives_current: dict[str, Any]) -> SignalComponentResult:
        rules = self._component_rules("put_call_ratio_pressure")
        put_call_ratio = self._as_float(derivatives_current.get("put_call_ratio"))
        if put_call_ratio is None:
            return self._missing_component(
                component_key="put_call_ratio_pressure",
                component_label="Put/Call 비율 압력",
                component_group="directional",
                weight=float(rules.get("weight", 1.0)),
                thresholds=rules,
                explanation_ko="Put/Call 비율이 없어 해당 신호를 0점으로 처리했습니다.",
                source_table="derivatives_daily_metrics",
                source_name=self._as_text(derivatives_current.get("source_name")),
                source_url=self._as_text(derivatives_current.get("source_url")),
                source_record_id=self._as_text(derivatives_current.get("source_record_id")),
                source_metric_key="put_call_ratio",
            )

        score_raw = self._score_low_bullish_high_bearish(
            put_call_ratio,
            bullish_threshold=float(rules.get("bullish_threshold", 0.9)),
            bearish_threshold=float(rules.get("bearish_threshold", 1.1)),
            scale=float(rules.get("scale", 0.35)),
        )
        score = score_raw * float(rules.get("weight", 1.0))
        explanation_ko = f"Put/Call 비율 {put_call_ratio:.3f}를 반영해 방향 점수 {score:.2f}점을 계산했습니다."
        return SignalComponentResult(
            component_key="put_call_ratio_pressure",
            component_label="Put/Call 비율 압력",
            component_group="directional",
            raw_value=put_call_ratio,
            reference_value=None,
            delta_value=None,
            score=score,
            volatility_score=0.0,
            weight=float(rules.get("weight", 1.0)),
            data_available=True,
            source_table="derivatives_daily_metrics",
            source_name=self._as_text(derivatives_current.get("source_name")),
            source_url=self._as_text(derivatives_current.get("source_url")),
            source_record_id=self._as_text(derivatives_current.get("source_record_id")),
            source_metric_key="put_call_ratio",
            thresholds=rules,
            metadata={},
            explanation_ko=explanation_ko,
        )

    def _score_implied_volatility(self, derivatives_current: dict[str, Any]) -> SignalComponentResult:
        rules = self._component_rules("implied_volatility_pressure")
        implied_volatility = self._as_float(derivatives_current.get("implied_volatility"))
        if implied_volatility is None:
            return self._missing_component(
                component_key="implied_volatility_pressure",
                component_label="내재변동성 압력",
                component_group="volatility",
                weight=float(rules.get("weight", 1.0)),
                thresholds=rules,
                explanation_ko="내재변동성 데이터가 없어 방향/변동성 점수를 0으로 처리했습니다.",
                source_table="derivatives_daily_metrics",
                source_name=self._as_text(derivatives_current.get("source_name")),
                source_url=self._as_text(derivatives_current.get("source_url")),
                source_record_id=self._as_text(derivatives_current.get("source_record_id")),
                source_metric_key="implied_volatility",
            )

        low_threshold = float(rules.get("low_threshold", 16.0))
        high_threshold = float(rules.get("high_threshold", 22.0))
        scale = float(rules.get("scale", 8.0))

        directional_raw = self._score_low_bullish_high_bearish(
            implied_volatility,
            bullish_threshold=low_threshold,
            bearish_threshold=high_threshold,
            scale=scale,
        )
        score = directional_raw * float(rules.get("weight", 1.0))

        volatility_raw = self._score_high_bullish(
            implied_volatility,
            bullish_threshold=high_threshold,
            bearish_threshold=low_threshold,
            scale=scale,
        )
        volatility_score = volatility_raw * float(rules.get("volatility_weight", 1.0))
        explanation_ko = (
            f"내재변동성 {implied_volatility:.2f}를 기준으로 "
            f"방향 점수 {score:.2f}, 변동성 점수 {volatility_score:.2f}를 반영했습니다."
        )

        return SignalComponentResult(
            component_key="implied_volatility_pressure",
            component_label="내재변동성 압력",
            component_group="volatility",
            raw_value=implied_volatility,
            reference_value=None,
            delta_value=None,
            score=score,
            volatility_score=volatility_score,
            weight=float(rules.get("weight", 1.0)),
            data_available=True,
            source_table="derivatives_daily_metrics",
            source_name=self._as_text(derivatives_current.get("source_name")),
            source_url=self._as_text(derivatives_current.get("source_url")),
            source_record_id=self._as_text(derivatives_current.get("source_record_id")),
            source_metric_key="implied_volatility",
            thresholds=rules,
            metadata={},
            explanation_ko=explanation_ko,
        )

    def _score_credit_trend(
        self,
        *,
        daily_current: dict[str, Any],
        daily_previous: dict[str, Any],
    ) -> SignalComponentResult:
        rules = self._component_rules("credit_balance_trend_pressure")
        current_credit = self._as_float(daily_current.get("credit_balance_total"))
        if current_credit is None:
            current_credit = self._as_float(daily_current.get("margin_loan_balance"))
        previous_credit = self._as_float(daily_previous.get("credit_balance_total"))
        if previous_credit is None:
            previous_credit = self._as_float(daily_previous.get("margin_loan_balance"))

        if current_credit is None or previous_credit is None:
            return self._missing_component(
                component_key="credit_balance_trend_pressure",
                component_label="신용잔고 추세 압력",
                component_group="directional",
                weight=float(rules.get("weight", 1.0)),
                thresholds=rules,
                explanation_ko="신용잔고(또는 융자잔고) 전일 비교 데이터가 없어 0점 처리했습니다.",
                source_table="market_daily_factors",
                source_name=self._as_text(daily_current.get("source_name")),
                source_url=self._as_text(daily_current.get("source_url")),
                source_record_id=self._as_text(daily_current.get("source_record_id")),
                source_metric_key="credit_balance_total/margin_loan_balance",
            )

        delta_pct = self._pct_change(current_credit, previous_credit)
        if delta_pct is None:
            return self._missing_component(
                component_key="credit_balance_trend_pressure",
                component_label="신용잔고 추세 압력",
                component_group="directional",
                weight=float(rules.get("weight", 1.0)),
                thresholds=rules,
                explanation_ko="신용잔고 변화율 계산이 불가능해 0점 처리했습니다.",
                source_table="market_daily_factors",
                source_name=self._as_text(daily_current.get("source_name")),
                source_url=self._as_text(daily_current.get("source_url")),
                source_record_id=self._as_text(daily_current.get("source_record_id")),
                source_metric_key="credit_balance_total/margin_loan_balance",
            )

        score_raw = self._score_high_bullish(
            delta_pct,
            bullish_threshold=float(rules.get("bullish_change_pct", 0.25)),
            bearish_threshold=float(rules.get("bearish_change_pct", -0.25)),
            scale=float(rules.get("scale_change_pct", 1.5)),
        )
        score = score_raw * float(rules.get("weight", 1.0))
        explanation_ko = f"신용잔고가 전일 대비 {delta_pct:.2f}% 변해 방향 점수 {score:.2f}점을 반영했습니다."

        return SignalComponentResult(
            component_key="credit_balance_trend_pressure",
            component_label="신용잔고 추세 압력",
            component_group="directional",
            raw_value=current_credit,
            reference_value=previous_credit,
            delta_value=delta_pct,
            score=score,
            volatility_score=0.0,
            weight=float(rules.get("weight", 1.0)),
            data_available=True,
            source_table="market_daily_factors",
            source_name=self._as_text(daily_current.get("source_name")),
            source_url=self._as_text(daily_current.get("source_url")),
            source_record_id=self._as_text(daily_current.get("source_record_id")),
            source_metric_key="credit_balance_total/margin_loan_balance",
            thresholds=rules,
            metadata={},
            explanation_ko=explanation_ko,
        )

    def _score_night_futures_gap(self, night_snapshot: dict[str, Any]) -> SignalComponentResult:
        rules = self._component_rules("night_futures_gap_signal")
        change_rate = self._as_float(night_snapshot.get("change_rate"))
        if change_rate is None:
            change_rate = self._as_float(night_snapshot.get("price_change"))

        if change_rate is None:
            return self._missing_component(
                component_key="night_futures_gap_signal",
                component_label="야간선물 갭 시그널",
                component_group="gap",
                weight=float(rules.get("weight", 1.0)),
                thresholds=rules,
                explanation_ko="야간선물 변동률 데이터가 없어 갭 시그널을 flat(0점) 처리했습니다.",
                source_table="market_intraday_snapshots",
                source_name=self._as_text(night_snapshot.get("source_name")),
                source_url=self._as_text(night_snapshot.get("source_url")),
                source_record_id=self._as_text(night_snapshot.get("source_record_id")),
                source_metric_key="change_rate",
            )

        score_raw = self._score_high_bullish(
            change_rate,
            bullish_threshold=float(rules.get("gap_up_pct", 0.2)),
            bearish_threshold=float(rules.get("gap_down_pct", -0.2)),
            scale=float(rules.get("scale_pct", 1.5)),
        )
        score = score_raw * float(rules.get("weight", 1.0))
        volatility_score = (
            self._clamp(abs(change_rate) / max(float(rules.get("scale_pct", 1.5)), 0.01), 0.0, 2.0)
            * float(rules.get("volatility_weight", 0.3))
        )
        explanation_ko = f"야간선물 변동률 {change_rate:.2f}%를 반영해 방향 점수 {score:.2f}점을 계산했습니다."
        return SignalComponentResult(
            component_key="night_futures_gap_signal",
            component_label="야간선물 갭 시그널",
            component_group="gap",
            raw_value=change_rate,
            reference_value=None,
            delta_value=None,
            score=score,
            volatility_score=volatility_score,
            weight=float(rules.get("weight", 1.0)),
            data_available=True,
            source_table="market_intraday_snapshots",
            source_name=self._as_text(night_snapshot.get("source_name")),
            source_url=self._as_text(night_snapshot.get("source_url")),
            source_record_id=self._as_text(night_snapshot.get("source_record_id")),
            source_metric_key="change_rate",
            thresholds=rules,
            metadata={
                "instrument_code": self._as_text(night_snapshot.get("instrument_code")),
                "instrument_name": self._as_text(night_snapshot.get("instrument_name")),
            },
            explanation_ko=explanation_ko,
        )

    def _score_global_risk(self, global_snapshot: dict[str, Any]) -> SignalComponentResult:
        rules = self._component_rules("global_risk_input")
        additional_metrics = global_snapshot.get("additional_metrics") or {}
        if not isinstance(additional_metrics, dict):
            additional_metrics = {}

        risk_off_raw = self._as_float(additional_metrics.get("global_risk_score"))
        risk_metric_key = "additional_metrics.global_risk_score"
        if risk_off_raw is None:
            risk_off_raw = self._as_float(additional_metrics.get("risk_score"))
            risk_metric_key = "additional_metrics.risk_score"

        if risk_off_raw is None:
            source_change_rate = self._as_float(global_snapshot.get("change_rate"))
            if source_change_rate is not None:
                risk_off_raw = -source_change_rate
                risk_metric_key = "change_rate"

        if risk_off_raw is None:
            return SignalComponentResult(
                component_key="global_risk_input",
                component_label="글로벌 리스크 입력(선택)",
                component_group="optional",
                raw_value=None,
                reference_value=None,
                delta_value=None,
                score=0.0,
                volatility_score=0.0,
                weight=float(rules.get("weight", 1.0)),
                data_available=False,
                source_table="market_intraday_snapshots",
                source_name=self._as_text(global_snapshot.get("source_name")),
                source_url=self._as_text(global_snapshot.get("source_url")),
                source_record_id=self._as_text(global_snapshot.get("source_record_id")),
                source_metric_key=risk_metric_key,
                thresholds=rules,
                metadata={},
                explanation_ko="글로벌 리스크 입력 데이터가 없어 선택 신호를 0점 처리했습니다.",
            )

        score_raw = self._score_high_bearish(
            risk_off_raw,
            bearish_threshold=float(rules.get("risk_off_threshold", 0.3)),
            bullish_threshold=float(rules.get("risk_on_threshold", -0.3)),
            scale=float(rules.get("scale", 1.5)),
        )
        score = score_raw * float(rules.get("weight", 1.0))
        volatility_score = (
            self._clamp(abs(risk_off_raw) / max(float(rules.get("scale", 1.5)), 0.01), 0.0, 2.0)
            * float(rules.get("volatility_weight", 0.5))
        )
        explanation_ko = f"글로벌 리스크 지표({risk_off_raw:.2f})를 반영해 점수 {score:.2f}점을 추가했습니다."
        return SignalComponentResult(
            component_key="global_risk_input",
            component_label="글로벌 리스크 입력(선택)",
            component_group="optional",
            raw_value=risk_off_raw,
            reference_value=None,
            delta_value=None,
            score=score,
            volatility_score=volatility_score,
            weight=float(rules.get("weight", 1.0)),
            data_available=True,
            source_table="market_intraday_snapshots",
            source_name=self._as_text(global_snapshot.get("source_name")),
            source_url=self._as_text(global_snapshot.get("source_url")),
            source_record_id=self._as_text(global_snapshot.get("source_record_id")),
            source_metric_key=risk_metric_key,
            thresholds=rules,
            metadata={},
            explanation_ko=explanation_ko,
        )

    def _missing_component(
        self,
        *,
        component_key: str,
        component_label: str,
        component_group: str,
        weight: float,
        thresholds: dict[str, Any],
        explanation_ko: str,
        source_table: str | None,
        source_name: str | None,
        source_url: str | None,
        source_record_id: str | None,
        source_metric_key: str | None,
    ) -> SignalComponentResult:
        return SignalComponentResult(
            component_key=component_key,
            component_label=component_label,
            component_group=component_group,
            raw_value=None,
            reference_value=None,
            delta_value=None,
            score=0.0,
            volatility_score=0.0,
            weight=weight,
            data_available=False,
            source_table=source_table,
            source_name=source_name,
            source_url=source_url,
            source_record_id=source_record_id,
            source_metric_key=source_metric_key,
            thresholds=thresholds,
            metadata={},
            explanation_ko=explanation_ko,
        )

    def _directional_bias(self, total_score: float) -> str:
        rules = self.rules["classification"]
        if total_score >= float(rules.get("directional_bullish_cutoff", 1.0)):
            return "bullish"
        if total_score <= float(rules.get("directional_bearish_cutoff", -1.0)):
            return "bearish"
        return "neutral"

    def _gap_bias_from_components(self, components: list[SignalComponentResult]) -> str:
        night_component = next(
            (item for item in components if item.component_key == "night_futures_gap_signal"),
            None,
        )
        if night_component is None or night_component.raw_value is None:
            return "flat"
        gap_pct = night_component.raw_value
        rules = self.rules["classification"]
        if gap_pct >= float(rules.get("gap_up_cutoff_pct", 0.2)):
            return "gap_up"
        if gap_pct <= float(rules.get("gap_down_cutoff_pct", -0.2)):
            return "gap_down"
        return "flat"

    def _volatility_bias(self, volatility_score: float) -> str:
        rules = self.rules["classification"]
        if volatility_score >= float(rules.get("volatility_rising_cutoff", 1.0)):
            return "rising"
        if volatility_score <= float(rules.get("volatility_falling_cutoff", -1.0)):
            return "falling"
        return "stable"

    def _confidence_bucket(self, *, total_score: float, components: list[SignalComponentResult]) -> str:
        rules = self.rules["classification"]
        available_mandatory = sum(
            1
            for component in components
            if component.component_key in MANDATORY_COMPONENT_KEYS and component.data_available
        )
        mandatory_count = len(MANDATORY_COMPONENT_KEYS)
        coverage = (available_mandatory / mandatory_count) if mandatory_count else 0.0
        absolute_score = abs(total_score)

        if (
            coverage >= float(rules.get("confidence_high_min_coverage", 0.75))
            and absolute_score >= float(rules.get("confidence_high_min_score", 2.5))
        ):
            return "high"
        if (
            coverage >= float(rules.get("confidence_medium_min_coverage", 0.5))
            and absolute_score >= float(rules.get("confidence_medium_min_score", 1.2))
        ):
            return "medium"
        return "low"

    def _build_korean_explanation(
        self,
        *,
        trade_date: date,
        directional_bias: str,
        gap_bias: str,
        volatility_bias: str,
        total_score: float,
        confidence_bucket: str,
        components: list[SignalComponentResult],
    ) -> str:
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

        lines = [
            (
                f"{trade_date.isoformat()} KRX 프리마켓 기준 총점은 {total_score:.2f}점이며 "
                f"방향성은 {directional_label}입니다."
            ),
            f"야간 갭 해석은 {gap_label}, 변동성 전망은 {volatility_label}, 신뢰도는 {confidence_bucket}입니다.",
        ]

        ranked = sorted(components, key=lambda item: abs(item.score), reverse=True)
        for component in ranked[:4]:
            lines.append(f"- {component.component_label}: {component.explanation_ko}")

        lines.append("본 브리핑은 정보 제공 목적이며 투자 성과를 보장하지 않습니다.")
        return "\n".join(lines)

    def _build_markdown_summary(
        self,
        *,
        trade_date: date,
        directional_bias: str,
        gap_bias: str,
        volatility_bias: str,
        confidence_bucket: str,
        total_score: float,
        volatility_score: float,
        components: list[SignalComponentResult],
        explanation_ko: str,
    ) -> str:
        lines = [
            f"# KRX 08:30 프리마켓 브리핑 ({trade_date.isoformat()})",
            "",
            f"- 방향성: **{directional_bias}**",
            f"- 갭 바이어스: **{gap_bias}**",
            f"- 변동성 바이어스: **{volatility_bias}**",
            f"- 종합 점수: **{total_score:.2f}**",
            f"- 변동성 점수: **{volatility_score:.2f}**",
            f"- 신뢰도: **{confidence_bucket}**",
            "",
            "## 신호 구성요소",
            "| 신호 | 점수 | 변동성 점수 | 설명 |",
            "| --- | ---: | ---: | --- |",
        ]
        for component in components:
            lines.append(
                f"| {component.component_label} | {component.score:.2f} | {component.volatility_score:.2f} | "
                f"{component.explanation_ko} |"
            )

        lines.extend(
            [
                "",
                "## 종합 해설",
                explanation_ko,
                "",
                "> 본 브리핑은 정보 제공 목적이며 투자 성과를 보장하지 않습니다.",
            ]
        )
        return "\n".join(lines)

    def _build_notification_payload(
        self,
        *,
        trade_date: date,
        directional_bias: str,
        gap_bias: str,
        volatility_bias: str,
        total_score: float,
        confidence_bucket: str,
    ) -> dict[str, Any] | None:
        return {
            "title": f"KRX 08:30 Briefing {trade_date.isoformat()}",
            "text": (
                f"{directional_bias} | {gap_bias} | {volatility_bias} | "
                f"score={total_score:.2f} | confidence={confidence_bucket}"
            ),
        }

    def _upsert_market_briefing(
        self,
        connection,
        *,
        trade_date_iso: str,
        run_mode: str,
        directional_bias: str,
        gap_bias: str,
        volatility_bias: str,
        confidence_bucket: str,
        total_score: float,
        volatility_score: float,
        explanation_ko: str,
        json_payload: dict[str, Any],
        markdown_summary: str,
        notification_payload: dict[str, Any] | None,
        input_snapshot: dict[str, Any],
    ) -> int:
        now = utcnow_iso()
        existing = connection.execute(
            """
            SELECT id
            FROM market_briefings
            WHERE trade_date = ? AND market_scope = ?
            LIMIT 1
            """,
            (trade_date_iso, self.market_scope),
        ).fetchone()

        serialized_rules = json.dumps(self.rules, ensure_ascii=False, sort_keys=True)
        serialized_payload = json.dumps(json_payload, ensure_ascii=False, sort_keys=True)
        serialized_notification = (
            json.dumps(notification_payload, ensure_ascii=False, sort_keys=True) if notification_payload else None
        )
        serialized_inputs = json.dumps(input_snapshot, ensure_ascii=False, sort_keys=True)

        if existing is None:
            connection.execute(
                """
                INSERT INTO market_briefings (
                    trade_date,
                    market_scope,
                    run_mode,
                    directional_bias,
                    gap_bias,
                    volatility_bias,
                    confidence_bucket,
                    total_score,
                    volatility_score,
                    explanation_ko,
                    json_payload,
                    markdown_summary,
                    notification_payload_json,
                    rule_config_json,
                    input_snapshot_json,
                    generated_at,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade_date_iso,
                    self.market_scope,
                    run_mode,
                    directional_bias,
                    gap_bias,
                    volatility_bias,
                    confidence_bucket,
                    total_score,
                    volatility_score,
                    explanation_ko,
                    serialized_payload,
                    markdown_summary,
                    serialized_notification,
                    serialized_rules,
                    serialized_inputs,
                    now,
                    now,
                    now,
                ),
            )
            row = connection.execute("SELECT last_insert_rowid() AS id").fetchone()
            return int(row["id"])

        briefing_id = int(existing["id"])
        connection.execute(
            """
            UPDATE market_briefings
            SET
                run_mode = ?,
                directional_bias = ?,
                gap_bias = ?,
                volatility_bias = ?,
                confidence_bucket = ?,
                total_score = ?,
                volatility_score = ?,
                explanation_ko = ?,
                json_payload = ?,
                markdown_summary = ?,
                notification_payload_json = ?,
                rule_config_json = ?,
                input_snapshot_json = ?,
                generated_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                run_mode,
                directional_bias,
                gap_bias,
                volatility_bias,
                confidence_bucket,
                total_score,
                volatility_score,
                explanation_ko,
                serialized_payload,
                markdown_summary,
                serialized_notification,
                serialized_rules,
                serialized_inputs,
                now,
                now,
                briefing_id,
            ),
        )
        return briefing_id

    def _upsert_signal_components(
        self,
        connection,
        *,
        briefing_id: int,
        trade_date_iso: str,
        components: list[SignalComponentResult],
    ) -> None:
        now = utcnow_iso()
        for component in components:
            existing = connection.execute(
                """
                SELECT id
                FROM market_signal_components
                WHERE briefing_id = ? AND component_key = ?
                LIMIT 1
                """,
                (briefing_id, component.component_key),
            ).fetchone()

            thresholds_json = json.dumps(component.thresholds, ensure_ascii=False, sort_keys=True)
            metadata_json = json.dumps(component.metadata, ensure_ascii=False, sort_keys=True)

            if existing is None:
                connection.execute(
                    """
                    INSERT INTO market_signal_components (
                        briefing_id,
                        trade_date,
                        market_scope,
                        component_key,
                        component_label,
                        component_group,
                        raw_value,
                        reference_value,
                        delta_value,
                        score,
                        volatility_score,
                        weight,
                        data_available,
                        source_table,
                        source_name,
                        source_url,
                        source_record_id,
                        source_metric_key,
                        threshold_json,
                        metadata_json,
                        explanation_ko,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        briefing_id,
                        trade_date_iso,
                        self.market_scope,
                        component.component_key,
                        component.component_label,
                        component.component_group,
                        component.raw_value,
                        component.reference_value,
                        component.delta_value,
                        component.score,
                        component.volatility_score,
                        component.weight,
                        1 if component.data_available else 0,
                        component.source_table,
                        component.source_name,
                        component.source_url,
                        component.source_record_id,
                        component.source_metric_key,
                        thresholds_json,
                        metadata_json,
                        component.explanation_ko,
                        now,
                        now,
                    ),
                )
                continue

            connection.execute(
                """
                UPDATE market_signal_components
                SET
                    trade_date = ?,
                    market_scope = ?,
                    component_label = ?,
                    component_group = ?,
                    raw_value = ?,
                    reference_value = ?,
                    delta_value = ?,
                    score = ?,
                    volatility_score = ?,
                    weight = ?,
                    data_available = ?,
                    source_table = ?,
                    source_name = ?,
                    source_url = ?,
                    source_record_id = ?,
                    source_metric_key = ?,
                    threshold_json = ?,
                    metadata_json = ?,
                    explanation_ko = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    trade_date_iso,
                    self.market_scope,
                    component.component_label,
                    component.component_group,
                    component.raw_value,
                    component.reference_value,
                    component.delta_value,
                    component.score,
                    component.volatility_score,
                    component.weight,
                    1 if component.data_available else 0,
                    component.source_table,
                    component.source_name,
                    component.source_url,
                    component.source_record_id,
                    component.source_metric_key,
                    thresholds_json,
                    metadata_json,
                    component.explanation_ko,
                    now,
                    int(existing["id"]),
                ),
            )

    def _upsert_backtest(
        self,
        connection,
        *,
        briefing_id: int,
        trade_date_iso: str,
        evaluation_date: str,
        predicted_directional_bias: str,
        actual_directional_bias: str,
        predicted_gap_bias: str,
        actual_gap_bias: str,
        predicted_volatility_bias: str,
        actual_volatility_bias: str,
        directional_hit: bool | None,
        gap_hit: bool | None,
        volatility_hit: bool | None,
    ) -> int:
        existing = connection.execute(
            """
            SELECT id
            FROM market_signal_backtests
            WHERE briefing_id = ? AND evaluation_date = ?
            LIMIT 1
            """,
            (briefing_id, evaluation_date),
        ).fetchone()
        now = utcnow_iso()

        if existing is None:
            connection.execute(
                """
                INSERT INTO market_signal_backtests (
                    briefing_id,
                    trade_date,
                    evaluation_date,
                    market_scope,
                    predicted_directional_bias,
                    actual_directional_bias,
                    predicted_gap_bias,
                    actual_gap_bias,
                    predicted_volatility_bias,
                    actual_volatility_bias,
                    directional_hit,
                    gap_hit,
                    volatility_hit,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    briefing_id,
                    trade_date_iso,
                    evaluation_date,
                    self.market_scope,
                    predicted_directional_bias,
                    actual_directional_bias,
                    predicted_gap_bias,
                    actual_gap_bias,
                    predicted_volatility_bias,
                    actual_volatility_bias,
                    self._bool_to_int(directional_hit),
                    self._bool_to_int(gap_hit),
                    self._bool_to_int(volatility_hit),
                    now,
                    now,
                ),
            )
            row = connection.execute("SELECT last_insert_rowid() AS id").fetchone()
            return int(row["id"])

        backtest_id = int(existing["id"])
        connection.execute(
            """
            UPDATE market_signal_backtests
            SET
                trade_date = ?,
                market_scope = ?,
                predicted_directional_bias = ?,
                actual_directional_bias = ?,
                predicted_gap_bias = ?,
                actual_gap_bias = ?,
                predicted_volatility_bias = ?,
                actual_volatility_bias = ?,
                directional_hit = ?,
                gap_hit = ?,
                volatility_hit = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                trade_date_iso,
                self.market_scope,
                predicted_directional_bias,
                actual_directional_bias,
                predicted_gap_bias,
                actual_gap_bias,
                predicted_volatility_bias,
                actual_volatility_bias,
                self._bool_to_int(directional_hit),
                self._bool_to_int(gap_hit),
                self._bool_to_int(volatility_hit),
                now,
                backtest_id,
            ),
        )
        return backtest_id

    def _resolve_next_evaluation_date(self, connection, *, trade_date_iso: str) -> str | None:
        row = connection.execute(
            """
            SELECT trade_date
            FROM (
                SELECT trade_date
                FROM market_intraday_snapshots
                WHERE trade_date > ?
                UNION
                SELECT trade_date
                FROM market_daily_factors
                WHERE trade_date > ?
                UNION
                SELECT trade_date
                FROM derivatives_daily_metrics
                WHERE trade_date > ?
            )
            ORDER BY trade_date ASC
            LIMIT 1
            """,
            (trade_date_iso, trade_date_iso, trade_date_iso),
        ).fetchone()
        if row is None:
            return None
        return str(row["trade_date"])

    def _resolve_actual_outcome(self, connection, *, evaluation_date: str) -> dict[str, Any]:
        snapshot_row = connection.execute(
            """
            SELECT *
            FROM market_intraday_snapshots
            WHERE
                trade_date = ?
                AND session_type IN ('PRE_OPEN', 'NIGHT_SESSION')
                AND source_name IN ('KIS_DOMESTIC_DERIVATIVES', 'KIS_NIGHT_FUTURES')
            ORDER BY
                CASE
                    WHEN instrument_name LIKE '%KOSPI200%' THEN 0
                    WHEN instrument_code LIKE '101%' THEN 1
                    WHEN source_name = 'KIS_DOMESTIC_DERIVATIVES' THEN 2
                    ELSE 3
                END,
                COALESCE(volume, 0) DESC,
                snapshot_time DESC,
                id DESC
            LIMIT 1
            """,
            (evaluation_date,),
        ).fetchone()

        change_rate: float | None = None
        if snapshot_row is not None:
            change_rate = self._as_float(snapshot_row["change_rate"])
            if change_rate is None:
                change_rate = self._as_float(snapshot_row["price_change"])

        rules = self.rules["classification"]
        outcome_up = float(rules.get("outcome_up_cutoff_pct", 0.15))
        outcome_down = float(rules.get("outcome_down_cutoff_pct", -0.15))
        gap_up = float(rules.get("gap_up_cutoff_pct", 0.2))
        gap_down = float(rules.get("gap_down_cutoff_pct", -0.2))

        directional_bias = "unknown"
        gap_bias = "unknown"
        if change_rate is not None:
            if change_rate >= outcome_up:
                directional_bias = "bullish"
            elif change_rate <= outcome_down:
                directional_bias = "bearish"
            else:
                directional_bias = "neutral"

            if change_rate >= gap_up:
                gap_bias = "gap_up"
            elif change_rate <= gap_down:
                gap_bias = "gap_down"
            else:
                gap_bias = "flat"

        current_iv_row = connection.execute(
            """
            SELECT implied_volatility
            FROM derivatives_daily_metrics
            WHERE trade_date = ?
            ORDER BY
                CASE
                    WHEN source_name = 'KRX_DERIVATIVES_REFERENCE' THEN 0
                    WHEN source_name = 'KRX_DERIVATIVES_MANUAL' THEN 1
                    ELSE 2
                END,
                id DESC
            LIMIT 1
            """,
            (evaluation_date,),
        ).fetchone()
        previous_iv_row = connection.execute(
            """
            SELECT implied_volatility
            FROM derivatives_daily_metrics
            WHERE trade_date < ?
            ORDER BY trade_date DESC, id DESC
            LIMIT 1
            """,
            (evaluation_date,),
        ).fetchone()

        volatility_bias = "unknown"
        iv_delta = None
        if current_iv_row is not None and previous_iv_row is not None:
            current_iv = self._as_float(current_iv_row["implied_volatility"])
            previous_iv = self._as_float(previous_iv_row["implied_volatility"])
            if current_iv is not None and previous_iv is not None:
                iv_delta = current_iv - previous_iv
                if iv_delta >= float(rules.get("outcome_iv_rising_delta", 0.7)):
                    volatility_bias = "rising"
                elif iv_delta <= float(rules.get("outcome_iv_falling_delta", -0.7)):
                    volatility_bias = "falling"
                else:
                    volatility_bias = "stable"

        return {
            "evaluation_date": evaluation_date,
            "change_rate": change_rate,
            "directional_bias": directional_bias,
            "gap_bias": gap_bias,
            "volatility_bias": volatility_bias,
            "iv_delta": iv_delta,
        }

    def _build_confusion_summary(self, connection) -> dict[str, Any]:
        rows = connection.execute(
            """
            SELECT predicted_directional_bias, actual_directional_bias, COUNT(*) AS count
            FROM market_signal_backtests
            WHERE market_scope = ? AND actual_directional_bias != 'unknown'
            GROUP BY predicted_directional_bias, actual_directional_bias
            """,
            (self.market_scope,),
        ).fetchall()
        matrix: dict[str, dict[str, int]] = {}
        total = 0
        for row in rows:
            predicted = str(row["predicted_directional_bias"])
            actual = str(row["actual_directional_bias"])
            count = int(row["count"])
            total += count
            matrix.setdefault(predicted, {})[actual] = count
        return {"total": total, "matrix": matrix}

    def _build_score_distribution(self, connection) -> dict[str, int]:
        rows = connection.execute(
            """
            SELECT
                CASE
                    WHEN total_score <= -2.0 THEN 'strong_bearish'
                    WHEN total_score < -0.75 THEN 'mild_bearish'
                    WHEN total_score < 0.75 THEN 'neutral_band'
                    WHEN total_score < 2.0 THEN 'mild_bullish'
                    ELSE 'strong_bullish'
                END AS bucket,
                COUNT(*) AS count
            FROM market_briefings
            WHERE market_scope = ?
            GROUP BY bucket
            """,
            (self.market_scope,),
        ).fetchall()
        distribution = {
            "strong_bearish": 0,
            "mild_bearish": 0,
            "neutral_band": 0,
            "mild_bullish": 0,
            "strong_bullish": 0,
        }
        for row in rows:
            distribution[str(row["bucket"])] = int(row["count"])
        return distribution

    def _compute_hit_rate(self, connection) -> float | None:
        row = connection.execute(
            """
            SELECT AVG(CAST(directional_hit AS REAL)) AS hit_rate
            FROM market_signal_backtests
            WHERE market_scope = ? AND directional_hit IS NOT NULL
            """,
            (self.market_scope,),
        ).fetchone()
        if row is None or row["hit_rate"] is None:
            return None
        return round(float(row["hit_rate"]), 4)

    def _count_evaluated_backtests(self, connection) -> int:
        row = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM market_signal_backtests
            WHERE market_scope = ? AND directional_hit IS NOT NULL
            """,
            (self.market_scope,),
        ).fetchone()
        return int(row["count"]) if row is not None else 0

    def _count_hits(self, connection, column_name: str) -> int:
        row = connection.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM market_signal_backtests
            WHERE market_scope = ? AND {column_name} = 1
            """,
            (self.market_scope,),
        ).fetchone()
        return int(row["count"]) if row is not None else 0

    def _list_components_by_briefing_id(self, connection, *, briefing_id: int) -> list[dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT *
            FROM market_signal_components
            WHERE briefing_id = ?
            ORDER BY id ASC
            """,
            (briefing_id,),
        ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["threshold"] = self._json_load(payload.pop("threshold_json", None))
            payload["metadata"] = self._json_load(payload.pop("metadata_json", None))
            payload["data_available"] = bool(payload.get("data_available"))
            items.append(payload)
        return items

    def _list_backtests_by_briefing_id(self, connection, *, briefing_id: int) -> list[dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT *
            FROM market_signal_backtests
            WHERE briefing_id = ?
            ORDER BY evaluation_date DESC, id DESC
            """,
            (briefing_id,),
        ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["confusion_summary"] = self._json_load(payload.pop("confusion_summary_json", None))
            payload["score_distribution"] = self._json_load(payload.pop("score_distribution_json", None))
            payload["metrics"] = self._json_load(payload.pop("metrics_json", None))
            payload["directional_hit"] = self._int_to_bool(payload.get("directional_hit"))
            payload["gap_hit"] = self._int_to_bool(payload.get("gap_hit"))
            payload["volatility_hit"] = self._int_to_bool(payload.get("volatility_hit"))
            items.append(payload)
        return items

    def _deserialize_briefing_row(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload["json_payload"] = self._json_load(payload.get("json_payload"))
        payload["notification_payload"] = self._json_load(payload.pop("notification_payload_json", None))
        payload["rule_config"] = self._json_load(payload.pop("rule_config_json", None))
        payload["input_snapshot"] = self._json_load(payload.pop("input_snapshot_json", None))
        return payload

    def _select_derivatives_row(self, connection, *, trade_date_iso: str) -> dict[str, Any] | None:
        row = connection.execute(
            """
            SELECT *
            FROM derivatives_daily_metrics
            WHERE trade_date = ?
            ORDER BY
                CASE
                    WHEN source_name = 'KRX_DERIVATIVES_REFERENCE' THEN 0
                    WHEN source_name = 'KRX_DERIVATIVES_MANUAL' THEN 1
                    ELSE 2
                END,
                id DESC
            LIMIT 1
            """,
            (trade_date_iso,),
        ).fetchone()
        return self._deserialize_input_row(row)

    def _select_previous_derivatives_row(self, connection, *, trade_date_iso: str) -> dict[str, Any] | None:
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
            (trade_date_iso,),
        ).fetchone()
        return self._deserialize_input_row(row)

    def _select_daily_factor_row(self, connection, *, trade_date_iso: str) -> dict[str, Any] | None:
        row = connection.execute(
            """
            SELECT *
            FROM market_daily_factors
            WHERE trade_date = ?
            ORDER BY
                CASE
                    WHEN source_name = 'KIS_MARKET_BREADTH' THEN 0
                    ELSE 1
                END,
                id DESC
            LIMIT 1
            """,
            (trade_date_iso,),
        ).fetchone()
        return self._deserialize_input_row(row)

    def _select_previous_daily_factor_row(self, connection, *, trade_date_iso: str) -> dict[str, Any] | None:
        row = connection.execute(
            """
            SELECT *
            FROM market_daily_factors
            WHERE trade_date < ?
            ORDER BY trade_date DESC, id DESC
            LIMIT 1
            """,
            (trade_date_iso,),
        ).fetchone()
        return self._deserialize_input_row(row)

    def _select_night_snapshot_row(self, connection, *, trade_date_iso: str) -> dict[str, Any] | None:
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
                COALESCE(volume, 0) DESC,
                snapshot_time DESC,
                id DESC
            LIMIT 1
            """,
            (trade_date_iso,),
        ).fetchone()
        return self._deserialize_input_row(row)

    def _select_global_snapshot_row(self, connection, *, trade_date_iso: str) -> dict[str, Any] | None:
        row = connection.execute(
            """
            SELECT *
            FROM market_intraday_snapshots
            WHERE
                trade_date = ?
                AND source_name LIKE 'GLOBAL_INPUT_PROVIDER_%'
            ORDER BY snapshot_time DESC, id DESC
            LIMIT 1
            """,
            (trade_date_iso,),
        ).fetchone()
        return self._deserialize_input_row(row)

    def _deserialize_input_row(self, row) -> dict[str, Any] | None:
        if row is None:
            return None
        payload = dict(row)
        payload["additional_metrics"] = self._json_load(payload.pop("additional_metrics_json", None)) or {}
        payload["raw_payload"] = self._json_load(payload.pop("raw_payload_json", None))
        return payload

    def _component_rules(self, component_key: str) -> dict[str, Any]:
        components = self.rules.get("components", {})
        raw = components.get(component_key, {})
        if isinstance(raw, dict):
            return raw
        return {}

    def _load_rules(self, rules_json: str | None) -> dict[str, Any]:
        merged = self._deep_copy(DEFAULT_SIGNAL_RULES)
        if not rules_json:
            return merged

        try:
            override_payload = json.loads(rules_json)
        except json.JSONDecodeError:
            logger.warning("market_briefing_rules_json_invalid_fallback_to_default")
            return merged

        if not isinstance(override_payload, dict):
            logger.warning("market_briefing_rules_json_not_object_fallback_to_default")
            return merged

        self._deep_merge(merged, override_payload)
        return merged

    def _normalize_mode(self, mode: str) -> str:
        normalized = (mode or "MANUAL").strip().upper()
        if normalized not in {"SCHEDULED", "MANUAL", "BACKFILL"}:
            return "MANUAL"
        return normalized

    def _score_high_bullish(
        self,
        value: float,
        *,
        bullish_threshold: float,
        bearish_threshold: float,
        scale: float,
    ) -> float:
        if value >= bullish_threshold:
            return self._clamp(0.5 + (value - bullish_threshold) / max(scale, 0.0001), 0.0, 2.0)
        if value <= bearish_threshold:
            return -self._clamp(0.5 + (bearish_threshold - value) / max(scale, 0.0001), 0.0, 2.0)
        return 0.0

    def _score_high_bearish(
        self,
        value: float,
        *,
        bearish_threshold: float,
        bullish_threshold: float,
        scale: float,
    ) -> float:
        if value >= bearish_threshold:
            return -self._clamp(0.5 + (value - bearish_threshold) / max(scale, 0.0001), 0.0, 2.0)
        if value <= bullish_threshold:
            return self._clamp(0.5 + (bullish_threshold - value) / max(scale, 0.0001), 0.0, 2.0)
        return 0.0

    def _score_low_bullish_high_bearish(
        self,
        value: float,
        *,
        bullish_threshold: float,
        bearish_threshold: float,
        scale: float,
    ) -> float:
        if value <= bullish_threshold:
            return self._clamp(0.5 + (bullish_threshold - value) / max(scale, 0.0001), 0.0, 2.0)
        if value >= bearish_threshold:
            return -self._clamp(0.5 + (value - bearish_threshold) / max(scale, 0.0001), 0.0, 2.0)
        return 0.0

    def _to_hit(self, *, predicted: str, actual: str) -> bool | None:
        if actual == "unknown":
            return None
        return predicted == actual

    def _bool_to_int(self, value: bool | None) -> int | None:
        if value is None:
            return None
        return 1 if value else 0

    def _int_to_bool(self, value: Any) -> bool | None:
        if value is None:
            return None
        if int(value) == 1:
            return True
        if int(value) == 0:
            return False
        return None

    def _as_float(self, value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(",", "")
        if not text or text in {"-", "--", "N/A", "NA", "null", "None"}:
            return None
        if text.startswith("+"):
            text = text[1:]
        if text.endswith("%"):
            text = text[:-1]
        try:
            return float(text)
        except ValueError:
            return None

    def _as_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _pct_change(self, current: float, previous: float) -> float | None:
        if abs(previous) < 0.0000001:
            return None
        return ((current - previous) / abs(previous)) * 100.0

    def _clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _deep_copy(self, payload: dict[str, Any]) -> dict[str, Any]:
        return json.loads(json.dumps(payload))

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> None:
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def _json_load(self, value: str | None) -> Any:
        if not value:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
