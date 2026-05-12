from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.argus_v2.db import get_connection, utcnow_iso
from src.config.env import Settings, get_settings
from src.main import app


def _get_dashboard(db_path: str):
    app.dependency_overrides[get_settings] = lambda: Settings(
        db_path=db_path,
        kis_app_key="app-key",
        kis_app_secret="app-secret",
    )
    try:
        with TestClient(app) as client:
            return client.get("/api/argus/v2/dashboard")
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_argus_v2_dashboard_contract_falls_back_to_mock_when_v2_db_is_empty(tmp_path: Path):
    response = _get_dashboard(str(tmp_path / "empty.db"))

    assert response.status_code == 200
    data = response.json()
    assert data["judgement"]["label"] in {"강한 상방", "상방 우위", "중립", "하방 우위", "강한 하방"}
    assert data["judgement"]["source"] == "rule_based"
    assert data["derivatives"]["foreign_futures_net_buy"]["unit"] == "KRW"
    assert data["derivatives"]["option_pressure"] in {"CALL", "PUT", "NEUTRAL", "UNKNOWN"}
    assert data["reaction"]["spot_foreign_net_buy"]["unit"] == "KRW"
    assert data["reaction"]["strong_sectors"][0]["name"] == "반도체"
    assert data["provider_health"][0]["key"] == "kis_derivatives"
    assert data["provider_health"][0]["status"] == "missing"


