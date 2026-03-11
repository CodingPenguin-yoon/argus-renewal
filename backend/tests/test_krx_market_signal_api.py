from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.config.env import get_settings
from src.krx.company_master.db import get_connection, utcnow_iso
from src.main import app


def _with_db(monkeypatch, tmp_path: Path) -> str:
    db_path = str(tmp_path / "market-signal-api.db")
    monkeypatch.setenv("DB_PATH", db_path)
    get_settings.cache_clear()
    return db_path


def _insert_daily_factor_row(
    db_path: str,
    *,
    trade_date_iso: str,
    foreign_net_buy: float | None = None,
    institution_net_buy: float | None = None,
    individual_net_buy: float | None = None,
    program_net_total: float | None = None,
    credit_balance_total: float | None = None,
) -> None:
    now = utcnow_iso()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO market_daily_factors (
                trade_date,
                source_name,
                market_scope,
                investor_individual_net_buy,
                investor_foreign_net_buy,
                investor_institution_net_buy,
                investor_other_net_buy,
                investor_bank_net_buy,
                investor_pension_net_buy,
                program_buy_total,
                program_sell_total,
                program_net_total,
                credit_balance_total,
                margin_loan_balance,
                stock_financing_balance,
                securities_lending_balance,
                additional_metrics_json,
                source_url,
                source_record_id,
                raw_payload_json,
                run_id,
                created_at,
                updated_at
            ) VALUES (?, 'KIS_MARKET_BREADTH', 'KRX', ?, ?, ?, NULL, NULL, NULL, NULL, NULL, ?, ?, NULL, NULL, NULL, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                trade_date_iso,
                individual_net_buy,
                foreign_net_buy,
                institution_net_buy,
                program_net_total,
                credit_balance_total,
                json.dumps({}, ensure_ascii=False),
                "https://kis.mock/market-breadth",
                f"daily-{trade_date_iso}",
                json.dumps({"trade_date": trade_date_iso}, ensure_ascii=False),
                now,
                now,
            ),
        )


def _insert_derivatives_row(
    db_path: str,
    *,
    trade_date_iso: str,
    put_call_ratio: float | None = None,
    implied_volatility: float | None = None,
    open_interest_total: float | None = None,
    call_open_interest: float | None = None,
    put_open_interest: float | None = None,
    futures_foreign_net_buy: float | None = None,
    futures_institution_net_buy: float | None = None,
    futures_individual_net_buy: float | None = None,
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
            ) VALUES (?, 'KRX_DERIVATIVES_REFERENCE', 'KRX_DERIVATIVES', ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                trade_date_iso,
                put_call_ratio,
                implied_volatility,
                open_interest_total,
                call_open_interest,
                put_open_interest,
                futures_foreign_net_buy,
                futures_institution_net_buy,
                futures_individual_net_buy,
                json.dumps({}, ensure_ascii=False),
                "https://krx.mock/derivatives",
                f"derivatives-{trade_date_iso}",
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


def _insert_market_briefing_row(
    db_path: str,
    *,
    trade_date_iso: str,
    explanation_ko: str,
) -> None:
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
            ) VALUES (?, 'KRX', 'MANUAL', 'bullish', 'gap_up', 'stable', 'high', 2.8, 0.4, ?, ?, ?, NULL, NULL, ?, ?, ?, ?)
            """,
            (
                trade_date_iso,
                explanation_ko,
                json.dumps({"trade_date": trade_date_iso}, ensure_ascii=False),
                f"briefing {trade_date_iso}",
                json.dumps({}, ensure_ascii=False),
                now,
                now,
                now,
            ),
        )
        briefing_id = connection.execute(
            """
            SELECT id
            FROM market_briefings
            WHERE trade_date = ? AND market_scope = 'KRX'
            """,
            (trade_date_iso,),
        ).fetchone()["id"]
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
            ) VALUES (?, ?, 'KRX', 'put_call_ratio_pressure', 'Put/Call 비율 압력', 'directional', 0.91, 1.00, -0.09, 0.9, 0.0, 1.0, 1, 'derivatives_daily_metrics', 'KRX_DERIVATIVES_REFERENCE', 'https://krx.mock/derivatives', 'component-row', 'put_call_ratio', ?, ?, ?, ?, ?)
            """,
            (
                briefing_id,
                trade_date_iso,
                json.dumps({"bullish_threshold": 0.9}, ensure_ascii=False),
                json.dumps({"delta_pct": -9.0}, ensure_ascii=False),
                "Put/Call 비율 개선을 반영했습니다.",
                now,
                now,
            ),
        )


