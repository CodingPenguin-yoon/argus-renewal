from __future__ import annotations

from src.argus_v2.contracts import DataPoint, DerivativesPressure, MarketReaction, SectorMove, TriggerEvent
from src.argus_v2.judgement import build_market_judgement


def _point(value: float | None, unit: str = "pct") -> DataPoint:
    return DataPoint(
        value=value,
        unit=unit,
        source="test",
        observed_at="2026-05-12T00:00:00Z",
        freshness="fresh" if value is not None else "missing",
    )


def test_judgement_uses_basis_and_open_interest_as_derivatives_evidence() -> None:
    derivatives = DerivativesPressure(
        foreign_futures_net_buy=_point(None, "KRW"),
        institution_futures_net_buy=_point(None, "KRW"),
        individual_futures_net_buy=_point(None, "KRW"),
        basis=_point(-1.2, "pt"),
        put_call_ratio=_point(None, "ratio"),
        open_interest_change_rate=_point(2.0, "pct"),
        kospi200_futures_change_rate=_point(-1.0, "pct"),
        option_pressure="UNKNOWN",
        key_levels=[],
        summary="KOSPI200 선물 약세, negative basis, OI 증가",
        freshness="fresh",
    )
    reaction = MarketReaction(
        kospi_change_rate=_point(-0.7, "pct"),
        kosdaq_change_rate=_point(None, "pct"),
        kospi200_futures_change_rate=_point(-1.0, "pct"),
        advancing_count=_point(None, "count"),
        declining_count=_point(None, "count"),
        spot_foreign_net_buy=_point(None, "KRW"),
        spot_institution_net_buy=_point(None, "KRW"),
        spot_individual_net_buy=_point(None, "KRW"),
        strong_sectors=[],
        weak_sectors=[],
        summary="현물도 약세입니다.",
        freshness="fresh",
    )

    judgement = build_market_judgement(
        derivatives,
        [],
        reaction,
        live_provider_missing=False,
    )

    assert judgement.label == "강한 하방"
    assert judgement.primary_driver == "KOSPI200 선물 basis"
    assert "basis는 -1.20pt" in judgement.summary
    assert "선물 미결제약정 변화율은 2.00%" in judgement.summary


def test_judgement_uses_option_oi_change_side_when_available() -> None:
    derivatives = DerivativesPressure(
        foreign_futures_net_buy=_point(None, "KRW"),
        institution_futures_net_buy=_point(None, "KRW"),
        individual_futures_net_buy=_point(None, "KRW"),
        basis=_point(None, "pt"),
        put_call_ratio=_point(None, "ratio"),
        open_interest_change_rate=_point(6.0, "pct"),
        kospi200_futures_change_rate=_point(0.0, "pct"),
        option_pressure="UNKNOWN",
        key_levels=[],
        summary="옵션 OI 변화는 PUT 우위입니다. 콜 1.00%, 풋 8.00%.",
        freshness="fresh",
    )
    reaction = MarketReaction(
        kospi_change_rate=_point(0.0, "pct"),
        kosdaq_change_rate=_point(None, "pct"),
        kospi200_futures_change_rate=_point(0.0, "pct"),
        advancing_count=_point(None, "count"),
        declining_count=_point(None, "count"),
        spot_foreign_net_buy=_point(None, "KRW"),
        spot_institution_net_buy=_point(None, "KRW"),
        spot_individual_net_buy=_point(None, "KRW"),
        strong_sectors=[],
        weak_sectors=[],
        summary="현물은 보합입니다.",
        freshness="fresh",
    )

    judgement = build_market_judgement(
        derivatives,
        [],
        reaction,
        live_provider_missing=False,
    )

    assert judgement.label == "하방 우위"


