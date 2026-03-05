from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_top_news():
    response = client.get("/api/news/top")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) >= 1


def test_search_news():
    response = client.get("/api/news/search", params={"q": "NVDA"})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
