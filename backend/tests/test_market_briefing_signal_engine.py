from __future__ import annotations

from datetime import date
import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.config.env import get_settings
from src.krx.company_master.db import get_connection, utcnow_iso
from src.krx.source_ingestion.briefing_signal_service import MarketBriefingSignalService
from src.main import app


def _insert_derivatives_row(
    db_path: str,
    *,
    trade_date_iso: str,
    put_call_ratio: float | None,
    implied_volatility: float | None,
    open_interest_total: float | None,
    futures_foreign_net_buy: float | None,
    futures_institution_net_buy: float | None,
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
                futures_investor_foreign_net_buy,
                futures_investor_institution_net_buy,
                additional_metrics_json,
                source_url,
                source_record_id,
                raw_payload_json,
                run_id,
                created_at,
                updated_at
            ) VALUES (?, ?, 'KRX_DERIVATIVES', ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                trade_date_iso,
                "KRX_DERIVATIVES_REFERENCE",
                put_call_ratio,
                implied_volatility,
                open_interest_total,
                futures_foreign_net_buy,
                futures_institution_net_buy,
                json.dumps({}, ensure_ascii=False),
                "https://data.krx.co.kr/mock",
                f"derivatives-{trade_date_iso}",
                json.dumps({"trade_date": trade_date_iso}, ensure_ascii=False),
                now,
                now,
            ),
        )


def _insert_daily_factor_row(
    db_path: str,
    *,
    trade_date_iso: str,
    credit_balance_total: float | None,
) -> None:
    now = utcnow_iso()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO market_daily_factors (
                trade_date,
                source_name,
                market_scope,
                credit_balance_total,
                additional_metrics_json,
                source_url,
                source_record_id,
                raw_payload_json,
                run_id,
                created_at,
                updated_at
            ) VALUES (?, 'KIS_MARKET_BREADTH', 'KRX', ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                trade_date_iso,
                credit_balance_total,
                json.dumps({}, ensure_ascii=False),
                "https://kis.mock/market-breadth",
                f"breadth-{trade_date_iso}",
                json.dumps({"trade_date": trade_date_iso}, ensure_ascii=False),
                now,
                now,
            ),
        )


def _insert_night_snapshot_row(
    db_path: str,
    *,
    trade_date_iso: str,
    change_rate: float | None,
    source_name: str = "KIS_NIGHT_FUTURES",
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
                change_rate,
                volume,
                additional_metrics_json,
                source_url,
                source_record_id,
                raw_payload_json,
                run_id,
                created_at,
                updated_at
            ) VALUES (?, ?, 'NIGHT_SESSION', ?, '101S3000', 'KOSPI200 야간선물', ?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                trade_date_iso,
                f"{trade_date_iso}T21:00:00Z",
                source_name,
                change_rate,
                10000,
                json.dumps({}, ensure_ascii=False),
                "https://kis.mock/night-futures",
                f"night-{trade_date_iso}",
                json.dumps({"trade_date": trade_date_iso}, ensure_ascii=False),
                now,
                now,
            ),
        )


def _build_service(tmp_path: Path, *, rules_json: str | None = None) -> tuple[MarketBriefingSignalService, str]:
    db_path = str(tmp_path / "briefing-signal.db")
    service = MarketBriefingSignalService(
        db_path=db_path,
        signal_enabled=True,
        market_scope="KRX",
        rules_json=rules_json,
    )
    return service, db_path


def test_bullish_case(tmp_path: Path) -> None:
    service, db_path = _build_service(tmp_path)
    _insert_derivatives_row(
        db_path,
        trade_date_iso="2026-03-08",
        put_call_ratio=1.0,
        implied_volatility=19.0,
        open_interest_total=100000,
        futures_foreign_net_buy=100,
        futures_institution_net_buy=100,
    )
    _insert_derivatives_row(
        db_path,
        trade_date_iso="2026-03-09",
        put_call_ratio=0.86,
        implied_volatility=14.8,
        open_interest_total=118000,
        futures_foreign_net_buy=2100,
        futures_institution_net_buy=1600,
    )
    _insert_daily_factor_row(db_path, trade_date_iso="2026-03-08", credit_balance_total=100000)
    _insert_daily_factor_row(db_path, trade_date_iso="2026-03-09", credit_balance_total=101500)
    _insert_night_snapshot_row(db_path, trade_date_iso="2026-03-09", change_rate=0.82)

    result = service.generate_briefing(trade_date=date(2026, 3, 9), mode="MANUAL")

    assert result.directional_bias == "bullish"
    assert result.gap_bias == "gap_up"
    assert result.total_score > 1.0
    assert len(result.components) == 7