def test_market_signal_summary_full_response(tmp_path: Path, monkeypatch) -> None:
    db_path = _with_db(monkeypatch, tmp_path)
    try:
        _insert_daily_factor_row(
            db_path,
            trade_date_iso="2026-03-08",
            foreign_net_buy=1200,
            institution_net_buy=400,
            individual_net_buy=-1600,
            program_net_total=180,
            credit_balance_total=10000000000000,
        )
        _insert_daily_factor_row(
            db_path,
            trade_date_iso="2026-03-09",
            foreign_net_buy=3400,
            institution_net_buy=1200,
            individual_net_buy=-4600,
            program_net_total=700,
            credit_balance_total=10150000000000,
        )
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-08",
            put_call_ratio=1.03,
            implied_volatility=18.9,
            open_interest_total=980000,
            call_open_interest=480000,
            put_open_interest=500000,
            futures_foreign_net_buy=300,
            futures_institution_net_buy=-200,
        )
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-09",
            put_call_ratio=0.91,
            implied_volatility=17.1,
            open_interest_total=1030000,
            call_open_interest=550000,
            put_open_interest=480000,
            futures_foreign_net_buy=1800,
            futures_institution_net_buy=600,
            futures_individual_net_buy=-2400,
        )
        _insert_night_snapshot_row(db_path, trade_date_iso="2026-03-09", change_rate=0.55)
        _insert_market_briefing_row(
            db_path,
            trade_date_iso="2026-03-09",
            explanation_ko="저장된 브리핑 설명을 우선 사용합니다.",
        )

        client = TestClient(app)
        response = client.get("/api/krx/market-signal/summary", params={"date": "2026-03-09"})

        assert response.status_code == 200
        item = response.json()["item"]
        assert item["date"] == "2026-03-09"
        assert item["explanation_source"] == "market_briefings"
        assert item["source_coverage"]["state"] in {"full", "partial"}
        assert len(item["cards"]) == 4
        assert item["cards"][0]["title"] == "오늘 시장 결론"
        assert item["cards"][1]["title"] == "자금 흐름"
        assert item["cards"][2]["title"] == "선물·옵션 신호"
        assert item["cards"][0]["supporting_metrics"][0]["label"] == "외국인+기관 현물"
        assert item["cards"][2]["supporting_metrics"][0]["label"] == "PCR"
        assert item["cards"][0]["source_coverage"]["coverage_ratio"] > 0
    finally:
        get_settings.cache_clear()


def test_market_signal_summary_partial_provider_coverage(tmp_path: Path, monkeypatch) -> None:
    db_path = _with_db(monkeypatch, tmp_path)
    try:
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-09",
            put_call_ratio=1.09,
            implied_volatility=20.4,
            open_interest_total=1005000,
            call_open_interest=500000,
            put_open_interest=505000,
            futures_foreign_net_buy=-900,
        )

        client = TestClient(app)
        response = client.get("/api/krx/market-signal/summary", params={"date": "2026-03-09"})

        assert response.status_code == 200
        item = response.json()["item"]
        assert item["date"] == "2026-03-09"
        assert item["source_coverage"]["state"] == "partial"
        assert "program_net_total" in item["missing_fields"]
        assert "credit_balance_total" in item["missing_fields"]
        assert item["cards"][1]["source_coverage"]["state"] in {"missing", "partial"}
    finally:
        get_settings.cache_clear()


def test_market_signal_summary_rule_based_explanation_fallback(tmp_path: Path, monkeypatch) -> None:
    db_path = _with_db(monkeypatch, tmp_path)
    try:
        _insert_daily_factor_row(
            db_path,
            trade_date_iso="2026-03-09",
            foreign_net_buy=500,
            institution_net_buy=300,
            individual_net_buy=-800,
            program_net_total=120,
            credit_balance_total=10080000000000,
        )
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-09",
            put_call_ratio=0.94,
            implied_volatility=16.8,
            open_interest_total=1110000,
            call_open_interest=560000,
            put_open_interest=500000,
            futures_foreign_net_buy=1300,
            futures_institution_net_buy=300,
        )
        _insert_night_snapshot_row(db_path, trade_date_iso="2026-03-09", change_rate=0.42)

        client = TestClient(app)
        response = client.get("/api/krx/market-signal/summary", params={"date": "2026-03-09"})

        assert response.status_code == 200
        item = response.json()["item"]
        assert item["explanation_source"] == "rule_based"
        assert "정보 제공 목적" in item["explanation_text"]
        assert item["cards"][0]["interpretation_line"]
    finally:
        get_settings.cache_clear()


def test_market_signal_trends_api_shape(tmp_path: Path, monkeypatch) -> None:
    db_path = _with_db(monkeypatch, tmp_path)
    try:
        _insert_daily_factor_row(
            db_path,
            trade_date_iso="2026-03-07",
            foreign_net_buy=300,
            institution_net_buy=100,
            individual_net_buy=-400,
            program_net_total=40,
            credit_balance_total=10000000000000,
        )
        _insert_daily_factor_row(
            db_path,
            trade_date_iso="2026-03-08",
            foreign_net_buy=500,
            institution_net_buy=150,
            individual_net_buy=-650,
            program_net_total=80,
            credit_balance_total=10020000000000,
        )
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-08",
            put_call_ratio=0.98,
            implied_volatility=18.2,
            open_interest_total=1005000,
            call_open_interest=510000,
            put_open_interest=495000,
            futures_foreign_net_buy=900,
        )
        _insert_night_snapshot_row(db_path, trade_date_iso="2026-03-08", change_rate=0.18)
        _insert_daily_factor_row(
            db_path,
            trade_date_iso="2026-03-09",
            foreign_net_buy=1200,
            institution_net_buy=300,
            individual_net_buy=-1500,
            program_net_total=180,
            credit_balance_total=10060000000000,
        )
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-09",
            put_call_ratio=0.93,
            implied_volatility=17.4,
            open_interest_total=1030000,
            call_open_interest=535000,
            put_open_interest=495000,
            futures_foreign_net_buy=1700,
        )
        _insert_night_snapshot_row(db_path, trade_date_iso="2026-03-09", change_rate=0.52)

        client = TestClient(app)
        response = client.get("/api/krx/market-signal/trends", params={"preset": "20d"})

        assert response.status_code == 200
        payload = response.json()
        assert payload["preset"] == "20d"
        assert len(payload["items"]) == 3
        assert set(payload["items"][0].keys()) >= {
            "date",
            "foreign_net_buy",
            "program_net_total",
            "credit_balance_total",
            "futures_foreign_net_buy",
            "pcr",
            "night_futures_change_rate",
        }
    finally:
        get_settings.cache_clear()
