from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ...config.env import get_settings
from .domain import DataMode
from .ports import MarketFlowFactReader
from .queries import MarketFlowDashboard, MarketFlowPoint, build_market_flow_dashboard
from .repository import SQLiteMarketFlowRepository


class MarketFlowFactResponse(BaseModel):
    source: str
    source_record_id: str
    data_mode: str
    is_live: bool
    market_scope: str
    quality: str
    trade_date: str
    observed_at: datetime
    collected_at: datetime
    freshness: str
    unit: str
    individual_net: int
    foreign_net: int
    institution_net: int


class MarketFlowRowResponse(BaseModel):
    segment: str
    label: str
    status: str
    estimate: MarketFlowFactResponse | None
    confirmed: MarketFlowFactResponse | None


class MarketFlowDashboardResponse(BaseModel):
    as_of: datetime
    data_mode: str
    is_live: bool
    market_scope: str
    status: str
    rows: list[MarketFlowRowResponse]


def _fact_response(point: MarketFlowPoint | None) -> MarketFlowFactResponse | None:
    if point is None:
        return None
    fact = point.fact
    return MarketFlowFactResponse(
        source=fact.source,
        source_record_id=fact.source_record_id,
        data_mode=fact.data_mode.value,
        is_live=fact.is_live,
        market_scope=fact.market_scope.value,
        quality=fact.quality.value,
        trade_date=fact.trade_date.isoformat(),
        observed_at=fact.observed_at,
        collected_at=fact.collected_at,
        freshness=point.freshness.value,
        unit=fact.unit.value,
        individual_net=fact.individual_net,
        foreign_net=fact.foreign_net,
        institution_net=fact.institution_net,
    )


def _dashboard_response(dashboard: MarketFlowDashboard) -> MarketFlowDashboardResponse:
    return MarketFlowDashboardResponse(
        as_of=dashboard.as_of,
        data_mode=dashboard.data_mode.value,
        is_live=dashboard.data_mode is DataMode.LIVE,
        market_scope=dashboard.market_scope.value,
        status=dashboard.status.value,
        rows=[
            MarketFlowRowResponse(
                segment=row.segment.value,
                label=row.label,
                status=row.status.value,
                estimate=_fact_response(row.estimate),
                confirmed=_fact_response(row.confirmed),
            )
            for row in dashboard.rows
        ],
    )


def create_market_flow_router(
    *,
    reader: MarketFlowFactReader | None = None,
    clock: Callable[[], datetime] | None = None,
) -> APIRouter:
    settings = get_settings()
    fact_reader = reader or SQLiteMarketFlowRepository(settings.db_path)
    now = clock or (lambda: datetime.now(timezone.utc))
    router = APIRouter(prefix="/api/market-data/v1", tags=["market-data"])

    @router.get(
        "/dashboard/market-flow",
        response_model=MarketFlowDashboardResponse,
    )
    def get_market_flow_dashboard(
        data_mode: DataMode = Query(default=DataMode(settings.market_data_mode)),
    ) -> MarketFlowDashboardResponse:
        dashboard = build_market_flow_dashboard(
            reader=fact_reader,
            data_mode=data_mode,
            now=now(),
            estimate_stale_after_seconds=settings.market_flow_estimate_stale_after_seconds,
            confirmed_stale_after_seconds=settings.market_flow_confirmed_stale_after_seconds,
        )
        return _dashboard_response(dashboard)

    return router

