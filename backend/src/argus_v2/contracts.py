from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


FreshnessStatus = Literal["fresh", "partial", "stale", "missing"]
DirectionTone = Literal["positive", "neutral", "negative"]
OptionPressureSide = Literal["CALL", "PUT", "NEUTRAL", "UNKNOWN"]
OptionQuotePressureSide = Literal["CALL", "PUT", "BALANCED", "UNKNOWN"]
ConnectionStrength = Literal["strong", "medium", "weak", "unclear"]
MarketJudgementLabel = Literal["강한 상방", "상방 우위", "중립", "하방 우위", "강한 하방"]
ConfidenceLevel = Literal["low", "medium", "high"]
SessionPhase = Literal["pre_open", "live", "post_close"]


class DataPoint(BaseModel):
    value: Optional[Union[float, int, str]]
    unit: str
    source: str
    observed_at: Optional[str]
    freshness: FreshnessStatus


class ProviderHealth(BaseModel):
    key: str
    label: str
    status: FreshnessStatus
    state: Optional[str] = None
    last_success_at: Optional[str] = None
    next_scheduled_run: Optional[str] = None
    observed_count: int = 0
    missing_fields: list[str] = Field(default_factory=list)
    error: Optional[str] = None


class OptionKeyLevel(BaseModel):
    role: Literal["atm", "call_wall", "put_wall", "pressure"]
    label: str
    side: OptionPressureSide
    strike_price: Optional[float]
    summary: str
    source: str
    observed_at: Optional[str]
    freshness: FreshnessStatus


class OptionOpenInterestChange(BaseModel):
    freshness: FreshnessStatus = "missing"
    call_change_rate: Optional[float] = None
    put_change_rate: Optional[float] = None
    net_change_rate: Optional[float] = None
    total_change_rate: Optional[float] = None
    dominant_side: OptionPressureSide = "UNKNOWN"
    source: str = "argus_v2.option_chain_comparison"
    observed_at: Optional[str] = None


class OptionQuoteRow(BaseModel):
    strike_price: float
    moneyness: str = "UNKNOWN"
    call_last_price: Optional[float] = None
    call_change_rate: Optional[float] = None
    call_volume: Optional[float] = None
    call_trading_value: Optional[float] = None
    call_open_interest: Optional[float] = None
    call_open_interest_change: Optional[float] = None
    call_implied_volatility: Optional[float] = None
    put_last_price: Optional[float] = None
    put_change_rate: Optional[float] = None
    put_volume: Optional[float] = None
    put_trading_value: Optional[float] = None
    put_open_interest: Optional[float] = None
    put_open_interest_change: Optional[float] = None
    put_implied_volatility: Optional[float] = None
    total_open_interest: Optional[float] = None
    net_call_put_oi: Optional[float] = None
    call_put_oi_ratio: Optional[float] = None
    pressure_side: OptionQuotePressureSide = "UNKNOWN"


class OptionQuotesResponse(BaseModel):
    as_of: Optional[str]
    trade_date: Optional[str]
    source: str
    status: FreshnessStatus
    observed_count: int
    underlying_code: Optional[str] = None
    underlying_name: Optional[str] = None
    underlying_price: Optional[float] = None
    expiry_date: Optional[str] = None
    contract_month: Optional[str] = None
    atm_strike: Optional[float] = None
    rows: list[OptionQuoteRow] = Field(default_factory=list)


class FuturesQuoteResponse(BaseModel):
    as_of: Optional[str]
    trade_date: Optional[str]
    source: str
    status: FreshnessStatus
    observed_count: int
    session_type: Optional[str] = None
    instrument_code: Optional[str] = None
    instrument_name: Optional[str] = None
    price: Optional[float] = None
    price_change: Optional[float] = None
    change_rate: Optional[float] = None
    volume: Optional[float] = None
    open_interest: Optional[float] = None
    put_call_ratio: Optional[float] = None
    implied_volatility: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    basis: Optional[float] = None
    market_basis: Optional[float] = None
    theoretical_price: Optional[float] = None
    disparity_rate: Optional[float] = None
    open_interest_change: Optional[float] = None
    open_interest_change_rate: Optional[float] = None


class DerivativesPressure(BaseModel):
    foreign_futures_net_buy: DataPoint
    institution_futures_net_buy: DataPoint
    individual_futures_net_buy: DataPoint
    basis: DataPoint
    put_call_ratio: DataPoint
    open_interest_change_rate: DataPoint
    kospi200_futures_change_rate: DataPoint
    option_pressure: OptionPressureSide
    option_open_interest_change: OptionOpenInterestChange = Field(default_factory=OptionOpenInterestChange)
    key_levels: list[OptionKeyLevel]
    summary: str
    freshness: FreshnessStatus


class TriggerEvent(BaseModel):
    id: str
    title: str
    summary: str
    impact: DirectionTone
    source: str
    published_at: Optional[str]
    connection_strength: ConnectionStrength
    ai_reason: Optional[str] = None
    ai_confidence: Optional[ConfidenceLevel] = None
    affected_factors: list[str] = Field(default_factory=list)
    freshness: FreshnessStatus


class NewsFeedItem(BaseModel):
    id: str
    title: str
    summary: str
    source: str
    published_at: Optional[str]
    source_url: Optional[str] = None
    freshness: FreshnessStatus


class NewsFeedResponse(BaseModel):
    as_of: str
    provider: str
    status: FreshnessStatus
    observed_count: int
    error: Optional[str] = None
    items: list[NewsFeedItem]


class SectorMove(BaseModel):
    name: str
    change_rate: Optional[float]
    reason: str
    tone: DirectionTone
    source: str
    observed_at: Optional[str]


class MarketReaction(BaseModel):
    kospi_change_rate: DataPoint
    kosdaq_change_rate: DataPoint
    kospi200_futures_change_rate: DataPoint
    advancing_count: DataPoint
    declining_count: DataPoint
    spot_foreign_net_buy: DataPoint
    spot_institution_net_buy: DataPoint
    spot_individual_net_buy: DataPoint
    strong_sectors: list[SectorMove]
    weak_sectors: list[SectorMove]
    summary: str
    freshness: FreshnessStatus


class MarketJudgement(BaseModel):
    label: MarketJudgementLabel
    summary: str
    primary_driver: str
    confidence: ConfidenceLevel
    data_reliability: FreshnessStatus
    reasons: list[str]
    counter_evidence: list[str]
    transition_condition: str
    watch_points: list[str]
    source: Literal["rule_based"]


class MarketDashboard(BaseModel):
    as_of: str
    session_phase: SessionPhase
    derivatives: DerivativesPressure
    triggers: list[TriggerEvent]
    reaction: MarketReaction
    judgement: MarketJudgement
    provider_health: list[ProviderHealth]
