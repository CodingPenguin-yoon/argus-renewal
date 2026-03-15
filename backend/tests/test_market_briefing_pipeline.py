from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path

from src.krx.company_master.db import get_connection
from src.krx.source_ingestion.briefing_service import MarketBriefingInputService
from src.krx.source_ingestion.providers import (
    KisDomesticDerivativesService,
    KisMarketBreadthService,
    KisNightFuturesService,
    KrxDerivativesReferenceService,
)


def _write_json(path: Path, payload: object) -> str:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _make_disabled_breadth() -> KisMarketBreadthService:
    return KisMarketBreadthService(
        provider="disabled",
        file_path=None,
        base_url="https://openapi.koreainvestment.com:9443",
        endpoint_path="/unused",
        app_key=None,
        app_secret=None,
        access_token=None,
    )


def _make_disabled_domestic() -> KisDomesticDerivativesService:
    return KisDomesticDerivativesService(
        provider="disabled",
        file_path=None,
        base_url="https://openapi.koreainvestment.com:9443",
        endpoint_path="/unused",
        app_key=None,
        app_secret=None,
        access_token=None,
    )


def _make_disabled_night() -> KisNightFuturesService:
    return KisNightFuturesService(
        provider="disabled",
        file_path=None,
        base_url="https://openapi.koreainvestment.com:9443",
        endpoint_path="/unused",
        app_key=None,
        app_secret=None,
        access_token=None,
    )


def _make_disabled_krx() -> KrxDerivativesReferenceService:
    return KrxDerivativesReferenceService(
        provider="disabled",
        file_path=None,
        base_url="https://data.krx.co.kr",
        endpoint_path="/unused",
        api_key=None,
    )


def _make_service(
    *,
    db_path: str,
    breadth: KisMarketBreadthService | None = None,
    domestic: KisDomesticDerivativesService | None = None,
    night: KisNightFuturesService | None = None,
    krx: KrxDerivativesReferenceService | None = None,
) -> MarketBriefingInputService:
    return MarketBriefingInputService(
        db_path=db_path,
        kis_market_breadth_service=breadth or _make_disabled_breadth(),
        kis_domestic_derivatives_service=domestic or _make_disabled_domestic(),
        kis_night_futures_service=night or _make_disabled_night(),
        krx_derivatives_reference_service=krx or _make_disabled_krx(),
    )


