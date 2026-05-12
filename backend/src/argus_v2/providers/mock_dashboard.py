from __future__ import annotations

from datetime import datetime, timezone

from ..contracts import (
    DataPoint,
    DerivativesPressure,
    MarketReaction,
    OptionKeyLevel,
    ProviderHealth,
    SectorMove,
    TriggerEvent,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _point(value: float | int | str | None, unit: str, source: str, observed_at: str) -> DataPoint:
    return DataPoint(value=value, unit=unit, source=source, observed_at=observed_at, freshness="partial")


def build_mock_dashboard_inputs(
    *,
    kis_app_key_set: bool = False,
    kis_app_secret_set: bool = False,
) -> tuple[DerivativesPressure, list[TriggerEvent], MarketReaction, list[ProviderHealth]]:
    observed_at = _now_iso()
    derivatives = DerivativesPressure(
        foreign_futures_net_buy=_point(-180_000_000_000, "KRW", "mock.kis.derivatives", observed_at),
        institution_futures_net_buy=_point(62_000_000_000, "KRW", "mock.kis.derivatives", observed_at),
        individual_futures_net_buy=_point(118_000_000_000, "KRW", "mock.kis.derivatives", observed_at),
        basis=_point(-0.42, "pt", "mock.kis.derivatives", observed_at),
        put_call_ratio=_point(1.08, "ratio", "mock.option_chain", observed_at),
        open_interest_change_rate=_point(1.7, "pct", "mock.option_chain", observed_at),
        kospi200_futures_change_rate=_point(-0.34, "pct", "mock.kis.derivatives", observed_at),
        option_pressure="PUT",
        key_levels=[
            OptionKeyLevel(
                role="put_wall",
                label="하단 풋 OI 집중",
                side="PUT",
                strike_price=365.0,
                summary="365pt 부근 풋 미결제약정이 방어/이탈 확인 레벨입니다.",
                source="mock.option_chain",
                observed_at=observed_at,
                freshness="partial",
            ),
            OptionKeyLevel(
                role="call_wall",
                label="상단 콜 OI 집중",
                side="CALL",
                strike_price=377.5,
                summary="377.5pt 위에서는 콜 매도 압력 확인이 필요합니다.",
                source="mock.option_chain",
                observed_at=observed_at,
                freshness="partial",
            ),
        ],
        summary="외국인 KOSPI200 선물 매도와 풋 우위 옵션 압력이 먼저 확인됩니다.",
        freshness="partial",
    )
    triggers = [
        TriggerEvent(
            id="mock-rates",
            title="미국 금리 상승 경계",
            summary="밤사이 금리 상승은 위험자산과 원화에는 부담으로 해석됩니다.",
            impact="negative",
            source="mock.news.macro",
            published_at=observed_at,
            connection_strength="medium",
            freshness="partial",
        ),
        TriggerEvent(
            id="mock-chip",
            title="반도체 상대 강세",
            summary="지수 영향도가 큰 반도체가 하락 압력을 일부 상쇄합니다.",
            impact="positive",
            source="mock.news.sector",
            published_at=observed_at,
            connection_strength="medium",
            freshness="partial",
        ),
    ]
    reaction = MarketReaction(
        kospi_change_rate=_point(-0.18, "pct", "mock.market.reaction", observed_at),
        kosdaq_change_rate=_point(0.12, "pct", "mock.market.reaction", observed_at),
        kospi200_futures_change_rate=_point(-0.34, "pct", "mock.market.reaction", observed_at),
        advancing_count=_point(432, "count", "mock.market.reaction", observed_at),
        declining_count=_point(511, "count", "mock.market.reaction", observed_at),
        spot_foreign_net_buy=_point(-82_000_000_000, "KRW", "mock.market.reaction", observed_at),
        spot_institution_net_buy=_point(34_000_000_000, "KRW", "mock.market.reaction", observed_at),
        spot_individual_net_buy=_point(48_000_000_000, "KRW", "mock.market.reaction", observed_at),
        strong_sectors=[
            SectorMove(
                name="반도체",
                change_rate=1.15,
                reason="미국 AI/반도체 모멘텀 반영",
                tone="positive",
                source="mock.market.reaction",
                observed_at=observed_at,
            )
        ],
        weak_sectors=[
            SectorMove(
                name="금융",
                change_rate=-0.62,
                reason="금리 변동성 확대 구간",
                tone="negative",
                source="mock.market.reaction",
                observed_at=observed_at,
            )
        ],
        summary="지수는 약하지만 반도체가 버티며 하방 압력을 제한합니다.",
        freshness="partial",
    )
    missing_kis_fields = []
    if not kis_app_key_set:
        missing_kis_fields.append("KIS_APP_KEY")
    if not kis_app_secret_set:
        missing_kis_fields.append("KIS_APP_SECRET")

    health = [
        ProviderHealth(
            key="kis_derivatives",
            label="KIS 파생 실데이터",
            status="missing",
            observed_count=0,
            missing_fields=missing_kis_fields,
            error="실데이터 smoke test 전입니다. access token은 app key/secret으로 자동 발급합니다.",
        ),
        ProviderHealth(
            key="mock_dashboard",
            label="Argus v2 mock contract",
            status="partial",
            last_success_at=observed_at,
            observed_count=1,
        ),
    ]
    return derivatives, triggers, reaction, health
