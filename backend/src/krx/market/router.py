from datetime import datetime

from fastapi import APIRouter, HTTPException

from .data import events, stocks


def _parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _sorted_events(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda item: _parse_iso_datetime(item["event_date"]))


def create_krx_market_router() -> APIRouter:
    router = APIRouter(tags=["krx-market"])

    @router.get("/stocks")
    async def all_stocks() -> dict[str, list[dict]]:
        return {"items": stocks}

    @router.get("/stocks/{ticker}")
    async def stock_detail(ticker: str) -> dict[str, dict]:
        query = ticker.strip().upper()
        item = next((stock for stock in stocks if stock["ticker"].upper() == query), None)
        if not item:
            raise HTTPException(status_code=404, detail="Stock not found")
        return {"item": item}

    @router.get("/events/upcoming")
    async def upcoming_events() -> dict[str, list[dict]]:
        return {"items": _sorted_events(events)}

    return router
