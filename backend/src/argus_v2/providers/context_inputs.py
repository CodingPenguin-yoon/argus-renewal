from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import html
import logging
import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlparse

import httpx

from ...config.env import Settings
from ..db import get_connection, resolve_db_path, utcnow_iso
from ..storage import ArgusV2Storage
from .kis_common import as_float, load_json_file, pick_float, pick_text
from .kis_auth import KisAuthClient
from .kis_market_reaction import KisMarketReactionService
from .models import (
    BriefingProviderBatch,
    MarketReactionSectorRecord,
    MarketReactionSnapshotRecord,
    NewsTriggerRecord,
)


logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

DEFAULT_RSS_URLS = (
    "https://www.mk.co.kr/rss/30100041/",
    "https://www.mk.co.kr/rss/50200011/",
)
DEFAULT_NAVER_BASE_URL = "https://openapi.naver.com"
DEFAULT_NAVER_NEWS_PATH = "/v1/search/news.json"
DEFAULT_DART_BASE_URL = "https://opendart.fss.or.kr"
DEFAULT_DART_LIST_PATH = "/api/list.json"
DEFAULT_KIS_TOKEN_CACHE_PATH = "data/kis_token_cache.json"
KIS_MARKET_REACTION_PROVIDERS = {"kis", "kis_api", "kis_index"}

NEGATIVE_TERMS = (
    "금리 상승",
    "금리인상",
    "긴축",
    "인플레이션",
    "물가",
    "환율 상승",
    "달러 강세",
    "급락",
    "하락",
    "우려",
    "침체",
    "관세",
    "전쟁",
    "매도",
    "유상증자",
    "감자",
    "횡령",
    "소송",
    "상장폐지",
    "관리종목",
)
POSITIVE_TERMS = (
    "반도체",
    "ai",
    "호실적",
    "상승",
    "강세",
    "금리 인하",
    "완화",
    "수주",
    "공급계약",
    "자사주",
    "배당",
    "회복",
    "실적 개선",
)

NEWS_IMPORTANCE_TERMS: tuple[tuple[str, int], ...] = (
    ("fomc", 6),
    ("cpi", 6),
    ("pce", 6),
    ("금리", 6),
    ("국채금리", 6),
    ("환율", 5),
    ("달러", 5),
    ("원화", 5),
    ("미국", 4),
    ("나스닥", 4),
    ("s&p", 4),
    ("다우", 3),
    ("반도체", 5),
    ("엔비디아", 5),
    ("ai", 3),
    ("코스피", 4),
    ("코스닥", 4),
    ("외국인", 5),
    ("기관", 3),
    ("선물", 5),
    ("옵션", 5),
    ("미결제약정", 5),
    ("수급", 4),
    ("유가", 4),
    ("원유", 4),
    ("관세", 4),
    ("정책", 3),
    ("공급계약", 4),
    ("자사주", 3),
    ("실적", 3),
    ("유상증자", 4),
    ("감자", 5),
    ("관리종목", 5),
    ("상장폐지", 6),
)
LOW_SIGNAL_NEWS_TERMS = (
    "연예",
    "스포츠",
    "날씨",
    "여행",
    "맛집",
    "부동산 매물",
)
HIGH_QUALITY_SOURCES = (
    "dart",
    "mk.co.kr",
    "hankyung.com",
    "yna.co.kr",
    "reuters",
    "bloomberg",
)


@dataclass(frozen=True)
class ContextProviderResult:
    provider_key: str
    status: str
    run_id: int | None
    observed_count: int
    sample_count: int
    market_reaction_snapshot_count: int
    news_trigger_count: int
    error: str | None = None


@dataclass(frozen=True)
class ContextCollectionResult:
    db_path: str
    trade_date: str
    snapshot_time: str
    providers: list[ContextProviderResult]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ArgusMarketReactionService:
    def __init__(self, *, provider: str, file_path: str | None = None) -> None:
        self.provider = provider.strip().lower()
        self.file_path = file_path

    def fetch_snapshot(self, *, trade_date: date, snapshot_time: datetime | None = None) -> BriefingProviderBatch:
        enabled, reason = self.is_enabled()
        if not enabled:
            return BriefingProviderBatch(records=[], disabled_reason=reason)

        snapshot_iso = _snapshot_iso(snapshot_time or datetime.now(timezone.utc))
        if self.provider == "mock":
            return BriefingProviderBatch(
                records=[_mock_market_reaction(trade_date=trade_date, snapshot_time=snapshot_iso)],
                metadata={"provider": "mock"},
            )

        payload = load_json_file(self.file_path or "")
        row = _pick_dated_payload(payload=payload, trade_date=trade_date)
        return BriefingProviderBatch(
            records=[self._normalize_file_row(row=row, trade_date=trade_date, snapshot_time=snapshot_iso)],
            metadata={"provider": "file", "file_path": self.file_path},
        )

    def is_enabled(self) -> tuple[bool, str | None]:
        if self.provider in {"", "disabled"}:
            return False, "feature_flag_disabled"
        if self.provider == "mock":
            return True, None
        if self.provider == "file":
            return (True, None) if self.file_path else (False, "missing_file_path")
        return False, f"unsupported_provider:{self.provider}"

    def _normalize_file_row(
        self,
        *,
        row: dict[str, Any],
        trade_date: date,
        snapshot_time: str,
    ) -> MarketReactionSnapshotRecord:
        source = pick_text(row, ("source_name", "source")) or "argus_v2.market_reaction_file"
        observed_at = pick_text(row, ("snapshot_time", "observed_at")) or snapshot_time
        return MarketReactionSnapshotRecord(
            source_name=source,
            trade_date=pick_text(row, ("trade_date", "date")) or trade_date.isoformat(),
            snapshot_time=observed_at,
            kospi_change_rate=pick_float(row, ("kospi_change_rate", "kospi", "kospi_rate")),
            kosdaq_change_rate=pick_float(row, ("kosdaq_change_rate", "kosdaq", "kosdaq_rate")),
            kospi200_futures_change_rate=pick_float(row, ("kospi200_futures_change_rate", "futures_change_rate")),
            advancing_count=_as_int(row.get("advancing_count") or row.get("advancers")),
            declining_count=_as_int(row.get("declining_count") or row.get("decliners")),
            spot_foreign_net_buy=pick_float(row, ("spot_foreign_net_buy", "foreign_spot_net_buy", "foreign_net_buy")),
            spot_institution_net_buy=pick_float(
                row,
                ("spot_institution_net_buy", "institution_spot_net_buy", "institution_net_buy"),
            ),
            spot_individual_net_buy=pick_float(row, ("spot_individual_net_buy", "individual_spot_net_buy", "individual_net_buy")),
            summary=pick_text(row, ("summary", "memo")) or "",
            freshness_state=pick_text(row, ("freshness_state", "freshness")) or "partial",
            source_url=pick_text(row, ("source_url", "url")),
            source_record_id=pick_text(row, ("source_record_id", "id")),
            raw_payload=row,
            strong_sectors=_sector_records(row.get("strong_sectors"), role="strong", observed_at=observed_at, source=source),
            weak_sectors=_sector_records(row.get("weak_sectors"), role="weak", observed_at=observed_at, source=source),
        )


