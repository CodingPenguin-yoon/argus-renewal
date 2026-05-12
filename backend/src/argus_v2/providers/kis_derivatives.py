from __future__ import annotations

import io
from datetime import date, datetime, timezone
import logging
from typing import Any
import zipfile

import httpx

from .kis_common import (
    extract_rows,
    fetch_json_with_retries,
    load_json_file,
    parse_query_params_json,
    parse_response_paths,
    pick_float,
    pick_text,
)
from .models import BriefingProviderBatch, MarketIntradaySnapshotRecord


logger = logging.getLogger(__name__)

DEFAULT_KIS_DOMESTIC_DERIVATIVES_TR_ID = "FHMIF10000000"
DEFAULT_KIS_DOMESTIC_DERIVATIVES_MARKET_DIV_CODE = "F"
AUTO_KIS_DOMESTIC_DERIVATIVES_INPUT_ISCD = "AUTO_KOSPI200_FRONT"
KIS_DOMESTIC_DERIVATIVES_MASTER_URL = "https://new.real.download.dws.co.kr/common/master/fo_idx_code_mts.mst.zip"
KIS_DOMESTIC_DERIVATIVES_MASTER_ENTRY_NAME = "fo_idx_code_mts.mst"


class KisDomesticDerivativesService:
    def __init__(
        self,
        *,
        provider: str,
        file_path: str | None,
        base_url: str,
        endpoint_path: str,
        app_key: str | None,
        app_secret: str | None,
        access_token: str | None,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        response_paths: str | None = None,
        query_params_json: str | None = None,
        field_alias_map_json: str | None = None,
        tr_id: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.provider = provider.strip().lower()
        self.file_path = file_path
        self.base_url = base_url.rstrip("/")
        self.endpoint_path = endpoint_path
        self.app_key = (app_key or "").strip()
        self.app_secret = (app_secret or "").strip()
        self.access_token = (access_token or "").strip()
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.response_paths = parse_response_paths(response_paths)
        self.query_params = parse_query_params_json(query_params_json)
        self.tr_id = (tr_id or "").strip() or DEFAULT_KIS_DOMESTIC_DERIVATIVES_TR_ID
        self._http_client = http_client

    def is_enabled(self) -> tuple[bool, str | None]:
        if self.provider in {"", "disabled"}:
            return False, "feature_flag_disabled"
        if self.provider == "file":
            return (True, None) if self.file_path else (False, "missing_file_path")
        if self.provider == "api":
            if not self.endpoint_path:
                return False, "missing_endpoint_path"
            if not self.app_key or not self.app_secret or not self.access_token:
                return False, "missing_kis_credentials"
            if not self._query_param_value("FID_INPUT_ISCD"):
                return False, "missing_fid_input_iscd"
            return True, None
        return False, f"unsupported_provider:{self.provider}"

    def fetch_pre_open_snapshots(
        self,
        *,
        trade_date: date,
        snapshot_time: datetime | None = None,
    ) -> BriefingProviderBatch:
        enabled, reason = self.is_enabled()
        if not enabled:
            return BriefingProviderBatch(records=[], disabled_reason=reason)

        if self.provider == "file":
            source_url = self.file_path
            payload = load_json_file(self.file_path or "")
            retry_count = 0
        else:
            source_url = f"{self.base_url}{self.endpoint_path}"
            payload, retry_count = self._fetch_api_payload(trade_date=trade_date)

        rows = self._extract_rows(payload=payload, trade_date=trade_date)
        snapshot_at = (snapshot_time or datetime.now(timezone.utc)).astimezone(timezone.utc)
        snapshot_iso = snapshot_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        records = [
            self._normalize_row(
                row=row,
                index=index,
                trade_date=trade_date,
                snapshot_time=snapshot_iso,
                source_url=source_url,
            )
            for index, row in enumerate(rows)
        ]
        return BriefingProviderBatch(
            records=records,
            metadata={"row_count": len(rows), "provider": self.provider},
            retry_count=retry_count,
        )

    def _fetch_api_payload(self, *, trade_date: date) -> tuple[Any, int]:
        url = f"{self.base_url}{self.endpoint_path}"
        headers = {
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "authorization": f"Bearer {self.access_token}",
            "content-type": "application/json; charset=utf-8",
            "tr_id": self.tr_id,
        }
        params = self._render_query_params(trade_date=trade_date)
        return fetch_json_with_retries(
            logger=logger,
            log_prefix="argus_v2_kis_derivatives_fetch",
            max_retries=self.max_retries,
            backoff_seconds=self.backoff_seconds,
            do_request=lambda: self._do_request(url=url, headers=headers, params=params),
        )

    def _do_request(self, *, url: str, headers: dict[str, str], params: dict[str, str]) -> httpx.Response:
        if self._http_client is not None:
            return self._http_client.get(url, headers=headers, params=params, timeout=self.timeout_seconds)
        with httpx.Client() as client:
            return client.get(url, headers=headers, params=params, timeout=self.timeout_seconds)

    def _render_query_params(self, *, trade_date: date) -> dict[str, str]:
        rendered = {key: value.replace("{trade_date}", trade_date.isoformat()) for key, value in self.query_params.items()}
        if not self._query_param_value("FID_COND_MRKT_DIV_CODE", params=rendered):
            rendered["FID_COND_MRKT_DIV_CODE"] = DEFAULT_KIS_DOMESTIC_DERIVATIVES_MARKET_DIV_CODE
        if self._query_param_value("FID_INPUT_ISCD", params=rendered) == AUTO_KIS_DOMESTIC_DERIVATIVES_INPUT_ISCD:
            rendered["FID_INPUT_ISCD"] = self._resolve_auto_input_iscd()
        return rendered

    def _query_param_value(self, key: str, *, params: dict[str, str] | None = None) -> str | None:
        normalized_key = "".join(ch for ch in key.lower() if ch not in {"_", "-", " "})
        source = params if params is not None else self.query_params
        for candidate_key, candidate_value in source.items():
            normalized_candidate = "".join(ch for ch in candidate_key.lower() if ch not in {"_", "-", " "})
            if normalized_candidate == normalized_key and str(candidate_value).strip():
                return str(candidate_value).strip()
        return None

    def _resolve_auto_input_iscd(self) -> str:
        payload = self._download_master_archive()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            raw = archive.read(KIS_DOMESTIC_DERIVATIVES_MASTER_ENTRY_NAME)
        rows = raw.decode("cp949", errors="ignore").splitlines()
        for row in rows:
            parts = [part.strip() for part in row.split("|")]
            if len(parts) < 9:
                continue
            product_type, short_code, name, maturity_division, underlying_name = parts[0], parts[1], parts[3], parts[6], parts[8]
            if product_type == "1" and maturity_division == "1" and underlying_name == "KOSPI200" and short_code:
                logger.info("argus_v2_kis_front_month_resolved", extra={"name": name, "short_code": short_code})
                return short_code
        raise ValueError("auto_kospi200_front_symbol_not_found")

    def _download_master_archive(self) -> bytes:
        if self._http_client is not None:
            response = self._http_client.get(KIS_DOMESTIC_DERIVATIVES_MASTER_URL, timeout=self.timeout_seconds)
        else:
            with httpx.Client() as client:
                response = client.get(KIS_DOMESTIC_DERIVATIVES_MASTER_URL, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response.content

    def _extract_rows(self, *, payload: Any, trade_date: date) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            dated = payload.get(trade_date.isoformat())
            if isinstance(dated, dict):
                return [dated]
            if self._looks_like_snapshot_row(payload):
                return [payload]
        rows = extract_rows(payload, self.response_paths)
        return [row for row in rows if self._looks_like_snapshot_row(row)] or rows

    def _normalize_row(
        self,
        *,
        row: dict[str, Any],
        index: int,
        trade_date: date,
        snapshot_time: str,
        source_url: str | None,
    ) -> MarketIntradaySnapshotRecord:
        instrument_code = pick_text(row, ("instrument_code", "futures_code", "symbol", "code", "pdno", "futs_shrn_iscd", "optn_shrn_iscd"))
        open_interest = pick_float(row, ("open_interest", "opn_interest", "open_int", "hts_otst_stpl_qty"))
        open_interest_change = pick_float(row, ("open_interest_change", "oi_change", "otst_stpl_qty_icdc"))
        return MarketIntradaySnapshotRecord(
            source_name="KIS_DOMESTIC_DERIVATIVES",
            trade_date=trade_date.isoformat(),
            snapshot_time=snapshot_time,
            session_type="PRE_OPEN",
            instrument_code=instrument_code or f"UNKNOWN_{index + 1}",
            instrument_name=pick_text(row, ("instrument_name", "name", "prdt_name", "hts_kor_isnm")),
            price=pick_float(row, ("price", "current_price", "stck_prpr", "futs_prpr", "last")),
            price_change=pick_float(row, ("price_change", "change", "prdy_vrss", "futs_prdy_vrss", "diff")),
            change_rate=pick_float(row, ("change_rate", "chg_rate", "prdy_ctrt", "futs_prdy_ctrt", "rate")),
            volume=pick_float(row, ("volume", "acml_vol", "trade_volume")),
            open_interest=open_interest,
            put_call_ratio=pick_float(row, ("put_call_ratio", "putcall_ratio", "pcr")),
            implied_volatility=pick_float(row, ("implied_volatility", "iv", "impl_vol", "hts_ints_vltl", "hist_vltl", "unas_hist_vltl")),
            source_url=source_url,
            source_record_id=pick_text(row, ("id", "record_id", "seq")),
            raw_payload=row,
            additional_metrics={
                "bid": pick_float(row, ("bid", "bid_price", "best_bid")),
                "ask": pick_float(row, ("ask", "ask_price", "best_ask")),
                "basis": pick_float(row, ("basis",)),
                "market_basis": pick_float(row, ("market_basis", "mrkt_basis")),
                "theoretical_price": pick_float(row, ("theoretical_price", "hts_thpr")),
                "disparity_rate": pick_float(row, ("disparity_rate", "dprt")),
                "open_interest_change": open_interest_change,
                "open_interest_change_rate": _open_interest_change_rate(
                    open_interest=open_interest,
                    open_interest_change=open_interest_change,
                ),
            },
        )

    def _looks_like_snapshot_row(self, payload: dict[str, Any]) -> bool:
        return bool(pick_text(payload, ("instrument_code", "futures_code", "symbol", "code", "pdno", "futs_shrn_iscd", "hts_kor_isnm")))


def _open_interest_change_rate(*, open_interest: float | None, open_interest_change: float | None) -> float | None:
    if open_interest is None or open_interest_change is None:
        return None
    previous = open_interest - open_interest_change
    if previous == 0:
        return None
    return (open_interest_change / previous) * 100
