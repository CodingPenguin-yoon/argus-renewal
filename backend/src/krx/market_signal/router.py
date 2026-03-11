from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from ...config.env import get_settings
from .service import MarketSignalService


def create_krx_market_signal_router() -> APIRouter:
    router = APIRouter(prefix="/market-signal", tags=["krx-market-signal"])

    @router.get("/summary")
    async def market_signal_summary(
        date: Optional[str] = Query(default=None),
    ) -> dict:
        settings = get_settings()
        service = MarketSignalService.from_settings(settings)
        return {"item": service.get_summary(date=date)}

    @router.get("/trends")
    async def market_signal_trends(
        preset: str = Query(default="20d"),
        date: Optional[str] = Query(default=None),
    ) -> dict:
        settings = get_settings()
        service = MarketSignalService.from_settings(settings)
        return service.get_trends(preset=preset, date=date)

    @router.get("/components")
    async def market_signal_components(
        date: Optional[str] = Query(default=None),
    ) -> dict:
        settings = get_settings()
        service = MarketSignalService.from_settings(settings)
        return {"item": service.get_components(date=date)}

    return router
