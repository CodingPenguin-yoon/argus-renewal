from __future__ import annotations

from fastapi import APIRouter

from ...config.env import get_settings
from .factory import create_macro_reference_service


def create_krx_macro_reference_router() -> APIRouter:
    router = APIRouter(prefix="/macro-reference", tags=["krx-macro-reference"])

    @router.get("/cards")
    async def macro_reference_cards() -> dict:
        settings = get_settings()
        service = create_macro_reference_service(settings)
        return service.get_cards()

    return router
