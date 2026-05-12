from __future__ import annotations

from pathlib import Path
import json
import logging
from typing import Any, Callable

import httpx


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    cleaned = text.replace(",", "").replace("%", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def pick_float(payload: dict[str, Any], aliases: tuple[str, ...]) -> float | None:
    value = pick_value(payload, aliases)
    return as_float(value)


def pick_text(payload: dict[str, Any], aliases: tuple[str, ...]) -> str | None:
    value = pick_value(payload, aliases)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def pick_value(payload: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    normalized = {normalize_key(key): value for key, value in payload.items()}
    for alias in aliases:
        key = normalize_key(alias)
        if key in normalized:
            return normalized[key]
    return None


def normalize_key(value: str) -> str:
    return "".join(ch for ch in value.lower().strip() if ch not in {"_", "-", " "})


def parse_query_params_json(value: str | None) -> dict[str, str]:
    if not value:
        return {}
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("query params must be a JSON object")
    return {str(key): str(item) for key, item in payload.items()}


def parse_response_paths(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def load_json_file(file_path: str) -> Any:
    return json.loads(Path(file_path).read_text(encoding="utf-8"))


def extract_rows(payload: Any, response_paths: list[str]) -> list[dict[str, Any]]:
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    if isinstance(payload, dict):
        for path in response_paths:
            candidate = value_by_path(payload, path)
            if isinstance(candidate, list) and all(isinstance(item, dict) for item in candidate):
                return candidate
            if isinstance(candidate, dict):
                return [candidate]
        for key in ("output", "output1", "items", "data"):
            candidate = payload.get(key)
            if isinstance(candidate, list) and all(isinstance(item, dict) for item in candidate):
                return candidate
            if isinstance(candidate, dict):
                return [candidate]
    return []


def value_by_path(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for segment in [part.strip() for part in path.split(".") if part.strip()]:
        if not isinstance(current, dict):
            return None
        normalized_segment = normalize_key(segment)
        for key, value in current.items():
            if normalize_key(key) == normalized_segment:
                current = value
                break
        else:
            return None
    return current


def fetch_json_with_retries(
    *,
    logger: logging.Logger,
    log_prefix: str,
    max_retries: int,
    backoff_seconds: float,
    do_request: Callable[[], httpx.Response],
) -> tuple[Any, int]:
    last_error: Exception | None = None
    attempts = max(1, max_retries)
    for attempt in range(1, attempts + 1):
        try:
            response = do_request()
            response.raise_for_status()
            return response.json(), attempt - 1
        except (httpx.HTTPError, ValueError) as error:
            last_error = error
            logger.warning("%s_failed", log_prefix, extra={"attempt": attempt, "max_retries": attempts})
            if attempt < attempts and backoff_seconds > 0:
                import time

                time.sleep(backoff_seconds)
    raise RuntimeError(f"{log_prefix}_failed") from last_error
