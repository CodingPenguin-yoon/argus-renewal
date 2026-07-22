from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from zoneinfo import ZoneInfo

from ..domain import (
    DataMode,
    DataQuality,
    FlowUnit,
    MarketFlowFact,
    MarketScope,
    MarketSegment,
)


KST = ZoneInfo("Asia/Seoul")


class FixtureScenario(str, Enum):
    NORMAL = "normal"
    PARTIAL = "partial"
    EMPTY = "empty"
    STALE = "stale"
    ERROR = "error"


class FixtureProviderError(RuntimeError):
    pass


ESTIMATE_VALUES: dict[MarketSegment, tuple[int, int, int]] = {
    MarketSegment.KOSPI_SPOT: (-240_000_000_000, 150_000_000_000, 90_000_000_000),
    MarketSegment.KOSPI200_FUTURES: (85_000_000_000, -130_000_000_000, 45_000_000_000),
    MarketSegment.KOSPI200_CALL: (-12_000_000_000, 25_000_000_000, -13_000_000_000),
    MarketSegment.KOSPI200_PUT: (18_000_000_000, -30_000_000_000, 12_000_000_000),
}

CONFIRMED_VALUES: dict[MarketSegment, tuple[int, int, int]] = {
    MarketSegment.KOSPI_SPOT: (-228_000_000_000, 143_000_000_000, 85_000_000_000),
    MarketSegment.KOSPI200_FUTURES: (81_000_000_000, -125_000_000_000, 44_000_000_000),
    MarketSegment.KOSPI200_CALL: (-10_000_000_000, 23_000_000_000, -13_000_000_000),
    MarketSegment.KOSPI200_PUT: (17_000_000_000, -28_000_000_000, 11_000_000_000),
}


def _previous_business_date(value: date) -> date:
    candidate = value - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


class FixtureMarketFlowAdapter:
    data_mode = DataMode.MOCK

    def __init__(self, *, scenario: FixtureScenario = FixtureScenario.NORMAL) -> None:
        self.scenario = scenario

    def fetch(self, *, as_of: datetime | None = None) -> list[MarketFlowFact]:
        if self.scenario is FixtureScenario.ERROR:
            raise FixtureProviderError("fixture_market_flow_provider_error")
        if self.scenario is FixtureScenario.EMPTY:
            return []

        current = as_of or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        current_kst = current.astimezone(KST).replace(second=0, microsecond=0)
        estimate_observed_at = current_kst
        collected_at = current_kst
        if self.scenario is FixtureScenario.STALE:
            estimate_observed_at -= timedelta(minutes=30)
            collected_at = estimate_observed_at

        confirmed_date = _previous_business_date(current_kst.date())
        confirmed_observed_at = datetime.combine(confirmed_date, time(15, 30), tzinfo=KST)
        segments = list(MarketSegment)
        if self.scenario is FixtureScenario.PARTIAL:
            segments = [MarketSegment.KOSPI_SPOT, MarketSegment.KOSPI200_FUTURES]

        facts: list[MarketFlowFact] = []
        for segment in segments:
            facts.append(
                self._build_fact(
                    source="FIXTURE_BROKER",
                    segment=segment,
                    quality=DataQuality.ESTIMATE,
                    observed_at=estimate_observed_at,
                    collected_at=collected_at,
                    values=ESTIMATE_VALUES[segment],
                )
            )
            facts.append(
                self._build_fact(
                    source="FIXTURE_KRX",
                    segment=segment,
                    quality=DataQuality.CONFIRMED,
                    observed_at=confirmed_observed_at,
                    collected_at=current_kst,
                    values=CONFIRMED_VALUES[segment],
                )
            )
        return facts

    @staticmethod
    def _build_fact(
        *,
        source: str,
        segment: MarketSegment,
        quality: DataQuality,
        observed_at: datetime,
        collected_at: datetime,
        values: tuple[int, int, int],
    ) -> MarketFlowFact:
        individual_net, foreign_net, institution_net = values
        record_time = observed_at.isoformat(timespec="minutes")
        return MarketFlowFact(
            source=source,
            source_record_id=f"{source}:{segment.value}:{quality.value}:{record_time}",
            data_mode=DataMode.MOCK,
            market_scope=MarketScope.KRX,
            segment=segment,
            quality=quality,
            trade_date=observed_at.date(),
            observed_at=observed_at,
            collected_at=collected_at,
            unit=FlowUnit.KRW,
            individual_net=individual_net,
            foreign_net=foreign_net,
            institution_net=institution_net,
        )