def test_judgement_softens_derivatives_downside_when_market_reaction_conflicts() -> None:
    derivatives = DerivativesPressure(
        foreign_futures_net_buy=_point(-1200.0, "KRW"),
        institution_futures_net_buy=_point(None, "KRW"),
        individual_futures_net_buy=_point(None, "KRW"),
        basis=_point(None, "pt"),
        put_call_ratio=_point(None, "ratio"),
        open_interest_change_rate=_point(None, "pct"),
        kospi200_futures_change_rate=_point(-0.8, "pct"),
        option_pressure="UNKNOWN",
        key_levels=[],
        summary="외국인 선물 순매도와 KOSPI200 선물 약세가 우선 신호입니다.",
        freshness="fresh",
    )
    triggers = [
        TriggerEvent(
            id="macro-rate-hike",
            title="밤사이 금리인상",
            summary="미국 금리 상승은 국내 위험자산에 부담입니다.",
            impact="negative",
            source="test",
            published_at="2026-05-12T00:00:00Z",
            connection_strength="strong",
            freshness="fresh",
        ),
        TriggerEvent(
            id="semiconductor-strength",
            title="반도체 강세",
            summary="AI 반도체 흐름이 낙폭을 제한하고 있습니다.",
            impact="positive",
            source="test",
            published_at="2026-05-12T00:01:00Z",
            connection_strength="medium",
            freshness="fresh",
        ),
    ]
    reaction = MarketReaction(
        kospi_change_rate=_point(-0.2, "pct"),
        kosdaq_change_rate=_point(None, "pct"),
        kospi200_futures_change_rate=_point(-0.8, "pct"),
        advancing_count=_point(None, "count"),
        declining_count=_point(None, "count"),
        spot_foreign_net_buy=_point(None, "KRW"),
        spot_institution_net_buy=_point(None, "KRW"),
        spot_individual_net_buy=_point(None, "KRW"),
        strong_sectors=[
            SectorMove(
                name="반도체",
                change_rate=1.4,
                reason="AI 반도체 강세",
                tone="positive",
                source="test",
                observed_at="2026-05-12T00:02:00Z",
            )
        ],
        weak_sectors=[],
        summary="지수는 약하지만 반도체 강세가 낙폭을 제한합니다.",
        freshness="fresh",
    )

    judgement = build_market_judgement(
        derivatives,
        triggers,
        reaction,
        live_provider_missing=False,
    )

    assert judgement.label == "하방 우위"
    assert judgement.primary_driver == "외국인 KOSPI200 선물 순매도"
    assert judgement.confidence == "medium"
    assert "반도체 강세가 지수 낙폭을 제한합니다." in judgement.counter_evidence


def test_judgement_softens_upside_when_weak_sectors_conflict() -> None:
    derivatives = DerivativesPressure(
        foreign_futures_net_buy=_point(900.0, "KRW"),
        institution_futures_net_buy=_point(None, "KRW"),
        individual_futures_net_buy=_point(None, "KRW"),
        basis=_point(0.8, "pt"),
        put_call_ratio=_point(None, "ratio"),
        open_interest_change_rate=_point(None, "pct"),
        kospi200_futures_change_rate=_point(0.7, "pct"),
        option_pressure="UNKNOWN",
        key_levels=[],
        summary="외국인 선물 순매수와 positive basis가 우선 신호입니다.",
        freshness="fresh",
    )
    reaction = MarketReaction(
        kospi_change_rate=_point(0.1, "pct"),
        kosdaq_change_rate=_point(None, "pct"),
        kospi200_futures_change_rate=_point(0.7, "pct"),
        advancing_count=_point(None, "count"),
        declining_count=_point(None, "count"),
        spot_foreign_net_buy=_point(None, "KRW"),
        spot_institution_net_buy=_point(None, "KRW"),
        spot_individual_net_buy=_point(None, "KRW"),
        strong_sectors=[],
        weak_sectors=[
            SectorMove(
                name="증권",
                change_rate=-1.2,
                reason="위험선호 둔화",
                tone="negative",
                source="test",
                observed_at="2026-05-12T00:02:00Z",
            )
        ],
        summary="지수는 버티지만 증권 약세가 상방 확신을 제한합니다.",
        freshness="fresh",
    )

    triggers = [
        TriggerEvent(
            id="risk-off",
            title="위험선호 둔화",
            summary="미국 기술주 약세가 국내 위험자산에 부담입니다.",
            impact="negative",
            source="test",
            published_at="2026-05-12T00:01:00Z",
            connection_strength="medium",
            freshness="fresh",
        )
    ]

    judgement = build_market_judgement(
        derivatives,
        triggers,
        reaction,
        live_provider_missing=False,
    )

    assert judgement.label == "상방 우위"
    assert judgement.confidence == "medium"
    assert "증권 약세가 상방 확신을 제한합니다." in judgement.counter_evidence


