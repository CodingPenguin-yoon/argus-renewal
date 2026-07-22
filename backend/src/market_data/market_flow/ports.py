from __future__ import annotations

from datetime import datetime
from typing import Protocol, Sequence

from .domain import DataMode, MarketFlowFact


class MarketFlowProvider(Protocol):
    data_mode: DataMode

    def fetch(self, *, as_of: datetime | None = None) -> Sequence[MarketFlowFact]: ...


class MarketFlowFactWriter(Protocol):
    def save(self, facts: Sequence[MarketFlowFact]) -> int: ...


class MarketFlowFactReader(Protocol):
    def list_latest(self, *, data_mode: DataMode) -> Sequence[MarketFlowFact]: ...

