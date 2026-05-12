from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from .contracts import (
    DataPoint,
    DerivativesPressure,
    MarketDashboard,
    MarketReaction,
    OptionOpenInterestChange,
    OptionKeyLevel,
    OptionPressureSide,
    ProviderHealth,
    SectorMove,
    TriggerEvent,
)
from .judgement import build_market_judgement
from .storage import ArgusV2Storage


KIS_SOURCE = "KIS_DOMESTIC_DERIVATIVES"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_dashboard_from_storage(storage: ArgusV2Storage) -> MarketDashboard | None:
    latest_derivatives = storage.get_latest_derivatives_snapshot()
    latest_option_chain = storage.get_latest_option_chain_snapshot()
    previous_option_chain = (
        storage.get_previous_option_chain_snapshot(latest_snapshot=latest_option_chain)
        if latest_option_chain is not None
        else None
    )
    latest_reaction = storage.get_latest_market_reaction_snapshot()
    latest_triggers = storage.get_latest_news_triggers()
    if latest_derivatives is None and latest_option_chain is None and latest_reaction is None and not latest_triggers:
        return None

    derivatives = _build_derivatives_pressure(
        latest_derivatives=latest_derivatives,
        latest_option_chain=latest_option_chain,
        previous_option_chain=previous_option_chain,
    )
    triggers = _build_triggers(latest_triggers)
    reaction = _build_market_reaction(
        latest_derivatives=latest_derivatives,
        latest_reaction=latest_reaction,
    )
    provider_health = _build_provider_health(storage)
    live_provider_missing = any(item.status in {"missing", "stale"} for item in provider_health)
    judgement = build_market_judgement(
        derivatives,
        triggers,
        reaction,
        live_provider_missing=live_provider_missing,
    )
    as_of_candidates = [
        _as_text(latest_derivatives, "snapshot_time"),
        _as_text(latest_option_chain, "snapshot_time"),
        _as_text(latest_reaction, "snapshot_time"),
        next((_as_text(trigger, "published_at") for trigger in latest_triggers if _as_text(trigger, "published_at")), None),
    ]
    as_of = max((value for value in as_of_candidates if value), default=utcnow_iso())
    return MarketDashboard(
        as_of=as_of,
        session_phase="live",
        derivatives=derivatives,
        triggers=triggers,
        reaction=reaction,
        judgement=judgement,
        provider_health=provider_health,
    )


