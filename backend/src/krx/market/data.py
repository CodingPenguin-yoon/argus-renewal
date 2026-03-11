from datetime import datetime, timedelta, timezone

now = datetime.now(timezone.utc)

stocks: list[dict] = [
    {"ticker": "005930.KS", "name": "삼성전자", "market": "KR", "sector": "반도체"},
    {"ticker": "000660.KS", "name": "SK하이닉스", "market": "KR", "sector": "반도체"},
    {"ticker": "035420.KS", "name": "NAVER", "market": "KR", "sector": "커뮤니케이션"},
    {"ticker": "105560.KS", "name": "KB금융", "market": "KR", "sector": "금융"},
]

events: list[dict] = [
    {
        "id": "krx-event-001",
        "title": "한국 CPI 발표",
        "event_date": (now + timedelta(days=1)).isoformat(),
        "country": "KR",
        "description": "국내 물가 발표로 금리 기대 경로가 조정될 수 있습니다.",
        "impact_level": "high",
        "related_tickers": ["105560.KS", "035420.KS"],
    },
    {
        "id": "krx-event-002",
        "title": "한국은행 금융통화위원회",
        "event_date": (now + timedelta(days=4)).isoformat(),
        "country": "KR",
        "description": "통화정책 방향 확인으로 금융주와 성장주의 변동성이 커질 수 있습니다.",
        "impact_level": "high",
        "related_tickers": ["105560.KS", "005930.KS"],
    },
    {
        "id": "krx-event-003",
        "title": "OPEC+ 월간 회의",
        "event_date": (now + timedelta(days=7)).isoformat(),
        "country": "GLOBAL",
        "description": "유가 흐름이 수입물가와 국내 업종별 마진에 영향을 줄 수 있습니다.",
        "impact_level": "medium",
        "related_tickers": ["005930.KS", "000660.KS"],
    },
]
