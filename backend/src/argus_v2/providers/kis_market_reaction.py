from __future__ import annotations

from datetime import date, datetime, timezone
import logging
import re
from typing import Any

import httpx

from .kis_common import extract_rows, fetch_json_with_retries, pick_float, pick_text, value_by_path
from .models import BriefingProviderBatch, MarketReactionSectorRecord, MarketReactionSnapshotRecord


logger = logging.getLogger(__name__)

KIS_MARKET_REACTION_SOURCE_NAME = "KIS_DOMESTIC_STOCK_INDEX"
DEFAULT_KIS_INDEX_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-index-price"
DEFAULT_KIS_INDEX_PRICE_TR_ID = "FHPUP02100000"
DEFAULT_KIS_INDEX_CATEGORY_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-index-category-price"
DEFAULT_KIS_INDEX_CATEGORY_PRICE_TR_ID = "FHPUP02140000"
DEFAULT_KIS_INVESTOR_TIME_PATH = "/uapi/domestic-stock/v1/quotations/inquire-investor-time-by-market"
DEFAULT_KIS_INVESTOR_TIME_TR_ID = "FHPTJ04030000"
DEFAULT_SECTOR_LIMIT = 3
NON_SPOT_SECTOR_TERMS = (
    "vkospi",
    "wise",
    "krx",
    "k200",
    "ksq",
    "top",
    "인버스",
    "레버리지",
    "커버드콜",
    "선물",
    "지수",
    "테마",
    "twap",
    "trf",
    "futures",
    "future",
    "leveraged",
    "inverse",
    "index",
    "nikkei",
    "nasdaq",
    "dow",
    "s&p",
    "msci",
    "etf",
    "etn",
    "종합",
    "대형주",
    "중형주",
    "소형주",
)

INDEX_REQUESTS = (
    {"name": "KOSPI", "code": "0001"},
    {"name": "KOSDAQ", "code": "1001"},
)

SECTOR_REQUESTS = (
    {"market": "K", "code": "0001"},
    {"market": "Q", "code": "1001"},
)

SPOT_FLOW_REQUEST = {"market_code": "999", "sector_code": "S001"}


