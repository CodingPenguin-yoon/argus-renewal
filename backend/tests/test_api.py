from fastapi.testclient import TestClient

from src.config.env import get_settings
from src.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_app_header_endpoint():
    response = client.get("/api/app/header", params={"market": "krx"})
    assert response.status_code == 200
    data = response.json()
    assert data["market"] == "krx"
    assert isinstance(data["market_tone_line"], str)
    assert len(data["supporting_points"]) >= 1
    assert data["phase"] in {"pre-open", "live", "post-close"}
    assert data["source_coverage"]["state"] in {"full", "partial", "empty"}
    assert data["source_coverage"]["expected_sources"] == 3
    assert "breaking_news" in data


def test_krx_company_mapping_summary_endpoint():
    response = client.get("/api/krx/admin/company-mappings/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_mapped" in data
    assert "unresolved" in data
    assert "conflicting_rows" in data
    assert "duplicate_groups" in data
    assert "recently_changed_mappings" in data


def test_krx_company_mapping_unresolved_endpoint():
    response = client.get("/api/krx/admin/company-mappings/unresolved")
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "items" in data


def test_krx_company_mapping_manual_overrides_endpoint():
    response = client.get("/api/krx/admin/company-mappings/manual-overrides")
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "items" in data


def test_krx_recent_events_feed_endpoint():
    response = client.get("/api/krx/news/events/recent")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


def test_krx_event_review_queue_endpoint():
    response = client.get("/api/krx/admin/events/review-queue")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


def test_krx_briefing_runs_endpoint():
    response = client.get("/api/krx/admin/briefing-inputs/runs")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


def test_krx_briefing_daily_factors_endpoint():
    response = client.get("/api/krx/admin/briefing-inputs/market-daily-factors")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


def test_krx_generated_briefing_latest_endpoint():
    response = client.get("/api/krx/admin/briefings/latest")
    assert response.status_code == 200
    data = response.json()
    assert "item" in data


def test_krx_generated_briefing_history_endpoint():
    response = client.get("/api/krx/admin/briefings/history")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


def test_krx_company_report_endpoints():
    universes_response = client.get("/api/krx/admin/company-reports/universes")
    assert universes_response.status_code == 200
    assert "items" in universes_response.json()

    inputs_response = client.get("/api/krx/admin/company-reports/inputs/daily-prices/1")
    assert inputs_response.status_code == 200
    assert "items" in inputs_response.json()


def test_krx_event_admin_requires_key_when_configured(monkeypatch):
    monkeypatch.setenv("KRX_ADMIN_API_KEY", "unit-test-admin-key")
    get_settings.cache_clear()

    try:
        unauthorized = client.get("/api/krx/admin/events/review-queue")
        assert unauthorized.status_code == 401

        authorized = client.get(
            "/api/krx/admin/events/review-queue",
            headers={"X-Admin-Key": "unit-test-admin-key"},
        )
        assert authorized.status_code == 200

        briefing_unauthorized = client.get("/api/krx/admin/briefing-inputs/runs")
        assert briefing_unauthorized.status_code == 401

        briefing_authorized = client.get(
            "/api/krx/admin/briefing-inputs/runs",
            headers={"X-Admin-Key": "unit-test-admin-key"},
        )
        assert briefing_authorized.status_code == 200

        signal_unauthorized = client.get("/api/krx/admin/briefings/history")
        assert signal_unauthorized.status_code == 401

        signal_authorized = client.get(
            "/api/krx/admin/briefings/history",
            headers={"X-Admin-Key": "unit-test-admin-key"},
        )
        assert signal_authorized.status_code == 200
    finally:
        get_settings.cache_clear()
