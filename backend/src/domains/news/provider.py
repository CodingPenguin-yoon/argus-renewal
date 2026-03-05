from typing import Protocol

from .news_types import NewsItem


class NewsProvider(Protocol):
    async def get_top_news(self) -> list[NewsItem]: ...

    async def search(self, query: str) -> list[NewsItem]: ...
