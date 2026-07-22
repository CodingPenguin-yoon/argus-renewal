from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class DataMode(str, Enum):
    MOCK = "mock"
    LIVE = "live"


class DataQuality(str, Enum):
    ESTIMATE = "estimate"
    CONFIRMED = "confirmed"


class MarketScope(str, Enum):
    KRX = "KRX"


class MarketSegment(str, Enum):
    KOSPI_SPOT = "kospi_spot"
    KOSPI200_FUTURES = "kospi200_futures"
    KOSPI200_CALL = "kospi200_call"
    KOSPI200_PUT = "kospi200_put"


class FlowUnit(str, Enum):
    KRW = "KRW"


@dataclass(frozen=True, slots=True)
class MarketFlowFact:
    source: str
    source_record_id: str
    data_mode: DataMode
    market_scope: MarketScope
    segment: MarketSegment
    quality: DataQuality
    trade_date: date
    observed_at: datetime
    collected_at: datetime
    unit: FlowUnit
    individual_net: int
    foreign_net: int
    institution_net: int

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("source must not be empty")
        if not self.source_record_id.strip():
            raise ValueError("source_record_id must not be empty")
        if self.observed_at.tzinfo is None or self.collected_at.tzinfo is None:
            raise ValueError("observed_at and collected_at must be timezone-aware")

    @property
    def is_live(self) -> bool:
        return self.data_mode is DataMode.LIVE

