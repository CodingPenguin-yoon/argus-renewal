from __future__ import annotations

from dataclasses import dataclass
import csv
import json
import logging
from pathlib import Path
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_RESPONSE_PATHS: tuple[str, ...] = (
    "output",
    "output1",
    "output2",
    "items",
    "data.items",
    "data.rows",
    "data",
)


@dataclass(frozen=True)
class KisCompanyRecord:
    symbol: str
    name: str
    market: str | None
    listing_status: str | None
    market_classification: str | None
    source_url: str | None


def _normalize_key(value: str) -> str:
    return "".join(ch for ch in value.lower().strip() if ch not in {"_", "-", " "})


def _normalized_mapping(record: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in record.items():
        normalized[_normalize_key(str(key))] = value
    return normalized


def _pick(record: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    normalized = _normalized_mapping(record)
    for key in keys:
        lookup = _normalize_key(key)
        value = normalized.get(lookup)
        if value is None:
            continue
        if isinstance(value, bool):
            return "Y" if value else "N"
        text = str(value).strip()
        if text:
            return text
    return None


def _normalize_listing_status(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip().upper()
    if not text:
        return None

    listed_tokens = {"Y", "YES", "TRUE", "1", "LISTED", "L", "ACTIVE", "NORMAL", "상장"}
    delisted_tokens = {
        "N",
        "NO",
        "FALSE",
        "0",
        "DELISTED",
        "D",
        "UNLISTED",
        "TERMINATED",
        "SUSPENDED",
        "상장폐지",
        "폐지",
    }
    if text in listed_tokens:
        return "LISTED"
    if text in delisted_tokens:
        return "DELISTED"
    return text


def _is_row_list(candidate: Any) -> bool:
    return isinstance(candidate, list) and all(isinstance(item, dict) for item in candidate)


def _get_by_path(payload: Any, path: str) -> Any:
    current = payload
    for segment in [part.strip() for part in path.split(".") if part.strip()]:
        if not isinstance(current, dict):
            return None
        normalized = _normalized_mapping(current)
        current = normalized.get(_normalize_key(segment))
    return current


def _collect_row_lists(payload: Any, max_depth: int = 4) -> list[list[dict[str, Any]]]:
    collected: list[list[dict[str, Any]]] = []

    def _walk(node: Any, depth: int) -> None:
        if depth > max_depth:
            return
        if _is_row_list(node):
            collected.append(node)
            return
        if isinstance(node, dict):
            for value in node.values():
                _walk(value, depth + 1)

    _walk(payload, 0)
    return collected


class KisFileMasterClient:
    def __init__(self, *, file_path: str) -> None:
        self.file_path = Path(file_path)

    def fetch_company_master(self) -> list[KisCompanyRecord]:
        if not self.file_path.exists():
            raise FileNotFoundError(f"KIS master file not found: {self.file_path}")

        raw_content: str
        try:
            raw_content = self.file_path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            raw_content = self.file_path.read_text(encoding="cp949")

        reader = csv.DictReader(raw_content.splitlines())
        records: list[KisCompanyRecord] = []

        for row in reader:
            symbol = _pick(row, ("symbol", "stock_code", "code", "ticker", "단축코드", "srtn_cd"))
            name = _pick(
                row,
                ("name", "corp_name", "korean_name", "한글명", "종목명", "hts_kor_isnm", "isu_abbrv"),
            )
            if not symbol or not name:
                continue

            records.append(
                KisCompanyRecord(
                    symbol=symbol,
                    name=name,
                    market=_pick(row, ("market", "exchange", "시장구분", "rprs_mrkt_kor_name")),
                    listing_status=_normalize_listing_status(
                        _pick(row, ("listing_status", "status", "상장상태", "list_yn", "list_stat"))
                    ),
                    market_classification=_pick(
                        row,
                        (
                            "market_classification",
                            "classification",
                            "시장분류",
                            "소속부",
                            "scty_grp_cls_code",
                        ),
                    ),
                    source_url=str(self.file_path),
                )
            )

        logger.info(
            "kis_master_file_loaded",
            extra={"path": str(self.file_path), "count": len(records)},
        )
        return records


class KisApiMasterClient:
    def __init__(
        self,
        *,
        base_url: str,
        symbol_master_path: str,
        app_key: str,
        app_secret: str,
        access_token: str,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        response_paths: tuple[str, ...] = _DEFAULT_RESPONSE_PATHS,
        query_params: dict[str, str] | None = None,
        tr_id: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.symbol_master_path = symbol_master_path
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token = access_token
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.response_paths = response_paths
        self.query_params = query_params or {}
        self.tr_id = tr_id
        self._http_client = http_client

    def fetch_company_master(self) -> list[KisCompanyRecord]:
        if not all([self.base_url, self.symbol_master_path, self.app_key, self.app_secret, self.access_token]):
            raise ValueError("KIS API configuration is incomplete")

        url = f"{self.base_url}{self.symbol_master_path}"
        headers = {
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "authorization": f"Bearer {self.access_token}",
            "content-type": "application/json; charset=utf-8",
        }
        if self.tr_id:
            headers["tr_id"] = self.tr_id

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "kis_master_fetch_attempt",
                    extra={"attempt": attempt, "url": url, "params": self.query_params},
                )
                response = self._request_master(url=url, headers=headers, query_params=self.query_params)
                response.raise_for_status()

                payload = response.json()
                rows = self._extract_rows(payload)
                records = self._parse_rows(rows, url)
                logger.info(
                    "kis_master_fetch_success",
                    extra={"count": len(records), "attempt": attempt},
                )
                return records
            except (httpx.HTTPError, json.JSONDecodeError, ValueError, AttributeError) as error:
                last_error = error
                logger.warning(
                    "kis_master_fetch_failed",
                    extra={"attempt": attempt, "error": str(error)},
                )
                if attempt < self.max_retries:
                    sleep_seconds = self.backoff_seconds * (2 ** (attempt - 1))
                    time.sleep(sleep_seconds)

        raise RuntimeError("Failed to fetch KIS symbol master after retries") from last_error

    def _request_master(
        self,
        *,
        url: str,
        headers: dict[str, str],
        query_params: dict[str, str],
    ) -> httpx.Response:
        if self._http_client is not None:
            return self._http_client.get(
                url,
                headers=headers,
                params=query_params,
                timeout=self.timeout_seconds,
            )
        with httpx.Client() as client:
            return client.get(
                url,
                headers=headers,
                params=query_params,
                timeout=self.timeout_seconds,
            )

    def _extract_rows(self, payload: Any) -> list[dict[str, Any]]:
        if _is_row_list(payload):
            return payload

        if isinstance(payload, dict):
            for path in self.response_paths:
                candidate = _get_by_path(payload, path)
                if _is_row_list(candidate):
                    return candidate

        candidates = _collect_row_lists(payload)
        if candidates:
            return max(candidates, key=len)

        raise ValueError("Unexpected KIS master response format")

    def _parse_rows(self, rows: list[dict[str, Any]], source_url: str) -> list[KisCompanyRecord]:
        records: list[KisCompanyRecord] = []
        for row in rows:
            symbol = _pick(
                row,
                (
                    "symbol",
                    "stock_code",
                    "pdno",
                    "code",
                    "mksc_shrn_iscd",
                    "stck_shrn_iscd",
                    "shtn_pdno",
                    "isu_srt_cd",
                    "srtn_cd",
                    "isu_cd",
                ),
            )
            name = _pick(
                row,
                (
                    "name",
                    "hts_kor_isnm",
                    "prdt_name",
                    "kor_name",
                    "prdt_abrv_name",
                    "stck_kor_isnm",
                    "isu_abbrv",
                    "isu_nm",
                ),
            )
            if not symbol or not name:
                continue

            records.append(
                KisCompanyRecord(
                    symbol=symbol,
                    name=name,
                    market=_pick(
                        row,
                        (
                            "market",
                            "exchange",
                            "market_code",
                            "mkt_id_cd",
                            "rprs_mrkt_kor_name",
                            "rprs_mrkt_name",
                        ),
                    ),
                    listing_status=_normalize_listing_status(
                        _pick(
                            row,
                            (
                                "listing_status",
                                "status",
                                "prdt_stat_name",
                                "list_yn",
                                "list_stat",
                                "lstg_yn",
                            ),
                        )
                    ),
                    market_classification=_pick(
                        row,
                        (
                            "market_classification",
                            "scty_grp_cls_code",
                            "classification",
                            "scty_cls_code",
                            "idx_bztp_lcls_cd_name",
                        ),
                    ),
                    source_url=source_url,
                )
            )

        return records


def _parse_response_paths(value: str | None) -> tuple[str, ...]:
    if not value:
        return _DEFAULT_RESPONSE_PATHS
    paths = tuple(part.strip() for part in value.split(",") if part.strip())
    return paths or _DEFAULT_RESPONSE_PATHS


def _parse_query_params_json(value: str | None) -> dict[str, str]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("KIS_SYMBOL_MASTER_QUERY_PARAMS_JSON must be valid JSON object") from error

    if not isinstance(payload, dict):
        raise ValueError("KIS_SYMBOL_MASTER_QUERY_PARAMS_JSON must be a JSON object")

    params: dict[str, str] = {}
    for key, raw_value in payload.items():
        if raw_value is None:
            continue
        params[str(key)] = str(raw_value)
    return params


def create_kis_master_client(
    *,
    provider: str,
    file_path: str | None,
    base_url: str,
    symbol_master_path: str,
    app_key: str | None,
    app_secret: str | None,
    access_token: str | None,
    response_paths: str | None = None,
    query_params_json: str | None = None,
    tr_id: str | None = None,
) -> KisFileMasterClient | KisApiMasterClient:
    normalized_provider = provider.strip().lower()
    if normalized_provider == "file":
        if not file_path:
            raise ValueError("KIS master file provider requires KIS_MASTER_FILE_PATH")
        return KisFileMasterClient(file_path=file_path)

    if normalized_provider == "api":
        return KisApiMasterClient(
            base_url=base_url,
            symbol_master_path=symbol_master_path,
            app_key=app_key or "",
            app_secret=app_secret or "",
            access_token=access_token or "",
            response_paths=_parse_response_paths(response_paths),
            query_params=_parse_query_params_json(query_params_json),
            tr_id=tr_id,
        )

    raise ValueError(f"Unsupported KIS master provider: {provider}")
