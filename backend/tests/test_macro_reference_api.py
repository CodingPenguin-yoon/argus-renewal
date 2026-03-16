from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.config.env import Settings, get_settings
from src.krx.macro_reference.factory import create_macro_reference_service
from src.main import app

client = TestClient(app)


def test_macro_reference_service_disabled_mode() -> None:
    service = create_macro_reference_service(Settings(fred_provider="disabled", fred_api_key=None, fred_file_path=None))

    payload = service.get_cards()

    assert payload["items"] == []
    assert payload["coverage"]["state"] == "empty"
    assert payload["coverage"]["provider"] == "disabled"
    assert payload["coverage"]["note"] == "feature_flag_disabled"


def test_macro_reference_service_normalizes_file_payload(tmp_path: Path) -> None:
    fixture_path = tmp_path / "fred-rates.json"
    fixture_path.write_text(
        json.dumps(
            {
                "DEXKOUS": {
                    "observations": [
                        {"date": "2026-03-16", "value": "1458.30"},
                        {"date": "2026-03-14", "value": "1452.10"},
                    ]
                },
                "DCOILWTICO": {
                    "observations": [
                        {"date": "2026-03-16", "value": "67.55"},
                        {"date": "2026-03-14", "value": "66.10"},
                    ]
                },
                "DGS10": {
                    "observations": [
                        {"date": "2026-03-16", "value": "4.31"},
                        {"date": "2026-03-15", "value": "."},
                        {"date": "2026-03-14", "value": "4.25"},
                    ]
                },
                "FEDFUNDS": {
                    "observations": [
                        {"date": "2026-03-01", "value": "4.33"},
                        {"date": "2026-02-01", "value": "4.33"},
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    service = create_macro_reference_service(
        Settings(fred_provider="file", fred_file_path=str(fixture_path))
    )

    payload = service.get_cards()

    assert payload["coverage"]["state"] == "full"
    assert [item["source"]["series_id"] for item in payload["items"]] == [
        "DEXKOUS",
        "DCOILWTICO",
        "DGS10",
        "FEDFUNDS",
    ]
    assert payload["items"][0]["label"] == "환율"
    assert payload["items"][0]["value_display"] == "1,458.30원"
    assert payload["items"][0]["change_display"] == "+6.20원"
    assert payload["items"][1]["label"] == "WTI·에너지"
    assert payload["items"][1]["value_display"] == "$67.55/bbl"
    assert payload["items"][2]["label"] == "미국채 10년물"
    assert payload["items"][2]["change_value"] == 0.06
    assert payload["items"][2]["metadata"]["semantics"] == "daily_market_yield_percent"
    assert payload["items"][3]["label"] == "연방기금실효금리(월평균)"
    assert payload["items"][3]["metadata"]["series_id"] == "FEDFUNDS"


def test_macro_reference_route_shape_with_file_provider(monkeypatch, tmp_path: Path) -> None:
    fixture_path = tmp_path / "fred-rates.json"
    fixture_path.write_text(
        json.dumps(
            {
                "DEXKOUS": {
                    "observations": [
                        {"date": "2026-03-16", "value": "1458.30"},
                        {"date": "2026-03-14", "value": "1452.10"},
                    ]
                },
                "DCOILWTICO": {
                    "observations": [
                        {"date": "2026-03-16", "value": "67.55"},
                        {"date": "2026-03-14", "value": "66.10"},
                    ]
                },
                "DGS10": {
                    "observations": [
                        {"date": "2026-03-16", "value": "4.31"},
                        {"date": "2026-03-14", "value": "4.25"},
                    ]
                },
                "FEDFUNDS": {
                    "observations": [
                        {"date": "2026-03-01", "value": "4.33"},
                        {"date": "2026-02-01", "value": "4.33"},
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("FRED_PROVIDER", "file")
    monkeypatch.setenv("FRED_FILE_PATH", str(fixture_path))
    get_settings.cache_clear()

    try:
        response = client.get("/api/krx/macro-reference/cards")
        assert response.status_code == 200
        payload = response.json()
    finally:
        get_settings.cache_clear()

    assert payload["coverage"]["state"] == "full"
    assert payload["coverage"]["expected_items"] == 4
    assert len(payload["items"]) == 4
    assert payload["items"][0]["source"]["key"] == "FRED"
    assert payload["items"][0]["freshness"]["status"] in {"fresh", "stale", "unknown"}
    assert payload["items"][0]["metadata"]["series_id"] == "DEXKOUS"
