from __future__ import annotations

from datetime import datetime, timezone

from src.argus_v2.collector import iter_collect_loop, run_collect_once
from src.argus_v2.db import get_connection
from src.argus_v2.market_calendar import resolve_market_session
from src.argus_v2.storage import ArgusV2Storage
from src.config.env import Settings


def test_market_session_resolves_regular_window() -> None:
    session = resolve_market_session(
        now=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert session.session_type == "regular"
    assert session.trading_date.isoformat() == "2026-05-18"
    assert session.is_market_open is True
    assert session.reason == "regular_session_open"


def test_market_session_keeps_night_disabled_by_default() -> None:
    session = resolve_market_session(
        now=datetime(2026, 5, 18, 9, 0, tzinfo=timezone.utc),
        night_enabled=False,
    )

    assert session.session_type == "closed"
    assert session.is_market_open is False
    assert session.reason == "after_regular_session"


def test_market_session_resolves_night_when_enabled() -> None:
    session = resolve_market_session(
        now=datetime(2026, 5, 18, 9, 0, tzinfo=timezone.utc),
        night_enabled=True,
    )

    assert session.session_type == "night"
    assert session.trading_date.isoformat() == "2026-05-19"
    assert session.is_market_open is True
    assert session.reason == "night_session_open"


def test_collect_once_skips_market_on_holiday_but_collects_news(tmp_path) -> None:
    db_path = str(tmp_path / "argus-v2.db")
    settings = Settings(
        db_path=db_path,
        kis_domestic_derivatives_provider="api",
        kis_option_chain_provider="api",
        argus_market_reaction_provider="kis",
        argus_news_triggers_provider="mock",
        argus_news_feed_provider="mock",
    )

    result = run_collect_once(
        settings=settings,
        snapshot_time=datetime(2026, 5, 16, 3, 0, tzinfo=timezone.utc),
    )

    provider_by_key = {provider.provider_key: provider for provider in result.providers}
    assert result.session.session_type == "closed"
    assert provider_by_key["market_session"].status == "skipped"
    assert provider_by_key["market_session"].reason == "market_holiday"
    assert provider_by_key["v2_news_triggers"].status == "success"
    assert provider_by_key["v2_news_feed"].status == "success"

    with get_connection(db_path) as connection:
        runs = ArgusV2Storage(connection).get_latest_provider_runs()

    assert {run["provider_key"] for run in runs} == {"v2_news_feed", "v2_news_triggers"}


def test_collect_loop_skips_when_lease_is_held(tmp_path) -> None:
    db_path = str(tmp_path / "argus-v2.db")
    settings = Settings(db_path=db_path, argus_news_triggers_provider="mock", argus_news_feed_provider="mock")

    with get_connection(db_path) as connection:
        lease = ArgusV2Storage(connection).acquire_collector_lease(
            collector_key="news",
            owner_id="existing-owner",
            ttl_seconds=300,
        )

    assert lease.acquired is True

    result = next(
        iter_collect_loop(
            settings=settings,
            interval_seconds=0,
            max_iterations=1,
            include_market=False,
            include_news=True,
        )
    )

    assert result.status == "skipped"
    assert result.collector_key == "news"
    assert result.reason == "lease_held_by:existing-owner"


def test_collect_loop_releases_lease_after_completion(tmp_path) -> None:
    db_path = str(tmp_path / "argus-v2.db")
    settings = Settings(db_path=db_path, argus_news_triggers_provider="mock", argus_news_feed_provider="mock")

    results = list(
        iter_collect_loop(
            settings=settings,
            interval_seconds=0,
            max_iterations=1,
            include_market=False,
            include_news=True,
        )
    )

    assert len(results) == 1
    with get_connection(db_path) as connection:
        row = connection.execute("SELECT * FROM argus_v2_collector_leases WHERE collector_key = 'news'").fetchone()

    assert row is None
