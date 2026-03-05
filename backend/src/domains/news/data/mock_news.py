from datetime import datetime, timedelta, timezone

from ..news_types import NewsItem

now = datetime.now(timezone.utc)

mock_news: list[NewsItem] = [
    NewsItem(
        id="m-1",
        type="macro",
        title="연준 위원, 금리 동결 기조 재확인",
        summary="물가 안정 전까지 신중한 통화정책 유지 가능성이 커졌습니다.",
        why_it_matters="성장주 밸류에이션 부담으로 기술주 변동성이 확대될 수 있습니다.",
        source="Argus Backend Desk",
        source_url="https://example.com/m-1",
        published_at=now.isoformat(),
        sentiment="neutral",
        importance="high",
        related_tickers=["NVDA", "MSFT"],
        category="금리",
        tags=["FOMC", "금리"],
    ),
    NewsItem(
        id="s-1",
        type="stock",
        title="NVIDIA, AI 서버 수요 강세 재확인",
        summary="클라우드 고객 주문이 예상보다 높은 수준을 유지했습니다.",
        why_it_matters="메모리/반도체 밸류체인 실적 추정치 상향 가능성이 있습니다.",
        source="Argus Backend Desk",
        source_url="https://example.com/s-1",
        published_at=(now - timedelta(hours=1)).isoformat(),
        sentiment="positive",
        importance="high",
        related_tickers=["NVDA", "000660.KS", "005930.KS"],
        category="실적",
        tags=["AI", "반도체"],
    ),
]