def test_market_briefing_happy_path_normalized_records(tmp_path: Path) -> None:
    db_path = str(tmp_path / "briefing.db")
    trade_date = date(2026, 3, 9)

    breadth_file = _write_json(
        tmp_path / "breadth.json",
        {
            "trade_date": "2026-03-09",
            "investor_individual_net_buy": -1200,
            "investor_foreign_net_buy": 3400,
            "investor_institution_net_buy": -2200,
            "program_buy_total": 5800,
            "program_sell_total": 5100,
            "program_net_total": 700,
            "credit_balance_total": 123456,
            "margin_loan_balance": 56789,
        },
    )
    domestic_file = _write_json(
        tmp_path / "domestic.json",
        {
            "put_call_ratio": 0.97,
            "implied_volatility": 17.9,
            "open_interest_total": 1015000,
            "call_open_interest": 540000,
            "put_open_interest": 475000,
            "futures_investor_foreign_net_buy": 1450,
            "futures_investor_institution_net_buy": 620,
            "futures_investor_individual_net_buy": -2070,
            "items": [
                {
                    "instrument_code": "101S3000",
                    "instrument_name": "KOSPI200 선물 최근월",
                    "price": 402.15,
                    "price_change": 1.2,
                    "change_rate": 0.3,
                    "volume": 15000,
                    "open_interest": 210000,
                },
                {
                    "instrument_code": "301S4000",
                    "instrument_name": "KOSPI200 콜옵션",
                    "price": 6.35,
                    "price_change": -0.1,
                    "change_rate": -1.5,
                    "volume": 180000,
                    "open_interest": 310000,
                },
            ]
        },
    )
    night_file = _write_json(
        tmp_path / "night.json",
        {
            "items": [
                {
                    "instrument_code": "NQK6",
                    "instrument_name": "KRX 야간선물",
                    "price": 401.6,
                    "price_change": 0.4,
                    "change_rate": 0.1,
                    "volume": 9200,
                    "open_interest": 50000,
                }
            ]
        },
    )
    krx_file = _write_json(
        tmp_path / "krx.json",
        {
            "put_call_ratio": 0.95,
            "implied_volatility": 18.7,
            "open_interest_total": 990000,
            "call_open_interest": 510000,
            "put_open_interest": 480000,
            "futures_investor_foreign_net_buy": 1200,
            "futures_investor_institution_net_buy": -800,
            "futures_investor_individual_net_buy": -400,
        },
    )

    service = _make_service(
        db_path=db_path,
        breadth=KisMarketBreadthService(
            provider="file",
            file_path=breadth_file,
            base_url="https://openapi.koreainvestment.com:9443",
            endpoint_path="/unused",
            app_key=None,
            app_secret=None,
            access_token=None,
        ),
        domestic=KisDomesticDerivativesService(
            provider="file",
            file_path=domestic_file,
            base_url="https://openapi.koreainvestment.com:9443",
            endpoint_path="/unused",
            app_key=None,
            app_secret=None,
            access_token=None,
        ),
        night=KisNightFuturesService(
            provider="file",
            file_path=night_file,
            base_url="https://openapi.koreainvestment.com:9443",
            endpoint_path="/unused",
            app_key=None,
            app_secret=None,
            access_token=None,
        ),
        krx=KrxDerivativesReferenceService(
            provider="file",
            file_path=krx_file,
            base_url="https://data.krx.co.kr",
            endpoint_path="/unused",
            api_key=None,
        ),
    )

    eod_result = service.collect_end_of_day_factors(trade_date=trade_date)
    night_result = service.collect_night_session_snapshots(
        trade_date=trade_date,
        snapshot_time=datetime(2026, 3, 9, 21, 0, tzinfo=timezone.utc),
    )
    preopen_result = service.collect_pre_open_snapshots(
        trade_date=trade_date,
        snapshot_time=datetime(2026, 3, 9, 23, 20, tzinfo=timezone.utc),
    )

    assert eod_result.status == "SUCCESS"
    assert night_result.status == "SUCCESS"
    assert preopen_result.status == "SUCCESS"

    with get_connection(db_path) as connection:
        factor_row = connection.execute(
            """
            SELECT investor_foreign_net_buy, program_net_total, credit_balance_total
            FROM market_daily_factors
            WHERE trade_date = '2026-03-09' AND source_name = 'KIS_MARKET_BREADTH'
            """
        ).fetchone()
        derivatives_row = connection.execute(
            """
            SELECT put_call_ratio, implied_volatility, open_interest_total
            FROM derivatives_daily_metrics
            WHERE trade_date = '2026-03-09' AND source_name = 'KRX_DERIVATIVES_REFERENCE'
            """
        ).fetchone()
        kis_pre_open_row = connection.execute(
            """
            SELECT put_call_ratio, implied_volatility, open_interest_total, futures_investor_foreign_net_buy
            FROM derivatives_daily_metrics
            WHERE trade_date = '2026-03-09' AND source_name = 'KIS_DOMESTIC_DERIVATIVES'
            """
        ).fetchone()
        snapshot_count = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM market_intraday_snapshots
            WHERE trade_date = '2026-03-09'
            """
        ).fetchone()["count"]
        run_count = connection.execute(
            "SELECT COUNT(*) AS count FROM briefing_input_runs"
        ).fetchone()["count"]

    assert factor_row is not None
    assert factor_row["investor_foreign_net_buy"] == 3400
    assert factor_row["program_net_total"] == 700
    assert factor_row["credit_balance_total"] == 123456

    assert derivatives_row is not None
    assert derivatives_row["put_call_ratio"] == 0.95
    assert derivatives_row["implied_volatility"] == 18.7
    assert derivatives_row["open_interest_total"] == 990000
    assert kis_pre_open_row is not None
    assert kis_pre_open_row["put_call_ratio"] == 0.97
    assert kis_pre_open_row["implied_volatility"] == 17.9
    assert kis_pre_open_row["open_interest_total"] == 1015000
    assert kis_pre_open_row["futures_investor_foreign_net_buy"] == 1450

    assert snapshot_count == 3
    assert run_count == 3


def test_market_breadth_field_alias_map_json_support(tmp_path: Path) -> None:
    db_path = str(tmp_path / "briefing.db")
    trade_date = date(2026, 3, 9)
    breadth_file = _write_json(
        tmp_path / "breadth_alias.json",
        {
            "frg_net_amt_custom": 4321,
            "prog_net_amt_custom": 321,
            "credit_bal_custom": 98765,
        },
    )

    service = _make_service(
        db_path=db_path,
        breadth=KisMarketBreadthService(
            provider="file",
            file_path=breadth_file,
            base_url="https://openapi.koreainvestment.com:9443",
            endpoint_path="/unused",
            app_key=None,
            app_secret=None,
            access_token=None,
            field_alias_map_json=json.dumps(
                {
                    "investor_foreign_net_buy": ["frg_net_amt_custom"],
                    "program_net_total": ["prog_net_amt_custom"],
                    "credit_balance_total": ["credit_bal_custom"],
                },
                ensure_ascii=False,
            ),
        ),
        krx=_make_disabled_krx(),
    )

    result = service.collect_end_of_day_factors(trade_date=trade_date)
    assert result.status == "SUCCESS"

    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT investor_foreign_net_buy, program_net_total, credit_balance_total
            FROM market_daily_factors
            WHERE trade_date = '2026-03-09' AND source_name = 'KIS_MARKET_BREADTH'
            """
        ).fetchone()

    assert row is not None
    assert row["investor_foreign_net_buy"] == 4321
    assert row["program_net_total"] == 321
    assert row["credit_balance_total"] == 98765