class ArgusNewsTriggerService:
    def __init__(
        self,
        *,
        provider: str,
        file_path: str | None = None,
        rss_urls: str | None = None,
        query: str | None = None,
        limit: int = 8,
        lookback_hours: int = 24,
        naver_client_id: str | None = None,
        naver_client_secret: str | None = None,
        naver_base_url: str = DEFAULT_NAVER_BASE_URL,
        naver_search_path: str = DEFAULT_NAVER_NEWS_PATH,
        naver_display: int = 20,
        naver_page_limit: int = 2,
        dart_api_key: str | None = None,
        dart_base_url: str = DEFAULT_DART_BASE_URL,
        dart_list_path: str = DEFAULT_DART_LIST_PATH,
        dart_corp_cls: str = "Y,K",
        dart_pblntf_ty: str = "B,I",
        dart_lookback_days: int = 1,
        dart_page_count: int = 50,
        macro_events_provider: str = "disabled",
        macro_events_file_path: str | None = None,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.provider = provider.strip().lower()
        self.file_path = file_path
        self.rss_urls = _split_csv(rss_urls) or list(DEFAULT_RSS_URLS)
        self.query_terms = _split_csv(query)
        self.limit = max(1, limit)
        self.lookback_hours = max(1, lookback_hours)
        self.naver_client_id = (naver_client_id or "").strip()
        self.naver_client_secret = (naver_client_secret or "").strip()
        self.naver_base_url = naver_base_url.rstrip("/")
        self.naver_search_path = naver_search_path
        self.naver_display = max(1, min(naver_display, 100))
        self.naver_page_limit = max(1, naver_page_limit)
        self.dart_api_key = (dart_api_key or "").strip()
        self.dart_base_url = dart_base_url.rstrip("/")
        self.dart_list_path = dart_list_path
        self.dart_corp_cls = _split_csv(dart_corp_cls)
        self.dart_pblntf_ty = _split_csv(dart_pblntf_ty)
        self.dart_lookback_days = max(1, dart_lookback_days)
        self.dart_page_count = max(1, min(dart_page_count, 100))
        self.macro_events_provider = macro_events_provider.strip().lower()
        self.macro_events_file_path = macro_events_file_path
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(1, max_retries)
        self.backoff_seconds = max(0.0, backoff_seconds)
        self._http_client = http_client

    def fetch_triggers(self, *, trade_date: date, snapshot_time: datetime | None = None) -> BriefingProviderBatch:
        enabled, reason = self.is_enabled()
        if not enabled:
            return BriefingProviderBatch(records=[], disabled_reason=reason)

        snapshot_at = (snapshot_time or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if self.provider == "mock":
            return BriefingProviderBatch(
                records=_mock_news_triggers(snapshot_time=_snapshot_iso(snapshot_at)),
                metadata={"provider": "mock"},
            )
        if self.provider == "file":
            payload = load_json_file(self.file_path or "")
            rows = _pick_news_rows(payload=payload, trade_date=trade_date)
            records = [self._normalize_file_row(row=row, index=index, snapshot_time=snapshot_at) for index, row in enumerate(rows)]
            return self._records_batch(records=records, provider="file", metadata={"file_path": self.file_path, "row_count": len(rows)})
        if self.provider == "naver":
            records = self._fetch_naver_records(snapshot_time=snapshot_at)
            return self._records_batch(records=records, provider="naver")
        if self.provider == "dart":
            records = self._fetch_dart_records(trade_date=trade_date)
            return self._records_batch(records=records, provider="dart")
        if self.provider == "macro":
            records = self._fetch_macro_records(trade_date=trade_date, snapshot_time=snapshot_at)
            return self._records_batch(records=records, provider="macro")
        if self.provider == "hybrid":
            records = []
            if self.rss_urls:
                records.extend(self._fetch_rss_records(snapshot_time=snapshot_at))
            if self.naver_client_id and self.naver_client_secret:
                records.extend(self._fetch_naver_records(snapshot_time=snapshot_at))
            if self.dart_api_key:
                records.extend(self._fetch_dart_records(trade_date=trade_date))
            records.extend(self._fetch_macro_records(trade_date=trade_date, snapshot_time=snapshot_at))
            return self._records_batch(records=_deduplicate_triggers(records), provider="hybrid")

        records = self._fetch_rss_records(snapshot_time=snapshot_at)
        return self._records_batch(records=records, provider="rss")

    def is_enabled(self) -> tuple[bool, str | None]:
        if self.provider in {"", "disabled"}:
            return False, "feature_flag_disabled"
        if self.provider == "mock":
            return True, None
        if self.provider == "file":
            return (True, None) if self.file_path else (False, "missing_file_path")
        if self.provider == "rss":
            return (True, None) if self.rss_urls else (False, "missing_rss_urls")
        if self.provider == "naver":
            if not self.naver_client_id or not self.naver_client_secret:
                return False, "missing_naver_credentials"
            return True, None
        if self.provider == "dart":
            return (True, None) if self.dart_api_key else (False, "missing_dart_api_key")
        if self.provider == "macro":
            return self._macro_events_enabled()
        if self.provider == "hybrid":
            macro_enabled, _ = self._macro_events_enabled()
            if self.rss_urls or (self.naver_client_id and self.naver_client_secret) or self.dart_api_key or macro_enabled:
                return True, None
            return False, "missing_hybrid_sources"
        return False, f"unsupported_provider:{self.provider}"

    def _macro_events_enabled(self) -> tuple[bool, str | None]:
        if self.macro_events_provider in {"", "disabled"}:
            return False, "feature_flag_disabled"
        if self.macro_events_provider == "mock":
            return True, None
        if self.macro_events_provider == "file":
            return (True, None) if self.macro_events_file_path else (False, "missing_macro_file_path")
        return False, f"unsupported_macro_provider:{self.macro_events_provider}"

    def _records_batch(
        self,
        *,
        records: list[NewsTriggerRecord],
        provider: str,
        metadata: dict[str, Any] | None = None,
    ) -> BriefingProviderBatch:
        ranked = [_with_importance(record) for record in records]
        important = [record for record in ranked if _importance_score_from_raw(record) > 0]
        important.sort(key=lambda item: (_importance_score_from_raw(item), item.published_at or ""), reverse=True)
        limited = important[: self.limit]
        return BriefingProviderBatch(
            records=limited,
            metadata={
                "provider": provider,
                "feed_urls": self.rss_urls if provider in {"rss", "hybrid"} else [],
                "query_terms": self.query_terms,
                "input_count": len(records),
                "filtered_count": len(limited),
                "expected_count": len(limited),
                **(metadata or {}),
            },
        )

    def _normalize_file_row(self, *, row: dict[str, Any], index: int, snapshot_time: datetime) -> NewsTriggerRecord:
        title = pick_text(row, ("title", "headline")) or f"뉴스 트리거 {index + 1}"
        summary = pick_text(row, ("summary", "description", "memo")) or ""
        published_at = pick_text(row, ("published_at", "pub_date", "observed_at")) or _snapshot_iso(snapshot_time)
        impact = pick_text(row, ("impact", "tone")) or _classify_impact(f"{title} {summary}")
        return NewsTriggerRecord(
            id=pick_text(row, ("id", "external_id", "source_record_id")) or _stable_trigger_id(title=title, published_at=published_at),
            title=title,
            summary=summary,
            impact=_valid_impact(impact),
            source=pick_text(row, ("source", "source_name", "publisher")) or "argus_v2.news_trigger_file",
            published_at=published_at,
            connection_strength=_valid_connection_strength(pick_text(row, ("connection_strength", "strength")) or _connection_strength(title, summary)),
            freshness=pick_text(row, ("freshness", "freshness_state")) or "partial",
            source_url=pick_text(row, ("source_url", "url", "link")),
            raw_payload=row,
        )

    def _fetch_rss_records(self, *, snapshot_time: datetime) -> list[NewsTriggerRecord]:
        cutoff = snapshot_time - timedelta(hours=self.lookback_hours)
        records: list[NewsTriggerRecord] = []
        for feed_url in self.rss_urls:
            feed_title, items = self._request_feed(feed_url=feed_url)
            for item in items:
                record = self._rss_item_to_record(item=item, feed_url=feed_url, feed_title=feed_title)
                if record is None:
                    continue
                published_at = _parse_iso(record.published_at)
                if published_at is not None and published_at < cutoff:
                    continue
                if self.query_terms and not _matches_any_term(record, self.query_terms):
                    continue
                records.append(record)

        records.sort(key=lambda item: item.published_at or "", reverse=True)
        return records

    def _fetch_naver_records(self, *, snapshot_time: datetime) -> list[NewsTriggerRecord]:
        cutoff = snapshot_time - timedelta(hours=self.lookback_hours)
        records: list[NewsTriggerRecord] = []
        queries = self.query_terms or ["코스피"]
        for query in queries:
            for page_index in range(self.naver_page_limit):
                start = 1 + page_index * self.naver_display
                payload = self._request_naver_page(query=query, start=start)
                rows = payload.get("items")
                if not isinstance(rows, list):
                    raise ValueError("naver_news_items_missing")
                if not rows:
                    break
                for index, row in enumerate(rows):
                    if not isinstance(row, dict):
                        continue
                    record = self._naver_item_to_record(row=row, query=query, index=index)
                    if record is None:
                        continue
                    published_at = _parse_iso(record.published_at)
                    if published_at is not None and published_at < cutoff:
                        continue
                    records.append(record)
                if len(rows) < self.naver_display:
                    break
        return _deduplicate_triggers(records)

    def _request_naver_page(self, *, query: str, start: int) -> dict[str, Any]:
        url = f"{self.naver_base_url}{self.naver_search_path}"
        headers = {
            "X-Naver-Client-Id": self.naver_client_id,
            "X-Naver-Client-Secret": self.naver_client_secret,
        }
        params = {
            "query": query,
            "display": str(self.naver_display),
            "start": str(start),
            "sort": "date",
        }
        payload = self._request_json(url=url, headers=headers, params=params)
        if not isinstance(payload, dict):
            raise ValueError("naver_news_payload_invalid")
        return payload

    def _naver_item_to_record(self, *, row: dict[str, Any], query: str, index: int) -> NewsTriggerRecord | None:
        title = _strip_html(_as_text(row.get("title")))
        summary = _strip_html(_as_text(row.get("description")))
        link = _as_text(row.get("originallink")) or _as_text(row.get("link"))
        published_at = _parse_rss_date(_as_text(row.get("pubDate")))
        if not title and not link:
            return None
        published_value = _snapshot_iso(published_at) if published_at is not None else None
        return NewsTriggerRecord(
            id=_stable_trigger_id(title=title or f"naver-{index}", published_at=published_value or link or query),
            title=title or link or f"Naver news {index + 1}",
            summary=summary,
            impact=_classify_impact(f"{title} {summary}"),
            source=_source_from_url(link or "naver.com"),
            published_at=published_value,
            connection_strength=_connection_strength(title, summary),
            freshness="fresh",
            source_url=link,
            raw_payload={
                "title": row.get("title"),
                "originallink": row.get("originallink"),
                "link": row.get("link"),
                "description": row.get("description"),
                "pubDate": row.get("pubDate"),
                "query": query,
            },
        )

    def _fetch_dart_records(self, *, trade_date: date) -> list[NewsTriggerRecord]:
        start_date = trade_date - timedelta(days=self.dart_lookback_days - 1)
        records: list[NewsTriggerRecord] = []
        corp_classes = self.dart_corp_cls or [""]
        disclosure_types = self.dart_pblntf_ty or [""]
        for corp_cls in corp_classes:
            for disclosure_type in disclosure_types:
                payload = self._request_dart_page(
                    start_date=start_date,
                    end_date=trade_date,
                    corp_cls=corp_cls,
                    disclosure_type=disclosure_type,
                )
                rows = payload.get("list") if isinstance(payload, dict) else None
                if rows is None and isinstance(payload, dict) and str(payload.get("status")) in {"013", "014"}:
                    continue
                if not isinstance(rows, list):
                    raise ValueError("dart_list_missing")
                for row in rows:
                    if isinstance(row, dict):
                        records.append(self._dart_row_to_record(row=row))
        return _deduplicate_triggers(records)

    def _fetch_macro_records(self, *, trade_date: date, snapshot_time: datetime) -> list[NewsTriggerRecord]:
        enabled, _ = self._macro_events_enabled()
        if not enabled:
            return []
        if self.macro_events_provider == "mock":
            return _mock_macro_triggers(snapshot_time=_snapshot_iso(snapshot_time))

        payload = load_json_file(self.macro_events_file_path or "")
        rows = _pick_macro_rows(payload=payload, trade_date=trade_date)
        return [
            self._macro_row_to_record(row=row, index=index, snapshot_time=snapshot_time)
            for index, row in enumerate(rows)
        ]

    def _macro_row_to_record(self, *, row: dict[str, Any], index: int, snapshot_time: datetime) -> NewsTriggerRecord:
        observed_at = pick_text(row, ("observed_at", "published_at", "event_time")) or _snapshot_iso(snapshot_time)
        event_type = pick_text(row, ("event_type", "type", "category")) or "macro"
        title = pick_text(row, ("title", "name", "event_name")) or f"매크로 이벤트 {index + 1}"
        value = pick_text(row, ("value", "actual"))
        unit = pick_text(row, ("unit",))
        previous = pick_text(row, ("previous", "prev"))
        summary = pick_text(row, ("summary", "description", "memo"))
        if not summary:
            current_text = f"{value}{unit or ''}" if value else "값 미수신"
            previous_text = f", 이전 {previous}" if previous else ""
            summary = f"{event_type}: 현재 {current_text}{previous_text}"
        return NewsTriggerRecord(
            id=pick_text(row, ("id", "external_id", "source_record_id")) or _stable_trigger_id(title=title, published_at=observed_at),
            title=title,
            summary=summary,
            impact=_valid_impact(pick_text(row, ("impact", "tone")) or _classify_impact(f"{title} {summary}")),
            source=pick_text(row, ("source", "source_name")) or "ARGUS_MACRO_EVENT",
            published_at=observed_at,
            connection_strength=_valid_connection_strength(pick_text(row, ("connection_strength", "strength")) or _connection_strength(title, summary)),
            freshness=pick_text(row, ("freshness", "freshness_state")) or "fresh",
            source_url=pick_text(row, ("source_url", "url")),
            raw_payload=row,
        )

    def _request_dart_page(
        self,
        *,
        start_date: date,
        end_date: date,
        corp_cls: str,
        disclosure_type: str,
    ) -> dict[str, Any]:
        url = f"{self.dart_base_url}{self.dart_list_path}"
        params = {
            "crtfc_key": self.dart_api_key,
            "bgn_de": start_date.strftime("%Y%m%d"),
            "end_de": end_date.strftime("%Y%m%d"),
            "last_reprt_at": "N",
            "corp_cls": corp_cls,
            "pblntf_ty": disclosure_type,
            "sort": "date",
            "sort_mth": "desc",
            "page_no": "1",
            "page_count": str(self.dart_page_count),
        }
        payload = self._request_json(url=url, headers={}, params={key: value for key, value in params.items() if value})
        if not isinstance(payload, dict):
            raise ValueError("dart_payload_invalid")
        return payload

    def _dart_row_to_record(self, *, row: dict[str, Any]) -> NewsTriggerRecord:
        corp_name = pick_text(row, ("corp_name", "corp")) or "공시회사"
        report_name = pick_text(row, ("report_nm", "report_name")) or "공시"
        receipt_no = pick_text(row, ("rcept_no", "receipt_no")) or _stable_trigger_id(title=corp_name, published_at=report_name)
        receipt_date = pick_text(row, ("rcept_dt", "receipt_date"))
        published_at = _dart_date_to_iso(receipt_date)
        title = f"{corp_name} {report_name}"
        summary = f"DART 공시: {report_name}"
        viewer_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}" if receipt_no else None
        return NewsTriggerRecord(
            id=f"dart-{receipt_no}",
            title=title,
            summary=summary,
            impact=_classify_impact(title),
            source="DART",
            published_at=published_at,
            connection_strength=_connection_strength(title, summary),
            freshness="fresh",
            source_url=viewer_url,
            raw_payload={
                "corp_name": row.get("corp_name"),
                "corp_code": row.get("corp_code"),
                "stock_code": row.get("stock_code"),
                "corp_cls": row.get("corp_cls"),
                "report_nm": row.get("report_nm"),
                "rcept_no": row.get("rcept_no"),
                "rcept_dt": row.get("rcept_dt"),
                "flr_nm": row.get("flr_nm"),
                "rm": row.get("rm"),
            },
        )

    def _request_json(self, *, url: str, headers: dict[str, str], params: dict[str, str]) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._do_json_request(url=url, headers=headers, params=params)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as error:
                last_error = error
                if attempt < self.max_retries and self.backoff_seconds > 0:
                    import time

                    time.sleep(self.backoff_seconds)
        raise RuntimeError(f"json_fetch_failed:{url}") from last_error

    def _do_json_request(self, *, url: str, headers: dict[str, str], params: dict[str, str]) -> httpx.Response:
        if self._http_client is not None:
            return self._http_client.get(url, headers=headers, params=params, timeout=self.timeout_seconds)
        with httpx.Client() as client:
            return client.get(url, headers=headers, params=params, timeout=self.timeout_seconds)

    def _request_feed(self, *, feed_url: str) -> tuple[str | None, list[ET.Element]]:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._do_request(feed_url=feed_url)
                response.raise_for_status()
                root = ET.fromstring(response.text)
                channel = root.find("channel")
                if channel is None:
                    raise ValueError("rss_channel_missing")
                return channel.findtext("title"), list(channel.findall("item"))
            except (httpx.HTTPError, ET.ParseError, ValueError) as error:
                last_error = error
                if attempt < self.max_retries and self.backoff_seconds > 0:
                    import time

                    time.sleep(self.backoff_seconds)
        raise RuntimeError(f"rss_fetch_failed:{feed_url}") from last_error

    def _do_request(self, *, feed_url: str) -> httpx.Response:
        headers = {"User-Agent": "ArgusRenewal/0.1"}
        if self._http_client is not None:
            return self._http_client.get(feed_url, headers=headers, timeout=self.timeout_seconds)
        with httpx.Client() as client:
            return client.get(feed_url, headers=headers, timeout=self.timeout_seconds)

    def _rss_item_to_record(
        self,
        *,
        item: ET.Element,
        feed_url: str,
        feed_title: str | None,
    ) -> NewsTriggerRecord | None:
        title = _strip_html(item.findtext("title"))
        link = _strip_html(item.findtext("link"))
        summary = _strip_html(item.findtext("description"))
        published_at = _parse_rss_date(item.findtext("pubDate"))
        if not title and not link:
            return None
        impact = _classify_impact(f"{title} {summary}")
        source = _strip_html(feed_title) or _source_from_url(link or feed_url)
        published_value = _snapshot_iso(published_at) if published_at is not None else None
        return NewsTriggerRecord(
            id=_stable_trigger_id(title=title, published_at=published_value or link or feed_url),
            title=title or link,
            summary=summary,
            impact=impact,
            source=source,
            published_at=published_value,
            connection_strength=_connection_strength(title, summary),
            freshness="fresh",
            source_url=link or feed_url,
            raw_payload={
                "title": title,
                "link": link,
                "description": summary,
                "pubDate": item.findtext("pubDate"),
                "feed_url": feed_url,
                "feed_title": feed_title,
            },
        )


def run_context_collection(
    *,
    settings: Settings,
    trade_date: date | None = None,
    snapshot_time: datetime | None = None,
    include_market_reaction: bool = True,
    include_news_triggers: bool = True,
    market_reaction_provider: str | None = None,
    news_triggers_provider: str | None = None,
    http_client: httpx.Client | None = None,
) -> ContextCollectionResult:
    resolved_trade_date = trade_date or datetime.now(KST).date()
    resolved_snapshot_time = (snapshot_time or datetime.now(timezone.utc)).astimezone(timezone.utc)
    providers: list[ContextProviderResult] = []

    with get_connection(settings.db_path) as connection:
        storage = ArgusV2Storage(connection)
        if include_market_reaction:
            providers.append(
                _fetch_and_store_market_reaction(
                    settings=settings,
                    storage=storage,
                    trade_date=resolved_trade_date,
                    snapshot_time=resolved_snapshot_time,
                    provider_override=market_reaction_provider,
                    http_client=http_client,
                )
            )
        if include_news_triggers:
            providers.append(
                _fetch_and_store_news_triggers(
                    settings=settings,
                    storage=storage,
                    trade_date=resolved_trade_date,
                    snapshot_time=resolved_snapshot_time,
                    provider_override=news_triggers_provider,
                    http_client=http_client,
                )
            )

    return ContextCollectionResult(
        db_path=str(resolve_db_path(settings.db_path)),
        trade_date=resolved_trade_date.isoformat(),
        snapshot_time=_snapshot_iso(resolved_snapshot_time),
        providers=providers,
    )


def _fetch_and_store_market_reaction(
    *,
    settings: Settings,
    storage: ArgusV2Storage,
    trade_date: date,
    snapshot_time: datetime,
    provider_override: str | None,
    http_client: httpx.Client | None,
) -> ContextProviderResult:
    provider_key = "v2_market_reaction"
    provider = (provider_override or settings.argus_market_reaction_provider).strip().lower()
    endpoint = provider_override or settings.argus_market_reaction_provider
    try:
        if provider in KIS_MARKET_REACTION_PROVIDERS:
            token = KisAuthClient(
                base_url=settings.kis_base_url,
                token_path=settings.kis_token_path,
                app_key=settings.kis_app_key,
                app_secret=settings.kis_app_secret,
                timeout_seconds=settings.market_briefing_timeout_seconds,
                cache_path=str(resolve_db_path(settings.kis_token_cache_path or DEFAULT_KIS_TOKEN_CACHE_PATH)),
                http_client=http_client,
            ).issue_access_token()
            endpoint = settings.argus_market_reaction_index_price_path
            batch = KisMarketReactionService(
                base_url=settings.kis_base_url,
                index_price_path=settings.argus_market_reaction_index_price_path,
                index_price_tr_id=settings.argus_market_reaction_index_price_tr_id,
                category_price_path=settings.argus_market_reaction_category_price_path,
                category_price_tr_id=settings.argus_market_reaction_category_price_tr_id,
                investor_time_path=settings.argus_market_reaction_investor_time_path,
                investor_time_tr_id=settings.argus_market_reaction_investor_time_tr_id,
                investor_amount_multiplier=settings.argus_market_reaction_investor_amount_multiplier,
                app_key=settings.kis_app_key,
                app_secret=settings.kis_app_secret,
                access_token=token.access_token,
                timeout_seconds=settings.market_briefing_timeout_seconds,
                max_retries=settings.market_briefing_max_retries,
                backoff_seconds=settings.market_briefing_backoff_seconds,
                sector_limit=settings.argus_market_reaction_sector_limit,
                http_client=http_client,
            ).fetch_snapshot(trade_date=trade_date, snapshot_time=snapshot_time)
        else:
            batch = ArgusMarketReactionService(
                provider=provider,
                file_path=settings.argus_market_reaction_file_path,
            ).fetch_snapshot(trade_date=trade_date, snapshot_time=snapshot_time)
        persisted = storage.save_provider_batch(
            provider_key=provider_key,
            provider_label="v2 현물 반응",
            endpoint=endpoint,
            batch=batch,
        )
        return ContextProviderResult(
            provider_key=provider_key,
            status=persisted.status,
            run_id=persisted.run_id,
            observed_count=persisted.observed_count,
            sample_count=len(persisted.sample_ids),
            market_reaction_snapshot_count=len(persisted.market_reaction_snapshot_ids),
            news_trigger_count=len(persisted.news_trigger_ids),
        )
    except Exception as error:
        return _persist_failed_context_run(
            storage=storage,
            provider_key=provider_key,
            provider_label="v2 현물 반응",
            endpoint=endpoint,
            error=error,
        )


def _fetch_and_store_news_triggers(
    *,
    settings: Settings,
    storage: ArgusV2Storage,
    trade_date: date,
    snapshot_time: datetime,
    provider_override: str | None,
    http_client: httpx.Client | None,
) -> ContextProviderResult:
    provider_key = "v2_news_triggers"
    try:
        batch = ArgusNewsTriggerService(
            provider=provider_override or settings.argus_news_triggers_provider,
            file_path=settings.argus_news_triggers_file_path,
            rss_urls=settings.argus_news_triggers_rss_urls,
            query=settings.argus_news_triggers_query,
            limit=settings.argus_news_triggers_limit,
            lookback_hours=settings.argus_news_triggers_lookback_hours,
            naver_client_id=settings.argus_news_naver_client_id,
            naver_client_secret=settings.argus_news_naver_client_secret,
            naver_base_url=settings.argus_news_naver_base_url,
            naver_search_path=settings.argus_news_naver_search_path,
            naver_display=settings.argus_news_naver_display,
            naver_page_limit=settings.argus_news_naver_page_limit,
            dart_api_key=settings.argus_disclosure_dart_api_key,
            dart_base_url=settings.argus_disclosure_dart_base_url,
            dart_list_path=settings.argus_disclosure_dart_list_path,
            dart_corp_cls=settings.argus_disclosure_dart_corp_cls,
            dart_pblntf_ty=settings.argus_disclosure_dart_pblntf_ty,
            dart_lookback_days=settings.argus_disclosure_dart_lookback_days,
            dart_page_count=settings.argus_disclosure_dart_page_count,
            macro_events_provider=settings.argus_macro_events_provider,
            macro_events_file_path=settings.argus_macro_events_file_path,
            timeout_seconds=settings.market_briefing_timeout_seconds,
            max_retries=settings.market_briefing_max_retries,
            backoff_seconds=settings.market_briefing_backoff_seconds,
            http_client=http_client,
        ).fetch_triggers(trade_date=trade_date, snapshot_time=snapshot_time)
        persisted = storage.save_provider_batch(
            provider_key=provider_key,
            provider_label="v2 뉴스 트리거",
            endpoint=provider_override or settings.argus_news_triggers_provider,
            batch=batch,
        )
        return ContextProviderResult(
            provider_key=provider_key,
            status=persisted.status,
            run_id=persisted.run_id,
            observed_count=persisted.observed_count,
            sample_count=len(persisted.sample_ids),
            market_reaction_snapshot_count=len(persisted.market_reaction_snapshot_ids),
            news_trigger_count=len(persisted.news_trigger_ids),
        )
    except Exception as error:
        return _persist_failed_context_run(
            storage=storage,
            provider_key=provider_key,
            provider_label="v2 뉴스 트리거",
            endpoint=provider_override or settings.argus_news_triggers_provider,
            error=error,
        )


def _persist_failed_context_run(
    *,
    storage: ArgusV2Storage,
    provider_key: str,
    provider_label: str,
    endpoint: str,
    error: Exception,
) -> ContextProviderResult:
    run_id = storage.start_provider_run(
        provider_key=provider_key,
        provider_label=provider_label,
        endpoint=endpoint,
        started_at=utcnow_iso(),
    )
    safe_error = f"{error.__class__.__name__}: {str(error)[:500]}" if str(error) else error.__class__.__name__
    storage.finish_provider_run(run_id=run_id, status="failed", observed_count=0, error=safe_error)
    return ContextProviderResult(
        provider_key=provider_key,
        status="failed",
        run_id=run_id,
        observed_count=0,
        sample_count=0,
        market_reaction_snapshot_count=0,
        news_trigger_count=0,
        error=safe_error,
    )


def _mock_market_reaction(*, trade_date: date, snapshot_time: str) -> MarketReactionSnapshotRecord:
    return MarketReactionSnapshotRecord(
        source_name="mock.market.reaction",
        trade_date=trade_date.isoformat(),
        snapshot_time=snapshot_time,
        kospi_change_rate=-0.18,
        kosdaq_change_rate=0.12,
        kospi200_futures_change_rate=-0.34,
        advancing_count=432,
        declining_count=511,
        spot_foreign_net_buy=-82_000_000_000,
        spot_institution_net_buy=34_000_000_000,
        spot_individual_net_buy=48_000_000_000,
        summary="지수는 약하지만 반도체가 버티며 하방 압력을 제한합니다.",
        freshness_state="partial",
        raw_payload={"provider": "mock"},
        strong_sectors=[
            MarketReactionSectorRecord(
                name="반도체",
                change_rate=1.15,
                reason="미국 AI/반도체 모멘텀 반영",
                tone="positive",
                source="mock.market.reaction",
                observed_at=snapshot_time,
            )
        ],
        weak_sectors=[
            MarketReactionSectorRecord(
                name="금융",
                change_rate=-0.62,
                reason="금리 변동성 확대 구간",
                tone="negative",
                source="mock.market.reaction",
                observed_at=snapshot_time,
            )
        ],
    )


def _mock_news_triggers(*, snapshot_time: str) -> list[NewsTriggerRecord]:
    return [
        NewsTriggerRecord(
            id="mock-rates",
            title="미국 금리 상승 경계",
            summary="밤사이 금리 상승은 위험자산과 원화에는 부담으로 해석됩니다.",
            impact="negative",
            source="mock.news.macro",
            published_at=snapshot_time,
            connection_strength="medium",
            freshness="partial",
            raw_payload={"provider": "mock"},
        ),
        NewsTriggerRecord(
            id="mock-chip",
            title="반도체 상대 강세",
            summary="지수 영향도가 큰 반도체가 하락 압력을 일부 상쇄합니다.",
            impact="positive",
            source="mock.news.sector",
            published_at=snapshot_time,
            connection_strength="medium",
            freshness="partial",
            raw_payload={"provider": "mock"},
        ),
    ]


def _mock_macro_triggers(*, snapshot_time: str) -> list[NewsTriggerRecord]:
    return [
        NewsTriggerRecord(
            id="mock-macro-us-yield",
            title="미국 10년물 금리 상승",
            summary="미국 국채금리 상승은 성장주와 원화에는 부담으로 해석합니다.",
            impact="negative",
            source="mock.macro.rates",
            published_at=snapshot_time,
            connection_strength="strong",
            freshness="partial",
            raw_payload={"provider": "mock_macro", "event_type": "rates"},
        ),
        NewsTriggerRecord(
            id="mock-macro-us-tech",
            title="나스닥 반도체 강세",
            summary="미국 기술주와 반도체 강세는 국내 반도체 대형주에 우호적입니다.",
            impact="positive",
            source="mock.macro.us_equity",
            published_at=snapshot_time,
            connection_strength="medium",
            freshness="partial",
            raw_payload={"provider": "mock_macro", "event_type": "us_equity"},
        ),
    ]


def _pick_dated_payload(*, payload: Any, trade_date: date) -> dict[str, Any]:
    if isinstance(payload, dict):
        dated = payload.get(trade_date.isoformat())
        if isinstance(dated, dict):
            return dated
        item = payload.get("item")
        if isinstance(item, dict):
            return item
        if _looks_like_reaction_row(payload):
            return payload
    raise ValueError("market_reaction_file_payload_invalid")


def _pick_news_rows(*, payload: Any, trade_date: date) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        dated = payload.get(trade_date.isoformat())
        if isinstance(dated, list):
            return [item for item in dated if isinstance(item, dict)]
        for key in ("triggers", "items", "data"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
    return []


def _pick_macro_rows(*, payload: Any, trade_date: date) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        dated = payload.get(trade_date.isoformat())
        if isinstance(dated, list):
            return [item for item in dated if isinstance(item, dict)]
        for key in ("events", "macro_events", "items", "data"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
    return []


def _looks_like_reaction_row(payload: dict[str, Any]) -> bool:
    return any(key in payload for key in ("kospi_change_rate", "kosdaq_change_rate", "strong_sectors", "weak_sectors"))


def _sector_records(payload: Any, *, role: str, observed_at: str, source: str) -> list[MarketReactionSectorRecord]:
    if not isinstance(payload, list):
        return []
    records = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = pick_text(item, ("name", "sector", "theme"))
        if not name:
            continue
        records.append(
            MarketReactionSectorRecord(
                name=name,
                change_rate=pick_float(item, ("change_rate", "rate", "change")),
                reason=pick_text(item, ("reason", "summary", "memo")) or "",
                tone=_valid_impact(pick_text(item, ("tone", "impact")) or ("positive" if role == "strong" else "negative")),
                source=pick_text(item, ("source", "source_name")) or source,
                observed_at=pick_text(item, ("observed_at", "snapshot_time")) or observed_at,
            )
        )
    return records


def _classify_impact(text: str) -> str:
    lower_text = text.casefold()
    positive_score = sum(1 for term in POSITIVE_TERMS if term.casefold() in lower_text)
    negative_score = sum(1 for term in NEGATIVE_TERMS if term.casefold() in lower_text)
    if positive_score > negative_score:
        return "positive"
    if negative_score > positive_score:
        return "negative"
    return "neutral"


def _connection_strength(title: str, summary: str) -> str:
    text = f"{title} {summary}".casefold()
    score = sum(1 for term in (*POSITIVE_TERMS, *NEGATIVE_TERMS) if term.casefold() in text)
    if score >= 3:
        return "strong"
    if score >= 1:
        return "medium"
    return "weak"


def _with_importance(record: NewsTriggerRecord) -> NewsTriggerRecord:
    score, matched_terms = _news_importance(record)
    raw_payload = record.raw_payload if isinstance(record.raw_payload, dict) else {}
    enriched_raw_payload = {
        **raw_payload,
        "_argus_importance_score": score,
        "_argus_importance_terms": matched_terms,
    }
    return replace(
        record,
        connection_strength=_strength_from_importance(score),
        raw_payload=enriched_raw_payload,
    )


def _news_importance(record: NewsTriggerRecord) -> tuple[int, list[str]]:
    text = f"{record.title} {record.summary} {record.source}".casefold()
    score = 0
    matched_terms: list[str] = []
    for term, weight in NEWS_IMPORTANCE_TERMS:
        if term.casefold() in text:
            score += weight
            matched_terms.append(term)

    if record.source_url:
        source_text = f"{record.source} {record.source_url}".casefold()
        if any(source.casefold() in source_text for source in HIGH_QUALITY_SOURCES):
            score += 2

    if record.source.casefold() == "dart":
        score += 3

    if any(term.casefold() in text for term in LOW_SIGNAL_NEWS_TERMS):
        score -= 5

    return max(score, 0), matched_terms[:8]


def _strength_from_importance(score: int) -> str:
    if score >= 10:
        return "strong"
    if score >= 5:
        return "medium"
    if score > 0:
        return "weak"
    return "unclear"


def _importance_score_from_raw(record: NewsTriggerRecord) -> int:
    raw_payload = record.raw_payload if isinstance(record.raw_payload, dict) else {}
    value = raw_payload.get("_argus_importance_score")
    return int(value) if isinstance(value, int) else 0


def _matches_any_term(record: NewsTriggerRecord, terms: list[str]) -> bool:
    text = f"{record.title} {record.summary}".casefold()
    return any(term.casefold() in text for term in terms)


def _deduplicate_triggers(records: list[NewsTriggerRecord]) -> list[NewsTriggerRecord]:
    seen: set[str] = set()
    deduped: list[NewsTriggerRecord] = []
    for record in records:
        key = (record.source_url or record.id or record.title).casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _valid_impact(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"positive", "neutral", "negative"}:
        return normalized
    return "neutral"


def _valid_connection_strength(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"strong", "medium", "weak", "unclear"}:
        return normalized
    return "unclear"


def _stable_trigger_id(*, title: str, published_at: str) -> str:
    import hashlib

    digest = hashlib.sha1(f"{title}|{published_at}".encode("utf-8")).hexdigest()[:12]
    return f"trigger-{digest}"


def _source_from_url(value: str) -> str:
    host = urlparse(value).netloc
    return host.replace("www.", "") or "rss"


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _strip_html(value: str | None) -> str:
    if value is None:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _parse_rss_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _dart_date_to_iso(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if len(text) != 8 or not text.isdigit():
        return None
    parsed = datetime(int(text[:4]), int(text[4:6]), int(text[6:8]), 0, 0, tzinfo=KST)
    return _snapshot_iso(parsed)


def _snapshot_iso(snapshot_time: datetime) -> str:
    return snapshot_time.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_int(value: Any) -> int | None:
    parsed = as_float(value)
    return int(parsed) if parsed is not None else None
