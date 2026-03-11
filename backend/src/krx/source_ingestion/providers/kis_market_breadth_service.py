from __future__ import annotations

from datetime import date
import logging
from typing import Any

import httpx

from ..briefing_models import BriefingProviderBatch, MarketDailyFactorRecord
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


class KisMarketBreadthService:
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

    def fetch_market_daily_factors(self, *, trade_date: date) -> BriefingProviderBatch:
        enabled, reason = self.is_enabled()
        if not enabled:
            logger.info(
                "kis_market_breadth_disabled",
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
        if not rows:
            logger.warning(
                "kis_market_breadth_rows_missing",
                extra={"trade_date": trade_date.isoformat()},
            )
            return BriefingProviderBatch(records=[], retry_count=retry_count)

        row = rows[0]
        normalized = self._normalize_row(
            row=row,
            trade_date=trade_date,
            source_url=source_url,
        )
        return BriefingProviderBatch(
            records=[normalized],
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

        payload, retry_count = fetch_json_with_retries(
            logger=logger,
            log_prefix="kis_market_breadth_fetch",
            max_retries=self.max_retries,
            backoff_seconds=self.backoff_seconds,
            do_request=lambda: self._do_request(url=url, headers=headers, params=params),
        )
        return payload, retry_count

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

        return extract_rows(payload, self.response_paths)

    def _normalize_row(
        self,
        *,
        row: dict[str, Any],
        trade_date: date,
        source_url: str | None,
    ) -> MarketDailyFactorRecord:
        record = MarketDailyFactorRecord(
            source_name="KIS_MARKET_BREADTH",
            trade_date=trade_date.isoformat(),
            investor_individual_net_buy=pick_float(
                row,
                self._aliases(
                    "investor_individual_net_buy",
                    (
                        "investor_individual_net_buy",
                        "individual_net_buy",
                        "personal_net_buy",
                        "retail_net_buy",
                        "frgn_ntby_qty",
                    ),
                ),
            ),
            investor_foreign_net_buy=pick_float(
                row,
                self._aliases(
                    "investor_foreign_net_buy",
                    (
                        "investor_foreign_net_buy",
                        "foreign_net_buy",
                        "frgn_ntby_amt",
                        "foreigners_net_buy",
                    ),
                ),
            ),
            investor_institution_net_buy=pick_float(
                row,
                self._aliases(
                    "investor_institution_net_buy",
                    (
                        "investor_institution_net_buy",
                        "institution_net_buy",
                        "inst_net_buy",
                        "orgn_ntby_amt",
                    ),
                ),
            ),
            investor_other_net_buy=pick_float(
                row,
                self._aliases(
                    "investor_other_net_buy",
                    (
                        "investor_other_net_buy",
                        "other_net_buy",
                        "othercorp_net_buy",
                    ),
                ),
            ),
            investor_bank_net_buy=pick_float(
                row,
                self._aliases(
                    "investor_bank_net_buy",
                    (
                        "investor_bank_net_buy",
                        "bank_net_buy",
                        "bank_ntby_amt",
                    ),
                ),
            ),
            investor_pension_net_buy=pick_float(
                row,
                self._aliases(
                    "investor_pension_net_buy",
                    (
                        "investor_pension_net_buy",
                        "pension_net_buy",
                        "pension_ntby_amt",
                    ),
                ),
            ),
            program_buy_total=pick_float(
                row,
                self._aliases(
                    "program_buy_total",
                    (
                        "program_buy_total",
                        "program_buy",
                        "program_buy_amt",
                    ),
                ),
            ),
            program_sell_total=pick_float(
                row,
                self._aliases(
                    "program_sell_total",
                    (
                        "program_sell_total",
                        "program_sell",
                        "program_sell_amt",
                    ),
                ),
            ),
            program_net_total=pick_float(
                row,
                self._aliases(
                    "program_net_total",
                    (
                        "program_net_total",
                        "program_net_buy",
                        "program_net",
                    ),
                ),
            ),
            credit_balance_total=pick_float(
                row,
                self._aliases(
                    "credit_balance_total",
                    (
                        "credit_balance_total",
                        "credit_balance",
                        "credit_amt",
                    ),
                ),
            ),
            margin_loan_balance=pick_float(
                row,
                self._aliases(
                    "margin_loan_balance",
                    (
                        "margin_loan_balance",
                        "margin_balance",
                        "loan_balance",
                    ),
                ),
            ),
            stock_financing_balance=pick_float(
                row,
                self._aliases(
                    "stock_financing_balance",
                    (
                        "stock_financing_balance",
                        "stock_finance_balance",
                        "stock_financing_amt",
                    ),
                ),
            ),
            securities_lending_balance=pick_float(
                row,
                self._aliases(
                    "securities_lending_balance",
                    (
                        "securities_lending_balance",
                        "stock_lending_balance",
                        "lending_balance",
                    ),
                ),
            ),
            source_url=source_url,
            source_record_id=pick_text(row, self._aliases("source_record_id", ("id", "record_id", "seq", "trade_date"))),
            raw_payload=row,
            additional_metrics={
                "market": pick_text(row, self._aliases("market", ("market", "market_code", "mkt_id"))),
                "currency": pick_text(row, self._aliases("currency", ("currency", "crncy"))),
            },
        )

        self._log_missing_fields(record=record)
        return record

    def _log_missing_fields(self, *, record: MarketDailyFactorRecord) -> None:
        missing = []
        if record.investor_foreign_net_buy is None:
            missing.append("investor_foreign_net_buy")
        if record.program_net_total is None:
            missing.append("program_net_total")
        if record.credit_balance_total is None:
            missing.append("credit_balance_total")

        if missing:
            logger.info(
                "kis_market_breadth_missing_fields",
                extra={
                    "trade_date": record.trade_date,
                    "missing_fields": missing,
                },
            )

    def _aliases(self, canonical_field: str, defaults: tuple[str, ...]) -> tuple[str, ...]:
        return merge_aliases(
            field_alias_map=self.field_alias_map,
            canonical_field=canonical_field,
            defaults=defaults,
        )
