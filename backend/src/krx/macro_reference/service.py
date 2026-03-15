from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .providers import FredRatesProvider
from .providers.fred_service import FredSeriesDefinition, FredSeriesSnapshot, utcnow

_FRED_SOURCE_KEY = "FRED"
_FRED_SOURCE_NAME = "Federal Reserve Economic Data"

_SERIES_DEFINITIONS: tuple[FredSeriesDefinition, ...] = (
    FredSeriesDefinition(
        key="us10y",
        label="미국채 10년물",
        series_id="DGS10",
        series_name="Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity",
        semantics="daily_market_yield_percent",
        frequency="daily",
        unit="pct",
        freshness_ttl_seconds=60 * 60 * 24 * 2,
        source_url="https://fred.stlouisfed.org/series/DGS10",
    ),
    FredSeriesDefinition(
        key="fedfunds",
        label="연방기금실효금리(월평균)",
        series_id="FEDFUNDS",
        series_name="Effective Federal Funds Rate",
        semantics="monthly_average_effective_federal_funds_rate_percent",
        frequency="monthly",
        unit="pct",
        freshness_ttl_seconds=60 * 60 * 24 * 45,
        source_url="https://fred.stlouisfed.org/series/FEDFUNDS",
    ),
)


class MacroReferenceService:
    def __init__(self, *, fred_rates_provider: FredRatesProvider, series_ids: str | None = None) -> None:
        self.fred_rates_provider = fred_rates_provider
        self.series_definitions = self._resolve_series_definitions(series_ids)

    def get_cards(self, *, now: datetime | None = None) -> dict[str, Any]:
        anchor = now or utcnow()
        snapshots, disabled_reason = self.fred_rates_provider.fetch_cards(
            series_definitions=list(self.series_definitions),
            now=anchor,
        )
        items = [self._to_card(snapshot=snapshot, now=anchor) for snapshot in snapshots if snapshot.value is not None]
        available_items = len(items)
        expected_items = len(self.series_definitions)
        coverage_state = _coverage_state(available_items=available_items, expected_items=expected_items)
        latest_updated_at = max((item["source"]["observed_at"] for item in items if item["source"]["observed_at"]), default=None)

        note = disabled_reason
        if note is None and coverage_state != "full":
            note = "partial_series_available" if available_items else "no_series_available"

        return {
            "updated_at": latest_updated_at,
            "items": items,
            "coverage": {
                "state": coverage_state,
                "available_items": available_items,
                "expected_items": expected_items,
                "provider": self.fred_rates_provider.provider,
                "summary": _coverage_summary(
                    provider=self.fred_rates_provider.provider,
                    available_items=available_items,
                    expected_items=expected_items,
                    disabled_reason=disabled_reason,
                ),
                "note": note,
                "items": self._coverage_items(snapshots=snapshots, now=anchor, disabled_reason=disabled_reason),
            },
        }

    def _resolve_series_definitions(self, series_ids: str | None) -> tuple[FredSeriesDefinition, ...]:
        if not series_ids:
            return _SERIES_DEFINITIONS
        requested = [item.strip().upper() for item in series_ids.split(",") if item.strip()]
        if not requested:
            return _SERIES_DEFINITIONS
        definitions: list[FredSeriesDefinition] = []
        for series_id in requested:
            definition = next((item for item in _SERIES_DEFINITIONS if item.series_id == series_id), None)
            if definition is not None:
                definitions.append(definition)
        return tuple(definitions or _SERIES_DEFINITIONS)

    def _to_card(self, *, snapshot: FredSeriesSnapshot, now: datetime) -> dict[str, Any]:
        freshness = _freshness(snapshot=snapshot, now=now)
        return {
            "key": snapshot.definition.key,
            "label": snapshot.definition.label,
            "value": snapshot.value,
            "value_display": _format_pct(snapshot.value),
            "change_value": snapshot.change_value,
            "change_display": _format_pct_point(snapshot.change_value),
            "summary": _summary_line(snapshot=snapshot),
            "unit": snapshot.definition.unit,
            "stale": freshness["status"] == "stale",
            "source": {
                "key": _FRED_SOURCE_KEY,
                "name": _FRED_SOURCE_NAME,
                "series_id": snapshot.definition.series_id,
                "series_name": snapshot.definition.series_name,
                "url": snapshot.definition.source_url,
                "observed_at": snapshot.observed_at,
                "updated_at": snapshot.series_updated_at,
            },
            "freshness": freshness,
            "metadata": {
                "series_id": snapshot.definition.series_id,
                "series_name": snapshot.definition.series_name,
                "semantics": snapshot.definition.semantics,
                "frequency": snapshot.definition.frequency,
                "freshness_ttl_seconds": snapshot.definition.freshness_ttl_seconds,
                "provider_mode": snapshot.provider,
                "retry_count": snapshot.retry_count,
            },
        }

    def _coverage_items(
        self,
        *,
        snapshots: list[FredSeriesSnapshot],
        now: datetime,
        disabled_reason: str | None,
    ) -> list[dict[str, Any]]:
        snapshot_map = {item.definition.series_id: item for item in snapshots}
        items: list[dict[str, Any]] = []
        for definition in self.series_definitions:
            snapshot = snapshot_map.get(definition.series_id)
            if snapshot is None or snapshot.value is None:
                items.append(
                    {
                        "key": definition.key,
                        "series_id": definition.series_id,
                        "label": definition.label,
                        "status": "missing",
                        "note": disabled_reason or "series_unavailable",
                        "observed_at": None,
                    }
                )
                continue

            freshness = _freshness(snapshot=snapshot, now=now)
            items.append(
                {
                    "key": definition.key,
                    "series_id": definition.series_id,
                    "label": definition.label,
                    "status": "partial" if freshness["status"] == "stale" else "available",
                    "note": None if freshness["status"] != "stale" else "stale_observation",
                    "observed_at": snapshot.observed_at,
                }
            )
        return items


