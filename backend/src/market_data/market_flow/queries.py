from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .domain import DataMode, DataQuality, MarketFlowFact, MarketScope, MarketSegment
from .ports import MarketFlowFactReader


SEGMENT_LABELS: dict[MarketSegment, str] = {
    MarketSegment.KOSPI_SPOT: "KOSPI 현물",
    MarketSegment.KOSPI200_FUTURES: "KOSPI200 선물",
    MarketSegment.KOSPI200_CALL: "KOSPI200 콜옵션",
    MarketSegment.KOSPI200_PUT: "KOSPI200 풋옵션",
}


class FreshnessStatus(str, Enum):
    FRESH = "fresh"
    STALE = "stale"


class CoverageStatus(str, Enum):
    FRESH = "fresh"
    PARTIAL = "partial"
    STALE = "stale"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class MarketFlowPoint:
    fact: MarketFlowFact
    freshness: FreshnessStatus


@dataclass(frozen=True, slots=True)
class MarketFlowRow:
    segment: MarketSegment
    label: str
    estimate: MarketFlowPoint | None
    confirmed: MarketFlowPoint | None
    status: CoverageStatus


@dataclass(frozen=True, slots=True)
class MarketFlowDashboard:
    as_of: datetime
    data_mode: DataMode
    market_scope: MarketScope
    status: CoverageStatus
    rows: tuple[MarketFlowRow, ...]


def _freshness(
    fact: MarketFlowFact,
    *,
    now: datetime,
    estimate_stale_after_seconds: int,
    confirmed_stale_after_seconds: int,
) -> FreshnessStatus:
    threshold = (
        estimate_stale_after_seconds
        if fact.quality is DataQuality.ESTIMATE
        else confirmed_stale_after_seconds
    )
    age_seconds = max(0.0, (now - fact.observed_at).total_seconds())
    return FreshnessStatus.STALE if age_seconds > threshold else FreshnessStatus.FRESH


def _row_status(
    estimate: MarketFlowPoint | None,
    confirmed: MarketFlowPoint | None,
) -> CoverageStatus:
    if estimate is None and confirmed is None:
        return CoverageStatus.MISSING
    if estimate is None or confirmed is None:
        return CoverageStatus.PARTIAL
    if FreshnessStatus.STALE in {estimate.freshness, confirmed.freshness}:
        return CoverageStatus.STALE
    return CoverageStatus.FRESH


def _dashboard_status(rows: list[MarketFlowRow]) -> CoverageStatus:
    statuses = {row.status for row in rows}
    if statuses == {CoverageStatus.MISSING}:
        return CoverageStatus.MISSING
    if CoverageStatus.MISSING in statuses or CoverageStatus.PARTIAL in statuses:
        return CoverageStatus.PARTIAL
    if CoverageStatus.STALE in statuses:
        return CoverageStatus.STALE
    return CoverageStatus.FRESH


def build_market_flow_dashboard(
    *,
    reader: MarketFlowFactReader,
    data_mode: DataMode,
    now: datetime,
    estimate_stale_after_seconds: int,
    confirmed_stale_after_seconds: int,
) -> MarketFlowDashboard:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    facts = reader.list_latest(data_mode=data_mode)
    points: dict[tuple[MarketSegment, DataQuality], MarketFlowPoint] = {}
    for fact in facts:
        points[(fact.segment, fact.quality)] = MarketFlowPoint(
            fact=fact,
            freshness=_freshness(
                fact,
                now=now,
                estimate_stale_after_seconds=estimate_stale_after_seconds,
                confirmed_stale_after_seconds=confirmed_stale_after_seconds,
            ),
        )

    rows: list[MarketFlowRow] = []
    for segment in MarketSegment:
        estimate = points.get((segment, DataQuality.ESTIMATE))
        confirmed = points.get((segment, DataQuality.CONFIRMED))
        rows.append(
            MarketFlowRow(
                segment=segment,
                label=SEGMENT_LABELS[segment],
                estimate=estimate,
                confirmed=confirmed,
                status=_row_status(estimate, confirmed),
            )
        )

    return MarketFlowDashboard(
        as_of=now,
        data_mode=data_mode,
        market_scope=MarketScope.KRX,
        status=_dashboard_status(rows),
        rows=tuple(rows),
    )

