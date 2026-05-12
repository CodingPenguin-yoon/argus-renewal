from __future__ import annotations

from datetime import date, datetime, timezone
import logging
from typing import Any

import httpx

from .kis_common import (
    as_float,
    extract_rows,
    fetch_json_with_retries,
    load_json_file,
    parse_query_params_json,
    parse_response_paths,
    pick_float,
    pick_text,
    value_by_path,
)
from .models import (
    BriefingProviderBatch,
    DerivativesOptionChainLevelRecord,
    DerivativesOptionChainSnapshotRecord,
    DerivativesSourceStatusRecord,
)


logger = logging.getLogger(__name__)

KIS_OPTION_CHAIN_SOURCE_NAME = "KIS_DOMESTIC_DERIVATIVES"
DEFAULT_UNDERLYING_CODE = "KOSPI200"
DEFAULT_UNDERLYING_NAME = "KOSPI200"
DEFAULT_STALE_AFTER_SECONDS = 300
DEFAULT_KIS_OPTION_CHAIN_PATH = "/uapi/domestic-futureoption/v1/quotations/display-board-callput"
DEFAULT_KIS_OPTION_CHAIN_TR_ID = "FHPIF05030100"
DEFAULT_KIS_OPTION_LIST_PATH = "/uapi/domestic-futureoption/v1/quotations/display-board-option-list"
DEFAULT_KIS_OPTION_LIST_TR_ID = "FHPIO056104C0"
DEFAULT_KIS_OPTION_LIST_RESPONSE_PATHS = "output,data.items,data.rows,data"
DEFAULT_KIS_OPTION_CHAIN_QUERY_PARAMS = {
    "FID_COND_MRKT_DIV_CODE": "O",
    "FID_COND_SCR_DIV_CODE": "20503",
    "FID_MRKT_CLS_CODE": "CO",
    "FID_MRKT_CLS_CODE1": "PO",
    "FID_COND_MRKT_CLS_CODE": "",
}
DEFAULT_KIS_OPTION_LIST_QUERY_PARAMS = {
    "FID_COND_SCR_DIV_CODE": "509",
    "FID_COND_MRKT_DIV_CODE": "O",
    "FID_COND_MRKT_CLS_CODE": "",
}


