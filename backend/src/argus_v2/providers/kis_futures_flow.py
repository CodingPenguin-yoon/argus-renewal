from __future__ import annotations

from datetime import date, datetime, timezone
import logging
from typing import Any

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
from .models import BriefingProviderBatch, FuturesInvestorFlowSnapshotRecord


logger = logging.getLogger(__name__)

KIS_FUTURES_INVESTOR_FLOW_SOURCE_NAME = "KIS_FUTURES_INVESTOR_FLOW"
DEFAULT_KIS_FUTURES_INVESTOR_FLOW_RESPONSE_PATHS = "output,output1,output2,data.output,data.output1,data.output2,items,rows,data.items,data.rows,data"

DIRECT_FOREIGN_ALIASES = ("foreign_futures_net_buy", "foreign_net_buy", "frgn_futures_net_buy", "frgn_net_buy", "frgn_net_buy_krw")
DIRECT_INSTITUTION_ALIASES = ("institution_futures_net_buy", "institution_net_buy", "orgn_futures_net_buy", "orgn_net_buy", "inst_net_buy_krw")
DIRECT_INDIVIDUAL_ALIASES = ("individual_futures_net_buy", "individual_net_buy", "prsn_futures_net_buy", "prsn_net_buy", "indv_net_buy_krw")

AMOUNT_FOREIGN_ALIASES = ("frgn_ntby_tr_pbmn", "frgn_ntby_pbmn", "frgn_ntby_amt", "frgn_ntby_tr_amt")
AMOUNT_INSTITUTION_ALIASES = ("orgn_ntby_tr_pbmn", "orgn_ntby_pbmn", "inst_ntby_tr_pbmn", "institution_ntby_tr_pbmn", "orgn_ntby_amt")
AMOUNT_INDIVIDUAL_ALIASES = ("prsn_ntby_tr_pbmn", "prsn_ntby_pbmn", "indv_ntby_tr_pbmn", "individual_ntby_tr_pbmn", "prsn_ntby_amt")

PARTICIPANT_ALIASES = ("investor", "investor_type", "participant", "participant_name", "invst_tcd_nm", "invst_dvsn_name", "invst_dvsn_nm", "trdptn_nm")
ROW_NET_BUY_DIRECT_ALIASES = ("futures_net_buy", "net_buy", "net_buy_krw", "ntby", "ntby_krw")
ROW_NET_BUY_AMOUNT_ALIASES = ("ntby_tr_pbmn", "ntby_pbmn", "net_buy_amount", "net_buy_tr_pbmn")