def test_partial_provider_failure_keeps_successful_provider_data(tmp_path: Path) -> None:
    db_path = str(tmp_path / "briefing.db")

    breadth_file = _write_json(
        tmp_path / "breadth.json",
        {
            "trade_date": "2026-03-09",
            "investor_foreign_net_buy": 1000,
            "program_net_total": 150,
            "credit_balance_total": 777,
        },
    )
    broken_krx_path = tmp_path / "broken_krx.json"
    broken_krx_path.write_text("{broken", encoding="utf-8")

    service = _make_service(
        db_path=db_path,
        breadth=KisMarketBreadthService(
            provider="file",
            file_path=breadth_file,
            base_url="https://openapi.koreainvestment.com:9443",
            endpoint_path="/unused",
            app_key=None,
            app_secret=None,
            access_token=None,
        ),
        krx=KrxDerivativesReferenceService(
            provider="file",
            file_path=str(broken_krx_path),
            base_url="https://data.krx.co.kr",
            endpoint_path="/unused",
            api_key=None,
        ),
    )

    result = service.collect_end_of_day_factors(trade_date=date(2026, 3, 9))

    assert result.status == "PARTIAL_SUCCESS"
    assert result.success_provider_count == 1
    assert result.failed_provider_count == 1

    with get_connection(db_path) as connection:
        factor_count = connection.execute(
            "SELECT COUNT(*) AS count FROM market_daily_factors"
        ).fetchone()["count"]
        health = connection.execute(
            """
            SELECT provider_name, status
            FROM provider_health_checks
            ORDER BY provider_name
            """
        ).fetchall()

    assert factor_count == 1
    status_by_provider = {row["provider_name"]: row["status"] for row in health}
    assert status_by_provider["KIS_MARKET_BREADTH"] == "SUCCESS"
    assert status_by_provider["KRX_DERIVATIVES_REFERENCE"] == "FAILED"


