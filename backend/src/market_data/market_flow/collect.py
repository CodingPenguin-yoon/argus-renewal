from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .domain import DataMode
from .ports import MarketFlowFactWriter, MarketFlowProvider


@dataclass(frozen=True, slots=True)
class MarketFlowCollectionResult:
    data_mode: DataMode
    fetched_count: int
    inserted_count: int


def collect_market_flow(
    *,
    provider: MarketFlowProvider,
    writer: MarketFlowFactWriter,
    as_of: datetime | None = None,
) -> MarketFlowCollectionResult:
    facts = provider.fetch(as_of=as_of)
    inserted_count = writer.save(facts)
    return MarketFlowCollectionResult(
        data_mode=provider.data_mode,
        fetched_count=len(facts),
        inserted_count=inserted_count,
    )

