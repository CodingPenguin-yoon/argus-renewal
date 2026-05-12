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


def test_legacy_krx_api_is_not_mounted():
    response = client.get("/api/krx/derivatives/summary")

    assert response.status_code == 404
