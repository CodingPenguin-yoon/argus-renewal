from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.market_data.market_flow.adapters import (
    FixtureMarketFlowAdapter,
    FixtureProviderError,
    FixtureScenario,
)
from src.market_data.market_flow.api import create_market_flow_router
from src.market_data.market_flow.collect import collect_market_flow
from src.market_data.market_flow.domain import DataMode, DataQuality, MarketScope, MarketSegment
from src.market_data.market_flow.queries import build_market_flow_dashboard
from src.market_data.market_flow.repository import SQLiteMarketFlowRepository


AS_OF = datetime(2026, 7, 22, 1, 30, tzinfo=timezone.utc)


def test_fixture_market_flow_is_explicit_mock_with_estimate_and_confirmed() -> None:
    facts = FixtureMarketFlowAdapter().fetch(as_of=AS_OF)

    assert len(facts) == 8
    assert {fact.data_mode for fact in facts} == {DataMode.MOCK}
    assert {fact.market_scope for fact in facts} == {MarketScope.KRX}
    assert {fact.segment for fact in facts} == set(MarketSegment)
    assert {fact.quality for fact in facts} == {
        DataQuality.ESTIMATE,
        DataQuality.CONFIRMED,
    }
    assert all(not fact.is_live for fact in facts)
    assert {fact.source for fact in facts} == {"FIXTURE_BROKER", "FIXTURE_KRX"}


def test_repository_insert_is_idempotent_and_keeps_both_quality_facts(tmp_path) -> None:
    repository = SQLiteMarketFlowRepository(str(tmp_path / "market-flow.db"))
    provider = FixtureMarketFlowAdapter()

    first = collect_market_flow(provider=provider, writer=repository, as_of=AS_OF)
    second = collect_market_flow(provider=provider, writer=repository, as_of=AS_OF)
    latest = repository.list_latest(data_mode=DataMode.MOCK)

    assert first.fetched_count == 8
    assert first.inserted_count == 8
    assert second.fetched_count == 8
    assert second.inserted_count == 0
    assert len(latest) == 8
    assert {
        (fact.segment, fact.quality)
        for fact in latest
    } == {
        (segment, quality)
        for segment in MarketSegment
        for quality in DataQuality
    }


def test_query_reports_stale_estimates_without_hiding_confirmed_data(tmp_path) -> None:
    repository = SQLiteMarketFlowRepository(str(tmp_path / "stale-market-flow.db"))
    provider = FixtureMarketFlowAdapter(scenario=FixtureScenario.STALE)
    collect_market_flow(provider=provider, writer=repository, as_of=AS_OF)

    dashboard = build_market_flow_dashboard(
        reader=repository,
        data_mode=DataMode.MOCK,
        now=AS_OF + timedelta(minutes=1),
        estimate_stale_after_seconds=300,
        confirmed_stale_after_seconds=604800,
    )

    assert dashboard.status.value == "stale"
    assert all(row.estimate is not None for row in dashboard.rows)
    assert all(row.estimate.freshness.value == "stale" for row in dashboard.rows if row.estimate)
    assert all(row.confirmed is not None for row in dashboard.rows)


def test_empty_repository_returns_explicit_missing_rows(tmp_path) -> None:
    db_path = tmp_path / "empty-market-flow.db"
    repository = SQLiteMarketFlowRepository(str(db_path))

    dashboard = build_market_flow_dashboard(
        reader=repository,
        data_mode=DataMode.MOCK,
        now=AS_OF,
        estimate_stale_after_seconds=300,
        confirmed_stale_after_seconds=604800,
    )

    assert dashboard.status.value == "missing"
    assert len(dashboard.rows) == 4
    assert all(row.estimate is None and row.confirmed is None for row in dashboard.rows)
    assert not db_path.exists()


def test_partial_fixture_keeps_missing_segments_visible(tmp_path) -> None:
    repository = SQLiteMarketFlowRepository(str(tmp_path / "partial-market-flow.db"))
    collect_market_flow(
        provider=FixtureMarketFlowAdapter(scenario=FixtureScenario.PARTIAL),
        writer=repository,
        as_of=AS_OF,
    )

    dashboard = build_market_flow_dashboard(
        reader=repository,
        data_mode=DataMode.MOCK,
        now=AS_OF,
        estimate_stale_after_seconds=300,
        confirmed_stale_after_seconds=604800,
    )

    assert dashboard.status.value == "partial"
    assert [row.status.value for row in dashboard.rows] == [
        "fresh",
        "fresh",
        "missing",
        "missing",
    ]


def test_fixture_provider_error_is_not_silently_converted_to_empty_data(tmp_path) -> None:
    repository = SQLiteMarketFlowRepository(str(tmp_path / "error-market-flow.db"))

    with pytest.raises(FixtureProviderError, match="fixture_market_flow_provider_error"):
        collect_market_flow(
            provider=FixtureMarketFlowAdapter(scenario=FixtureScenario.ERROR),
            writer=repository,
            as_of=AS_OF,
        )

    assert repository.list_latest(data_mode=DataMode.MOCK) == []


def test_market_flow_api_reads_precollected_storage_and_exposes_demo_mode(tmp_path) -> None:
    repository = SQLiteMarketFlowRepository(str(tmp_path / "api-market-flow.db"))
    collect_market_flow(
        provider=FixtureMarketFlowAdapter(),
        writer=repository,
        as_of=AS_OF,
    )
    app = FastAPI()
    app.include_router(create_market_flow_router(reader=repository, clock=lambda: AS_OF))
    client = TestClient(app)

    response = client.get("/api/market-data/v1/dashboard/market-flow")
    body = response.json()

    assert response.status_code == 200
    assert body["data_mode"] == "mock"
    assert body["is_live"] is False
    assert body["market_scope"] == "KRX"
    assert body["status"] == "fresh"
    assert len(body["rows"]) == 4
    assert body["rows"][0]["estimate"]["source"] == "FIXTURE_BROKER"
    assert body["rows"][0]["confirmed"]["source"] == "FIXTURE_KRX"

    live_response = client.get(
        "/api/market-data/v1/dashboard/market-flow",
        params={"data_mode": "live"},
    )
    assert live_response.status_code == 200
    assert live_response.json()["status"] == "missing"
    assert live_response.json()["is_live"] is True
