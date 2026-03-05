from ..data.mock_news import mock_news
from ..news_types import NewsItem


class MockNewsProvider:
    async def get_top_news(self) -> list[NewsItem]:
        return sorted(mock_news, key=lambda item: item.published_at, reverse=True)

    async def search(self, query: str) -> list[NewsItem]:
        q = query.strip().lower()
        if not q:
            return []

        return [
            item
            for item in mock_news
            if q in item.title.lower()
            or q in item.summary.lower()
            or any(q in tag.lower() for tag in item.tags)
            or any(q in ticker.lower() for ticker in item.related_tickers)
        ]
