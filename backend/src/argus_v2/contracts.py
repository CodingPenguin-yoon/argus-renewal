from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


FreshnessStatus = Literal["fresh", "partial", "stale", "missing"]
DirectionTone = Literal["positive", "neutral", "negative"]
OptionPressureSide = Literal["CALL", "PUT", "NEUTRAL", "UNKNOWN"]
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
    last_success_at: Optional[str] = None
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