class KisMarketReactionService:
    def __init__(
        self,
        *,
        base_url: str,
        index_price_path: str,
        index_price_tr_id: str | None,
        category_price_path: str,
        category_price_tr_id: str | None,
        investor_time_path: str,
        investor_time_tr_id: str | None,
        app_key: str | None,
        app_secret: str | None,
        access_token: str | None,
        investor_amount_multiplier: float = 10000.0,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        sector_limit: int = DEFAULT_SECTOR_LIMIT,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.index_price_path = index_price_path or DEFAULT_KIS_INDEX_PRICE_PATH
        self.index_price_tr_id = (index_price_tr_id or "").strip() or DEFAULT_KIS_INDEX_PRICE_TR_ID
        self.category_price_path = category_price_path or DEFAULT_KIS_INDEX_CATEGORY_PRICE_PATH
        self.category_price_tr_id = (category_price_tr_id or "").strip() or DEFAULT_KIS_INDEX_CATEGORY_PRICE_TR_ID
        self.investor_time_path = investor_time_path or DEFAULT_KIS_INVESTOR_TIME_PATH
        self.investor_time_tr_id = (investor_time_tr_id or "").strip() or DEFAULT_KIS_INVESTOR_TIME_TR_ID
        self.investor_amount_multiplier = investor_amount_multiplier
        self.app_key = (app_key or "").strip()
        self.app_secret = (app_secret or "").strip()
        self.access_token = (access_token or "").strip()
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.sector_limit = max(1, sector_limit)
        self._http_client = http_client

    def is_ready(self) -> tuple[bool, str | None]:
        if not self.app_key or not self.app_secret or not self.access_token:
            return False, "missing_kis_credentials"
        return True, None

    def fetch_snapshot(
        self,
        *,
        trade_date: date,
        snapshot_time: datetime | None = None,
    ) -> BriefingProviderBatch:
        ready, reason = self.is_ready()
        if not ready:
            return BriefingProviderBatch(records=[], disabled_reason=reason)

        snapshot_at = (snapshot_time or datetime.now(timezone.utc)).astimezone(timezone.utc)
        snapshot_iso = snapshot_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")

        index_payloads = {
            request["name"]: self._fetch_index_price(index_code=request["code"])
            for request in INDEX_REQUESTS
        }
        sector_payloads = [
            self._fetch_sector_category(market_code=request["market"], index_code=request["code"])
            for request in SECTOR_REQUESTS
        ]
        spot_flow_error = None
        try:
            spot_flow_payload = self._fetch_spot_investor_flow()
        except RuntimeError as error:
            spot_flow_payload = None
            spot_flow_error = str(error)
            logger.warning("argus_v2_kis_spot_flow_fetch_failed", extra={"error": spot_flow_error})

        kospi_row = _first_row(index_payloads.get("KOSPI"))
        kosdaq_row = _first_row(index_payloads.get("KOSDAQ"))
        sector_rows = [row for payload in sector_payloads for row in _sector_rows(payload)]
        spot_flow_row = _first_row(spot_flow_payload)
        strong_sectors, weak_sectors = _sector_records(
            rows=sector_rows,
            observed_at=snapshot_iso,
            source=KIS_MARKET_REACTION_SOURCE_NAME,
            limit=self.sector_limit,
        )

        if not kospi_row and not kosdaq_row and not sector_rows and not spot_flow_row:
            raise ValueError("kis_market_reaction_payload_empty")

        kospi_advancers = _as_int(pick_float(kospi_row or {}, ("ascn_issu_cnt", "advancing_count", "advancers")))
        kosdaq_advancers = _as_int(pick_float(kosdaq_row or {}, ("ascn_issu_cnt", "advancing_count", "advancers")))
        kospi_decliners = _as_int(pick_float(kospi_row or {}, ("down_issu_cnt", "declining_count", "decliners")))
        kosdaq_decliners = _as_int(pick_float(kosdaq_row or {}, ("down_issu_cnt", "declining_count", "decliners")))
        spot_foreign_net_buy = _spot_net_buy(
            spot_flow_row,
            ("frgn_ntby_tr_pbmn", "foreign_net_buy", "spot_foreign_net_buy"),
            multiplier=self.investor_amount_multiplier,
        )
        spot_institution_net_buy = _spot_net_buy(
            spot_flow_row,
            ("orgn_ntby_tr_pbmn", "institution_net_buy", "spot_institution_net_buy"),
            multiplier=self.investor_amount_multiplier,
        )
        spot_individual_net_buy = _spot_net_buy(
            spot_flow_row,
            ("prsn_ntby_tr_pbmn", "individual_net_buy", "spot_individual_net_buy"),
            multiplier=self.investor_amount_multiplier,
        )

        record = MarketReactionSnapshotRecord(
            source_name=KIS_MARKET_REACTION_SOURCE_NAME,
            trade_date=trade_date.isoformat(),
            snapshot_time=snapshot_iso,
            kospi_change_rate=_index_change_rate(kospi_row),
            kosdaq_change_rate=_index_change_rate(kosdaq_row),
            advancing_count=_sum_optional(kospi_advancers, kosdaq_advancers),
            declining_count=_sum_optional(kospi_decliners, kosdaq_decliners),
            spot_foreign_net_buy=spot_foreign_net_buy,
            spot_institution_net_buy=spot_institution_net_buy,
            spot_individual_net_buy=spot_individual_net_buy,
            summary=_summary(
                kospi_change_rate=_index_change_rate(kospi_row),
                kosdaq_change_rate=_index_change_rate(kosdaq_row),
                advancing_count=_sum_optional(kospi_advancers, kosdaq_advancers),
                declining_count=_sum_optional(kospi_decliners, kosdaq_decliners),
                spot_foreign_net_buy=spot_foreign_net_buy,
                strong_sectors=strong_sectors,
                weak_sectors=weak_sectors,
            ),
            freshness_state="fresh",
            source_url=f"{self.base_url}{self.index_price_path}",
            source_record_id=f"kis-market-reaction-{trade_date.isoformat()}",
            raw_payload={
                "index_price": index_payloads,
                "index_category_price": sector_payloads,
                "investor_time_by_market": spot_flow_payload,
            },
            strong_sectors=strong_sectors,
            weak_sectors=weak_sectors,
        )

        return BriefingProviderBatch(
            records=[record],
            metadata={
                "provider": "kis",
                "index_count": sum(1 for row in (kospi_row, kosdaq_row) if row),
                "sector_row_count": len(sector_rows),
                "investor_amount_multiplier": self.investor_amount_multiplier,
                "spot_flow_count": 1 if spot_flow_row else 0,
                "spot_flow_error": spot_flow_error,
                "expected_count": 1,
            },
        )

    def _fetch_index_price(self, *, index_code: str) -> Any:
        url = f"{self.base_url}{self.index_price_path}"
        params = {
            "FID_COND_MRKT_DIV_CODE": "U",
            "FID_INPUT_ISCD": index_code,
        }
        payload, _ = fetch_json_with_retries(
            logger=logger,
            log_prefix="argus_v2_kis_index_price_fetch",
            max_retries=self.max_retries,
            backoff_seconds=self.backoff_seconds,
            do_request=lambda: self._do_request(url=url, headers=self._headers(self.index_price_tr_id), params=params),
        )
        return payload

    def _fetch_sector_category(self, *, market_code: str, index_code: str) -> Any:
        url = f"{self.base_url}{self.category_price_path}"
        params = {
            "FID_COND_MRKT_DIV_CODE": "U",
            "FID_INPUT_ISCD": index_code,
            "FID_COND_SCR_DIV_CODE": "20214",
            "FID_MRKT_CLS_CODE": market_code,
            "FID_BLNG_CLS_CODE": "0",
        }
        payload, _ = fetch_json_with_retries(
            logger=logger,
            log_prefix="argus_v2_kis_index_category_price_fetch",
            max_retries=self.max_retries,
            backoff_seconds=self.backoff_seconds,
            do_request=lambda: self._do_request(url=url, headers=self._headers(self.category_price_tr_id), params=params),
        )
        return payload

    def _fetch_spot_investor_flow(self) -> Any:
        url = f"{self.base_url}{self.investor_time_path}"
        params = {
            "FID_INPUT_ISCD": SPOT_FLOW_REQUEST["market_code"],
            "FID_INPUT_ISCD_2": SPOT_FLOW_REQUEST["sector_code"],
        }
        payload, _ = fetch_json_with_retries(
            logger=logger,
            log_prefix="argus_v2_kis_investor_time_fetch",
            max_retries=self.max_retries,
            backoff_seconds=self.backoff_seconds,
            do_request=lambda: self._do_request(url=url, headers=self._headers(self.investor_time_tr_id), params=params),
        )
        return payload

    def _headers(self, tr_id: str) -> dict[str, str]:
        return {
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "authorization": f"Bearer {self.access_token}",
            "content-type": "application/json; charset=utf-8",
            "tr_id": tr_id,
        }

    def _do_request(self, *, url: str, headers: dict[str, str], params: dict[str, str]) -> httpx.Response:
        if self._http_client is not None:
            return self._http_client.get(url, headers=headers, params=params, timeout=self.timeout_seconds)
        with httpx.Client() as client:
            return client.get(url, headers=headers, params=params, timeout=self.timeout_seconds)


def _first_row(payload: Any) -> dict[str, Any] | None:
    rows = extract_rows(payload, ["output", "output1", "data.output", "data.output1", "data"])
    return rows[0] if rows else None


def _sector_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        rows = value_by_path(payload, "output2")
        if isinstance(rows, list) and all(isinstance(item, dict) for item in rows):
            return rows
        rows = value_by_path(payload, "data.output2")
        if isinstance(rows, list) and all(isinstance(item, dict) for item in rows):
            return rows
    return extract_rows(payload, ["output2", "output1", "output", "data.output2", "data.output1", "data"])


def _sector_records(
    *,
    rows: list[dict[str, Any]],
    observed_at: str,
    source: str,
    limit: int,
) -> tuple[list[MarketReactionSectorRecord], list[MarketReactionSectorRecord]]:
    parsed_by_name: dict[str, float] = {}
    for row in rows:
        raw_name = pick_text(row, ("hts_kor_isnm", "name", "sector", "bstp_kor_isnm"))
        name = _sector_display_name(raw_name)
        change_rate = pick_float(row, ("bstp_nmix_prdy_ctrt", "change_rate", "prdy_ctrt", "rate"))
        if not raw_name or not name or change_rate is None or not _is_spot_sector_name(raw_name):
            continue
        previous = parsed_by_name.get(name)
        if previous is None or abs(change_rate) > abs(previous):
            parsed_by_name[name] = change_rate
    parsed = list(parsed_by_name.items())

    strong = [
        MarketReactionSectorRecord(
            name=name,
            change_rate=change_rate,
            reason="KIS 업종지수 등락률 상위",
            tone="positive",
            source=source,
            observed_at=observed_at,
        )
        for name, change_rate in sorted((item for item in parsed if item[1] > 0), key=lambda item: item[1], reverse=True)[:limit]
    ]
    weak = [
        MarketReactionSectorRecord(
            name=name,
            change_rate=change_rate,
            reason="KIS 업종지수 등락률 하위",
            tone="negative",
            source=source,
            observed_at=observed_at,
        )
        for name, change_rate in sorted((item for item in parsed if item[1] < 0), key=lambda item: item[1])[:limit]
    ]
    return strong, weak


def _index_change_rate(row: dict[str, Any] | None) -> float | None:
    if not row:
        return None
    return pick_float(row, ("bstp_nmix_prdy_ctrt", "change_rate", "prdy_ctrt", "rate"))


def _spot_net_buy(row: dict[str, Any] | None, aliases: tuple[str, ...], *, multiplier: float) -> float | None:
    if not row:
        return None
    value = pick_float(row, aliases)
    return value * multiplier if value is not None else None


def _is_spot_sector_name(name: str) -> bool:
    normalized = name.casefold()
    if normalized.startswith("f-"):
        return False
    if not re.search(r"[가-힣]", name):
        return False
    return not any(term.casefold() in normalized for term in NON_SPOT_SECTOR_TERMS)


def _sector_display_name(name: str | None) -> str | None:
    if not name:
        return None
    normalized = name.strip()
    if re.match(r"^K(?=[가-힣])", normalized):
        normalized = normalized[1:]
    normalized = re.sub(r"^코스(?:피|닥)\s*\d+\s*", "", normalized)
    return normalized


def _summary(
    *,
    kospi_change_rate: float | None,
    kosdaq_change_rate: float | None,
    advancing_count: int | None,
    declining_count: int | None,
    spot_foreign_net_buy: float | None,
    strong_sectors: list[MarketReactionSectorRecord],
    weak_sectors: list[MarketReactionSectorRecord],
) -> str:
    parts = []
    if kospi_change_rate is not None:
        parts.append(f"KOSPI {kospi_change_rate:+.2f}%")
    if kosdaq_change_rate is not None:
        parts.append(f"KOSDAQ {kosdaq_change_rate:+.2f}%")
    if advancing_count is not None and declining_count is not None:
        parts.append(f"상승 {advancing_count:,} / 하락 {declining_count:,}")
    if spot_foreign_net_buy is not None:
        direction = "순매수" if spot_foreign_net_buy > 0 else "순매도" if spot_foreign_net_buy < 0 else "중립"
        parts.append(f"외국인 현물 {direction} {_format_krw(abs(spot_foreign_net_buy))}")
    if strong_sectors:
        sector = strong_sectors[0]
        parts.append(f"강세 업종 {sector.name} {sector.change_rate:+.2f}%")
    if weak_sectors:
        sector = weak_sectors[0]
        parts.append(f"약세 업종 {sector.name} {sector.change_rate:+.2f}%")
    return ". ".join(parts) + "." if parts else "KIS 현물 반응 데이터가 수신됐지만 요약할 핵심 값이 부족합니다."


def _sum_optional(*values: int | None) -> int | None:
    observed = [value for value in values if value is not None]
    return sum(observed) if observed else None


def _as_int(value: float | None) -> int | None:
    return int(value) if value is not None else None


def _format_krw(value: float) -> str:
    if value >= 100_000_000:
        return f"{value / 100_000_000:,.1f}억원"
    if value >= 10_000:
        return f"{value / 10_000:,.0f}만원"
    return f"{value:,.0f}원"
