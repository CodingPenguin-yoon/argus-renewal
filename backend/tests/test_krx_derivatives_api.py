from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.config.env import get_settings
from src.krx.company_master.db import get_connection, utcnow_iso
from src.main import app


def _insert_derivatives_row(
    db_path: str,
    *,
    trade_date_iso: str,
    source_name: str = "KRX_DERIVATIVES_REFERENCE",
    put_call_ratio: float | None = None,
    implied_volatility: float | None = None,
    open_interest_total: float | None = None,
    call_open_interest: float | None = None,
    put_open_interest: float | None = None,
    futures_foreign_net_buy: float | None = None,
    futures_institution_net_buy: float | None = None,
    futures_individual_net_buy: float | None = None,
    options_foreign_net_buy: float | None = None,
    options_institution_net_buy: float | None = None,
    options_individual_net_buy: float | None = None,
    additional_metrics: dict | None = None,
) -> None:
    now = utcnow_iso()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO derivatives_daily_metrics (
                trade_date,
                source_name,
                metric_scope,
                put_call_ratio,
                implied_volatility,
                open_interest_total,
                call_open_interest,
                put_open_interest,
                futures_investor_foreign_net_buy,
                futures_investor_institution_net_buy,
                futures_investor_individual_net_buy,
                options_investor_foreign_net_buy,
                options_investor_institution_net_buy,
                options_investor_individual_net_buy,
                futures_volume_total,
                options_volume_total,
                additional_metrics_json,
                source_url,
                source_record_id,
                raw_payload_json,
                run_id,
                created_at,
                updated_at
            ) VALUES (?, ?, 'KRX_DERIVATIVES', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                trade_date_iso,
                source_name,
                put_call_ratio,
                implied_volatility,
                open_interest_total,
                call_open_interest,
                put_open_interest,
                futures_foreign_net_buy,
                futures_institution_net_buy,
                futures_individual_net_buy,
                options_foreign_net_buy,
                options_institution_net_buy,
                options_individual_net_buy,
                json.dumps(additional_metrics or {}, ensure_ascii=False),
                "https://data.krx.co.kr/mock",
                f"derivatives-{source_name}-{trade_date_iso}",
                json.dumps({"trade_date": trade_date_iso}, ensure_ascii=False),
                now,
                now,
            ),
        )


def _insert_night_snapshot_row(
    db_path: str,
    *,
    trade_date_iso: str,
    change_rate: float,
) -> None:
    now = utcnow_iso()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO market_intraday_snapshots (
                trade_date,
                snapshot_time,
                session_type,
                source_name,
                instrument_code,
                instrument_name,
                price,
                price_change,
                change_rate,
                volume,
                open_interest,
                put_call_ratio,
                implied_volatility,
                additional_metrics_json,
                source_url,
                source_record_id,
                raw_payload_json,
                run_id,
                created_at,
                updated_at
            ) VALUES (?, ?, 'NIGHT_SESSION', 'KIS_NIGHT_FUTURES', '101S3000', 'KOSPI200 야간선물', 350.0, 1.2, ?, 18000, NULL, NULL, NULL, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                trade_date_iso,
                f"{trade_date_iso}T21:00:00Z",
                change_rate,
                json.dumps({}, ensure_ascii=False),
                "https://kis.mock/night-futures",
                f"night-{trade_date_iso}",
                json.dumps({"trade_date": trade_date_iso}, ensure_ascii=False),
                now,
                now,
            ),
        )