def test_bearish_case(tmp_path: Path) -> None:
    service, db_path = _build_service(tmp_path)
    _insert_derivatives_row(
        db_path,
        trade_date_iso="2026-03-08",
        put_call_ratio=1.0,
        implied_volatility=18.0,
        open_interest_total=100000,
        futures_foreign_net_buy=100,
        futures_institution_net_buy=100,
    )
    _insert_derivatives_row(
        db_path,
        trade_date_iso="2026-03-09",
        put_call_ratio=1.25,
        implied_volatility=28.0,
        open_interest_total=123000,
        futures_foreign_net_buy=-1900,
        futures_institution_net_buy=-1100,
    )
    _insert_daily_factor_row(db_path, trade_date_iso="2026-03-08", credit_balance_total=100000)
    _insert_daily_factor_row(db_path, trade_date_iso="2026-03-09", credit_balance_total=98000)
    _insert_night_snapshot_row(db_path, trade_date_iso="2026-03-09", change_rate=-0.95)

    result = service.generate_briefing(trade_date=date(2026, 3, 9), mode="MANUAL")

    assert result.directional_bias == "bearish"
    assert result.gap_bias == "gap_down"
    assert result.volatility_bias in {"rising", "stable"}
    assert result.total_score < -1.0


def test_mixed_neutral_case(tmp_path: Path) -> None:
    service, db_path = _build_service(tmp_path)
    _insert_derivatives_row(
        db_path,
        trade_date_iso="2026-03-08",
        put_call_ratio=0.98,
        implied_volatility=18.0,
        open_interest_total=100000,
        futures_foreign_net_buy=100,
        futures_institution_net_buy=0,
    )
    _insert_derivatives_row(
        db_path,
        trade_date_iso="2026-03-09",
        put_call_ratio=1.02,
        implied_volatility=18.3,
        open_interest_total=101500,
        futures_foreign_net_buy=150,
        futures_institution_net_buy=-200,
    )
    _insert_daily_factor_row(db_path, trade_date_iso="2026-03-08", credit_balance_total=100000)
    _insert_daily_factor_row(db_path, trade_date_iso="2026-03-09", credit_balance_total=100050)
    _insert_night_snapshot_row(db_path, trade_date_iso="2026-03-09", change_rate=0.03)

    result = service.generate_briefing(trade_date=date(2026, 3, 9), mode="MANUAL")

    assert result.directional_bias == "neutral"
    assert result.gap_bias == "flat"
    assert abs(result.total_score) < 1.0


def test_missing_input_fallback(tmp_path: Path) -> None:
    service, db_path = _build_service(tmp_path)
    _insert_derivatives_row(
        db_path,
        trade_date_iso="2026-03-09",
        put_call_ratio=None,
        implied_volatility=None,
        open_interest_total=None,
        futures_foreign_net_buy=None,
        futures_institution_net_buy=None,
    )

    result = service.generate_briefing(trade_date=date(2026, 3, 9), mode="MANUAL")

    assert result.directional_bias == "neutral"
    assert result.confidence_bucket == "low"
    missing_components = [item for item in result.components if item["data_available"] is False]
    assert len(missing_components) >= 5


def test_markdown_generation(tmp_path: Path) -> None:
    service, db_path = _build_service(tmp_path)
    _insert_derivatives_row(
        db_path,
        trade_date_iso="2026-03-08",
        put_call_ratio=1.0,
        implied_volatility=19.0,
        open_interest_total=100000,
        futures_foreign_net_buy=100,
        futures_institution_net_buy=100,
    )
    _insert_derivatives_row(
        db_path,
        trade_date_iso="2026-03-09",
        put_call_ratio=0.9,
        implied_volatility=16.0,
        open_interest_total=110000,
        futures_foreign_net_buy=500,
        futures_institution_net_buy=400,
    )
    _insert_daily_factor_row(db_path, trade_date_iso="2026-03-08", credit_balance_total=100000)
    _insert_daily_factor_row(db_path, trade_date_iso="2026-03-09", credit_balance_total=100500)
    _insert_night_snapshot_row(db_path, trade_date_iso="2026-03-09", change_rate=0.31)

    result = service.generate_briefing(trade_date=date(2026, 3, 9), mode="MANUAL")
    markdown = result.markdown_summary
    assert "# KRX 08:30 프리마켓 브리핑" in markdown
    assert "## 신호 구성요소" in markdown
    assert "본 브리핑은 정보 제공 목적" in markdown