def _coverage_state(*, available_items: int, expected_items: int) -> str:
    if available_items <= 0:
        return "empty"
    if available_items >= expected_items:
        return "full"
    return "partial"


def _coverage_summary(
    *,
    provider: str,
    available_items: int,
    expected_items: int,
    disabled_reason: str | None,
) -> str:
    if disabled_reason:
        return f"FRED 금리 reference가 비활성화되어 있습니다. ({disabled_reason})"
    return f"FRED 금리 reference {available_items}/{expected_items}개가 {provider} 경로로 준비됐습니다."


def _format_pct(value: float | None) -> str | None:
    if value is None:
        return None
    return f"{value:.2f}%"


def _format_pct_point(value: float | None) -> str | None:
    if value is None:
        return None
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%p"


def _freshness(*, snapshot: FredSeriesSnapshot, now: datetime) -> dict[str, Any]:
    observed_at = _parse_observed_at(snapshot.observed_at)
    age_seconds = None
    status = "unknown"
    if observed_at is not None:
        age_seconds = max(int((now - observed_at).total_seconds()), 0)
        status = "fresh" if age_seconds <= snapshot.definition.freshness_ttl_seconds else "stale"
    return {
        "status": status,
        "observed_at": snapshot.observed_at,
        "age_seconds": age_seconds,
        "ttl_seconds": snapshot.definition.freshness_ttl_seconds,
    }


def _parse_observed_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if len(value) == 10:
            return datetime.fromisoformat(f"{value}T00:00:00+00:00").astimezone(timezone.utc)
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _summary_line(*, snapshot: FredSeriesSnapshot) -> str | None:
    value_display = _format_pct(snapshot.value)
    if value_display is None:
        return None
    if snapshot.observed_at:
        return f"{snapshot.definition.label} {value_display} · {snapshot.observed_at} 기준"
    return f"{snapshot.definition.label} {value_display}"
