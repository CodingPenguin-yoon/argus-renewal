from fastapi import APIRouter, Query

from ...config.env import get_settings
from ..news.factory import create_news_product_service


def create_market_news_router() -> APIRouter:
    router = APIRouter(prefix="/api/news", tags=["market-news"])

    @router.get("/kr")
    async def kr_news(
        limit: int = Query(default=12, ge=1, le=50),
    ) -> dict:
        service = create_news_product_service(get_settings())
        return {"items": service.list_cards(region="KR", limit=limit)}

    @router.get("/global")
    async def global_news(
        limit: int = Query(default=12, ge=1, le=50),
    ) -> dict:
        service = create_news_product_service(get_settings())
        return {"items": service.list_cards(region="GLOBAL", limit=limit)}

    @router.get("/disclosures")
    async def disclosures(
        limit: int = Query(default=12, ge=1, le=50),
    ) -> dict:
        service = create_news_product_service(get_settings())
        return {"items": service.list_disclosure_cards(limit=limit)}

    @router.get("/header-context")
    async def header_context() -> dict:
        service = create_news_product_service(get_settings())
        return service.get_header_context()

    @router.get("/coverage")
    async def coverage() -> dict:
        service = create_news_product_service(get_settings())
        return service.get_coverage()

    return router
