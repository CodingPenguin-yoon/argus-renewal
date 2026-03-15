from __future__ import annotations

from datetime import date, datetime, timezone
import logging
from typing import Any

import httpx

from ..briefing_models import (
    BriefingProviderBatch,
    DerivativesDailyMetricRecord,
    MarketIntradaySnapshotRecord,
)
from ._briefing_common import (
    extract_rows,
    fetch_json_with_retries,
    load_json_file,
    merge_aliases,
    parse_field_alias_map_json,
    parse_query_params_json,
    parse_response_paths,
    pick_float,
    pick_text,
)

logger = logging.getLogger(__name__)


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
        self.field_alias_map = parse_field_alias_map_json(field_alias_map_json)
        self.tr_id = (tr_id or "").strip() or None
        self._http_client = http_client

    def is_enabled(self) -> tuple[bool, str | None]:
        if self.provider in {"", "disabled"}:
            return False, "feature_flag_disabled"

        if self.provider == "file":
            if not self.file_path:
                return False, "missing_file_path"
            return True, None

        if self.provider == "api":
            if not self.endpoint_path:
                return False, "missing_endpoint_path"
            if not self.app_key or not self.app_secret or not self.access_token:
                return False, "missing_kis_credentials"
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
            logger.info(
                "kis_domestic_derivatives_disabled",
                extra={"reason": reason, "trade_date": trade_date.isoformat()},
            )
            return BriefingProviderBatch(records=[], disabled_reason=reason)

        payload: Any
        retry_count = 0
        source_url = None

        if self.provider == "file":
            source_url = self.file_path
            payload = load_json_file(self.file_path or "")
        else:
            source_url = f"{self.base_url}{self.endpoint_path}"
            payload, retry_count = self._fetch_api_payload(trade_date=trade_date)

        rows = self._extract_rows(payload=payload, trade_date=trade_date)
        summary_record = self._normalize_summary_record(
            payload=payload,
            trade_date=trade_date,
            source_url=source_url,
        )
        if not rows:
            logger.warning(
                "kis_domestic_derivatives_rows_missing",
                extra={"trade_date": trade_date.isoformat()},
            )
            records = [summary_record] if summary_record is not None else []
            return BriefingProviderBatch(records=records, retry_count=retry_count)

        snapshot_at = (snapshot_time or datetime.now(timezone.utc)).astimezone(timezone.utc)
        snapshot_iso = snapshot_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")

        records: list[MarketIntradaySnapshotRecord | DerivativesDailyMetricRecord] = []
        if summary_record is not None:
            records.append(summary_record)
        for index, row in enumerate(rows):
            records.append(
                self._normalize_row(
                    row=row,
                    index=index,
                    trade_date=trade_date,
                    snapshot_time=snapshot_iso,
                    source_url=source_url,
                )
            )

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
        }
        if self.tr_id:
            headers["tr_id"] = self.tr_id

        params = self._render_query_params(trade_date=trade_date)

        return fetch_json_with_retries(
            logger=logger,
            log_prefix="kis_domestic_derivatives_fetch",
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
        rendered: dict[str, str] = {}
        for key, value in self.query_params.items():
            rendered[key] = value.replace("{trade_date}", trade_date.isoformat())
        if not rendered:
            rendered["trade_date"] = trade_date.isoformat()
        return rendered

    def _extract_rows(self, *, payload: Any, trade_date: date) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            direct_row = payload.get(trade_date.isoformat())
            if isinstance(direct_row, dict):
                return [direct_row]
            if all(not isinstance(value, (dict, list)) for value in payload.values()) and self._looks_like_snapshot_row(payload):
                return [payload]
        return extract_rows(payload, self.response_paths)

    def _normalize_summary_record(
        self,
        *,
        payload: Any,
        trade_date: date,
        source_url: str | None,
    ) -> DerivativesDailyMetricRecord | None:
        summary_payload = self._extract_summary_payload(payload)
        if summary_payload is None:
            return None

        record = DerivativesDailyMetricRecord(
            source_name="KIS_DOMESTIC_DERIVATIVES",
            trade_date=trade_date.isoformat(),
            metric_scope="KRX_DERIVATIVES",
            put_call_ratio=pick_float(
                summary_payload,
                self._aliases("put_call_ratio", ("put_call_ratio", "putcall_ratio", "pcr")),
            ),
            implied_volatility=pick_float(
                summary_payload,
                self._aliases("implied_volatility", ("implied_volatility", "iv", "impl_vol", "vkospi")),
            ),
            open_interest_total=pick_float(
                summary_payload,
                self._aliases("open_interest_total", ("open_interest_total", "open_interest", "total_open_interest")),
            ),
            call_open_interest=pick_float(
                summary_payload,
                self._aliases("call_open_interest", ("call_open_interest", "call_oi", "call_openint")),
            ),
            put_open_interest=pick_float(
                summary_payload,
                self._aliases("put_open_interest", ("put_open_interest", "put_oi", "put_openint")),
            ),
            futures_investor_foreign_net_buy=pick_float(
                summary_payload,
                self._aliases(
                    "futures_investor_foreign_net_buy",
                    ("futures_investor_foreign_net_buy", "futures_foreign_net_buy", "fut_frgn_net_buy"),
                ),
            ),
            futures_investor_institution_net_buy=pick_float(
                summary_payload,
                self._aliases(
                    "futures_investor_institution_net_buy",
                    ("futures_investor_institution_net_buy", "futures_institution_net_buy", "fut_inst_net_buy"),
                ),
            ),
            futures_investor_individual_net_buy=pick_float(
                summary_payload,
                self._aliases(
                    "futures_investor_individual_net_buy",
                    ("futures_investor_individual_net_buy", "futures_individual_net_buy", "fut_indv_net_buy"),
                ),
            ),
            options_investor_foreign_net_buy=pick_float(
                summary_payload,
                self._aliases(
                    "options_investor_foreign_net_buy",
                    ("options_investor_foreign_net_buy", "options_foreign_net_buy", "opt_frgn_net_buy"),
                ),
            ),
            options_investor_institution_net_buy=pick_float(
                summary_payload,
                self._aliases(
                    "options_investor_institution_net_buy",
                    ("options_investor_institution_net_buy", "options_institution_net_buy", "opt_inst_net_buy"),
                ),
            ),
            options_investor_individual_net_buy=pick_float(
                summary_payload,
                self._aliases(
                    "options_investor_individual_net_buy",
                    ("options_investor_individual_net_buy", "options_individual_net_buy", "opt_indv_net_buy"),
                ),
            ),
            futures_volume_total=pick_float(
                summary_payload,
                self._aliases("futures_volume_total", ("futures_volume_total", "futures_volume", "fut_volume")),
            ),
            options_volume_total=pick_float(
                summary_payload,
                self._aliases("options_volume_total", ("options_volume_total", "options_volume", "opt_volume")),
            ),
            source_url=source_url,
            source_record_id=pick_text(
                summary_payload,
                self._aliases("source_record_id", ("id", "record_id", "seq", "trade_date")),
            )
            or trade_date.isoformat(),
            raw_payload=summary_payload,
            additional_metrics={
                "source_date": pick_text(summary_payload, self._aliases("source_date", ("trade_date", "date"))),
                "note": pick_text(summary_payload, self._aliases("note", ("note", "remark", "memo"))),
            },
        )

        if not any(
            value is not None
            for value in (
                record.put_call_ratio,
                record.implied_volatility,
                record.open_interest_total,
                record.call_open_interest,
                record.put_open_interest,
                record.futures_investor_foreign_net_buy,
                record.options_investor_foreign_net_buy,
            )
        ):
            return None

        return record

    def _extract_summary_payload(self, payload: Any) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None

        candidates: list[dict[str, Any]] = [payload]
        for key in ("summary", "market_summary", "overview", "totals", "market_totals"):
            value = payload.get(key)
            if isinstance(value, dict):
                candidates.append(value)

        for candidate in candidates:
            if self._has_summary_metrics(candidate):
                return candidate
        return None

    def _has_summary_metrics(self, payload: dict[str, Any]) -> bool:
        return any(
            pick_float(payload, self._aliases(field, aliases)) is not None
            for field, aliases in (
                ("put_call_ratio", ("put_call_ratio", "putcall_ratio", "pcr")),
                ("implied_volatility", ("implied_volatility", "iv", "impl_vol", "vkospi")),
                ("open_interest_total", ("open_interest_total", "open_interest", "total_open_interest")),
                (
                    "futures_investor_foreign_net_buy",
                    ("futures_investor_foreign_net_buy", "futures_foreign_net_buy", "fut_frgn_net_buy"),
                ),
            )
        )

    def _looks_like_snapshot_row(self, payload: dict[str, Any]) -> bool:
        return any(
            pick_text(payload, self._aliases(field, aliases))
            for field, aliases in (
                ("instrument_code", ("instrument_code", "futures_code", "symbol", "code", "item_code", "pdno")),
                ("instrument_name", ("instrument_name", "name", "prdt_name", "hts_kor_isnm")),
            )
        )

    def _normalize_row(
        self,
        *,
        row: dict[str, Any],
        index: int,
        trade_date: date,
        snapshot_time: str,
        source_url: str | None,
    ) -> MarketIntradaySnapshotRecord:
        instrument_code = pick_text(
            row,
            self._aliases(
                "instrument_code",
                (
                    "instrument_code",
                    "futures_code",
                    "symbol",
                    "code",
                    "item_code",
                    "pdno",
                ),
            ),
        )
        if not instrument_code:
            instrument_code = f"UNKNOWN_{index + 1}"
            logger.info(
                "kis_domestic_derivatives_missing_instrument_code",
                extra={"trade_date": trade_date.isoformat(), "row_index": index},
            )

        record = MarketIntradaySnapshotRecord(
            source_name="KIS_DOMESTIC_DERIVATIVES",
            trade_date=trade_date.isoformat(),
            snapshot_time=snapshot_time,
            session_type="PRE_OPEN",
            instrument_code=instrument_code,
            instrument_name=pick_text(
                row,
                self._aliases("instrument_name", ("instrument_name", "name", "prdt_name", "hts_kor_isnm")),
            ),
            price=pick_float(row, self._aliases("price", ("price", "current_price", "stck_prpr", "last"))),
            price_change=pick_float(
                row,
                self._aliases("price_change", ("price_change", "change", "prdy_vrss", "diff")),
            ),
            change_rate=pick_float(
                row,
                self._aliases("change_rate", ("change_rate", "chg_rate", "prdy_ctrt", "rate")),
            ),
            volume=pick_float(row, self._aliases("volume", ("volume", "acml_vol", "trade_volume"))),
            open_interest=pick_float(
                row,
                self._aliases("open_interest", ("open_interest", "opn_interest", "open_int")),
            ),
            put_call_ratio=pick_float(
                row,
                self._aliases("put_call_ratio", ("put_call_ratio", "putcall_ratio", "pcr")),
            ),
            implied_volatility=pick_float(
                row,
                self._aliases("implied_volatility", ("implied_volatility", "iv", "impl_vol")),
            ),
            source_url=source_url,
            source_record_id=pick_text(row, self._aliases("source_record_id", ("id", "record_id", "seq"))),
            raw_payload=row,
            additional_metrics={
                "bid": pick_float(row, self._aliases("bid", ("bid", "bid_price", "best_bid"))),
                "ask": pick_float(row, self._aliases("ask", ("ask", "ask_price", "best_ask"))),
            },
        )
        return record

    def _aliases(self, canonical_field: str, defaults: tuple[str, ...]) -> tuple[str, ...]:
        return merge_aliases(
            field_alias_map=self.field_alias_map,
            canonical_field=canonical_field,
            defaults=defaults,
        )
