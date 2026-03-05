from typing import Literal

from pydantic import BaseModel


class NewsItem(BaseModel):
    id: str
    type: Literal["macro", "stock"]
    title: str
    summary: str
    why_it_matters: str
    source: str
    source_url: str
    published_at: str
    sentiment: Literal["positive", "neutral", "negative"]
    importance: Literal["high", "medium", "low"]
    related_tickers: list[str]
    category: str
    tags: list[str]
