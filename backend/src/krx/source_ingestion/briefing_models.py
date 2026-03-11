from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class MarketDailyFactorRecord:
    source_name: str
    trade_date: str
    market_scope: str = "KRX"
    investor_individual_net_buy: float | None = None
    investor_foreign_net_buy: float | None = None
    investor_institution_net_buy: float | None = None
    investor_other_net_buy: float | None = None
    investor_bank_net_buy: float | None = None
    investor_pension_net_buy: float | None = None
    program_buy_total: float | None = None
    program_sell_total: float | None = None
    program_net_total: float | None = None
    credit_balance_total: float | None = None
    margin_loan_balance: float | None = None
    stock_financing_balance: float | None = None
    securities_lending_balance: float | None = None
    additional_metrics: dict[str, Any] = field(default_factory=dict)
    source_url: str | None = None
    source_record_id: str | None = None
    raw_payload: dict[str, Any] | None = None


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
class DerivativesDailyMetricRecord:
    source_name: str
    trade_date: str
    metric_scope: str = "KRX_DERIVATIVES"
    put_call_ratio: float | None = None
    implied_volatility: float | None = None
    open_interest_total: float | None = None
    call_open_interest: float | None = None
    put_open_interest: float | None = None
    futures_investor_foreign_net_buy: float | None = None
    futures_investor_institution_net_buy: float | None = None
    futures_investor_individual_net_buy: float | None = None
    options_investor_foreign_net_buy: float | None = None
    options_investor_institution_net_buy: float | None = None
    options_investor_individual_net_buy: float | None = None
    futures_volume_total: float | None = None
    options_volume_total: float | None = None
    additional_metrics: dict[str, Any] = field(default_factory=dict)
    source_url: str | None = None
    source_record_id: str | None = None
    raw_payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class BriefingProviderBatch:
    records: list[Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    disabled_reason: str | None = None
    retry_count: int = 0


@dataclass(frozen=True)
class BriefingInputRunResult:
    run_id: int
    status: str
    job_name: str
    mode: str
    trade_date: str | None
    start_date: str | None
    end_date: str | None
    processed_provider_count: int
    success_provider_count: int
    failed_provider_count: int
    skipped_provider_count: int
    inserted_count: int
    updated_count: int
    provider_results: list[dict[str, Any]]
    error_message: str | None = None


class GlobalInputProvider(Protocol):
    def fetch_pre_open_inputs(
        self,
        *,
        trade_date: date,
        snapshot_at: datetime,
    ) -> BriefingProviderBatch:
        ...
