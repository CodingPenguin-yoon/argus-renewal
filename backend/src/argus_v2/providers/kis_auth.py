from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

import httpx


@dataclass(frozen=True)
class KisAccessToken:
    access_token: str
    token_type: str | None
    expires_in: int | None
    raw: dict[str, Any]


class KisAuthError(RuntimeError):
    pass


class KisAuthClient:
    def __init__(
        self,
        *,
        base_url: str,
        token_path: str,
        app_key: str | None,
        app_secret: str | None,
        timeout_seconds: float = 20.0,
        cache_path: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token_path = token_path if token_path.startswith("/") else f"/{token_path}"
        self.app_key = (app_key or "").strip()
        self.app_secret = (app_secret or "").strip()
        self.timeout_seconds = timeout_seconds
        self.cache_path = Path(cache_path) if cache_path else None
        self._http_client = http_client

    def is_ready(self) -> tuple[bool, list[str]]:
        missing = []
        if not self.app_key:
            missing.append("KIS_APP_KEY")
        if not self.app_secret:
            missing.append("KIS_APP_SECRET")
        return len(missing) == 0, missing

    def issue_access_token(self) -> KisAccessToken:
        cached = self._read_cached_token()
        if cached is not None:
            return cached

        ready, missing = self.is_ready()
        if not ready:
            raise KisAuthError(f"missing_kis_credentials:{','.join(missing)}")

        payload = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }
        headers = {"content-type": "application/json"}
        url = f"{self.base_url}{self.token_path}"

        if self._http_client is not None:
            response = self._http_client.post(url, headers=headers, json=payload, timeout=self.timeout_seconds)
        else:
            with httpx.Client() as client:
                response = client.post(url, headers=headers, json=payload, timeout=self.timeout_seconds)

        try:
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise KisAuthError("kis_token_request_failed") from error

        token = str(data.get("access_token") or "").strip()
        if not token:
            raise KisAuthError("kis_access_token_missing_in_response")

        expires_in = self._parse_expires_in(data)
        issued = KisAccessToken(
            access_token=token,
            token_type=str(data.get("token_type")).strip() if data.get("token_type") else None,
            expires_in=expires_in,
            raw=data,
        )
        self._write_cached_token(issued)
        return issued

    def _parse_expires_in(self, data: dict[str, Any]) -> int | None:
        expires_raw = data.get("expires_in")
        if isinstance(expires_raw, (int, float, str)) and str(expires_raw).isdigit():
            return int(expires_raw)

        expired_at_raw = str(data.get("access_token_token_expired") or "").strip()
        if not expired_at_raw:
            return None

        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"):
            try:
                expired_at = datetime.strptime(expired_at_raw, fmt).replace(tzinfo=timezone.utc)
                return max(0, int((expired_at - datetime.now(timezone.utc)).total_seconds()))
            except ValueError:
                continue
        return None

    def _read_cached_token(self) -> KisAccessToken | None:
        if self.cache_path is None or not self.cache_path.exists():
            return None
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        token = str(data.get("access_token") or "").strip()
        expires_at_raw = str(data.get("expires_at") or "").strip()
        if not token or not expires_at_raw:
            return None

        try:
            expires_at = datetime.fromisoformat(expires_at_raw)
        except ValueError:
            return None
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc) + timedelta(minutes=5):
            return None

        expires_in = max(0, int((expires_at - datetime.now(timezone.utc)).total_seconds()))
        return KisAccessToken(
            access_token=token,
            token_type=str(data.get("token_type")).strip() if data.get("token_type") else None,
            expires_in=expires_in,
            raw={"cache": True},
        )

    def _write_cached_token(self, token: KisAccessToken) -> None:
        if self.cache_path is None:
            return
        expires_in = token.expires_in if token.expires_in is not None else 60 * 60 * 23
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(0, expires_in))
        payload = {
            "access_token": token.access_token,
            "token_type": token.token_type,
            "expires_at": expires_at.isoformat(),
        }
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(payload), encoding="utf-8")