def test_argus_v2_dashboard_reads_latest_v2_db_snapshots(tmp_path: Path):
    db_path = str(tmp_path / "argus-v2.db")
    previous_snapshot_time = "2026-05-12T02:00:38Z"
    snapshot_time = "2026-05-12T02:03:38Z"

    with get_connection(db_path) as connection:
        derivatives_run_id = connection.execute(
            """
            INSERT INTO argus_v2_provider_runs (
                provider_key, provider_label, endpoint, status, started_at, finished_at, observed_count
            )
            VALUES ('kis_derivatives', 'KIS 국내파생', '/derivatives', 'success', ?, ?, 1)
            """,
            (utcnow_iso(), utcnow_iso()),
        ).lastrowid
        option_run_id = connection.execute(
            """
            INSERT INTO argus_v2_provider_runs (
                provider_key, provider_label, endpoint, status, started_at, finished_at, observed_count, expected_count
            )
            VALUES ('kis_option_chain', 'KIS 옵션체인', '/options', 'success', ?, ?, 2, 2)
            """,
            (utcnow_iso(), utcnow_iso()),
        ).lastrowid
        reaction_run_id = connection.execute(
            """
            INSERT INTO argus_v2_provider_runs (
                provider_key, provider_label, endpoint, status, started_at, finished_at, observed_count
            )
            VALUES ('v2_market_reaction', 'v2 현물 반응', '/reaction', 'success', ?, ?, 1)
            """,
            (utcnow_iso(), utcnow_iso()),
        ).lastrowid
        trigger_run_id = connection.execute(
            """
            INSERT INTO argus_v2_provider_runs (
                provider_key, provider_label, endpoint, status, started_at, finished_at, observed_count
            )
            VALUES ('v2_news_triggers', 'v2 뉴스 트리거', '/triggers', 'success', ?, ?, 2)
            """,
            (utcnow_iso(), utcnow_iso()),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO argus_v2_derivatives_snapshots (
                run_id, trade_date, snapshot_time, session_type, source_name, instrument_code,
                instrument_name, price, price_change, change_rate, open_interest, additional_metrics_json, created_at
            )
            VALUES (?, '2026-05-12', ?, 'PRE_OPEN', 'KIS_DOMESTIC_DERIVATIVES', 'A01606',
                    'F 202606', 392.5, -4.85, -1.23, 199271, ?, ?)
            """,
            (
                derivatives_run_id,
                snapshot_time,
                json.dumps({"basis": -0.4, "open_interest_change_rate": -1.23}),
                utcnow_iso(),
            ),
        )
        previous_option_snapshot_id = connection.execute(
            """
            INSERT INTO argus_v2_option_chain_snapshots (
                run_id, trade_date, snapshot_time, market_scope, underlying_code, underlying_name,
                underlying_price, expiry_date, contract_month, source_name, atm_strike,
                expected_level_count, observed_level_count, freshness_state, created_at
            )
            VALUES (?, '2026-05-12', ?, 'KRX', 'KOSPI200', 'KOSPI200',
                    392.1, '202605', '202605', 'KIS_DOMESTIC_DERIVATIVES', 392.5,
                    2, 2, 'fresh', ?)
            """,
            (option_run_id, previous_snapshot_time, utcnow_iso()),
        ).lastrowid
        connection.executemany(
            """
            INSERT INTO argus_v2_option_chain_levels (
                snapshot_id, strike_price, moneyness, call_open_interest, put_open_interest,
                total_open_interest, net_call_put_oi, call_put_oi_ratio, pressure_side, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (previous_option_snapshot_id, 390.0, "ITM", 1000, 2000, 3000, -1000, 0.50, "PUT", utcnow_iso()),
                (previous_option_snapshot_id, 395.0, "OTM", 500, 500, 1000, 0, 1.00, "BALANCED", utcnow_iso()),
            ],
        )
        option_snapshot_id = connection.execute(
            """
            INSERT INTO argus_v2_option_chain_snapshots (
                run_id, trade_date, snapshot_time, market_scope, underlying_code, underlying_name,
                underlying_price, expiry_date, contract_month, source_name, atm_strike,
                expected_level_count, observed_level_count, freshness_state, created_at
            )
            VALUES (?, '2026-05-12', ?, 'KRX', 'KOSPI200', 'KOSPI200',
                    392.4, '202605', '202605', 'KIS_DOMESTIC_DERIVATIVES', 392.5,
                    2, 2, 'fresh', ?)
            """,
            (option_run_id, snapshot_time, utcnow_iso()),
        ).lastrowid
        connection.executemany(
            """
            INSERT INTO argus_v2_option_chain_levels (
                snapshot_id, strike_price, moneyness, call_open_interest, put_open_interest,
                total_open_interest, net_call_put_oi, call_put_oi_ratio, pressure_side, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (option_snapshot_id, 390.0, "ITM", 1000, 3000, 4000, -2000, 0.33, "PUT", utcnow_iso()),
                (option_snapshot_id, 395.0, "OTM", 500, 700, 1200, -200, 0.71, "PUT", utcnow_iso()),
            ],
        )
        reaction_snapshot_id = connection.execute(
            """
            INSERT INTO argus_v2_market_reaction_snapshots (
                run_id, trade_date, snapshot_time, source_name, kospi_change_rate, kosdaq_change_rate,
                kospi200_futures_change_rate, advancing_count, declining_count,
                spot_foreign_net_buy, spot_institution_net_buy, spot_individual_net_buy, summary,
                freshness_state, created_at
            )
            VALUES (?, '2026-05-12', ?, 'mock.market.reaction', -0.64, 0.18,
                    -1.23, 410, 522, -82000000000, 34000000000, 48000000000,
                    '현물은 약하지만 반도체가 낙폭을 제한합니다.', 'fresh', ?)
            """,
            (reaction_run_id, snapshot_time, utcnow_iso()),
        ).lastrowid
        connection.executemany(
            """
            INSERT INTO argus_v2_market_reaction_sectors (
                snapshot_id, role, name, change_rate, reason, tone, source_name, observed_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    reaction_snapshot_id,
                    "strong",
                    "반도체",
                    1.25,
                    "AI 반도체 강세",
                    "positive",
                    "mock.market.reaction",
                    snapshot_time,
                    utcnow_iso(),
                ),
                (
                    reaction_snapshot_id,
                    "weak",
                    "금융",
                    -0.72,
                    "금리 변동성 부담",
                    "negative",
                    "mock.market.reaction",
                    snapshot_time,
                    utcnow_iso(),
                ),
            ],
        )
        connection.executemany(
            """
            INSERT INTO argus_v2_news_triggers (
                run_id, external_id, title, summary, impact, source_name, published_at,
                connection_strength, freshness_state, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    trigger_run_id,
                    "rates",
                    "미국 금리 상승",
                    "밤사이 금리 상승은 위험자산에 부담입니다.",
                    "negative",
                    "mock.news.macro",
                    "2026-05-12T02:00:00Z",
                    "medium",
                    "fresh",
                    utcnow_iso(),
                ),
                (
                    trigger_run_id,
                    "chip",
                    "반도체 강세",
                    "반도체가 지수 낙폭을 일부 제한합니다.",
                    "positive",
                    "mock.news.sector",
                    "2026-05-12T02:01:00Z",
                    "strong",
                    "fresh",
                    utcnow_iso(),
                ),
            ],
        )

    response = _get_dashboard(db_path)

    assert response.status_code == 200
    data = response.json()
    assert data["as_of"] == snapshot_time
    assert data["triggers"][0]["id"] == "chip"
    assert data["triggers"][1]["impact"] == "negative"
    assert data["derivatives"]["kospi200_futures_change_rate"]["value"] == -1.23
    assert data["derivatives"]["kospi200_futures_change_rate"]["freshness"] == "fresh"
    assert data["derivatives"]["basis"]["value"] == -0.4
    assert round(data["derivatives"]["open_interest_change_rate"]["value"], 2) == 30.0
    assert data["derivatives"]["open_interest_change_rate"]["source"] == "argus_v2.option_chain_comparison"
    assert "옵션 OI 변화는 PUT 우위" in data["derivatives"]["summary"]
    assert data["derivatives"]["foreign_futures_net_buy"]["freshness"] == "missing"
    assert data["derivatives"]["option_pressure"] == "PUT"
    assert round(data["derivatives"]["put_call_ratio"]["value"], 2) == 2.47
    assert data["derivatives"]["key_levels"][0]["role"] == "atm"
    assert data["reaction"]["strong_sectors"][0]["name"] == "반도체"
    assert data["reaction"]["kospi_change_rate"]["value"] == -0.64
    assert data["reaction"]["kospi_change_rate"]["freshness"] == "fresh"
    assert data["reaction"]["spot_foreign_net_buy"]["value"] == -82_000_000_000
    assert data["reaction"]["spot_institution_net_buy"]["value"] == 34_000_000_000
    assert data["reaction"]["spot_individual_net_buy"]["value"] == 48_000_000_000
    assert data["judgement"]["label"] == "강한 하방"
    assert data["judgement"]["primary_driver"] == "옵션 미결제약정 PUT 우위"
    assert "외국인" not in data["judgement"]["summary"]
    assert data["provider_health"][0]["key"] == "kis_derivatives"
    assert data["provider_health"][0]["status"] == "fresh"
    assert data["provider_health"][1]["key"] == "kis_option_chain"
    assert data["provider_health"][1]["observed_count"] == 2
    assert data["provider_health"][2]["key"] == "v2_market_reaction"
    assert data["provider_health"][2]["status"] == "fresh"
    assert data["provider_health"][3]["key"] == "v2_news_triggers"