def test_judgement_caps_high_confidence_when_reaction_or_triggers_are_missing() -> None:
    derivatives = DerivativesPressure(
        foreign_futures_net_buy=_point(-1500.0, "KRW"),
        institution_futures_net_buy=_point(None, "KRW"),
        individual_futures_net_buy=_point(None, "KRW"),
        basis=_point(-1.1, "pt"),
        put_call_ratio=_point(None, "ratio"),
        open_interest_change_rate=_point(2.2, "pct"),
        kospi200_futures_change_rate=_point(-1.2, "pct"),
        option_pressure="PUT",
        key_levels=[],
        summary="외국인 선물 순매도, PUT 우위, negative basis가 동시에 확인됩니다.",
        freshness="fresh",
    )
    reaction = MarketReaction(
        kospi_change_rate=_point(None, "pct"),
        kosdaq_change_rate=_point(None, "pct"),
        kospi200_futures_change_rate=_point(None, "pct"),
        advancing_count=_point(None, "count"),
        declining_count=_point(None, "count"),
        spot_foreign_net_buy=_point(None, "KRW"),
        spot_institution_net_buy=_point(None, "KRW"),
        spot_individual_net_buy=_point(None, "KRW"),
        strong_sectors=[],
        weak_sectors=[],
        summary="현물 반응은 아직 미수신입니다.",
        freshness="missing",
    )

    judgement = build_market_judgement(
        derivatives,
        [],
        reaction,
        live_provider_missing=False,
    )

    assert judgement.label == "강한 하방"
    assert judgement.confidence == "medium"
    assert judgement.data_reliability == "partial"
    assert "현물 반응 또는 뉴스 트리거가 아직 충분히 연결되지 않아 결론 확신도를 제한합니다." in judgement.counter_evidence


def test_judgement_marks_live_provider_missing_as_low_confidence() -> None:
    derivatives = DerivativesPressure(
        foreign_futures_net_buy=_point(-1500.0, "KRW"),
        institution_futures_net_buy=_point(None, "KRW"),
        individual_futures_net_buy=_point(None, "KRW"),
        basis=_point(-1.1, "pt"),
        put_call_ratio=_point(None, "ratio"),
        open_interest_change_rate=_point(2.2, "pct"),
        kospi200_futures_change_rate=_point(-1.2, "pct"),
        option_pressure="PUT",
        key_levels=[],
        summary="mock 파생 데이터만 있습니다.",
        freshness="partial",
    )
    reaction = MarketReaction(
        kospi_change_rate=_point(-0.8, "pct"),
        kosdaq_change_rate=_point(None, "pct"),
        kospi200_futures_change_rate=_point(-1.2, "pct"),
        advancing_count=_point(None, "count"),
        declining_count=_point(None, "count"),
        spot_foreign_net_buy=_point(None, "KRW"),
        spot_institution_net_buy=_point(None, "KRW"),
        spot_individual_net_buy=_point(None, "KRW"),
        strong_sectors=[],
        weak_sectors=[],
        summary="현물도 약세입니다.",
        freshness="fresh",
    )
    triggers = [
        TriggerEvent(
            id="rates",
            title="금리 상승",
            summary="금리 상승은 위험자산에 부담입니다.",
            impact="negative",
            source="test",
            published_at="2026-05-12T00:01:00Z",
            connection_strength="strong",
            freshness="fresh",
        )
    ]

    judgement = build_market_judgement(
        derivatives,
        triggers,
        reaction,
        live_provider_missing=True,
    )

    assert judgement.confidence == "low"
    assert judgement.data_reliability == "partial"
