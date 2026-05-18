from __future__ import annotations

from datetime import date, datetime, timezone
import io
import json
from pathlib import Path
import zipfile

import httpx

from src.argus_v2.db import get_connection
from src.argus_v2.providers import AUTO_KIS_DOMESTIC_DERIVATIVES_INPUT_ISCD
from src.argus_v2.providers.kis_live import run_kis_live_smoke
from src.config.env import Settings


def _build_master_zip(*rows: str) -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, mode="w") as archive:
        archive.writestr("fo_idx_code_mts.mst", "\n".join(rows) + "\n")
    return payload.getvalue()


def test_run_kis_live_smoke_fetches_and_persists_kis_batches(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json={"access_token": "issued-token", "token_type": "Bearer", "expires_in": 86400})

        if request.url.host == "new.real.download.dws.co.kr":
            return httpx.Response(
                200,
                content=_build_master_zip("1|A01606|KR4A01660005|F 202606| |00000.00|1|2001|KOSPI200"),
            )

        assert request.headers["authorization"] == "Bearer issued-token"
        if request.url.path.endswith("/inquire-price"):
            assert request.url.params["FID_INPUT_ISCD"] == "A01606"
            return httpx.Response(
                200,
                json={
                    "output": {
                        "futs_shrn_iscd": "A01606",
                        "hts_kor_isnm": "F 202606",
                        "futs_prpr": "392.50",
                        "futs_prdy_vrss": "-1.20",
                        "futs_prdy_ctrt": "-0.31",
                        "acml_vol": "1500",
                        "hts_otst_stpl_qty": "215000",
                        "otst_stpl_qty_icdc": "-500",
                        "basis": "-0.40",
                        "mrkt_basis": "-0.25",
                    }
                },
            )

        if request.url.path.endswith("/display-board-option-list"):
            return httpx.Response(200, json={"output": [{"mtrt_yymm": "202605"}]})

        if request.url.path.endswith("/display-board-callput"):
            assert request.url.params["FID_MTRT_CNT"] == "202605"
            return httpx.Response(
                200,
                json={
                    "output1": [
                        {
                            "acpr": "390.00",
                            "optn_prpr": "5.25",
                            "acml_vol": "1500",
                            "acml_tr_pbmn": "7875",
                            "hts_otst_stpl_qty": "12200",
                            "hts_ints_vltl": "18.5",
                            "nmix_sdpr": "392.40",
                        }
                    ],
                    "output2": [
                        {
                            "acpr": "390.00",
                            "optn_prpr": "2.10",
                            "acml_vol": "2000",
                            "acml_tr_pbmn": "4200",
                            "hts_otst_stpl_qty": "19800",
                            "hts_ints_vltl": "20.1",
                            "nmix_sdpr": "392.40",
                        }
                    ],
                },
            )

        if request.url.path.endswith("/inquire-investor-flow"):
            return httpx.Response(
                200,
                json={
                    "output": {
                        "frgn_ntby_tr_pbmn": "-18000000",
                        "orgn_ntby_tr_pbmn": "6200000",
                        "prsn_ntby_tr_pbmn": "11800000",
                    }
                },
            )

        return httpx.Response(404, json={"error": "unexpected path"})

    settings = Settings(
        db_path=str(tmp_path / "argus-v2.db"),
        kis_app_key="app-key",
        kis_app_secret="app-secret",
        kis_domestic_derivatives_provider="api",
        kis_domestic_derivatives_query_params_json=json.dumps(
            {"FID_INPUT_ISCD": AUTO_KIS_DOMESTIC_DERIVATIVES_INPUT_ISCD}
        ),
        kis_futures_investor_flow_provider="api",
        kis_futures_investor_flow_path="/uapi/domestic-futureoption/v1/quotations/inquire-investor-flow",
        kis_futures_investor_flow_tr_id="FUTINV00000000",
        kis_option_chain_provider="api",
    )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = run_kis_live_smoke(
            settings=settings,
            trade_date=date(2026, 5, 12),
            snapshot_time=datetime(2026, 5, 12, 0, 10, tzinfo=timezone.utc),
            token_cache_path=str(tmp_path / "kis_token_cache.json"),
            http_client=http_client,
        )

    assert result.token_status == "ready"
    assert result.token_source == "issued"
    assert [provider.status for provider in result.providers] == ["success", "success", "success"]
    assert result.providers[0].observed_count == 1
    assert result.providers[1].observed_count == 1
    assert result.providers[2].observed_count == 1
    assert len(requests) == 6

    with get_connection(settings.db_path) as connection:
        run_count = connection.execute("SELECT COUNT(*) AS count FROM argus_v2_provider_runs").fetchone()["count"]
        future = connection.execute(
            "SELECT instrument_name, change_rate, additional_metrics_json FROM argus_v2_derivatives_snapshots"
        ).fetchone()
        option_snapshot = connection.execute(
            "SELECT contract_month, observed_level_count FROM argus_v2_option_chain_snapshots"
        ).fetchone()
        option_level = connection.execute(
            "SELECT call_trading_value, put_trading_value, call_open_interest, put_open_interest, pressure_side FROM argus_v2_option_chain_levels"
        ).fetchone()
        futures_flow = connection.execute(
            "SELECT foreign_net_buy, institution_net_buy, individual_net_buy FROM argus_v2_futures_investor_flow_snapshots"
        ).fetchone()

    assert run_count == 3
    assert future["instrument_name"] == "F 202606"
    assert future["change_rate"] == -0.31
    additional_metrics = json.loads(future["additional_metrics_json"])
    assert additional_metrics["basis"] == -0.4
    assert additional_metrics["market_basis"] == -0.25
    assert round(additional_metrics["open_interest_change_rate"], 2) == -0.23
    assert option_snapshot["contract_month"] == "202605"
    assert option_snapshot["observed_level_count"] == 1
    assert option_level["call_trading_value"] == 7_875_000
    assert option_level["put_trading_value"] == 4_200_000
    assert option_level["call_open_interest"] == 12200
    assert option_level["put_open_interest"] == 19800
    assert option_level["pressure_side"] == "PUT"
    assert futures_flow["foreign_net_buy"] == -180_000_000_000
    assert futures_flow["institution_net_buy"] == 62_000_000_000
    assert futures_flow["individual_net_buy"] == 118_000_000_000