def _insert_pre_open_snapshot_row(
    db_path: str,
    *,
    trade_date_iso: str,
    change_rate: float,
) -> None:
    now = utcnow_iso()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO market_intraday_snapshots (
                trade_date,
                snapshot_time,
                session_type,
                source_name,
                instrument_code,
                instrument_name,
                price,
                price_change,
                change_rate,
                volume,
                open_interest,
                put_call_ratio,
                implied_volatility,
                additional_metrics_json,
                source_url,
                source_record_id,
                raw_payload_json,
                run_id,
                created_at,
                updated_at
            ) VALUES (?, ?, 'PRE_OPEN', 'KIS_DOMESTIC_DERIVATIVES', '101S3000', 'KOSPI200 선물', 351.2, 0.9, ?, 15000, NULL, NULL, NULL, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                trade_date_iso,
                f"{trade_date_iso}T08:40:00Z",
                change_rate,
                json.dumps({}, ensure_ascii=False),
                "https://kis.mock/pre-open",
                f"pre-open-{trade_date_iso}",
                json.dumps({"trade_date": trade_date_iso}, ensure_ascii=False),
                now,
                now,
            ),
        )


def _insert_market_briefing_row(
    db_path: str,
    *,
    trade_date_iso: str,
    directional_bias: str,
    gap_bias: str,
    volatility_bias: str,
    confidence_bucket: str,
    explanation_ko: str,
) -> int:
    now = utcnow_iso()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO market_briefings (
                trade_date,
                market_scope,
                run_mode,
                directional_bias,
                gap_bias,
                volatility_bias,
                confidence_bucket,
                total_score,
                volatility_score,
                explanation_ko,
                json_payload,
                markdown_summary,
                notification_payload_json,
                rule_config_json,
                input_snapshot_json,
                generated_at,
                created_at,
                updated_at
            ) VALUES (?, 'KRX', 'MANUAL', ?, ?, ?, ?, 2.5, 0.8, ?, ?, ?, NULL, NULL, ?, ?, ?, ?)
            """,
            (
                trade_date_iso,
                directional_bias,
                gap_bias,
                volatility_bias,
                confidence_bucket,
                explanation_ko,
                json.dumps({"trade_date": trade_date_iso}, ensure_ascii=False),
                f"briefing {trade_date_iso}",
                json.dumps({}, ensure_ascii=False),
                now,
                now,
                now,
            ),
        )
        row = connection.execute(
            """
            SELECT id
            FROM market_briefings
            WHERE trade_date = ? AND market_scope = 'KRX'
            """,
            (trade_date_iso,),
        ).fetchone()
        assert row is not None
        briefing_id = int(row["id"])
        connection.execute(
            """
            INSERT INTO market_signal_components (
                briefing_id,
                trade_date,
                market_scope,
                component_key,
                component_label,
                component_group,
                raw_value,
                reference_value,
                delta_value,
                score,
                volatility_score,
                weight,
                data_available,
                source_table,
                source_name,
                source_url,
                source_record_id,
                source_metric_key,
                threshold_json,
                metadata_json,
                explanation_ko,
                created_at,
                updated_at
            ) VALUES (?, ?, 'KRX', 'put_call_ratio_pressure', 'Put/Call 비율 압력', 'directional', 0.92, 1.00, -0.08, 0.8, 0.0, 1.0, 1, 'derivatives_daily_metrics', 'KRX_DERIVATIVES_REFERENCE', 'https://data.krx.co.kr/mock', 'mock-row', 'put_call_ratio', ?, ?, ?, ?, ?)
            """,
            (
                briefing_id,
                trade_date_iso,
                json.dumps({"bullish_threshold": 0.9}, ensure_ascii=False),
                json.dumps({"delta_pct": -8.0}, ensure_ascii=False),
                "Put/Call 비율이 개선되어 점수를 반영했습니다.",
                now,
                now,
            ),
        )
        return briefing_id


def _with_db(monkeypatch, tmp_path: Path) -> str:
    db_path = str(tmp_path / "derivatives-api.db")
    monkeypatch.setenv("DB_PATH", db_path)
    get_settings.cache_clear()
    return db_path


def test_summary_endpoint_with_full_data(tmp_path: Path, monkeypatch) -> None:
    db_path = _with_db(monkeypatch, tmp_path)
    try:
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-08",
            put_call_ratio=1.02,
            implied_volatility=19.6,
            open_interest_total=990000,
            call_open_interest=495000,
            put_open_interest=495000,
            futures_foreign_net_buy=200,
            futures_institution_net_buy=-100,
        )
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-09",
            put_call_ratio=0.92,
            implied_volatility=17.4,
            open_interest_total=1040000,
            call_open_interest=560000,
            put_open_interest=480000,
            futures_foreign_net_buy=1800,
            futures_institution_net_buy=900,
            futures_individual_net_buy=-400,
            options_foreign_net_buy=300,
            options_institution_net_buy=-50,
            options_individual_net_buy=-250,
            additional_metrics={
                "call_notional": 4200000000000,
                "put_notional": 3300000000000,
                "expiry_summary": [
                    {"expiry": "2026-03", "call_oi": 220000, "put_oi": 190000},
                ],
            },
        )
        _insert_pre_open_snapshot_row(db_path, trade_date_iso="2026-03-09", change_rate=0.34)
        _insert_night_snapshot_row(db_path, trade_date_iso="2026-03-09", change_rate=0.61)
        _insert_market_briefing_row(
            db_path,
            trade_date_iso="2026-03-09",
            directional_bias="bullish",
            gap_bias="gap_up",
            volatility_bias="stable",
            confidence_bucket="high",
            explanation_ko="기존 브리핑 해석을 사용합니다.",
        )

        client = TestClient(app)
        response = client.get("/api/krx/derivatives/summary", params={"date": "2026-03-09"})
        assert response.status_code == 200
        item = response.json()["item"]

        assert item["date"] == "2026-03-09"
        assert item["pcr"] == 0.92
        assert item["pcr_change"] is not None
        assert item["call_notional"] == 4200000000000.0
        assert item["put_notional"] == 3300000000000.0
        assert item["detail_level"] == 3
        assert item["briefing_source"] == "market_briefings"
        assert item["directional_bias"] == "bullish"
        assert item["pre_open_futures"]["signal"] == "gap_up"
        assert item["pre_open_futures"]["source_name"] == "KIS_DOMESTIC_DERIVATIVES"
        assert item["night_futures"]["signal"] == "gap_up"
        assert "call_notional" not in item["missing_fields"]
        assert len(item["source_coverage"]["sections"]) >= 5
        assert "KIS_DOMESTIC_DERIVATIVES" in item["source_coverage"]["source_names"]
        comparison_map = {
            comparison["key"]: comparison for comparison in item["source_coverage"]["comparisons"]
        }
        assert comparison_map["pcr_change"]["current_source_name"] == "KRX_DERIVATIVES_REFERENCE"
        assert comparison_map["pcr_change"]["previous_source_name"] == "KRX_DERIVATIVES_REFERENCE"
        assert comparison_map["pcr_change"]["mixed_source"] is False
    finally:
        get_settings.cache_clear()


def test_summary_endpoint_with_partial_data(tmp_path: Path, monkeypatch) -> None:
    db_path = _with_db(monkeypatch, tmp_path)
    try:
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-09",
            put_call_ratio=1.11,
            implied_volatility=None,
            open_interest_total=1010000,
            call_open_interest=500000,
            put_open_interest=510000,
            futures_foreign_net_buy=None,
            futures_institution_net_buy=None,
        )

        client = TestClient(app)
        response = client.get("/api/krx/derivatives/summary", params={"date": "2026-03-09"})
        assert response.status_code == 200
        item = response.json()["item"]

        assert item["date"] == "2026-03-09"
        assert item["briefing_source"] == "rule_based"
        assert item["detail_level"] == 1
        assert item["pre_open_futures"]["signal"] is None
        assert item["night_futures"]["signal"] is None
        assert "call_notional" in item["missing_fields"]
        assert "foreign_futures_net_position" in item["missing_fields"]
    finally:
        get_settings.cache_clear()


def test_trends_endpoint_shape(tmp_path: Path, monkeypatch) -> None:
    db_path = _with_db(monkeypatch, tmp_path)
    try:
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-07",
            put_call_ratio=1.01,
            implied_volatility=20.1,
            call_open_interest=490000,
            put_open_interest=500000,
        )
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-08",
            put_call_ratio=0.98,
            implied_volatility=19.3,
            call_open_interest=505000,
            put_open_interest=495000,
        )
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-09",
            put_call_ratio=0.94,
            implied_volatility=17.8,
            call_open_interest=520000,
            put_open_interest=480000,
        )

        client = TestClient(app)
        response = client.get("/api/krx/derivatives/trends", params={"preset": "20d"})
        assert response.status_code == 200
        payload = response.json()

        assert payload["preset"] == "20d"
        assert isinstance(payload["items"], list)
        assert len(payload["items"]) == 3
        assert payload["items"][0]["date"] == "2026-03-07"
        assert set(payload["items"][0].keys()) >= {
            "date",
            "pcr",
            "call_open_interest",
            "put_open_interest",
            "implied_volatility",
        }
    finally:
        get_settings.cache_clear()


def test_existing_data_reuse_priority_prefers_manual_override(tmp_path: Path, monkeypatch) -> None:
    db_path = _with_db(monkeypatch, tmp_path)
    try:
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-09",
            source_name="KRX_DERIVATIVES_MANUAL",
            put_call_ratio=1.34,
        )
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-09",
            source_name="KRX_DERIVATIVES_REFERENCE",
            put_call_ratio=0.87,
        )

        client = TestClient(app)
        response = client.get("/api/krx/derivatives/summary", params={"date": "2026-03-09"})
        assert response.status_code == 200
        item = response.json()["item"]
        assert item["pcr"] == 1.34
        assert item["source_coverage"]["sections"][0]["source_name"] == "KRX_DERIVATIVES_MANUAL"
    finally:
        get_settings.cache_clear()


def test_same_day_summary_prefers_kis_over_krx_reference(tmp_path: Path, monkeypatch) -> None:
    db_path = _with_db(monkeypatch, tmp_path)
    try:
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-09",
            source_name="KRX_DERIVATIVES_REFERENCE",
            put_call_ratio=0.87,
        )
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-09",
            source_name="KIS_DOMESTIC_DERIVATIVES",
            put_call_ratio=0.94,
        )

        client = TestClient(app)
        response = client.get("/api/krx/derivatives/summary", params={"date": "2026-03-09"})
        assert response.status_code == 200
        item = response.json()["item"]
        assert item["pcr"] == 0.94
        assert item["source_coverage"]["sections"][0]["source_name"] == "KIS_DOMESTIC_DERIVATIVES"
    finally:
        get_settings.cache_clear()


def test_trends_endpoint_prefers_priority_row_per_date(tmp_path: Path, monkeypatch) -> None:
    db_path = _with_db(monkeypatch, tmp_path)
    try:
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-08",
            source_name="KRX_DERIVATIVES_REFERENCE",
            put_call_ratio=1.08,
            implied_volatility=20.8,
            call_open_interest=490000,
            put_open_interest=510000,
        )
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-08",
            source_name="KIS_DOMESTIC_DERIVATIVES",
            put_call_ratio=0.96,
            implied_volatility=18.6,
            call_open_interest=520000,
            put_open_interest=480000,
        )
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-09",
            source_name="KRX_DERIVATIVES_REFERENCE",
            put_call_ratio=0.93,
            implied_volatility=17.9,
            call_open_interest=530000,
            put_open_interest=470000,
        )

        client = TestClient(app)
        response = client.get("/api/krx/derivatives/trends", params={"preset": "20d"})
        assert response.status_code == 200
        payload = response.json()

        item_by_date = {item["date"]: item for item in payload["items"]}
        assert item_by_date["2026-03-08"]["pcr"] == 0.96
        assert item_by_date["2026-03-08"]["source_name"] == "KIS_DOMESTIC_DERIVATIVES"
        assert item_by_date["2026-03-09"]["pcr"] == 0.93
    finally:
        get_settings.cache_clear()


def test_summary_source_coverage_flags_mixed_source_deltas(tmp_path: Path, monkeypatch) -> None:
    db_path = _with_db(monkeypatch, tmp_path)
    try:
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-08",
            source_name="KRX_DERIVATIVES_REFERENCE",
            put_call_ratio=1.08,
            implied_volatility=20.3,
            open_interest_total=995000,
            call_open_interest=500000,
            put_open_interest=495000,
        )
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-09",
            source_name="KIS_DOMESTIC_DERIVATIVES",
            put_call_ratio=0.97,
            implied_volatility=18.4,
            open_interest_total=1032000,
            call_open_interest=535000,
            put_open_interest=497000,
        )

        client = TestClient(app)
        response = client.get("/api/krx/derivatives/summary", params={"date": "2026-03-09"})
        assert response.status_code == 200
        item = response.json()["item"]

        comparison_map = {
            comparison["key"]: comparison for comparison in item["source_coverage"]["comparisons"]
        }
        assert comparison_map["pcr_change"]["current_source_name"] == "KIS_DOMESTIC_DERIVATIVES"
        assert comparison_map["pcr_change"]["previous_source_name"] == "KRX_DERIVATIVES_REFERENCE"
        assert comparison_map["pcr_change"]["mixed_source"] is True
        assert comparison_map["pcr_change"]["status"] == "available"
    finally:
        get_settings.cache_clear()


def test_summary_endpoint_falls_back_to_kis_domestic_daily_metrics(tmp_path: Path, monkeypatch) -> None:
    db_path = _with_db(monkeypatch, tmp_path)
    try:
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-09",
            source_name="KIS_DOMESTIC_DERIVATIVES",
            put_call_ratio=0.97,
            implied_volatility=17.9,
            open_interest_total=1015000,
            call_open_interest=540000,
            put_open_interest=475000,
            futures_foreign_net_buy=1450,
            futures_institution_net_buy=620,
            futures_individual_net_buy=-2070,
        )
        _insert_pre_open_snapshot_row(db_path, trade_date_iso="2026-03-09", change_rate=0.34)

        client = TestClient(app)
        response = client.get("/api/krx/derivatives/summary", params={"date": "2026-03-09"})
        assert response.status_code == 200
        item = response.json()["item"]

        assert item["pcr"] == 0.97
        assert item["pre_open_futures"]["signal"] == "gap_up"
        assert item["source_coverage"]["sections"][0]["source_name"] == "KIS_DOMESTIC_DERIVATIVES"
        assert "KIS_DOMESTIC_DERIVATIVES" in item["source_coverage"]["source_names"]
    finally:
        get_settings.cache_clear()


def test_no_llm_deterministic_briefing_path(tmp_path: Path, monkeypatch) -> None:
    db_path = _with_db(monkeypatch, tmp_path)
    try:
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-09",
            put_call_ratio=0.89,
            implied_volatility=16.8,
            open_interest_total=1120000,
            call_open_interest=570000,
            put_open_interest=500000,
            futures_foreign_net_buy=1300,
            futures_institution_net_buy=300,
        )
        _insert_night_snapshot_row(db_path, trade_date_iso="2026-03-09", change_rate=0.48)

        client = TestClient(app)
        response = client.get("/api/krx/derivatives/briefing", params={"date": "2026-03-09"})
        assert response.status_code == 200
        item = response.json()["item"]

        assert item["briefing_source"] == "rule_based"
        assert item["directional_bias"] in {"bullish", "neutral", "bearish"}
        assert "정보 제공 목적" in item["explanation_text"]
        assert len(item["components"]) >= 1
    finally:
        get_settings.cache_clear()
