from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FredSeriesDefinition:
    key: str
    label: str
    series_id: str
    series_name: str
    semantics: str
    frequency: str
    unit: str
    freshness_ttl_seconds: int
    source_url: str


@dataclass(frozen=True)
class FredSeriesSnapshot:
    definition: FredSeriesDefinition
    provider: str
    observed_at: str | None
    value: float | None
    previous_value: float | None
    change_value: float | None
    series_updated_at: str | None
    retry_count: int = 0


class FredRatesProvider:
    def __init__(
        self,
        *,
        provider: str,
        file_path: str | None,
        base_url: str,
        series_observations_path: str,
        api_key: str | None,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.provider = provider.strip().lower()
        self.file_path = file_path
        self.base_url = base_url.rstrip("/")
        self.series_observations_path = series_observations_path
        self.api_key = (api_key or "").strip() or None
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(1, max_retries)
        self.backoff_seconds = max(backoff_seconds, 0.0)
        self._http_client = http_client

    def is_enabled(self) -> tuple[bool, str | None]:
        if self.provider in {"", "disabled"}:
            return False, "feature_flag_disabled"
        if self.provider == "file":
            if not self.file_path:
                return False, "missing_file_path"
            return True, None
        if self.provider == "api":
            if not self.series_observations_path:
                return False, "missing_series_observations_path"
            if not self.api_key:
                return False, "missing_fred_api_key"
            return True, None
        return False, f"unsupported_provider:{self.provider}"

    def fetch_cards(
        self,
        *,
        series_definitions: list[FredSeriesDefinition],
        now: datetime | None = None,
    ) -> tuple[list[FredSeriesSnapshot], str | None]:
        enabled, reason = self.is_enabled()
        if not enabled:
            logger.info("fred_rates_provider_disabled", extra={"reason": reason})
            return [], reason

        payloads: dict[str, Any]
        total_retries = 0
        if self.provider == "file":
            payloads = self._load_file_payloads()
        else:
            payloads = {}
            for definition in series_definitions:
                payload, retry_count = self._fetch_api_payload(series_id=definition.series_id)
                payloads[definition.series_id] = payload
                total_retries += retry_count

        snapshots = [
            self._build_snapshot(
                definition=definition,
                payload=payloads.get(definition.series_id),
                now=now,
                retry_count=total_retries if self.provider == "api" else 0,
            )
            for definition in series_definitions
        ]
        return snapshots, None

    def _load_file_payloads(self) -> dict[str, Any]:
        source = Path(self.file_path or "")
        if not source.exists():
            raise FileNotFoundError(f"FRED fixture file not found: {source}")
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("FRED fixture payload must be a JSON object")
        return payload

    def _fetch_api_payload(self, *, series_id: str) -> tuple[Any, int]:
        url = f"{self.base_url}{self.series_observations_path}"
        params = {
            "file_type": "json",
            "series_id": series_id,
            "sort_order": "desc",
            "limit": "10",
        }
        if self.api_key:
            params["api_key"] = self.api_key

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._do_request(url=url, params=params)
                response.raise_for_status()
                return response.json(), attempt - 1
            except (httpx.HTTPError, json.JSONDecodeError, ValueError) as error:
                last_error = error
                logger.warning(
                    "fred_rates_fetch_retry",
                    extra={"attempt": attempt, "series_id": series_id, "error": str(error)},
                )
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * (2 ** (attempt - 1)))

        raise RuntimeError(f"fred_rates_fetch_failed:{series_id}") from last_error

    def _do_request(self, *, url: str, params: dict[str, str]) -> httpx.Response:
        if self._http_client is not None:
            return self._http_client.get(url, params=params, timeout=self.timeout_seconds)
        with httpx.Client() as client:
            return client.get(url, params=params, timeout=self.timeout_seconds)

    def _build_snapshot(
        self,
        *,
        definition: FredSeriesDefinition,
        payload: Any,
        now: datetime | None,
        retry_count: int,
    ) -> FredSeriesSnapshot:
        observations = self._extract_observations(payload=payload, series_id=definition.series_id)
        latest = self._next_valid_observation(observations, start_index=0)
        previous = self._next_valid_observation(observations, start_index=1 if latest else 0)

        latest_value = _as_float(latest.get("value")) if latest else None
        previous_value = _as_float(previous.get("value")) if previous else None
        change_value = None
        if latest_value is not None and previous_value is not None:
            change_value = round(latest_value - previous_value, 6)

        series_updated_at = _coalesce_text(
            payload.get("realtime_start") if isinstance(payload, dict) else None,
            payload.get("observation_end") if isinstance(payload, dict) else None,
        )
        observed_at = _coalesce_text(latest.get("date") if latest else None, series_updated_at)
        _ = now

        return FredSeriesSnapshot(
            definition=definition,
            provider=self.provider,
            observed_at=observed_at,
            value=latest_value,
            previous_value=previous_value,
            change_value=change_value,
            series_updated_at=series_updated_at,
            retry_count=retry_count,
        )

    def _extract_observations(self, *, payload: Any, series_id: str) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []

        direct = payload.get(series_id)
        if isinstance(direct, dict):
            return self._extract_observations(payload=direct, series_id=series_id)

        wrapped = payload.get("series")
        if isinstance(wrapped, dict):
            observations = wrapped.get(series_id)
            if isinstance(observations, list):
                return [item for item in observations if isinstance(item, dict)]

        observations = payload.get("observations")
        if isinstance(observations, list):
            return [item for item in observations if isinstance(item, dict)]

        return []

    def _next_valid_observation(
        self,
        observations: list[dict[str, Any]],
        *,
        start_index: int,
    ) -> dict[str, Any] | None:
        for item in observations[start_index:]:
            if _as_float(item.get("value")) is not None:
                return item
        return None


def _coalesce_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text == ".":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
