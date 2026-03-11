from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ...config.env import get_settings
from ..source_ingestion.factory import create_event_normalization_service
from .data import news_items


def _parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _sorted_news(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda item: _parse_iso_datetime(item["published_at"]), reverse=True)


def create_krx_news_router() -> APIRouter:
    router = APIRouter(prefix="/news", tags=["krx-news"])

    @router.get("")
    async def all_news() -> dict[str, list[dict]]:
        return {"items": _sorted_news(news_items)}

    @router.get("/top")
    async def top_news() -> dict[str, list[dict]]:
        return {"items": _sorted_news(news_items)[:10]}

    @router.get("/macro")
    async def macro_news() -> dict[str, list[dict]]:
        return {"items": _sorted_news([item for item in news_items if item["type"] == "macro"])}

    @router.get("/stock")
    async def stock_news() -> dict[str, list[dict]]:
        return {"items": _sorted_news([item for item in news_items if item["type"] == "stock"])}

    @router.get("/by-ticker/{ticker}")
    async def news_by_ticker(ticker: str) -> dict[str, list[dict]]:
        query = ticker.strip().upper()
        items = [
            item
            for item in news_items
            if any(candidate.upper() == query for candidate in item["related_tickers"])
        ]
        return {"items": _sorted_news(items)}

    @router.get("/search")
    async def news_search(q: str = Query(default="")) -> dict[str, list[dict]]:
        query = q.strip().lower()
        if not query:
            return {"items": []}

        items = [
            item
            for item in news_items
            if query in item["title"].lower()
            or query in item["summary"].lower()
            or query in item["why_it_matters"].lower()
            or any(query in tag.lower() for tag in item["tags"])
            or any(query in ticker.lower() for ticker in item["related_tickers"])
        ]
        return {"items": _sorted_news(items)}

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
        item = next((news for news in news_items if news["id"] == news_id), None)
        if not item:
            raise HTTPException(status_code=404, detail="News not found")
        return {"item": item}

    return router
