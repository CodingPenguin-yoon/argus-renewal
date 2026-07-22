from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_argus_v2_dashboard_endpoint():
    response = client.get("/api/argus/v2/dashboard")
    data = response.json()

    assert response.status_code == 200
    assert data["judgement"]["source"] == "rule_based"
    assert data["derivatives"]["option_pressure"] in {"CALL", "PUT", "NEUTRAL", "UNKNOWN"}


def test_market_flow_endpoint_is_mounted():
    response = client.get("/api/market-data/v1/dashboard/market-flow")
    data = response.json()

    assert response.status_code == 200
    assert data["data_mode"] == "mock"
    assert data["is_live"] is False
    assert data["market_scope"] == "KRX"
    assert len(data["rows"]) == 4


def test_legacy_krx_api_is_not_mounted():
    response = client.get("/api/krx/derivatives/summary")

    assert response.status_code == 404
