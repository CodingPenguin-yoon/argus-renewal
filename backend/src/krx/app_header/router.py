from typing import Literal

from fastapi import APIRouter, Query

from ...config.env import get_settings
from .service import AppHeaderService


def create_app_header_router() -> APIRouter:
    router = APIRouter(prefix="/api/app", tags=["app-header"])

    @router.get("/header")
    async def app_header(
        market: Literal["krx"] = Query(default="krx"),
    ) -> dict:
        settings = get_settings()
        service = AppHeaderService(settings)
        return service.get_header(market=market)

    return router
