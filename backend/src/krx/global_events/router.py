from __future__ import annotations

from datetime import date
import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ...config.env import get_settings
from .factory import create_global_events_service


def _parse_window_hours(value: str) -> int:
    match = re.fullmatch(r"(\d+)\s*h", value.strip().lower())
    if not match:
        raise HTTPException(status_code=400, detail="window must look like 24h")
    return int(match.group(1))


def create_global_events_router() -> APIRouter:
    router = APIRouter(prefix="/api/global-events", tags=["global-events"])

    @router.get("/upcoming")
    async def upcoming(window: str = Query(default="24h")) -> dict:
        service = create_global_events_service(get_settings())
        return service.get_upcoming(window_hours=_parse_window_hours(window))

    @router.get("/week")
    async def week(anchor_date: Optional[date] = Query(default=None)) -> dict:
        service = create_global_events_service(get_settings())
        return service.get_week(anchor=anchor_date)

    @router.get("/highlight")
    async def highlight(
        anchor_date: Optional[date] = Query(default=None),
        limit: int = Query(default=6, ge=1, le=20),
    ) -> dict:
        service = create_global_events_service(get_settings())
        return service.get_highlight(anchor=anchor_date, limit=limit)

    @router.get("/coverage")
    async def coverage() -> dict:
        service = create_global_events_service(get_settings())
        return service.get_coverage()

    return router
