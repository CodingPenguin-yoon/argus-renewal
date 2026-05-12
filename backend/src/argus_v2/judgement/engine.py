from __future__ import annotations

from ..contracts import DerivativesPressure, MarketJudgement, MarketReaction, TriggerEvent


SPOT_FLOW_SIGNAL_THRESHOLD = 1_000_000_000


def _number(value: float | int | str | None) -> float | None:
    return float(value) if isinstance(value, (float, int)) else None


def _data_limited(
    *,
    live_provider_missing: bool,
    derivatives: DerivativesPressure,
    reaction: MarketReaction,
    triggers: list[TriggerEvent],
) -> bool:
    limited_states = {"missing", "partial", "stale"}
    return (
        live_provider_missing
        or derivatives.freshness in limited_states
        or reaction.freshness in limited_states
        or not triggers
    )


def _confidence(*, score: int, live_provider_missing: bool, data_limited: bool) -> str:
    if live_provider_missing:
        return "low"
    if abs(score) >= 3:
        base = "high"
    elif abs(score) >= 1:
        base = "medium"
    else:
        base = "low"
    if not data_limited or base == "low":
        return base
    return "medium" if base == "high" else "low"


def _reliability(
    *,
    live_provider_missing: bool,
    derivatives: DerivativesPressure,
    reaction: MarketReaction,
    triggers: list[TriggerEvent],
) -> str:
    if live_provider_missing or "missing" in {derivatives.freshness, reaction.freshness}:
        return "partial"
    if "stale" in {derivatives.freshness, reaction.freshness}:
        return "stale"
    if not triggers or "partial" in {derivatives.freshness, reaction.freshness}:
        return "partial"
    return "fresh"


def build_market_judgement(
    derivatives: DerivativesPressure,
    triggers: list[TriggerEvent],
    reaction: MarketReaction,
    *,
    live_provider_missing: bool,
) -> MarketJudgement:
    foreign_flow = _number(derivatives.foreign_futures_net_buy.value)
    spot_foreign_flow = _number(reaction.spot_foreign_net_buy.value)
    futures_change = _number(derivatives.kospi200_futures_change_rate.value)
    basis = _number(derivatives.basis.value)
    open_interest_change = _number(derivatives.open_interest_change_rate.value)
    option_oi_change_side = (
        derivatives.option_open_interest_change.dominant_side
        if derivatives.option_open_interest_change.freshness == "fresh"
        else "UNKNOWN"
    )
    kospi_change = _number(reaction.kospi_change_rate.value)
    negative_triggers = [item for item in triggers if item.impact == "negative"]
    positive_triggers = [item for item in triggers if item.impact == "positive"]
    strong_sector = reaction.strong_sectors[0].name if reaction.strong_sectors else None
    weak_sector = reaction.weak_sectors[0].name if reaction.weak_sectors else None

    score = 0
    if foreign_flow is not None:
        score += 2 if foreign_flow > 0 else -2 if foreign_flow < 0 else 0
    elif spot_foreign_flow is not None:
        score += _spot_flow_score(spot_foreign_flow)
    if derivatives.option_pressure == "CALL":
        score += 1
    elif derivatives.option_pressure == "PUT":
        score -= 1
    if futures_change is not None:
        score += 1 if futures_change > 0.3 else -1 if futures_change < -0.3 else 0
    if basis is not None:
        score += 1 if basis > 0.5 else -1 if basis < -0.5 else 0
    if futures_change is not None and open_interest_change is not None and open_interest_change > 0.5:
        score += 1 if futures_change > 0.3 else -1 if futures_change < -0.3 else 0
    if open_interest_change is not None and open_interest_change > 0.5:
        if option_oi_change_side == "CALL":
            score += 1
        elif option_oi_change_side == "PUT":
            score -= 1
    if kospi_change is not None:
        score += 1 if kospi_change > 0.5 else -1 if kospi_change < -0.5 else 0
    score += len(positive_triggers) - len(negative_triggers)
    if score < 0 and strong_sector:
        score += 1
    if score > 0 and weak_sector:
        score -= 1

    if score >= 3:
        label = "강한 상방"
    elif score >= 1:
        label = "상방 우위"
    elif score <= -3:
        label = "강한 하방"
    elif score <= -1:
        label = "하방 우위"
    else:
        label = "중립"

    data_limited = _data_limited(
        live_provider_missing=live_provider_missing,
        derivatives=derivatives,
        reaction=reaction,
        triggers=triggers,
    )
    confidence = _confidence(score=score, live_provider_missing=live_provider_missing, data_limited=data_limited)

    primary_driver = _primary_driver(
        foreign_flow=foreign_flow,
        spot_foreign_flow=spot_foreign_flow,
        option_pressure=derivatives.option_pressure,
        futures_change=futures_change,
        basis=basis,
    )
    reasons = [derivatives.summary]
    if negative_triggers:
        reasons.append(f"{negative_triggers[0].title}: {negative_triggers[0].summary}")
    if positive_triggers:
        reasons.append(f"{positive_triggers[0].title}: {positive_triggers[0].summary}")
    reasons.append(reaction.summary)

    counter_evidence = []
    if strong_sector:
        counter_evidence.append(f"{strong_sector} 강세가 지수 낙폭을 제한합니다.")
    if weak_sector:
        counter_evidence.append(f"{weak_sector} 약세가 상방 확신을 제한합니다.")
    if positive_triggers:
        counter_evidence.append(f"{positive_triggers[0].title} 신호는 하방 압력을 일부 상쇄합니다.")
    if _flows_conflict(foreign_flow=foreign_flow, spot_foreign_flow=spot_foreign_flow):
        counter_evidence.append("외국인 현물 수급은 선물 수급과 반대로 움직입니다.")
    if futures_change is not None and open_interest_change is not None and open_interest_change < -0.5:
        counter_evidence.append("선물 미결제약정 감소는 현재 방향의 추세 확신도를 낮춥니다.")
    if reaction.freshness in {"missing", "partial", "stale"} or not triggers:
        counter_evidence.append("현물 반응 또는 뉴스 트리거가 아직 충분히 연결되지 않아 결론 확신도를 제한합니다.")

    return MarketJudgement(
        label=label,
        summary=_summary(
            label=label,
            foreign_flow=foreign_flow,
            spot_foreign_flow=spot_foreign_flow,
            option_pressure=derivatives.option_pressure,
            futures_change=futures_change,
            basis=basis,
            open_interest_change=open_interest_change,
            data_limited=data_limited,
        ),
        primary_driver=primary_driver,
        confidence=confidence,
        data_reliability=_reliability(
            live_provider_missing=live_provider_missing,
            derivatives=derivatives,
            reaction=reaction,
            triggers=triggers,
        ),
        reasons=reasons[:3],
        counter_evidence=counter_evidence[:2],
        transition_condition=_transition_condition(label),
        watch_points=_watch_points(derivatives),
        source="rule_based",
    )