def _build_derivatives_pressure(
    *,
    latest_derivatives: dict[str, Any] | None,
    latest_option_chain: dict[str, Any] | None,
    previous_option_chain: dict[str, Any] | None,
) -> DerivativesPressure:
    futures_observed_at = _as_text(latest_derivatives, "snapshot_time")
    option_observed_at = _as_text(latest_option_chain, "snapshot_time")
    option_stats = _option_stats(latest_option_chain)
    previous_option_stats = _option_stats(previous_option_chain)
    option_oi_change = _option_open_interest_change(option_stats=option_stats, previous_option_stats=previous_option_stats)
    option_pressure = option_stats["pressure"]
    futures_change_rate = _as_number(latest_derivatives, "change_rate")
    futures_metrics = _additional_metrics(latest_derivatives)
    basis = _metric_number(futures_metrics, "basis")
    if basis is None:
        basis = _derived_basis(latest_derivatives=latest_derivatives, latest_option_chain=latest_option_chain)
    open_interest_change_rate = _metric_number(futures_metrics, "open_interest_change_rate")
    combined_oi_change_rate = _combined_open_interest_change_rate(
        futures_oi_change_rate=open_interest_change_rate,
        option_oi_change=option_oi_change,
    )

    summary_parts = []
    if futures_change_rate is not None:
        summary_parts.append(f"KOSPI200 선물은 {futures_change_rate:.2f}% 변동 중입니다.")
    if basis is not None:
        summary_parts.append(f"basis는 {basis:.2f}pt입니다.")
    if open_interest_change_rate is not None:
        summary_parts.append(f"선물 미결제약정은 직전 대비 {open_interest_change_rate:.2f}% 변했습니다.")
    if option_oi_change.get("freshness") == "fresh":
        summary_parts.append(_option_oi_change_summary(option_oi_change))
    if option_pressure != "UNKNOWN":
        summary_parts.append(f"옵션 미결제약정은 {option_pressure} 우위로 집계됩니다.")
    if not summary_parts:
        summary_parts.append("KIS 파생 데이터가 아직 dashboard 판단에 충분하지 않습니다.")

    return DerivativesPressure(
        foreign_futures_net_buy=_missing_point("KRW", "KIS 수급 endpoint 미연결"),
        institution_futures_net_buy=_missing_point("KRW", "KIS 수급 endpoint 미연결"),
        individual_futures_net_buy=_missing_point("KRW", "KIS 수급 endpoint 미연결"),
        basis=_point(
            basis,
            "pt",
            _as_text(latest_derivatives, "source_name") or KIS_SOURCE,
            futures_observed_at,
            _freshness(latest_derivatives) if basis is not None else "missing",
        ),
        put_call_ratio=_point(option_stats["put_call_ratio"], "ratio", "argus_v2.option_chain", option_observed_at, _freshness(latest_option_chain)),
        open_interest_change_rate=_point(
            combined_oi_change_rate,
            "pct",
            _open_interest_change_source(
                futures_source=_as_text(latest_derivatives, "source_name") or KIS_SOURCE,
                option_oi_change=option_oi_change,
            ),
            _open_interest_observed_at(futures_observed_at=futures_observed_at, option_observed_at=option_observed_at, option_oi_change=option_oi_change),
            _open_interest_change_freshness(
                futures_oi_change_rate=open_interest_change_rate,
                latest_derivatives=latest_derivatives,
                option_oi_change=option_oi_change,
            ),
        ),
        kospi200_futures_change_rate=_point(
            futures_change_rate,
            "pct",
            _as_text(latest_derivatives, "source_name") or KIS_SOURCE,
            futures_observed_at,
            _freshness(latest_derivatives),
        ),
        option_pressure=option_pressure,
        option_open_interest_change=_option_oi_change_contract(
            option_oi_change=option_oi_change,
            observed_at=_open_interest_observed_at(
                futures_observed_at=futures_observed_at,
                option_observed_at=option_observed_at,
                option_oi_change=option_oi_change,
            ),
            source=_open_interest_change_source(
                futures_source=_as_text(latest_derivatives, "source_name") or KIS_SOURCE,
                option_oi_change=option_oi_change,
            ),
        ),
        key_levels=_key_levels(latest_option_chain, option_stats),
        summary=" ".join(summary_parts),
        freshness=_combined_freshness(_freshness(latest_derivatives), _freshness(latest_option_chain)),
    )


def _build_triggers(rows: list[dict[str, Any]]) -> list[TriggerEvent]:
    return [
        TriggerEvent(
            id=_as_text(row, "external_id") or str(row.get("id")),
            title=_as_text(row, "title") or "제목 없음",
            summary=_as_text(row, "summary") or "",
            impact=_direction_tone(_as_text(row, "impact")),
            source=_as_text(row, "source_name") or "argus_v2.news_triggers",
            published_at=_as_text(row, "published_at"),
            connection_strength=_connection_strength(_as_text(row, "connection_strength")),
            freshness=_freshness(row),
        )
        for row in rows
    ]


