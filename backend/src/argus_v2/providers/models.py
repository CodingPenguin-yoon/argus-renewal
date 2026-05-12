from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MarketIntradaySnapshotRecord:
    source_name: str
    trade_date: str
    snapshot_time: str
    session_type: str
    instrument_code: str
    instrument_name: str | None = None
    price: float | None = None
    price_change: float | None = None
    change_rate: float | None = None
    volume: float | None = None
    open_interest: float | None = None
    put_call_ratio: float | None = None
    implied_volatility: float | None = None
    additional_metrics: dict[str, Any] = field(default_factory=dict)
    source_url: str | None = None
    source_record_id: str | None = None
    raw_payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class DerivativesOptionChainLevelRecord:
    strike_price: float
    moneyness: str = "UNKNOWN"
    call_last_price: float | None = None
    call_change_rate: float | None = None
    call_volume: float | None = None
    call_open_interest: float | None = None
    call_open_interest_change: float | None = None
    call_implied_volatility: float | None = None
    put_last_price: float | None = None
    put_change_rate: float | None = None
    put_volume: float | None = None
    put_open_interest: float | None = None
    put_open_interest_change: float | None = None
    put_implied_volatility: float | None = None
    total_open_interest: float | None = None
    net_call_put_oi: float | None = None
    call_put_oi_ratio: float | None = None
    pressure_side: str = "UNKNOWN"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DerivativesOptionChainSnapshotRecord:
    source_name: str
    trade_date: str
    snapshot_time: str
    expiry_date: str
    market_scope: str = "KRX"
    underlying_code: str = "KOSPI200"
    underlying_name: str | None = "KOSPI200"
    underlying_price: float | None = None
    contract_month: str | None = None
    source_url: str | None = None
    source_record_id: str | None = None
    atm_strike: float | None = None
    expected_level_count: int | None = None
    observed_level_count: int = 0
    freshness_state: str = "missing"
    raw_payload: Any = None
    levels: list[DerivativesOptionChainLevelRecord] = field(default_factory=list)


@dataclass(frozen=True)
class DerivativesSourceStatusRecord:
    trade_date: str
    source_name: str
    source_scope: str
    status: str
    expected_count: int | None = None
    observed_count: int | None = None
    latest_observed_at: str | None = None
    stale_after_seconds: int | None = None
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketReactionSectorRecord:
    name: str
    change_rate: float | None
    reason: str
    tone: str
    source: str
    observed_at: str | None = None


@dataclass(frozen=True)
class MarketReactionSnapshotRecord:
    source_name: str
    trade_date: str
    snapshot_time: str
    kospi_change_rate: float | None = None
    kosdaq_change_rate: float | None = None
    kospi200_futures_change_rate: float | None = None
    advancing_count: int | None = None
    declining_count: int | None = None
    spot_foreign_net_buy: float | None = None
    spot_institution_net_buy: float | None = None
    spot_individual_net_buy: float | None = None
    summary: str = ""
    freshness_state: str = "partial"
    source_url: str | None = None
    source_record_id: str | None = None
    raw_payload: Any = None
    strong_sectors: list[MarketReactionSectorRecord] = field(default_factory=list)
    weak_sectors: list[MarketReactionSectorRecord] = field(default_factory=list)


@dataclass(frozen=True)
class NewsTriggerRecord:
    id: str
    title: str
    summary: str
    impact: str
    source: str
    published_at: str | None
    connection_strength: str
    freshness: str = "partial"
    source_url: str | None = None
    raw_payload: Any = None


@dataclass(frozen=True)
class BriefingProviderBatch:
    records: list[Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    disabled_reason: str | None = None
    retry_count: int = 0
