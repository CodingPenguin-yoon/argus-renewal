from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.argus_v2.db import get_connection
from src.argus_v2.storage import ArgusV2Storage


@dataclass(frozen=True)
class FakeBatch:
    records: list[Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    disabled_reason: str | None = None


@dataclass(frozen=True)
class FakeDerivativesSnapshot:
    source_name: str = "KIS_DOMESTIC_DERIVATIVES"
    trade_date: str = "2026-05-12"
    snapshot_time: str = "2026-05-12T00:10:00Z"
    session_type: str = "PRE_OPEN"
    instrument_code: str = "F202606"
    instrument_name: str = "KOSPI200 선물 202606"
    price: float = 392.5
    price_change: float = -1.2
    change_rate: float = -0.31
    volume: float = 1500
    open_interest: float = 215000
    put_call_ratio: float | None = None
    implied_volatility: float | None = None
    additional_metrics: dict[str, Any] = field(default_factory=lambda: {"basis": -0.4})
    source_url: str = "https://example.test/derivatives"
    source_record_id: str = "future-1"
    raw_payload: dict[str, Any] = field(
        default_factory=lambda: {
            "instrument_code": "F202606",
            "appsecret": "must-not-be-saved",
            "authorization": "Bearer must-not-be-saved",
        }
    )


@dataclass(frozen=True)
class FakeFuturesInvestorFlowSnapshot:
    source_name: str = "KIS_FUTURES_INVESTOR_FLOW"
    trade_date: str = "2026-05-12"
    snapshot_time: str = "2026-05-12T00:10:30Z"
    market_scope: str = "KOSPI200_FUTURES"
    foreign_net_buy: float = -180_000_000_000
    institution_net_buy: float = 62_000_000_000
    individual_net_buy: float = 118_000_000_000
    source_url: str = "https://example.test/futures-flow"
    source_record_id: str = "futures-flow-1"
    raw_payload: dict[str, Any] = field(default_factory=lambda: {"frgn_ntby_tr_pbmn": "-18000000"})


@dataclass(frozen=True)
class FakeOptionLevel:
    strike_price: float
    moneyness: str
    call_open_interest: float
    put_open_interest: float
    total_open_interest: float
    net_call_put_oi: float
    call_put_oi_ratio: float
    pressure_side: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FakeOptionChainSnapshot:
    source_name: str = "KIS_DOMESTIC_DERIVATIVES"
    trade_date: str = "2026-05-12"
    snapshot_time: str = "2026-05-12T00:11:00Z"
    expiry_date: str = "202605"
    market_scope: str = "KRX"
    underlying_code: str = "KOSPI200"
    underlying_name: str = "KOSPI200"
    underlying_price: float = 392.0
    contract_month: str = "202605"
    source_url: str = "https://example.test/options"
    source_record_id: str = "option-chain-1"
    atm_strike: float = 392.5
    expected_level_count: int = 2
    observed_level_count: int = 2
    freshness_state: str = "fresh"
    raw_payload: dict[str, Any] = field(
        default_factory=lambda: {
            "output": [{"strike_price": 390.0}],
            "access_token": "must-not-be-saved",
        }
    )
    levels: list[FakeOptionLevel] = field(
        default_factory=lambda: [
            FakeOptionLevel(
                strike_price=390.0,
                moneyness="ITM",
                call_open_interest=1200,
                put_open_interest=800,
                total_open_interest=2000,
                net_call_put_oi=400,
                call_put_oi_ratio=1.5,
                pressure_side="CALL",
            ),
            FakeOptionLevel(
                strike_price=395.0,
                moneyness="OTM",
                call_open_interest=700,
                put_open_interest=1500,
                total_open_interest=2200,
                net_call_put_oi=-800,
                call_put_oi_ratio=0.47,
                pressure_side="PUT",
            ),
        ]
    )


@dataclass(frozen=True)
class FakeSourceStatus:
    observed_count: int
    expected_count: int
    status: str


@dataclass(frozen=True)
class FakeSectorMove:
    name: str
    change_rate: float
    reason: str
    tone: str
    source: str = "mock.market.reaction"
    observed_at: str = "2026-05-12T00:12:00Z"


@dataclass(frozen=True)
class FakeMarketReactionSnapshot:
    trade_date: str = "2026-05-12"
    snapshot_time: str = "2026-05-12T00:12:00Z"
    source_name: str = "mock.market.reaction"
    kospi_change_rate: float = -0.42
    kosdaq_change_rate: float = 0.18
    kospi200_futures_change_rate: float = -0.31
    advancing_count: int = 411
    declining_count: int = 523
    spot_foreign_net_buy: float = -82_000_000_000
    spot_institution_net_buy: float = 34_000_000_000
    spot_individual_net_buy: float = 48_000_000_000
    summary: str = "지수는 약하지만 반도체가 하락 압력을 일부 상쇄합니다."
    freshness_state: str = "fresh"
    source_url: str = "https://example.test/reaction"
    source_record_id: str = "reaction-1"
    raw_payload: dict[str, Any] = field(default_factory=lambda: {"token": "must-not-be-saved"})
    strong_sectors: list[FakeSectorMove] = field(
        default_factory=lambda: [
            FakeSectorMove(
                name="반도체",
                change_rate=1.24,
                reason="AI 반도체 강세",
                tone="positive",
            )
        ]
    )
    weak_sectors: list[FakeSectorMove] = field(
        default_factory=lambda: [
            FakeSectorMove(
                name="금융",
                change_rate=-0.72,
                reason="금리 변동성 부담",
                tone="negative",
            )
        ]
    )


@dataclass(frozen=True)
class FakeNewsTrigger:
    id: str
    title: str
    summary: str
    impact: str
    source: str
    published_at: str
    connection_strength: str
    freshness: str = "fresh"
    source_url: str = "https://example.test/news"
    raw_payload: dict[str, Any] = field(default_factory=lambda: {"authorization": "must-not-be-saved"})


def test_argus_v2_storage_persists_derivatives_snapshot_and_redacted_sample(tmp_path: Path) -> None:
    db_path = str(tmp_path / "argus-v2.db")

    with get_connection(db_path) as connection:
        storage = ArgusV2Storage(connection)
        result = storage.save_provider_batch(
            provider_key="kis_derivatives",
            provider_label="KIS 파생 선물",
            endpoint="/uapi/domestic-futureoption/v1/quotations/inquire-price",
            batch=FakeBatch(records=[FakeDerivativesSnapshot()]),
        )

        latest = storage.get_latest_derivatives_snapshot()
        sample = connection.execute(
            "SELECT payload_json FROM argus_v2_provider_samples WHERE id = ?",
            (result.sample_ids[0],),
        ).fetchone()

    assert result.status == "success"
    assert result.observed_count == 1
    assert latest is not None
    assert latest["instrument_code"] == "F202606"
    assert latest["change_rate"] == -0.31
    payload = json.loads(sample["payload_json"])
    assert payload["appsecret"] == "[REDACTED]"
    assert payload["authorization"] == "[REDACTED]"


def test_argus_v2_storage_persists_futures_investor_flow_snapshot(tmp_path: Path) -> None:
    db_path = str(tmp_path / "argus-v2.db")

    with get_connection(db_path) as connection:
        storage = ArgusV2Storage(connection)
        result = storage.save_provider_batch(
            provider_key="kis_futures_investor_flow",
            provider_label="KIS 선물 투자자 수급",
            endpoint="/uapi/domestic-futureoption/v1/quotations/inquire-investor-flow",
            batch=FakeBatch(records=[FakeFuturesInvestorFlowSnapshot()]),
        )
        latest = storage.get_latest_futures_investor_flow_snapshot()

    assert result.status == "success"
    assert result.observed_count == 1
    assert result.futures_investor_flow_snapshot_ids
    assert latest is not None
    assert latest["foreign_net_buy"] == -180_000_000_000
    assert latest["institution_net_buy"] == 62_000_000_000
    assert latest["individual_net_buy"] == 118_000_000_000


def test_argus_v2_storage_persists_option_chain_snapshot_and_levels(tmp_path: Path) -> None:
    db_path = str(tmp_path / "argus-v2.db")

    with get_connection(db_path) as connection:
        storage = ArgusV2Storage(connection)
        result = storage.save_provider_batch(
            provider_key="kis_option_chain",
            provider_label="KIS 옵션 체인",
            endpoint="/uapi/domestic-futureoption/v1/quotations/display-board-callput",
            batch=FakeBatch(
                records=[
                    FakeOptionChainSnapshot(),
                    FakeSourceStatus(observed_count=2, expected_count=2, status="available"),
                ],
                metadata={"expected_level_count": 2},
            ),
        )

        latest = storage.get_latest_option_chain_snapshot()
        sample = connection.execute(
            "SELECT payload_json FROM argus_v2_provider_samples WHERE id = ?",
            (result.sample_ids[0],),
        ).fetchone()

    assert result.status == "success"
    assert result.observed_count == 2
    assert latest is not None
    assert latest["contract_month"] == "202605"
    assert latest["freshness_state"] == "fresh"
    assert len(latest["levels"]) == 2
    assert latest["levels"][0]["pressure_side"] == "CALL"
    assert latest["levels"][1]["pressure_side"] == "PUT"
    payload = json.loads(sample["payload_json"])
    assert payload["access_token"] == "[REDACTED]"


def test_argus_v2_storage_records_disabled_provider_run(tmp_path: Path) -> None:
    db_path = str(tmp_path / "argus-v2.db")

    with get_connection(db_path) as connection:
        storage = ArgusV2Storage(connection)
        result = storage.save_provider_batch(
            provider_key="kis_option_chain",
            batch=FakeBatch(records=[], disabled_reason="feature_flag_disabled"),
        )
        row = connection.execute(
            "SELECT status, observed_count, missing_fields_json FROM argus_v2_provider_runs WHERE id = ?",
            (result.run_id,),
        ).fetchone()

    assert result.status == "skipped"
    assert row["status"] == "skipped"
    assert row["observed_count"] == 0
    assert json.loads(row["missing_fields_json"]) == ["feature_flag_disabled"]


def test_argus_v2_storage_persists_market_reaction_snapshot_and_sectors(tmp_path: Path) -> None:
    db_path = str(tmp_path / "argus-v2.db")

    with get_connection(db_path) as connection:
        storage = ArgusV2Storage(connection)
        result = storage.save_provider_batch(
            provider_key="v2_market_reaction",
            provider_label="v2 현물 반응",
            endpoint="mock://market-reaction",
            batch=FakeBatch(records=[FakeMarketReactionSnapshot()]),
        )

        latest = storage.get_latest_market_reaction_snapshot()
        sample = connection.execute(
            "SELECT payload_json FROM argus_v2_provider_samples WHERE id = ?",
            (result.sample_ids[0],),
        ).fetchone()

    assert result.status == "success"
    assert result.observed_count == 1
    assert result.market_reaction_snapshot_ids
    assert latest is not None
    assert latest["kospi_change_rate"] == -0.42
    assert latest["spot_foreign_net_buy"] == -82_000_000_000
    assert latest["spot_institution_net_buy"] == 34_000_000_000
    assert latest["spot_individual_net_buy"] == 48_000_000_000
    assert latest["strong_sectors"][0]["name"] == "반도체"
    assert latest["weak_sectors"][0]["name"] == "금융"
    payload = json.loads(sample["payload_json"])
    assert payload["token"] == "[REDACTED]"


def test_argus_v2_storage_persists_news_triggers(tmp_path: Path) -> None:
    db_path = str(tmp_path / "argus-v2.db")

    with get_connection(db_path) as connection:
        storage = ArgusV2Storage(connection)
        result = storage.save_provider_batch(
            provider_key="v2_news_triggers",
            provider_label="v2 뉴스 트리거",
            endpoint="mock://news-triggers",
            batch=FakeBatch(
                records=[
                    FakeNewsTrigger(
                        id="rates",
                        title="미국 금리 상승",
                        summary="밤사이 금리 상승은 위험자산에 부담입니다.",
                        impact="negative",
                        source="mock.news.macro",
                        published_at="2026-05-12T00:15:00Z",
                        connection_strength="medium",
                    ),
                    FakeNewsTrigger(
                        id="chip",
                        title="반도체 강세",
                        summary="반도체가 지수 하락을 일부 제한합니다.",
                        impact="positive",
                        source="mock.news.sector",
                        published_at="2026-05-12T00:16:00Z",
                        connection_strength="strong",
                    ),
                ]
            ),
        )

        latest = storage.get_latest_news_triggers(limit=2)
        sample = connection.execute(
            "SELECT payload_json FROM argus_v2_provider_samples WHERE id = ?",
            (result.sample_ids[0],),
        ).fetchone()

    assert result.status == "success"
    assert result.observed_count == 2
    assert len(result.news_trigger_ids) == 2
    assert latest[0]["external_id"] == "chip"
    assert latest[1]["external_id"] == "rates"
    payload = json.loads(sample["payload_json"])
    assert payload["authorization"] == "[REDACTED]"


def test_argus_v2_storage_persists_raw_news_feed_items(tmp_path: Path) -> None:
    db_path = str(tmp_path / "argus-v2.db")

    with get_connection(db_path) as connection:
        storage = ArgusV2Storage(connection)
        result = storage.save_news_feed_batch(
            provider_key="v2_news_feed",
            provider_label="v2 원천 뉴스 피드",
            endpoint="mock://news-feed",
            batch=FakeBatch(
                records=[
                    FakeNewsTrigger(
                        id="rates",
                        title="미국 금리 상승",
                        summary="밤사이 금리 상승은 위험자산에 부담입니다.",
                        impact="neutral",
                        source="mock.news.macro",
                        published_at="2026-05-12T00:15:00Z",
                        connection_strength="unclear",
                    ),
                    FakeNewsTrigger(
                        id="rates",
                        title="미국 금리 상승",
                        summary="중복 feed item입니다.",
                        impact="neutral",
                        source="mock.news.macro",
                        published_at="2026-05-12T00:15:00Z",
                        connection_strength="unclear",
                    ),
                ]
            ),
        )

        latest = storage.get_latest_news_feed_items(limit=10)
        sample = connection.execute(
            "SELECT payload_json FROM argus_v2_provider_samples WHERE id = ?",
            (result.sample_ids[0],),
        ).fetchone()

    assert result.status == "success"
    assert result.observed_count == 2
    assert len(result.news_feed_item_ids) == 2
    assert len(latest) == 1
    assert latest[0]["external_id"] == "rates"
    payload = json.loads(sample["payload_json"])
    assert payload["authorization"] == "[REDACTED]"