def _build_market_reaction(
    *,
    latest_derivatives: dict[str, Any] | None,
    latest_reaction: dict[str, Any] | None,
) -> MarketReaction:
    if latest_reaction is not None:
        observed_at = _as_text(latest_reaction, "snapshot_time")
        source = _as_text(latest_reaction, "source_name") or "argus_v2.market_reaction"
        freshness = _freshness(latest_reaction)
        spot_foreign_net_buy = _as_number(latest_reaction, "spot_foreign_net_buy")
        spot_institution_net_buy = _as_number(latest_reaction, "spot_institution_net_buy")
        spot_individual_net_buy = _as_number(latest_reaction, "spot_individual_net_buy")
        return MarketReaction(
            kospi_change_rate=_point(_as_number(latest_reaction, "kospi_change_rate"), "pct", source, observed_at, freshness),
            kosdaq_change_rate=_point(_as_number(latest_reaction, "kosdaq_change_rate"), "pct", source, observed_at, freshness),
            kospi200_futures_change_rate=_point(
                _as_number(latest_reaction, "kospi200_futures_change_rate"),
                "pct",
                source,
                observed_at,
                freshness,
            ),
            advancing_count=_point(_as_number(latest_reaction, "advancing_count"), "count", source, observed_at, freshness),
            declining_count=_point(_as_number(latest_reaction, "declining_count"), "count", source, observed_at, freshness),
            spot_foreign_net_buy=_point(
                spot_foreign_net_buy,
                "KRW",
                source,
                observed_at,
                freshness if spot_foreign_net_buy is not None else "missing",
            ),
            spot_institution_net_buy=_point(
                spot_institution_net_buy,
                "KRW",
                source,
                observed_at,
                freshness if spot_institution_net_buy is not None else "missing",
            ),
            spot_individual_net_buy=_point(
                spot_individual_net_buy,
                "KRW",
                source,
                observed_at,
                freshness if spot_individual_net_buy is not None else "missing",
            ),
            strong_sectors=_build_sector_moves(latest_reaction.get("strong_sectors") or []),
            weak_sectors=_build_sector_moves(latest_reaction.get("weak_sectors") or []),
            summary=_as_text(latest_reaction, "summary") or "현물 반응 데이터가 수신됐지만 요약은 아직 없습니다.",
            freshness=freshness,
        )

    futures_observed_at = _as_text(latest_derivatives, "snapshot_time")
    futures_change_rate = _as_number(latest_derivatives, "change_rate")
    summary = "현물 지수/섹터 반응은 아직 v2 저장소에 연결되지 않았고, KOSPI200 선물 변화율만 확인합니다."
    return MarketReaction(
        kospi_change_rate=_missing_point("pct", "현물 지수 endpoint 미연결"),
        kosdaq_change_rate=_missing_point("pct", "현물 지수 endpoint 미연결"),
        kospi200_futures_change_rate=_point(
            futures_change_rate,
            "pct",
            _as_text(latest_derivatives, "source_name") or KIS_SOURCE,
            futures_observed_at,
            _freshness(latest_derivatives),
        ),
        advancing_count=_missing_point("count", "시장 breadth endpoint 미연결"),
        declining_count=_missing_point("count", "시장 breadth endpoint 미연결"),
        spot_foreign_net_buy=_missing_point("KRW", "현물 수급 endpoint 미연결"),
        spot_institution_net_buy=_missing_point("KRW", "현물 수급 endpoint 미연결"),
        spot_individual_net_buy=_missing_point("KRW", "현물 수급 endpoint 미연결"),
        strong_sectors=[],
        weak_sectors=[],
        summary=summary,
        freshness="partial" if futures_change_rate is not None else "missing",
    )


def _build_provider_health(storage: ArgusV2Storage) -> list[ProviderHealth]:
    rows = {row["provider_key"]: row for row in storage.get_latest_provider_runs()}
    health = [
        _provider_health_from_run(
            key="kis_derivatives",
            label="KIS 국내파생",
            row=rows.get("kis_derivatives"),
        ),
        _provider_health_from_run(
            key="kis_option_chain",
            label="KIS 옵션체인",
            row=rows.get("kis_option_chain"),
        ),
        _provider_health_from_run(
            key="v2_market_reaction",
            label="v2 현물 반응",
            row=rows.get("v2_market_reaction"),
        ),
        _provider_health_from_run(
            key="v2_news_triggers",
            label="v2 뉴스 트리거",
            row=rows.get("v2_news_triggers"),
        ),
    ]
    return health


def _provider_health_from_run(*, key: str, label: str, row: dict[str, Any] | None) -> ProviderHealth:
    if row is None:
        return ProviderHealth(
            key=key,
            label=label,
            status="missing",
            observed_count=0,
            missing_fields=["provider_run"],
            error="아직 수신 run이 없습니다.",
        )

    status = _run_status_to_freshness(str(row.get("status") or ""))
    return ProviderHealth(
        key=key,
        label=label,
        status=status,
        last_success_at=str(row["finished_at"]) if row.get("finished_at") else None,
        observed_count=int(row.get("observed_count") or 0),
        missing_fields=_json_list(row.get("missing_fields_json")),
        error=str(row["error"]) if row.get("error") else None,
    )