def test_kis_domestic_inquire_price_object_payload_support(tmp_path: Path) -> None:
    db_path = str(tmp_path / "briefing.db")
    trade_date = date(2026, 3, 9)

    domestic_file = _write_json(
        tmp_path / "domestic_inquire_price.json",
        {
            "output1": {
                "futs_shrn_iscd": "101W09",
                "hts_kor_isnm": "KOSPI200 선물 최근월",
                "futs_prpr": "402.15",
                "futs_prdy_vrss": "1.20",
                "futs_prdy_ctrt": "0.30",
                "acml_vol": "15000",
                "hts_otst_stpl_qty": "210000",
                "hts_ints_vltl": "17.90",
            },
            "output2": {
                "put_call_ratio": "0.97",
                "open_interest_total": "1015000",
                "futures_investor_foreign_net_buy": "1450",
            },
            "output3": {
                "hist_vltl": "18.10",
                "note": "official-kis-object-shape",
            },
        },
    )

    service = _make_service(
        db_path=db_path,
        domestic=KisDomesticDerivativesService(
            provider="file",
            file_path=domestic_file,
            base_url="https://openapi.koreainvestment.com:9443",
            endpoint_path="/uapi/domestic-futureoption/v1/quotations/inquire-price",
            app_key=None,
            app_secret=None,
            access_token=None,
        ),
    )

    result = service.collect_pre_open_snapshots(
        trade_date=trade_date,
        snapshot_time=datetime(2026, 3, 9, 23, 20, tzinfo=timezone.utc),
    )

    assert result.status == "SUCCESS"

    with get_connection(db_path) as connection:
        snapshot_row = connection.execute(
            """
            SELECT instrument_code, instrument_name, price, price_change, change_rate, volume, open_interest, implied_volatility
            FROM market_intraday_snapshots
            WHERE trade_date = '2026-03-09' AND source_name = 'KIS_DOMESTIC_DERIVATIVES'
            """
        ).fetchone()
        summary_row = connection.execute(
            """
            SELECT put_call_ratio, open_interest_total, futures_investor_foreign_net_buy, implied_volatility
            FROM derivatives_daily_metrics
            WHERE trade_date = '2026-03-09' AND source_name = 'KIS_DOMESTIC_DERIVATIVES'
            """
        ).fetchone()

    assert snapshot_row is not None
    assert snapshot_row["instrument_code"] == "101W09"
    assert snapshot_row["instrument_name"] == "KOSPI200 선물 최근월"
    assert snapshot_row["price"] == 402.15
    assert snapshot_row["price_change"] == 1.2
    assert snapshot_row["change_rate"] == 0.3
    assert snapshot_row["volume"] == 15000
    assert snapshot_row["open_interest"] == 210000
    assert snapshot_row["implied_volatility"] == 17.9

    assert summary_row is not None
    assert summary_row["put_call_ratio"] == 0.97
    assert summary_row["open_interest_total"] == 1015000
    assert summary_row["futures_investor_foreign_net_buy"] == 1450
    assert summary_row["implied_volatility"] == 17.9


def test_kis_domestic_api_requires_fid_input_iscd() -> None:
    service = KisDomesticDerivativesService(
        provider="api",
        file_path=None,
        base_url="https://openapi.koreainvestment.com:9443",
        endpoint_path="/uapi/domestic-futureoption/v1/quotations/inquire-price",
        app_key="app-key",
        app_secret="app-secret",
        access_token="access-token",
        query_params_json=json.dumps({"FID_COND_MRKT_DIV_CODE": "F"}),
    )

    assert service.is_enabled() == (False, "missing_fid_input_iscd")


def test_kis_domestic_api_defaults_market_div_code_to_f() -> None:
    service = KisDomesticDerivativesService(
        provider="api",
        file_path=None,
        base_url="https://openapi.koreainvestment.com:9443",
        endpoint_path="/uapi/domestic-futureoption/v1/quotations/inquire-price",
        app_key="app-key",
        app_secret="app-secret",
        access_token="access-token",
        query_params_json=json.dumps({"fid_input_iscd": "101W09"}),
    )

    assert service.is_enabled() == (True, None)
    assert service._render_query_params(trade_date=date(2026, 3, 9)) == {
        "fid_input_iscd": "101W09",
        "FID_COND_MRKT_DIV_CODE": "F",
    }


