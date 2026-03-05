from fastapi import APIRouter, Query

from .service import NewsService


def create_news_router(news_service: NewsService) -> APIRouter:
    router = APIRouter(prefix="/api/news", tags=["news"])

    @router.get("/top")
    async def top_news() -> dict[str, list[dict]]:
        items = await news_service.get_top_news()
        return {"items": [item.model_dump() for item in items]}

    @router.get("/search")
    async def search_news(q: str = Query(default="")) -> dict[str, list[dict]]:
        items = await news_service.search(q)
        return {"items": [item.model_dump() for item in items]}

    return router