def _option_stats(latest_option_chain: dict[str, Any] | None) -> dict[str, Any]:
    levels = list((latest_option_chain or {}).get("levels") or [])
    call_oi = sum(value for value in (_as_number(level, "call_open_interest") for level in levels) if value is not None)
    put_oi = sum(value for value in (_as_number(level, "put_open_interest") for level in levels) if value is not None)
    net_oi = call_oi - put_oi
    pressure: OptionPressureSide
    if not levels:
        pressure = "UNKNOWN"
    elif abs(net_oi) <= max(call_oi + put_oi, 1.0) * 0.03:
        pressure = "NEUTRAL"
    elif net_oi > 0:
        pressure = "CALL"
    else:
        pressure = "PUT"

    call_wall = _max_level(levels, "call_open_interest")
    put_wall = _max_level(levels, "put_open_interest")
    pressure_level = max(levels, key=lambda level: abs(_as_number(level, "net_call_put_oi") or 0.0), default=None)
    return {
        "call_oi": call_oi,
        "put_oi": put_oi,
        "net_oi": net_oi,
        "total_oi": call_oi + put_oi,
        "put_call_ratio": (put_oi / call_oi) if call_oi else None,
        "pressure": pressure,
        "call_wall": call_wall,
        "put_wall": put_wall,
        "pressure_level": pressure_level,
    }


def _key_levels(latest_option_chain: dict[str, Any] | None, option_stats: dict[str, Any]) -> list[OptionKeyLevel]:
    if latest_option_chain is None:
        return []

    observed_at = _as_text(latest_option_chain, "snapshot_time")
    freshness = _freshness(latest_option_chain)
    source = _as_text(latest_option_chain, "source_name") or KIS_SOURCE
    levels: list[OptionKeyLevel] = []
    atm_strike = _as_number(latest_option_chain, "atm_strike")
    if atm_strike is not None:
        levels.append(
            OptionKeyLevel(
                role="atm",
                label="ATM 기준",
                side="UNKNOWN",
                strike_price=atm_strike,
                summary=f"현재 옵션체인 기준 ATM은 {atm_strike:g}pt 부근입니다.",
                source=source,
                observed_at=observed_at,
                freshness=freshness,
            )
        )

    call_wall = option_stats.get("call_wall")
    if call_wall is not None:
        strike = _as_number(call_wall, "strike_price")
        oi = _as_number(call_wall, "call_open_interest")
        levels.append(
            OptionKeyLevel(
                role="call_wall",
                label="콜 OI 집중",
                side="CALL",
                strike_price=strike,
                summary=f"{strike:g}pt 콜 미결제약정 {oi:,.0f}계약이 가장 큽니다." if strike is not None and oi is not None else "콜 OI 집중 레벨입니다.",
                source=source,
                observed_at=observed_at,
                freshness=freshness,
            )
        )

    put_wall = option_stats.get("put_wall")
    if put_wall is not None:
        strike = _as_number(put_wall, "strike_price")
        oi = _as_number(put_wall, "put_open_interest")
        levels.append(
            OptionKeyLevel(
                role="put_wall",
                label="풋 OI 집중",
                side="PUT",
                strike_price=strike,
                summary=f"{strike:g}pt 풋 미결제약정 {oi:,.0f}계약이 가장 큽니다." if strike is not None and oi is not None else "풋 OI 집중 레벨입니다.",
                source=source,
                observed_at=observed_at,
                freshness=freshness,
            )
        )

    pressure_level = option_stats.get("pressure_level")
    if pressure_level is not None:
        strike = _as_number(pressure_level, "strike_price")
        side = _pressure_side(_as_text(pressure_level, "pressure_side"))
        net_oi = _as_number(pressure_level, "net_call_put_oi")
        levels.append(
            OptionKeyLevel(
                role="pressure",
                label="순 OI 압력",
                side=side,
                strike_price=strike,
                summary=f"{strike:g}pt 순 OI 차이 {net_oi:,.0f}계약입니다." if strike is not None and net_oi is not None else "순 OI 차이가 큰 레벨입니다.",
                source=source,
                observed_at=observed_at,
                freshness=freshness,
            )
        )

    return levels[:4]