def test_backtest_record_creation(tmp_path: Path) -> None:
    service, db_path = _build_service(tmp_path)
    _insert_derivatives_row(
        db_path,
        trade_date_iso="2026-03-08",
        put_call_ratio=1.0,
        implied_volatility=18.0,
        open_interest_total=100000,
        futures_foreign_net_buy=100,
        futures_institution_net_buy=100,
    )
    _insert_derivatives_row(
        db_path,
        trade_date_iso="2026-03-09",
        put_call_ratio=0.88,
        implied_volatility=16.0,
        open_interest_total=117000,
        futures_foreign_net_buy=1800,
        futures_institution_net_buy=900,
    )
    _insert_derivatives_row(
        db_path,
        trade_date_iso="2026-03-10",
        put_call_ratio=0.92,
        implied_volatility=17.1,
        open_interest_total=116000,
        futures_foreign_net_buy=200,
        futures_institution_net_buy=150,
    )
    _insert_daily_factor_row(db_path, trade_date_iso="2026-03-08", credit_balance_total=100000)
    _insert_daily_factor_row(db_path, trade_date_iso="2026-03-09", credit_balance_total=101000)
    _insert_night_snapshot_row(db_path, trade_date_iso="2026-03-09", change_rate=0.55)
    _insert_night_snapshot_row(db_path, trade_date_iso="2026-03-10", change_rate=0.48)

    generate_result = service.generate_briefing(trade_date=date(2026, 3, 9), mode="MANUAL")
    backtest_result = service.backtest_briefing(trade_date=date(2026, 3, 9))

    assert backtest_result.briefing_id == generate_result.briefing_id
    assert backtest_result.evaluation_date == "2026-03-10"
    assert backtest_result.confusion_summary["total"] >= 1
    assert "neutral_band" in backtest_result.score_distribution

    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM market_signal_backtests
            WHERE trade_date = '2026-03-09'
            """
        ).fetchone()
    assert row["count"] == 1


def test_signal_briefing_api_happy_path(tmp_path: Path, monkeypatch) -> None:
    db_path = str(tmp_path / "api-briefing.db")
    monkeypatch.setenv("DB_PATH", db_path)
    get_settings.cache_clear()

    try:
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-08",
            put_call_ratio=1.0,
            implied_volatility=19.0,
            open_interest_total=100000,
            futures_foreign_net_buy=100,
            futures_institution_net_buy=100,
        )
        _insert_derivatives_row(
            db_path,
            trade_date_iso="2026-03-09",
            put_call_ratio=0.88,
            implied_volatility=15.2,
            open_interest_total=118000,
            futures_foreign_net_buy=1700,
            futures_institution_net_buy=900,
        )
        _insert_daily_factor_row(db_path, trade_date_iso="2026-03-08", credit_balance_total=100000)
        _insert_daily_factor_row(db_path, trade_date_iso="2026-03-09", credit_balance_total=101200)
        _insert_night_snapshot_row(db_path, trade_date_iso="2026-03-09", change_rate=0.66)

        client = TestClient(app)
        generated = client.post("/api/krx/admin/briefings/generate", params={"trade_date": "2026-03-09"})
        assert generated.status_code == 200
        generated_item = generated.json()["item"]
        assert generated_item["trade_date"] == "2026-03-09"

        latest = client.get("/api/krx/admin/briefings/latest")
        assert latest.status_code == 200
        assert latest.json()["item"] is not None

        history = client.get("/api/krx/admin/briefings/history")
        assert history.status_code == 200
        assert len(history.json()["items"]) >= 1

        components = client.get("/api/krx/admin/briefings/2026-03-09/components")
        assert components.status_code == 200
        assert len(components.json()["items"]) >= 1
    finally:
        get_settings.cache_clear()