def test_pre_open_rerun_is_idempotent(tmp_path: Path) -> None:
    db_path = str(tmp_path / "briefing.db")

    domestic_file = _write_json(
        tmp_path / "domestic.json",
        {
            "items": [
                {
                    "instrument_code": "101S3000",
                    "instrument_name": "KOSPI200 선물",
                    "price": 402.15,
                    "price_change": 1.2,
                    "change_rate": 0.3,
                    "volume": 15000,
                    "open_interest": 210000,
                }
            ]
        },
    )

    service = _make_service(
        db_path=db_path,
        domestic=KisDomesticDerivativesService(
            provider="file",
            file_path=domestic_file,
            base_url="https://openapi.koreainvestment.com:9443",
            endpoint_path="/unused",
            app_key=None,
            app_secret=None,
            access_token=None,
        ),
    )

    snapshot_time = datetime(2026, 3, 9, 23, 20, tzinfo=timezone.utc)

    first = service.collect_pre_open_snapshots(trade_date=date(2026, 3, 9), snapshot_time=snapshot_time)
    second = service.collect_pre_open_snapshots(trade_date=date(2026, 3, 9), snapshot_time=snapshot_time)

    assert first.inserted_count == 1
    assert second.inserted_count == 0
    assert second.updated_count == 1

    with get_connection(db_path) as connection:
        snapshot_count = connection.execute(
            "SELECT COUNT(*) AS count FROM market_intraday_snapshots"
        ).fetchone()["count"]

    assert snapshot_count == 1


def test_backfill_date_range_collects_each_trade_date(tmp_path: Path) -> None:
    db_path = str(tmp_path / "briefing.db")

    breadth_file = _write_json(
        tmp_path / "breadth_by_date.json",
        {
            "2026-03-08": {
                "investor_foreign_net_buy": 100,
                "program_net_total": 10,
                "credit_balance_total": 1000,
            },
            "2026-03-09": {
                "investor_foreign_net_buy": 200,
                "program_net_total": 20,
                "credit_balance_total": 2000,
            },
        },
    )

    service = _make_service(
        db_path=db_path,
        breadth=KisMarketBreadthService(
            provider="file",
            file_path=breadth_file,
            base_url="https://openapi.koreainvestment.com:9443",
            endpoint_path="/unused",
            app_key=None,
            app_secret=None,
            access_token=None,
        ),
        krx=_make_disabled_krx(),
    )

    results = service.backfill_by_date_range(
        start_date=date(2026, 3, 8),
        end_date=date(2026, 3, 9),
        include_end_of_day=True,
        include_night_session=False,
        include_pre_open=False,
    )

    assert len(results) == 2
    assert all(result.status == "SUCCESS" for result in results)

    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT trade_date, investor_foreign_net_buy
            FROM market_daily_factors
            WHERE source_name = 'KIS_MARKET_BREADTH'
            ORDER BY trade_date
            """
        ).fetchall()

    assert len(rows) == 2
    assert rows[0]["trade_date"] == "2026-03-08"
    assert rows[0]["investor_foreign_net_buy"] == 100
    assert rows[1]["trade_date"] == "2026-03-09"
    assert rows[1]["investor_foreign_net_buy"] == 200


def test_manual_import_path_for_krx_derivatives_reference_csv(tmp_path: Path) -> None:
    db_path = str(tmp_path / "briefing.db")
    csv_path = tmp_path / "krx_manual.csv"
    csv_path.write_text(
        "put_call_ratio,implied_volatility,open_interest_total,futures_investor_foreign_net_buy\n"
        "1.02,19.5,1200000,3200\n",
        encoding="utf-8",
    )

    service = _make_service(db_path=db_path)

    result = service.manual_import_krx_derivatives_reference(
        trade_date=date(2026, 3, 9),
        input_path=str(csv_path),
    )

    assert result.status == "SUCCESS"
    assert result.inserted_count == 1

    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT source_name, put_call_ratio, implied_volatility, futures_investor_foreign_net_buy
            FROM derivatives_daily_metrics
            WHERE trade_date = '2026-03-09'
            """
        ).fetchone()

    assert row is not None
    assert row["source_name"] == "KRX_DERIVATIVES_MANUAL"
    assert row["put_call_ratio"] == 1.02
    assert row["implied_volatility"] == 19.5
    assert row["futures_investor_foreign_net_buy"] == 3200
