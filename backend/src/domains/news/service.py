from .provider import NewsProvider
from .news_types import NewsItem


class NewsService:
    def __init__(self, provider: NewsProvider):
        self._provider = provider

    async def get_top_news(self) -> list[NewsItem]:
        return await self._provider.get_top_news()

    async def search(self, query: str) -> list[NewsItem]:
        return await self._provider.search(query)
