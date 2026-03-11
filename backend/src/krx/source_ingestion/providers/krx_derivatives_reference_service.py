from __future__ import annotations

import csv
from datetime import date
import io
import logging
from pathlib import Path
from typing import Any

import httpx

from ..briefing_models import BriefingProviderBatch, DerivativesDailyMetricRecord
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


class KrxDerivativesReferenceService:
    def __init__(
        self,
        *,
        provider: str,
        file_path: str | None,
        base_url: str,
        endpoint_path: str,
        api_key: str | None,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        response_paths: str | None = None,
        query_params_json: str | None = None,
        field_alias_map_json: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.provider = provider.strip().lower()
        self.file_path = file_path
        self.base_url = base_url.rstrip("/")
        self.endpoint_path = endpoint_path
        self.api_key = (api_key or "").strip()
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.response_paths = parse_response_paths(response_paths)
        self.query_params = parse_query_params_json(query_params_json)
        self.field_alias_map = parse_field_alias_map_json(field_alias_map_json)
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
            return True, None

        return False, f"unsupported_provider:{self.provider}"

    def fetch_daily_metrics(self, *, trade_date: date) -> BriefingProviderBatch:
        enabled, reason = self.is_enabled()
        if not enabled:
            logger.info(
                "krx_derivatives_reference_disabled",
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

        records = self.parse_payload_to_records(
            payload=payload,
            trade_date=trade_date,
            source_name="KRX_DERIVATIVES_REFERENCE",
            source_url=source_url,
        )

        return BriefingProviderBatch(
            records=records,
            metadata={"record_count": len(records), "provider": self.provider},
            retry_count=retry_count,
        )

    def load_manual_records(self, *, trade_date: date, input_path: str) -> list[DerivativesDailyMetricRecord]:
        source = Path(input_path)
        if not source.exists():
            raise FileNotFoundError(f"Manual input file not found: {source}")

        if source.suffix.lower() == ".csv":
            rows = self._load_csv_rows(source)
            payload: Any = rows
        else:
            payload = load_json_file(str(source))

        records = self.parse_payload_to_records(
            payload=payload,
            trade_date=trade_date,
            source_name="KRX_DERIVATIVES_MANUAL",
            source_url=str(source),
        )
        return records

    def parse_payload_to_records(
        self,
        *,
        payload: Any,
        trade_date: date,
        source_name: str,
        source_url: str | None,
    ) -> list[DerivativesDailyMetricRecord]:
        rows = self._extract_rows(payload=payload, trade_date=trade_date)
        if not rows:
            logger.warning(
                "krx_derivatives_reference_rows_missing",
                extra={"trade_date": trade_date.isoformat(), "source_name": source_name},
            )
            return []

        row = rows[0]
        record = DerivativesDailyMetricRecord(
            source_name=source_name,
            trade_date=trade_date.isoformat(),
            metric_scope="KRX_DERIVATIVES",
            put_call_ratio=pick_float(
                row,
                self._aliases("put_call_ratio", ("put_call_ratio", "putcall_ratio", "pcr")),
            ),
            implied_volatility=pick_float(
                row,
                self._aliases(
                    "implied_volatility",
                    (
                        "implied_volatility",
                        "implied_vol",
                        "iv",
                        "vkospi",
                    ),
                ),
            ),
            open_interest_total=pick_float(
                row,
                self._aliases(
                    "open_interest_total",
                    (
                        "open_interest_total",
                        "open_interest",
                        "total_open_interest",
                    ),
                ),
            ),
            call_open_interest=pick_float(
                row,
                self._aliases("call_open_interest", ("call_open_interest", "call_oi", "call_openint")),
            ),
            put_open_interest=pick_float(
                row,
                self._aliases("put_open_interest", ("put_open_interest", "put_oi", "put_openint")),
            ),
            futures_investor_foreign_net_buy=pick_float(
                row,
                self._aliases(
                    "futures_investor_foreign_net_buy",
                    (
                        "futures_investor_foreign_net_buy",
                        "futures_foreign_net_buy",
                        "fut_frgn_net_buy",
                    ),
                ),
            ),
            futures_investor_institution_net_buy=pick_float(
                row,
                self._aliases(
                    "futures_investor_institution_net_buy",
                    (
                        "futures_investor_institution_net_buy",
                        "futures_institution_net_buy",
                        "fut_inst_net_buy",
                    ),
                ),
            ),
            futures_investor_individual_net_buy=pick_float(
                row,
                self._aliases(
                    "futures_investor_individual_net_buy",
                    (
                        "futures_investor_individual_net_buy",
                        "futures_individual_net_buy",
                        "fut_indv_net_buy",
                    ),
                ),
            ),
            options_investor_foreign_net_buy=pick_float(
                row,
                self._aliases(
                    "options_investor_foreign_net_buy",
                    (
                        "options_investor_foreign_net_buy",
                        "options_foreign_net_buy",
                        "opt_frgn_net_buy",
                    ),
                ),
            ),
            options_investor_institution_net_buy=pick_float(
                row,
                self._aliases(
                    "options_investor_institution_net_buy",
                    (
                        "options_investor_institution_net_buy",
                        "options_institution_net_buy",
                        "opt_inst_net_buy",
                    ),
                ),
            ),
            options_investor_individual_net_buy=pick_float(
                row,
                self._aliases(
                    "options_investor_individual_net_buy",
                    (
                        "options_investor_individual_net_buy",
                        "options_individual_net_buy",
                        "opt_indv_net_buy",
                    ),
                ),
            ),
            futures_volume_total=pick_float(
                row,
                self._aliases("futures_volume_total", ("futures_volume_total", "futures_volume", "fut_volume")),
            ),
            options_volume_total=pick_float(
                row,
                self._aliases("options_volume_total", ("options_volume_total", "options_volume", "opt_volume")),
            ),
            source_url=source_url,
            source_record_id=pick_text(
                row,
                self._aliases("source_record_id", ("id", "record_id", "seq", "trade_date")),
            ),
            raw_payload=row,
            additional_metrics={
                "source_date": pick_text(row, self._aliases("source_date", ("trade_date", "date"))),
                "note": pick_text(row, self._aliases("note", ("note", "remark", "memo"))),
            },
        )

        self._log_missing_fields(record=record)
        return [record]

    def _fetch_api_payload(self, *, trade_date: date) -> tuple[Any, int]:
        url = f"{self.base_url}{self.endpoint_path}"
        params = self._render_query_params(trade_date=trade_date)
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return fetch_json_with_retries(
            logger=logger,
            log_prefix="krx_derivatives_reference_fetch",
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
            if all(not isinstance(value, (dict, list)) for value in payload.values()):
                return [payload]
        if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
            return [item for item in payload if isinstance(item, dict)]
        return extract_rows(payload, self.response_paths)

    def _load_csv_rows(self, source: Path) -> list[dict[str, Any]]:
        text = source.read_text(encoding="utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        return [dict(row) for row in reader]

    def _log_missing_fields(self, *, record: DerivativesDailyMetricRecord) -> None:
        missing = []
        if record.put_call_ratio is None:
            missing.append("put_call_ratio")
        if record.implied_volatility is None:
            missing.append("implied_volatility")

        if missing:
            logger.info(
                "krx_derivatives_reference_missing_fields",
                extra={"trade_date": record.trade_date, "missing_fields": missing},
            )

    def _aliases(self, canonical_field: str, defaults: tuple[str, ...]) -> tuple[str, ...]:
        return merge_aliases(
            field_alias_map=self.field_alias_map,
            canonical_field=canonical_field,
            defaults=defaults,
        )