def _primary_driver(
    *,
    foreign_flow: float | None,
    spot_foreign_flow: float | None,
    option_pressure: str,
    futures_change: float | None,
    basis: float | None,
) -> str:
    if foreign_flow is not None:
        if foreign_flow > 0:
            return "외국인 KOSPI200 선물 순매수"
        if foreign_flow < 0:
            return "외국인 KOSPI200 선물 순매도"
    if option_pressure in {"CALL", "PUT"}:
        return f"옵션 미결제약정 {option_pressure} 우위"
    if basis is not None and abs(basis) > 0.5:
        return "KOSPI200 선물 basis"
    if spot_foreign_flow is not None and abs(spot_foreign_flow) >= SPOT_FLOW_SIGNAL_THRESHOLD:
        if spot_foreign_flow > 0:
            return "외국인 현물 순매수"
        if spot_foreign_flow < 0:
            return "외국인 현물 순매도"
    if futures_change is not None:
        return "KOSPI200 선물 변동률"
    return "데이터 수신 상태"


def _summary(
    *,
    label: str,
    foreign_flow: float | None,
    spot_foreign_flow: float | None,
    option_pressure: str,
    futures_change: float | None,
    basis: float | None,
    open_interest_change: float | None,
    data_limited: bool,
) -> str:
    parts = []
    if foreign_flow is not None:
        direction = "순매수" if foreign_flow > 0 else "순매도" if foreign_flow < 0 else "중립"
        parts.append(f"외국인 KOSPI200 선물은 {direction}입니다.")
    elif spot_foreign_flow is not None and abs(spot_foreign_flow) >= SPOT_FLOW_SIGNAL_THRESHOLD:
        direction = "순매수" if spot_foreign_flow > 0 else "순매도" if spot_foreign_flow < 0 else "중립"
        parts.append(f"외국인 현물은 {direction}입니다.")
    if option_pressure in {"CALL", "PUT", "NEUTRAL"}:
        parts.append(f"옵션 미결제약정은 {option_pressure} 우위입니다.")
    if futures_change is not None:
        parts.append(f"KOSPI200 선물 변동률은 {futures_change:.2f}%입니다.")
    if basis is not None:
        parts.append(f"basis는 {basis:.2f}pt입니다.")
    if open_interest_change is not None:
        parts.append(f"선물 미결제약정 변화율은 {open_interest_change:.2f}%입니다.")
    if not parts:
        parts.append("핵심 파생 데이터가 아직 충분하지 않아 중립으로 봅니다.")
    parts.append(f"현재 종합 판단은 {label}입니다.")
    if data_limited:
        parts.append("다만 미연결 데이터가 있어 결론은 보수적으로 해석해야 합니다.")
    return " ".join(parts)


def _transition_condition(label: str) -> str:
    if "하방" in label:
        return "옵션 PUT 우위가 완화되거나 KOSPI200 선물이 주요 압력 레벨 위로 회복하면 중립 쪽으로 낮춥니다."
    if "상방" in label:
        return "옵션 CALL 우위가 약해지거나 KOSPI200 선물이 주요 압력 레벨 아래로 밀리면 중립 쪽으로 낮춥니다."
    return "옵션 압력과 KOSPI200 선물 변동률이 같은 방향으로 누적되면 방향성 판단을 높입니다."


def _watch_points(derivatives: DerivativesPressure) -> list[str]:
    points = ["KOSPI200 선물 변동률 유지 여부", "basis 0pt 회귀 여부", "선물 미결제약정 증감"]
    for level in derivatives.key_levels[:2]:
        if level.strike_price is not None:
            points.append(f"{level.strike_price:g}pt {level.label}")
    return points[:4]


def _spot_flow_score(value: float) -> int:
    if value >= SPOT_FLOW_SIGNAL_THRESHOLD:
        return 1
    if value <= -SPOT_FLOW_SIGNAL_THRESHOLD:
        return -1
    return 0


def _flows_conflict(*, foreign_flow: float | None, spot_foreign_flow: float | None) -> bool:
    if foreign_flow is None or spot_foreign_flow is None:
        return False
    if abs(spot_foreign_flow) < SPOT_FLOW_SIGNAL_THRESHOLD:
        return False
    return (foreign_flow > 0 and spot_foreign_flow < 0) or (foreign_flow < 0 and spot_foreign_flow > 0)
