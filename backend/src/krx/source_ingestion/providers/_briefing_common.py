from __future__ import annotations

import json
import logging
from pathlib import Path
import time
from typing import Any, Callable

import httpx

DEFAULT_RESPONSE_PATHS: tuple[str, ...] = (
    "output",
    "output1",
    "output2",
    "items",
    "data.items",
    "data.rows",
    "data",
)


def normalize_key(value: str) -> str:
    return "".join(ch for ch in value.lower().strip() if ch not in {"_", "-", " "})


def _normalized_mapping(record: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in record.items():
        normalized[normalize_key(str(key))] = value
    return normalized


def pick_text(record: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    normalized = _normalized_mapping(record)
    for key in keys:
        value = normalized.get(normalize_key(key))
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def pick_float(record: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    raw_value = pick_text(record, keys)
    return as_float(raw_value)


def as_float(value: Any) -> float | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    normalized = text.replace(",", "")
    if normalized.endswith("%"):
        normalized = normalized[:-1].strip()

    if normalized.startswith("+"):
        normalized = normalized[1:]

    if normalized in {"-", "--", "N/A", "NA", "null", "None"}:
        return None

    try:
        return float(normalized)
    except ValueError:
        return None


def is_row_list(candidate: Any) -> bool:
    return isinstance(candidate, list) and all(isinstance(item, dict) for item in candidate)


def _get_by_path(payload: Any, path: str) -> Any:
    current = payload
    for segment in [part.strip() for part in path.split(".") if part.strip()]:
        if not isinstance(current, dict):
            return None
        normalized = _normalized_mapping(current)
        current = normalized.get(normalize_key(segment))
    return current


def _collect_row_lists(payload: Any, max_depth: int = 4) -> list[list[dict[str, Any]]]:
    collected: list[list[dict[str, Any]]] = []

    def _walk(node: Any, depth: int) -> None:
        if depth > max_depth:
            return
        if is_row_list(node):
            collected.append(node)
            return
        if isinstance(node, dict):
            for value in node.values():
                _walk(value, depth + 1)

    _walk(payload, 0)
    return collected


def extract_rows(payload: Any, response_paths: tuple[str, ...]) -> list[dict[str, Any]]:
    if is_row_list(payload):
        return payload

    if isinstance(payload, dict):
        for path in response_paths:
            candidate = _get_by_path(payload, path)
            if is_row_list(candidate):
                return candidate

    candidates = _collect_row_lists(payload)
    if candidates:
        return max(candidates, key=len)

    raise ValueError("Response payload does not include rows")


def parse_response_paths(value: str | None) -> tuple[str, ...]:
    if not value:
        return DEFAULT_RESPONSE_PATHS
    paths = tuple(part.strip() for part in value.split(",") if part.strip())
    return paths or DEFAULT_RESPONSE_PATHS


def parse_query_params_json(value: str | None) -> dict[str, str]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("Query params JSON must be a valid JSON object") from error

    if not isinstance(payload, dict):
        raise ValueError("Query params JSON must be a JSON object")

    params: dict[str, str] = {}
    for key, raw_value in payload.items():
        if raw_value is None:
            continue
        params[str(key)] = str(raw_value)
    return params


def parse_field_alias_map_json(value: str | None) -> dict[str, tuple[str, ...]]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("Field alias map JSON must be a valid JSON object") from error

    if not isinstance(payload, dict):
        raise ValueError("Field alias map JSON must be a JSON object")

    parsed: dict[str, tuple[str, ...]] = {}
    for key, aliases in payload.items():
        canonical = str(key).strip()
        if not canonical:
            continue

        alias_list: list[str] = []
        if isinstance(aliases, list):
            for item in aliases:
                text = str(item).strip()
                if text:
                    alias_list.append(text)
        elif aliases is not None:
            text = str(aliases).strip()
            if text:
                alias_list.append(text)

        if alias_list:
            parsed[canonical] = tuple(alias_list)

    return parsed


def merge_aliases(
    *,
    field_alias_map: dict[str, tuple[str, ...]],
    canonical_field: str,
    defaults: tuple[str, ...],
) -> tuple[str, ...]:
    custom = field_alias_map.get(canonical_field, ())
    merged: list[str] = []
    seen: set[str] = set()
    for value in [*custom, *defaults]:
        normalized = normalize_key(value)
        if normalized in seen:
            continue
        seen.add(normalized)
        merged.append(value)
    return tuple(merged)


def load_json_file(file_path: str) -> Any:
    source = Path(file_path)
    if not source.exists():
        raise FileNotFoundError(f"JSON file not found: {source}")
    return json.loads(source.read_text(encoding="utf-8-sig"))


def fetch_json_with_retries(
    *,
    logger: logging.Logger,
    log_prefix: str,
    max_retries: int,
    backoff_seconds: float,
    do_request: Callable[[], httpx.Response],
) -> tuple[Any, int]:
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            response = do_request()
            response.raise_for_status()
            payload = response.json()
            return payload, attempt - 1
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as error:
            last_error = error
            logger.warning(
                f"{log_prefix}_retry",
                extra={"attempt": attempt, "error": str(error)},
            )
            if attempt < max_retries:
                time.sleep(backoff_seconds * (2 ** (attempt - 1)))

    raise RuntimeError(f"{log_prefix}_failed_after_retries") from last_error
