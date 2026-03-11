from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from ...config.env import get_settings
from .service import DerivativesDashboardService


def create_krx_derivatives_router() -> APIRouter:
    router = APIRouter(prefix="/derivatives", tags=["krx-derivatives"])

    @router.get("/summary")
    async def derivatives_summary(
        date: Optional[str] = Query(default=None),
    ) -> dict:
        settings = get_settings()
        service = DerivativesDashboardService.from_settings(settings)
        return {"item": service.get_summary(date=date)}

    @router.get("/trends")
    async def derivatives_trends(
        preset: str = Query(default="20d"),
        date: Optional[str] = Query(default=None),
    ) -> dict:
        settings = get_settings()
        service = DerivativesDashboardService.from_settings(settings)
        return service.get_trends(preset=preset, date=date)

    @router.get("/investor-flow")
    async def derivatives_investor_flow(
        preset: str = Query(default="20d"),
        date: Optional[str] = Query(default=None),
    ) -> dict:
        settings = get_settings()
        service = DerivativesDashboardService.from_settings(settings)
        return service.get_investor_flow(preset=preset, date=date)

    @router.get("/briefing")
    async def derivatives_briefing(
        date: Optional[str] = Query(default=None),
    ) -> dict:
        settings = get_settings()
        service = DerivativesDashboardService.from_settings(settings)
        return {"item": service.get_briefing(date=date)}

    @router.get("/coverage")
    async def derivatives_coverage(
        date: Optional[str] = Query(default=None),
    ) -> dict:
        settings = get_settings()
        service = DerivativesDashboardService.from_settings(settings)
        return {"item": service.get_coverage(date=date)}

    return router
