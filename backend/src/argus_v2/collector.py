from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import os
import time
from typing import Any

import httpx

from ..config.env import Settings
from .db import get_connection, resolve_db_path, utcnow_iso
from .market_calendar import MarketSessionState, resolve_market_session
from .providers.context_inputs import build_news_feed_service, run_context_collection
from .providers.kis_live import run_kis_live_smoke
from .storage import ArgusV2Storage


@dataclass(frozen=True)
class CollectorProviderResult:
    domain: str
    provider_key: str
    status: str
    observed_count: int = 0
    run_id: int | None = None
    reason: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class CollectOnceResult:
    db_path: str
    snapshot_time: str
    session: MarketSessionState
    providers: list[CollectorProviderResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "db_path": self.db_path,
            "snapshot_time": self.snapshot_time,
            "session": self.session.to_dict(),
            "providers": [asdict(provider) for provider in self.providers],
        }


@dataclass(frozen=True)
class CollectLoopLeaseResult:
    db_path: str
    collector_key: str
    owner_id: str
    status: str
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_collect_once(
    *,
    settings: Settings,
    snapshot_time: datetime | None = None,
    trade_date: date | None = None,
    include_market: bool = True,
    include_news: bool = True,
    force_market: bool = False,
    include_derivatives: bool = True,
    include_option_chain: bool = True,
    include_futures_investor_flow: bool = True,
    market_reaction_provider: str | None = None,
    news_triggers_provider: str | None = None,
    token_cache_path: str | None = None,
    http_client: httpx.Client | None = None,
) -> CollectOnceResult:
    resolved_snapshot_time = (snapshot_time or datetime.now(timezone.utc)).astimezone(timezone.utc)
    session = resolve_market_session(
        now=resolved_snapshot_time,
        holiday_dates=settings.argus_market_holidays,
        regular_start=settings.argus_collector_regular_start,
        regular_end=settings.argus_collector_regular_end,
        night_start=settings.argus_collector_night_start,
        night_end=settings.argus_collector_night_end,
        night_enabled=settings.argus_collector_night_market_enabled,
    )
    resolved_trade_date = trade_date or session.trading_date
    providers: list[CollectorProviderResult] = []

    if include_market:
        if _should_collect_market(settings=settings, session=session, force_market=force_market):
            providers.extend(
                _collect_market(
                    settings=settings,
                    trade_date=resolved_trade_date,
                    snapshot_time=resolved_snapshot_time,
                    include_derivatives=include_derivatives,
                    include_option_chain=include_option_chain,
                    include_futures_investor_flow=include_futures_investor_flow,
                    market_reaction_provider=market_reaction_provider,
                    token_cache_path=token_cache_path,
                    http_client=http_client,
                )
            )
        else:
            providers.append(
                CollectorProviderResult(
                    domain="market",
                    provider_key="market_session",
                    status="skipped",
                    reason=_market_skip_reason(settings=settings, session=session),
                )
            )

    if include_news:
        if settings.argus_collector_news_enabled:
            providers.extend(
                _collect_news(
                    settings=settings,
                    trade_date=trade_date or session.local_time.date(),
                    snapshot_time=resolved_snapshot_time,
                    news_triggers_provider=news_triggers_provider,
                    http_client=http_client,
                )
            )
        else:
            providers.append(
                CollectorProviderResult(
                    domain="news",
                    provider_key="v2_news_triggers",
                    status="skipped",
                    reason="news_collector_disabled",
                )
            )

    return CollectOnceResult(
        db_path=str(resolve_db_path(settings.db_path)),
        snapshot_time=_snapshot_iso(resolved_snapshot_time),
        session=session,
        providers=providers,
    )


def iter_collect_loop(
    *,
    settings: Settings,
    interval_seconds: float,
    max_iterations: int = 0,
    include_market: bool = True,
    include_news: bool = True,
    force_market: bool = False,
    include_derivatives: bool = True,
    include_option_chain: bool = True,
    include_futures_investor_flow: bool = True,
    market_reaction_provider: str | None = None,
    news_triggers_provider: str | None = None,
    token_cache_path: str | None = None,
    collector_key: str | None = None,
    lease_ttl_seconds: float | None = None,
) -> Any:
    resolved_collector_key = collector_key or _collector_key(include_market=include_market, include_news=include_news)
    resolved_lease_ttl = lease_ttl_seconds or max(interval_seconds * 3, 180.0)
    owner_id = _owner_id()
    with get_connection(settings.db_path) as connection:
        lease = ArgusV2Storage(connection).acquire_collector_lease(
            collector_key=resolved_collector_key,
            owner_id=owner_id,
            ttl_seconds=resolved_lease_ttl,
            metadata={"mode": resolved_collector_key},
        )
    if not lease.acquired:
        yield CollectLoopLeaseResult(
            db_path=str(resolve_db_path(settings.db_path)),
            collector_key=resolved_collector_key,
            owner_id=owner_id,
            status="skipped",
            reason=lease.reason,
        )
        return

    iteration = 0
    try:
        while max_iterations <= 0 or iteration < max_iterations:
            with get_connection(settings.db_path) as connection:
                ArgusV2Storage(connection).heartbeat_collector_lease(
                    collector_key=resolved_collector_key,
                    owner_id=owner_id,
                    ttl_seconds=resolved_lease_ttl,
                    metadata={"iteration": iteration + 1},
                )
            yield run_collect_once(
                settings=settings,
                include_market=include_market,
                include_news=include_news,
                force_market=force_market,
                include_derivatives=include_derivatives,
                include_option_chain=include_option_chain,
                include_futures_investor_flow=include_futures_investor_flow,
                market_reaction_provider=market_reaction_provider,
                news_triggers_provider=news_triggers_provider,
                token_cache_path=token_cache_path,
            )
            iteration += 1
            if max_iterations > 0 and iteration >= max_iterations:
                break
            if interval_seconds > 0:
                time.sleep(interval_seconds)
    finally:
        with get_connection(settings.db_path) as connection:
            ArgusV2Storage(connection).release_collector_lease(
                collector_key=resolved_collector_key,
                owner_id=owner_id,
            )