class KisOptionChainService:
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
        expiry_month: str | None = None,
        expiry_list_path: str | None = None,
        expiry_list_response_paths: str | None = None,
        expiry_list_query_params_json: str | None = None,
        expiry_list_tr_id: str | None = None,
        expected_level_count: int | None = None,
        stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.provider = provider.strip().lower()
        self.file_path = file_path
        self.base_url = base_url.rstrip("/")
        self.endpoint_path = endpoint_path or DEFAULT_KIS_OPTION_CHAIN_PATH
        self.app_key = (app_key or "").strip()
        self.app_secret = (app_secret or "").strip()
        self.access_token = (access_token or "").strip()
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.response_paths = parse_response_paths(response_paths)
        self.query_params = parse_query_params_json(query_params_json)
        self.tr_id = (tr_id or "").strip() or DEFAULT_KIS_OPTION_CHAIN_TR_ID
        self.expiry_month = (expiry_month or "").strip() or None
        self.expiry_list_path = (expiry_list_path or "").strip() or DEFAULT_KIS_OPTION_LIST_PATH
        self.expiry_list_response_paths = parse_response_paths(expiry_list_response_paths or DEFAULT_KIS_OPTION_LIST_RESPONSE_PATHS)
        self.expiry_list_query_params = parse_query_params_json(expiry_list_query_params_json)
        self.expiry_list_tr_id = (expiry_list_tr_id or "").strip() or DEFAULT_KIS_OPTION_LIST_TR_ID
        self.expected_level_count = expected_level_count if expected_level_count and expected_level_count > 0 else None
        self.stale_after_seconds = stale_after_seconds
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
            return True, None
        return False, f"unsupported_provider:{self.provider}"

    def fetch_option_chain_snapshot(
        self,
        *,
        trade_date: date,
        snapshot_time: datetime | None = None,
    ) -> BriefingProviderBatch:
        enabled, reason = self.is_enabled()
        snapshot_at = (snapshot_time or datetime.now(timezone.utc)).astimezone(timezone.utc)
        snapshot_iso = snapshot_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        if not enabled:
            return BriefingProviderBatch(records=[], disabled_reason=reason)

        if self.provider == "file":
            source_url = self.file_path
            payload = load_json_file(self.file_path or "")
            retry_count = 0
        else:
            source_url = f"{self.base_url}{self.endpoint_path}"
            payload, retry_count = self._fetch_api_payload(trade_date=trade_date)

        rows = self._extract_level_rows(payload=payload, trade_date=trade_date)
        levels = self._normalize_levels(rows=rows, payload=payload)
        expected_count = self.expected_level_count or len(levels) or None
        freshness_state = self._freshness_state(observed_count=len(levels), expected_count=expected_count)
        status = "available" if freshness_state == "fresh" else freshness_state
        records: list[Any] = [
            DerivativesSourceStatusRecord(
                trade_date=trade_date.isoformat(),
                source_name=KIS_OPTION_CHAIN_SOURCE_NAME,
                source_scope="OPTION_CHAIN",
                status=status,
                expected_count=expected_count,
                observed_count=len(levels),
                latest_observed_at=snapshot_iso if levels else None,
                stale_after_seconds=self.stale_after_seconds,
                message=None if levels else "option_chain_levels_missing",
                metadata={"provider": self.provider, "source_url": source_url},
            )
        ]
        if levels:
            records.insert(
                0,
                self._build_snapshot_record(
                    payload=payload,
                    trade_date=trade_date,
                    snapshot_time=snapshot_iso,
                    source_url=source_url,
                    expected_count=expected_count,
                    freshness_state=freshness_state,
                    levels=levels,
                ),
            )
        return BriefingProviderBatch(
            records=records,
            metadata={"provider": self.provider, "level_count": len(levels), "expected_level_count": expected_count, "freshness_state": freshness_state},
            retry_count=retry_count,
        )

    def _fetch_api_payload(self, *, trade_date: date) -> tuple[Any, int]:
        url = f"{self.base_url}{self.endpoint_path}"
        headers = self._kis_headers(tr_id=self.tr_id)
        params = self._render_query_params(trade_date=trade_date)
        payload, retry_count = fetch_json_with_retries(
            logger=logger,
            log_prefix="argus_v2_kis_option_chain_fetch",
            max_retries=self.max_retries,
            backoff_seconds=self.backoff_seconds,
            do_request=lambda: self._do_request(url=url, headers=headers, params=params),
        )
        if isinstance(payload, dict):
            expiry_month = self._query_param_value("FID_MTRT_CNT", params=params)
            if expiry_month:
                payload.setdefault("_argus_option_expiry_month", expiry_month)
        return payload, retry_count

    def _kis_headers(self, *, tr_id: str | None) -> dict[str, str]:
        headers = {
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "authorization": f"Bearer {self.access_token}",
            "content-type": "application/json; charset=utf-8",
        }
        if tr_id:
            headers["tr_id"] = tr_id
        return headers

    def _do_request(self, *, url: str, headers: dict[str, str], params: dict[str, str]) -> httpx.Response:
        if self._http_client is not None:
            return self._http_client.get(url, headers=headers, params=params, timeout=self.timeout_seconds)
        with httpx.Client() as client:
            return client.get(url, headers=headers, params=params, timeout=self.timeout_seconds)

    def _render_query_params(self, *, trade_date: date) -> dict[str, str]:
        rendered = dict(DEFAULT_KIS_OPTION_CHAIN_QUERY_PARAMS)
        rendered.update({key: value.replace("{trade_date}", trade_date.isoformat()) for key, value in self.query_params.items()})
        if not self._query_param_value("FID_MTRT_CNT", params=rendered):
            rendered["FID_MTRT_CNT"] = self.expiry_month or self._resolve_option_expiry_month(trade_date=trade_date)
        return rendered

    def _render_expiry_list_query_params(self, *, trade_date: date) -> dict[str, str]:
        rendered = dict(DEFAULT_KIS_OPTION_LIST_QUERY_PARAMS)
        rendered.update({key: value.replace("{trade_date}", trade_date.isoformat()) for key, value in self.expiry_list_query_params.items()})
        return rendered

    def _resolve_option_expiry_month(self, *, trade_date: date) -> str:
        url = f"{self.base_url}{self.expiry_list_path}"
        headers = self._kis_headers(tr_id=self.expiry_list_tr_id)
        params = self._render_expiry_list_query_params(trade_date=trade_date)
        payload, _ = fetch_json_with_retries(
            logger=logger,
            log_prefix="argus_v2_kis_option_expiry_list_fetch",
            max_retries=self.max_retries,
            backoff_seconds=self.backoff_seconds,
            do_request=lambda: self._do_request(url=url, headers=headers, params=params),
        )
        expiry_month = self._pick_expiry_month(payload=payload, trade_date=trade_date)
        if not expiry_month:
            raise ValueError("kis_option_expiry_month_missing")
        return expiry_month

    def _pick_expiry_month(self, *, payload: Any, trade_date: date) -> str | None:
        candidates = []
        for row in extract_rows(payload, self.expiry_list_response_paths):
            raw = pick_text(row, ("mtrt_yymm", "mtrt_yymm_code", "FID_MTRT_CNT", "contract_month", "maturity_month", "yyyymm"))
            digits = "".join(ch for ch in (raw or "") if ch.isdigit())
            if len(digits) >= 6:
                candidates.append(digits[:6])
        current_month = trade_date.strftime("%Y%m")
        for candidate in candidates:
            if candidate >= current_month:
                return candidate
        return candidates[0] if candidates else None

    def _query_param_value(self, key: str, *, params: dict[str, str] | None = None) -> str | None:
        normalized_key = "".join(ch for ch in key.lower() if ch not in {"_", "-", " "})
        source = params if params is not None else self.query_params
        for candidate_key, candidate_value in source.items():
            normalized_candidate = "".join(ch for ch in candidate_key.lower() if ch not in {"_", "-", " "})
            if normalized_candidate == normalized_key and str(candidate_value).strip():
                return str(candidate_value).strip()
        return None

    def _extract_level_rows(self, *, payload: Any, trade_date: date) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            direct_rows = payload.get(trade_date.isoformat())
            if isinstance(direct_rows, list) and all(isinstance(item, dict) for item in direct_rows):
                return direct_rows
            callput_rows = self._extract_callput_output_rows(payload)
            if callput_rows:
                return callput_rows
        return extract_rows(payload, self.response_paths)

    def _extract_callput_output_rows(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path, side in (("output1", "CALL"), ("output2", "PUT"), ("data.output1", "CALL"), ("data.output2", "PUT")):
            candidate = value_by_path(payload, path)
            if isinstance(candidate, list) and all(isinstance(item, dict) for item in candidate):
                for row in candidate:
                    annotated = dict(row)
                    annotated.setdefault("_argus_option_side", side)
                    rows.append(annotated)
        return rows

    def _normalize_levels(self, *, rows: list[dict[str, Any]], payload: Any) -> list[DerivativesOptionChainLevelRecord]:
        buckets: dict[float, dict[str, Any]] = {}
        underlying_price = self._underlying_price(payload=payload)
        for index, row in enumerate(rows):
            strike = pick_float(row, ("strike_price", "strike", "exercise_price", "acpr", "optn_stk_prc"))
            if strike is None:
                continue
            bucket = buckets.setdefault(strike, {"strike_price": strike, "metadata": {"row_count": 0}})
            bucket["metadata"]["row_count"] += 1
            bucket["metadata"]["last_row_index"] = index
            side = self._option_side(row)
            if side == "CALL":
                self._merge_side_fields(bucket=bucket, row=row, side="call")
            elif side == "PUT":
                self._merge_side_fields(bucket=bucket, row=row, side="put")
            else:
                self._merge_combined_fields(bucket=bucket, row=row)

        levels = []
        atm_strike = self._nearest_atm_strike(underlying_price=underlying_price, strikes=list(buckets))
        for strike, bucket in sorted(buckets.items()):
            call_oi = as_float(bucket.get("call_open_interest"))
            put_oi = as_float(bucket.get("put_open_interest"))
            total_oi = as_float(bucket.get("total_open_interest"))
            if total_oi is None and (call_oi is not None or put_oi is not None):
                total_oi = (call_oi or 0.0) + (put_oi or 0.0)
            net_oi = as_float(bucket.get("net_call_put_oi"))
            if net_oi is None and (call_oi is not None or put_oi is not None):
                net_oi = (call_oi or 0.0) - (put_oi or 0.0)
            ratio = as_float(bucket.get("call_put_oi_ratio"))
            if ratio is None and call_oi is not None and put_oi not in {None, 0}:
                ratio = call_oi / put_oi
            levels.append(
                DerivativesOptionChainLevelRecord(
                    strike_price=strike,
                    moneyness="ATM" if atm_strike is not None and abs(strike - atm_strike) < 1e-9 else "UNKNOWN",
                    call_last_price=as_float(bucket.get("call_last_price")),
                    call_change_rate=as_float(bucket.get("call_change_rate")),
                    call_volume=as_float(bucket.get("call_volume")),
                    call_open_interest=call_oi,
                    call_open_interest_change=as_float(bucket.get("call_open_interest_change")),
                    call_implied_volatility=as_float(bucket.get("call_implied_volatility")),
                    put_last_price=as_float(bucket.get("put_last_price")),
                    put_change_rate=as_float(bucket.get("put_change_rate")),
                    put_volume=as_float(bucket.get("put_volume")),
                    put_open_interest=put_oi,
                    put_open_interest_change=as_float(bucket.get("put_open_interest_change")),
                    put_implied_volatility=as_float(bucket.get("put_implied_volatility")),
                    total_open_interest=total_oi,
                    net_call_put_oi=net_oi,
                    call_put_oi_ratio=ratio,
                    pressure_side=self._pressure_side(net_oi),
                    metadata=bucket.get("metadata") or {},
                )
            )
        return levels

    def _merge_side_fields(self, *, bucket: dict[str, Any], row: dict[str, Any], side: str) -> None:
        bucket[f"{side}_last_price"] = bucket.get(f"{side}_last_price") or pick_float(row, ("last_price", "price", "current_price", "stck_prpr", "optn_prpr"))
        bucket[f"{side}_change_rate"] = bucket.get(f"{side}_change_rate") or pick_float(row, ("change_rate", "chg_rate", "prdy_ctrt", "optn_prdy_ctrt"))
        bucket[f"{side}_volume"] = bucket.get(f"{side}_volume") or pick_float(row, ("volume", "acml_vol", "cntg_vol", "trading_volume"))
        bucket[f"{side}_open_interest"] = bucket.get(f"{side}_open_interest") or pick_float(row, ("open_interest", "oi", "hts_otst_stpl_qty", "openint"))
        bucket[f"{side}_open_interest_change"] = bucket.get(f"{side}_open_interest_change") or pick_float(row, ("open_interest_change", "oi_change", "otst_stpl_qty_icdc"))
        bucket[f"{side}_implied_volatility"] = bucket.get(f"{side}_implied_volatility") or pick_float(row, ("implied_volatility", "iv", "hts_ints_vltl"))

    def _merge_combined_fields(self, *, bucket: dict[str, Any], row: dict[str, Any]) -> None:
        for field, aliases in {
            "call_last_price": ("call_last_price", "call_price", "call_prpr"),
            "call_volume": ("call_volume", "call_acml_vol"),
            "call_open_interest": ("call_open_interest", "call_oi", "call_hts_otst_stpl_qty"),
            "put_last_price": ("put_last_price", "put_price", "put_prpr"),
            "put_volume": ("put_volume", "put_acml_vol"),
            "put_open_interest": ("put_open_interest", "put_oi", "put_hts_otst_stpl_qty"),
            "total_open_interest": ("total_open_interest", "open_interest_total", "total_oi"),
            "net_call_put_oi": ("net_call_put_oi", "call_put_oi_diff", "net_oi"),
            "call_put_oi_ratio": ("call_put_oi_ratio", "call_put_ratio", "oi_ratio"),
        }.items():
            bucket[field] = bucket.get(field) or pick_float(row, aliases)

    def _build_snapshot_record(
        self,
        *,
        payload: Any,
        trade_date: date,
        snapshot_time: str,
        source_url: str | None,
        expected_count: int | None,
        freshness_state: str,
        levels: list[DerivativesOptionChainLevelRecord],
    ) -> DerivativesOptionChainSnapshotRecord:
        meta = payload if isinstance(payload, dict) else {}
        contract_month = pick_text(meta, ("contract_month", "yyyymm", "maturity_month", "_argus_option_expiry_month", "fid_mtrt_cnt"))
        expiry_date = pick_text(meta, ("expiry_date", "maturity_date", "exp_date")) or contract_month or "unknown"
        underlying_price = self._underlying_price(payload=payload)
        atm_strike = self._nearest_atm_strike(underlying_price=underlying_price, strikes=[level.strike_price for level in levels])
        return DerivativesOptionChainSnapshotRecord(
            source_name=KIS_OPTION_CHAIN_SOURCE_NAME,
            trade_date=trade_date.isoformat(),
            snapshot_time=snapshot_time,
            expiry_date=expiry_date,
            market_scope="KRX",
            underlying_code=DEFAULT_UNDERLYING_CODE,
            underlying_name=DEFAULT_UNDERLYING_NAME,
            underlying_price=underlying_price,
            contract_month=contract_month,
            source_url=source_url,
            source_record_id=f"option-chain-{trade_date.isoformat()}",
            atm_strike=atm_strike,
            expected_level_count=expected_count,
            observed_level_count=len(levels),
            freshness_state=freshness_state,
            raw_payload=payload,
            levels=levels,
        )

    def _freshness_state(self, *, observed_count: int, expected_count: int | None) -> str:
        if observed_count <= 0:
            return "missing"
        if expected_count and observed_count < expected_count:
            return "partial"
        return "fresh"

    def _underlying_price(self, *, payload: Any) -> float | None:
        meta = payload if isinstance(payload, dict) else {}
        value = pick_float(meta, ("underlying_price", "index_price", "kospi200", "underlying_current_price", "nmix_sdpr"))
        if value is not None:
            return value
        rows = self._extract_callput_output_rows(meta) if isinstance(meta, dict) else []
        for row in rows:
            value = pick_float(row, ("underlying_price", "index_price", "kospi200", "underlying_current_price", "nmix_sdpr"))
            if value is not None:
                return value
        return None

    def _nearest_atm_strike(self, *, underlying_price: float | None, strikes: list[float]) -> float | None:
        if not strikes:
            return None
        if underlying_price is None:
            return sorted(strikes)[len(strikes) // 2]
        return min(strikes, key=lambda strike: abs(strike - underlying_price))

    def _option_side(self, row: dict[str, Any]) -> str | None:
        raw = pick_text(row, ("_argus_option_side", "option_side", "option_type", "cp", "call_put", "put_call", "optn_type", "trad_dvsn_name"))
        normalized = (raw or "").strip().upper()
        if normalized in {"C", "CALL", "CE"} or "콜" in normalized:
            return "CALL"
        if normalized in {"P", "PUT", "PE"} or "풋" in normalized:
            return "PUT"
        return None

    def _pressure_side(self, net_oi: float | None) -> str:
        if net_oi is None:
            return "UNKNOWN"
        if net_oi > 0:
            return "CALL"
        if net_oi < 0:
            return "PUT"
        return "BALANCED"