class KisFuturesInvestorFlowService:
    def __init__(
        self,
        *,
        provider: str,
        file_path: str | None,
        base_url: str,
        endpoint_path: str | None,
        app_key: str | None,
        app_secret: str | None,
        access_token: str | None,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        response_paths: str | None = None,
        query_params_json: str | None = None,
        tr_id: str | None = None,
        amount_multiplier: float = 10000.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.provider = provider.strip().lower()
        self.file_path = file_path
        self.base_url = base_url.rstrip("/")
        self.endpoint_path = endpoint_path or ""
        self.app_key = (app_key or "").strip()
        self.app_secret = (app_secret or "").strip()
        self.access_token = (access_token or "").strip()
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.response_paths = parse_response_paths(response_paths or DEFAULT_KIS_FUTURES_INVESTOR_FLOW_RESPONSE_PATHS)
        self.query_params = parse_query_params_json(query_params_json)
        self.tr_id = (tr_id or "").strip()
        self.amount_multiplier = amount_multiplier
        self._http_client = http_client

    def is_enabled(self) -> tuple[bool, str | None]:
        if self.provider in {"", "disabled"}:
            return False, "feature_flag_disabled"
        if self.provider == "file":
            return (True, None) if self.file_path else (False, "missing_file_path")
        if self.provider == "api":
            if not self.endpoint_path:
                return False, "missing_endpoint_path"
            if not self.tr_id:
                return False, "missing_tr_id"
            if not self.app_key or not self.app_secret or not self.access_token:
                return False, "missing_kis_credentials"
            return True, None
        return False, f"unsupported_provider:{self.provider}"

    def fetch_snapshot(
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
        values = _flow_values(rows=rows, multiplier=self.amount_multiplier)
        if not any(value is not None for value in values.values()):
            return BriefingProviderBatch(
                records=[],
                metadata={"provider": self.provider, "row_count": len(rows), "message": "futures_investor_flow_fields_missing"},
                retry_count=retry_count,
            )

        snapshot_at = (snapshot_time or datetime.now(timezone.utc)).astimezone(timezone.utc)
        snapshot_iso = snapshot_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        record = FuturesInvestorFlowSnapshotRecord(
            source_name=KIS_FUTURES_INVESTOR_FLOW_SOURCE_NAME,
            trade_date=trade_date.isoformat(),
            snapshot_time=snapshot_iso,
            foreign_net_buy=values["foreign"],
            institution_net_buy=values["institution"],
            individual_net_buy=values["individual"],
            source_url=source_url,
            source_record_id=f"futures-investor-flow-{trade_date.isoformat()}",
            raw_payload=payload,
        )
        return BriefingProviderBatch(
            records=[record],
            metadata={"provider": self.provider, "row_count": len(rows), "expected_count": 1},
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
        params = {key: value.replace("{trade_date}", trade_date.isoformat()).replace("{trade_date_yyyymmdd}", trade_date.strftime("%Y%m%d")) for key, value in self.query_params.items()}
        return fetch_json_with_retries(
            logger=logger,
            log_prefix="argus_v2_kis_futures_investor_flow_fetch",
            max_retries=self.max_retries,
            backoff_seconds=self.backoff_seconds,
            do_request=lambda: self._do_request(url=url, headers=headers, params=params),
        )

    def _do_request(self, *, url: str, headers: dict[str, str], params: dict[str, str]) -> httpx.Response:
        if self._http_client is not None:
            return self._http_client.get(url, headers=headers, params=params, timeout=self.timeout_seconds)
        with httpx.Client() as client:
            return client.get(url, headers=headers, params=params, timeout=self.timeout_seconds)

    def _extract_rows(self, *, payload: Any, trade_date: date) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            dated = payload.get(trade_date.isoformat()) or payload.get(trade_date.strftime("%Y%m%d"))
            if isinstance(dated, dict):
                return [dated]
            if _looks_like_wide_flow_row(payload):
                return [payload]
        return extract_rows(payload, self.response_paths)


def _flow_values(*, rows: list[dict[str, Any]], multiplier: float) -> dict[str, float | None]:
    wide_row = next((row for row in rows if _looks_like_wide_flow_row(row)), None)
    if wide_row is not None:
        return {
            "foreign": _direct_or_amount(wide_row, direct_aliases=DIRECT_FOREIGN_ALIASES, amount_aliases=AMOUNT_FOREIGN_ALIASES, multiplier=multiplier),
            "institution": _direct_or_amount(wide_row, direct_aliases=DIRECT_INSTITUTION_ALIASES, amount_aliases=AMOUNT_INSTITUTION_ALIASES, multiplier=multiplier),
            "individual": _direct_or_amount(wide_row, direct_aliases=DIRECT_INDIVIDUAL_ALIASES, amount_aliases=AMOUNT_INDIVIDUAL_ALIASES, multiplier=multiplier),
        }

    values: dict[str, float | None] = {"foreign": None, "institution": None, "individual": None}
    for row in rows:
        participant = _participant_key(row)
        if participant is None:
            continue
        value = _direct_or_amount(row, direct_aliases=ROW_NET_BUY_DIRECT_ALIASES, amount_aliases=ROW_NET_BUY_AMOUNT_ALIASES, multiplier=multiplier)
        if value is not None:
            values[participant] = value
    return values


def _looks_like_wide_flow_row(row: dict[str, Any]) -> bool:
    aliases = (
        DIRECT_FOREIGN_ALIASES
        + DIRECT_INSTITUTION_ALIASES
        + DIRECT_INDIVIDUAL_ALIASES
        + AMOUNT_FOREIGN_ALIASES
        + AMOUNT_INSTITUTION_ALIASES
        + AMOUNT_INDIVIDUAL_ALIASES
    )
    return any(pick_float(row, (alias,)) is not None for alias in aliases)


def _direct_or_amount(
    row: dict[str, Any],
    *,
    direct_aliases: tuple[str, ...],
    amount_aliases: tuple[str, ...],
    multiplier: float,
) -> float | None:
    direct = pick_float(row, direct_aliases)
    if direct is not None:
        return direct
    amount = pick_float(row, amount_aliases)
    return amount * multiplier if amount is not None else None


def _participant_key(row: dict[str, Any]) -> str | None:
    raw = pick_text(row, PARTICIPANT_ALIASES)
    if not raw:
        return None
    normalized = raw.casefold().replace(" ", "")
    if any(token in normalized for token in ("외국", "foreign", "frgn")):
        return "foreign"
    if any(token in normalized for token in ("기관", "institution", "inst", "orgn")):
        return "institution"
    if any(token in normalized for token in ("개인", "individual", "indv", "prsn")):
        return "individual"
    return None
