from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ...config.env import get_settings
from .factory import create_news_product_service
from ..source_ingestion.factory import create_event_normalization_service


def create_krx_news_router() -> APIRouter:
    router = APIRouter(prefix="/news", tags=["krx-news"])

    @router.get("")
    async def all_news(
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, list[dict]]:
        service = create_news_product_service(get_settings())
        return {"items": service.list_feed_items(limit=limit)}

    @router.get("/top")
    async def top_news() -> dict[str, list[dict]]:
        service = create_news_product_service(get_settings())
        return {"items": service.list_feed_items(limit=10)}

    @router.get("/macro")
    async def macro_news(
        limit: int = Query(default=30, ge=1, le=100),
    ) -> dict[str, list[dict]]:
        service = create_news_product_service(get_settings())
        items = [item for item in service.list_feed_items(limit=max(limit * 2, 30)) if item["type"] == "macro"]
        return {"items": items[:limit]}

    @router.get("/stock")
    async def stock_news(
        limit: int = Query(default=30, ge=1, le=100),
    ) -> dict[str, list[dict]]:
        service = create_news_product_service(get_settings())
        items = [item for item in service.list_feed_items(limit=max(limit * 2, 30)) if item["type"] == "stock"]
        return {"items": items[:limit]}

    @router.get("/by-ticker/{ticker}")
    async def news_by_ticker(
        ticker: str,
        limit: int = Query(default=20, ge=1, le=100),
    ) -> dict[str, list[dict]]:
        service = create_news_product_service(get_settings())
        return {"items": service.list_feed_items_by_ticker(ticker=ticker, limit=limit)}

    @router.get("/search")
    async def news_search(
        q: str = Query(default=""),
        limit: int = Query(default=20, ge=1, le=100),
    ) -> dict[str, list[dict]]:
        service = create_news_product_service(get_settings())
        return {"items": service.search_feed_items(query=q, limit=limit)}

    @router.get("/events/recent")
    async def recent_events(
        limit: int = Query(default=50, ge=1, le=300),
        event_type: Optional[str] = Query(default=None),
        impact_tier: Optional[str] = Query(default=None),
        min_confidence: Optional[float] = Query(default=None, ge=0.0, le=1.0),
        source_type: Optional[str] = Query(default=None),
    ) -> dict[str, list[dict]]:
        settings = get_settings()
        service = create_event_normalization_service(settings)
        return {
            "items": service.list_recent_events(
                limit=limit,
                event_type=event_type,
                impact_tier=impact_tier,
                min_confidence=min_confidence,
                source_type=source_type,
            )
        }

    @router.get("/events/company/{company_id}")
    async def company_events(
        company_id: int,
        limit: int = Query(default=50, ge=1, le=300),
        event_type: Optional[str] = Query(default=None),
        impact_tier: Optional[str] = Query(default=None),
        min_confidence: Optional[float] = Query(default=None, ge=0.0, le=1.0),
        source_type: Optional[str] = Query(default=None),
    ) -> dict[str, list[dict]]:
        settings = get_settings()
        service = create_event_normalization_service(settings)
        return {
            "items": service.list_company_events(
                company_id=company_id,
                limit=limit,
                event_type=event_type,
                impact_tier=impact_tier,
                min_confidence=min_confidence,
                source_type=source_type,
            )
        }

    @router.get("/{news_id}")
    async def news_detail(news_id: str) -> dict[str, dict]:
        service = create_news_product_service(get_settings())
        item = service.get_feed_item(news_id=news_id)
        if not item:
            raise HTTPException(status_code=404, detail="News not found")
        return {"item": item}

    return router
