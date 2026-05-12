import json

import httpx
import pytest

from src.argus_v2.providers import KisAuthClient, KisAuthError


def test_kis_auth_client_issues_access_token_from_app_key_and_secret():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/oauth2/tokenP"
        assert request.headers["content-type"] == "application/json"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["grant_type"] == "client_credentials"
        assert payload["appkey"] == "app-key"
        assert payload["appsecret"] == "app-secret"
        return httpx.Response(
            200,
            json={
                "access_token": "issued-token",
                "token_type": "Bearer",
                "expires_in": 86400,
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        token = KisAuthClient(
            base_url="https://openapi.koreainvestment.com:9443",
            token_path="/oauth2/tokenP",
            app_key="app-key",
            app_secret="app-secret",
            http_client=http_client,
        ).issue_access_token()

    assert token.access_token == "issued-token"
    assert token.token_type == "Bearer"
    assert token.expires_in == 86400


def test_kis_auth_client_reuses_cached_access_token(tmp_path):
    cache_path = tmp_path / "kis_token_cache.json"
    call_count = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            200,
            json={
                "access_token": f"issued-token-{call_count}",
                "token_type": "Bearer",
                "expires_in": 86400,
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = KisAuthClient(
            base_url="https://openapi.koreainvestment.com:9443",
            token_path="/oauth2/tokenP",
            app_key="app-key",
            app_secret="app-secret",
            cache_path=str(cache_path),
            http_client=http_client,
        )
        first = client.issue_access_token()
        second = client.issue_access_token()

    assert first.access_token == "issued-token-1"
    assert second.access_token == "issued-token-1"
    assert call_count == 1


def test_kis_auth_client_reports_missing_app_credentials():
    client = KisAuthClient(
        base_url="https://openapi.koreainvestment.com:9443",
        token_path="/oauth2/tokenP",
        app_key="",
        app_secret=None,
    )

    ready, missing = client.is_ready()

    assert ready is False
    assert missing == ["KIS_APP_KEY", "KIS_APP_SECRET"]
    with pytest.raises(KisAuthError, match="missing_kis_credentials"):
        client.issue_access_token()