def _option_open_interest_change(*, option_stats: dict[str, Any], previous_option_stats: dict[str, Any]) -> dict[str, Any]:
    current_total = _safe_number(option_stats.get("total_oi"))
    previous_total = _safe_number(previous_option_stats.get("total_oi"))
    if current_total is None or previous_total is None or previous_total <= 0:
        return {"freshness": "missing"}

    call_change_rate = _change_rate(_safe_number(option_stats.get("call_oi")), _safe_number(previous_option_stats.get("call_oi")))
    put_change_rate = _change_rate(_safe_number(option_stats.get("put_oi")), _safe_number(previous_option_stats.get("put_oi")))
    net_change_rate = _change_rate(_safe_number(option_stats.get("net_oi")), _safe_number(previous_option_stats.get("net_oi")))
    total_change_rate = _change_rate(current_total, previous_total)
    dominant_side = _dominant_option_oi_change(call_change_rate=call_change_rate, put_change_rate=put_change_rate)
    return {
        "freshness": "fresh",
        "call_change_rate": call_change_rate,
        "put_change_rate": put_change_rate,
        "net_change_rate": net_change_rate,
        "total_change_rate": total_change_rate,
        "dominant_side": dominant_side,
    }


def _option_oi_change_contract(*, option_oi_change: dict[str, Any], observed_at: str | None, source: str) -> OptionOpenInterestChange:
    freshness = str(option_oi_change.get("freshness") or "missing")
    if freshness not in {"fresh", "partial", "stale", "missing"}:
        freshness = "missing"
    return OptionOpenInterestChange(
        freshness=freshness,
        call_change_rate=_safe_number(option_oi_change.get("call_change_rate")),
        put_change_rate=_safe_number(option_oi_change.get("put_change_rate")),
        net_change_rate=_safe_number(option_oi_change.get("net_change_rate")),
        total_change_rate=_safe_number(option_oi_change.get("total_change_rate")),
        dominant_side=_pressure_side(str(option_oi_change.get("dominant_side") or "UNKNOWN")),
        source=source,
        observed_at=observed_at,
    )


def _combined_open_interest_change_rate(*, futures_oi_change_rate: float | None, option_oi_change: dict[str, Any]) -> float | None:
    option_total_change = _safe_number(option_oi_change.get("total_change_rate")) if option_oi_change.get("freshness") == "fresh" else None
    if option_total_change is not None:
        return option_total_change
    return futures_oi_change_rate


def _open_interest_change_source(*, futures_source: str, option_oi_change: dict[str, Any]) -> str:
    if option_oi_change.get("freshness") == "fresh":
        return "argus_v2.option_chain_comparison"
    return futures_source


def _open_interest_observed_at(*, futures_observed_at: str | None, option_observed_at: str | None, option_oi_change: dict[str, Any]) -> str | None:
    if option_oi_change.get("freshness") == "fresh":
        return option_observed_at
    return futures_observed_at


def _open_interest_change_freshness(
    *,
    futures_oi_change_rate: float | None,
    latest_derivatives: dict[str, Any] | None,
    option_oi_change: dict[str, Any],
) -> str:
    if option_oi_change.get("freshness") == "fresh":
        return "fresh"
    if futures_oi_change_rate is not None:
        return _freshness(latest_derivatives)
    return "missing"


def _option_oi_change_summary(option_oi_change: dict[str, Any]) -> str:
    call_change = _safe_number(option_oi_change.get("call_change_rate"))
    put_change = _safe_number(option_oi_change.get("put_change_rate"))
    dominant_side = str(option_oi_change.get("dominant_side") or "NEUTRAL")
    if call_change is None or put_change is None:
        return "옵션 미결제약정 변화는 계산됐지만 콜/풋 세부 변화율이 부족합니다."
    return f"옵션 OI 변화는 {dominant_side} 우위입니다. 콜 {call_change:.2f}%, 풋 {put_change:.2f}%."