def _should_collect_market(*, settings: Settings, session: MarketSessionState, force_market: bool) -> bool:
    if force_market:
        return True
    if session.session_type == "regular":
        return settings.argus_collector_regular_market_enabled and session.is_market_open
    if session.session_type == "night":
        return settings.argus_collector_night_market_enabled and session.is_market_open
    return False


def _market_skip_reason(*, settings: Settings, session: MarketSessionState) -> str:
    if session.session_type == "regular" and not settings.argus_collector_regular_market_enabled:
        return "regular_market_collector_disabled"
    if session.session_type == "night" and not settings.argus_collector_night_market_enabled:
        return "night_market_collector_disabled"
    return session.reason


def _collect_market(
    *,
    settings: Settings,
    trade_date: date,
    snapshot_time: datetime,
    include_derivatives: bool,
    include_option_chain: bool,
    include_futures_investor_flow: bool,
    market_reaction_provider: str | None,
    token_cache_path: str | None,
    http_client: httpx.Client | None,
) -> list[CollectorProviderResult]:
    providers: list[CollectorProviderResult] = []
    kis_result = run_kis_live_smoke(
        settings=settings,
        trade_date=trade_date,
        snapshot_time=snapshot_time,
        include_derivatives=include_derivatives,
        include_option_chain=include_option_chain,
        include_futures_investor_flow=include_futures_investor_flow,
        token_cache_path=token_cache_path,
        http_client=http_client,
    )
    providers.extend(_provider_results(domain="market", providers=kis_result.providers))

    context_result = run_context_collection(
        settings=settings,
        trade_date=trade_date,
        snapshot_time=snapshot_time,
        include_market_reaction=True,
        include_news_triggers=False,
        market_reaction_provider=market_reaction_provider,
        http_client=http_client,
    )
    providers.extend(_provider_results(domain="market", providers=context_result.providers))
    return providers


def _collect_news(
    *,
    settings: Settings,
    trade_date: date,
    snapshot_time: datetime,
    news_triggers_provider: str | None,
    http_client: httpx.Client | None,
) -> list[CollectorProviderResult]:
    providers: list[CollectorProviderResult] = []
    result = run_context_collection(
        settings=settings,
        trade_date=trade_date,
        snapshot_time=snapshot_time,
        include_market_reaction=False,
        include_news_triggers=True,
        news_triggers_provider=news_triggers_provider,
        http_client=http_client,
    )
    providers.extend(_provider_results(domain="news", providers=result.providers))
    providers.append(
        _collect_news_feed(
            settings=settings,
            trade_date=trade_date,
            snapshot_time=snapshot_time,
            provider_override=news_triggers_provider,
            http_client=http_client,
        )
    )
    return providers


def _collect_news_feed(
    *,
    settings: Settings,
    trade_date: date,
    snapshot_time: datetime,
    provider_override: str | None,
    http_client: httpx.Client | None,
) -> CollectorProviderResult:
    provider = (provider_override or settings.argus_news_feed_provider or settings.argus_news_triggers_provider).strip().lower()
    provider_key = "v2_news_feed"
    try:
        batch = build_news_feed_service(
            settings=settings,
            provider_override=provider_override,
            http_client=http_client,
        ).fetch_feed(trade_date=trade_date, snapshot_time=snapshot_time)
        with get_connection(settings.db_path) as connection:
            persisted = ArgusV2Storage(connection).save_news_feed_batch(
                provider_key=provider_key,
                provider_label="v2 원천 뉴스 피드",
                endpoint=provider,
                batch=batch,
                started_at=_snapshot_iso(snapshot_time),
            )
        return CollectorProviderResult(
            domain="news",
            provider_key=provider_key,
            status=persisted.status,
            observed_count=persisted.observed_count,
            run_id=persisted.run_id,
        )
    except Exception as error:
        with get_connection(settings.db_path) as connection:
            storage = ArgusV2Storage(connection)
            run_id = storage.start_provider_run(
                provider_key=provider_key,
                provider_label="v2 원천 뉴스 피드",
                endpoint=provider,
                started_at=utcnow_iso(),
            )
            safe_error = f"{error.__class__.__name__}: {str(error)[:500]}" if str(error) else error.__class__.__name__
            storage.finish_provider_run(run_id=run_id, status="failed", observed_count=0, error=safe_error)
        return CollectorProviderResult(
            domain="news",
            provider_key=provider_key,
            status="failed",
            observed_count=0,
            run_id=run_id,
            error=safe_error,
        )


def _provider_results(*, domain: str, providers: list[Any]) -> list[CollectorProviderResult]:
    return [
        CollectorProviderResult(
            domain=domain,
            provider_key=str(getattr(provider, "provider_key", "unknown")),
            status=str(getattr(provider, "status", "missing")),
            observed_count=int(getattr(provider, "observed_count", 0) or 0),
            run_id=getattr(provider, "run_id", None),
            error=getattr(provider, "error", None),
        )
        for provider in providers
    ]


def _snapshot_iso(snapshot_time: datetime) -> str:
    return snapshot_time.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _collector_key(*, include_market: bool, include_news: bool) -> str:
    if include_market and include_news:
        return "all"
    if include_market:
        return "market"
    if include_news:
        return "news"
    return "noop"


def _owner_id() -> str:
    return f"{os.uname().nodename}:{os.getpid()}"