def _dominant_option_oi_change(*, call_change_rate: float | None, put_change_rate: float | None) -> str:
    if call_change_rate is None or put_change_rate is None:
        return "UNKNOWN"
    difference = call_change_rate - put_change_rate
    if abs(difference) < 0.5:
        return "NEUTRAL"
    return "CALL" if difference > 0 else "PUT"


def _change_rate(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return ((current - previous) / abs(previous)) * 100


def _build_sector_moves(rows: list[dict[str, Any]]) -> list[SectorMove]:
    return [
        SectorMove(
            name=_as_text(row, "name") or "미분류",
            change_rate=_as_number(row, "change_rate"),
            reason=_as_text(row, "reason") or "",
            tone=_direction_tone(_as_text(row, "tone")),
            source=_as_text(row, "source_name") or "argus_v2.market_reaction",
            observed_at=_as_text(row, "observed_at"),
        )
        for row in rows
    ]


def _point(value: float | int | str | None, unit: str, source: str, observed_at: str | None, freshness: str) -> DataPoint:
    return DataPoint(value=value, unit=unit, source=source, observed_at=observed_at, freshness=freshness)


def _missing_point(unit: str, source: str) -> DataPoint:
    return DataPoint(value=None, unit=unit, source=source, observed_at=None, freshness="missing")


def _freshness(row: dict[str, Any] | None) -> str:
    if row is None:
        return "missing"
    freshness = _as_text(row, "freshness_state")
    if freshness in {"fresh", "partial", "stale", "missing"}:
        return freshness
    return "fresh"


def _combined_freshness(first: str, second: str) -> str:
    if first == "fresh" and second == "fresh":
        return "fresh"
    if first == "missing" and second == "missing":
        return "missing"
    if "stale" in {first, second}:
        return "stale"
    return "partial"


def _run_status_to_freshness(status: str) -> str:
    if status == "success":
        return "fresh"
    if status == "partial":
        return "partial"
    if status == "skipped":
        return "missing"
    return "missing"


def _pressure_side(value: str | None) -> OptionPressureSide:
    if value in {"CALL", "PUT", "NEUTRAL", "UNKNOWN"}:
        return value
    if value == "BALANCED":
        return "NEUTRAL"
    return "UNKNOWN"


def _direction_tone(value: str | None) -> str:
    if value in {"positive", "neutral", "negative"}:
        return value
    return "neutral"


def _connection_strength(value: str | None) -> str:
    if value in {"strong", "medium", "weak", "unclear"}:
        return value
    return "unclear"


def _max_level(levels: list[dict[str, Any]], field: str) -> dict[str, Any] | None:
    candidates = [level for level in levels if _as_number(level, field) is not None]
    if not candidates:
        return None
    return max(candidates, key=lambda level: _as_number(level, field) or 0.0)


def _additional_metrics(row: dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {}
    payload = row.get("additional_metrics_json")
    if isinstance(payload, dict):
        return payload
    if not isinstance(payload, str) or not payload:
        return {}
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _metric_number(metrics: dict[str, Any], key: str) -> float | None:
    value = metrics.get(key)
    if isinstance(value, (float, int)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", ""))
        except ValueError:
            return None
    return None


def _safe_number(value: Any) -> float | None:
    if isinstance(value, (float, int)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", ""))
        except ValueError:
            return None
    return None


def _derived_basis(*, latest_derivatives: dict[str, Any] | None, latest_option_chain: dict[str, Any] | None) -> float | None:
    futures_price = _as_number(latest_derivatives, "price")
    underlying_price = _as_number(latest_option_chain, "underlying_price")
    if futures_price is None or underlying_price is None:
        return None
    return futures_price - underlying_price


def _as_number(row: dict[str, Any] | None, key: str) -> float | None:
    if row is None:
        return None
    value = row.get(key)
    if isinstance(value, (float, int)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", ""))
        except ValueError:
            return None
    return None


def _as_text(row: dict[str, Any] | None, key: str) -> str | None:
    if row is None:
        return None
    value = row.get(key)
    return str(value) if value not in {None, ""} else None


def _json_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        import json

        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(payload, list):
            return [str(item) for item in payload]
    return []
