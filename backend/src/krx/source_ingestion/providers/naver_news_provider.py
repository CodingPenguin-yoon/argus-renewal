from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import logging
import re
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from ...publisher_registry import normalize_publisher_key
from ..models import ProviderFetchBatch, RawDocumentCandidate
from ..normalize import canonicalize_url, news_dedup_key, strip_html, title_hash

logger = logging.getLogger(__name__)

_WHITESPACE_RE = re.compile(r"\s+")
_HOST_PUBLISHER_MAP = {
    "yna.co.kr": "연합뉴스",
    "newsis.com": "뉴시스",
    "hankyung.com": "한국경제",
    "mk.co.kr": "매일경제",
    "sedaily.com": "서울경제",
    "mt.co.kr": "머니투데이",
    "etnews.com": "전자신문",
    "chosun.com": "조선일보",
    "joongang.co.kr": "중앙일보",
    "donga.com": "동아일보",
    "khan.co.kr": "경향신문",
    "hani.co.kr": "한겨레",
    "sbs.co.kr": "SBS",
    "kbs.co.kr": "KBS",
    "mbc.co.kr": "MBC",
    "ytn.co.kr": "YTN",
}
_SAFE_RAW_KEYS = (
    "title",
    "originallink",
    "link",
    "description",
    "pubDate",
    "publisher",
)


class NaverNewsProvider:
    def __init__(
        self,
        *,
        enabled: bool,
        client_id: str | None,
        client_secret: str | None,
        base_url: str,
        search_path: str,
        company_query_template: str,
        theme_query_template: str,
        display: int = 50,
        page_limit: int = 5,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.enabled = enabled
        self.client_id = (client_id or "").strip()
        self.client_secret = (client_secret or "").strip()
        self.base_url = base_url.rstrip("/")
        self.search_path = search_path
        self.company_query_template = company_query_template
        self.theme_query_template = theme_query_template
        self.display = display
        self.page_limit = page_limit
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._http_client = http_client

    def is_enabled(self) -> tuple[bool, str | None]:
        if not self.enabled:
            return False, "feature_flag_disabled"
        if not self.client_id or not self.client_secret:
            return False, "missing_naver_credentials"
        return True, None

    def build_company_query(self, *, company_name: str) -> str:
        return self.company_query_template.format(company_name=company_name)

    def build_theme_query(self, *, keyword: str) -> str:
        return self.theme_query_template.format(keyword=keyword)

    def fetch_news(
        self,
        *,
        query: str,
        window_start: datetime,
        window_end: datetime,
        cursor: str | None,
    ) -> ProviderFetchBatch:
        enabled, reason = self.is_enabled()
        if not enabled:
            logger.info(
                "naver_news_provider_disabled",
                extra={"reason": reason, "query": query},
            )
            return ProviderFetchBatch(records=[], next_cursor=cursor, disabled_reason=reason)

        records: list[RawDocumentCandidate] = []
        next_cursor = cursor

        for page_index in range(self.page_limit):
            start = 1 + (page_index * self.display)
            payload = self._request_page(query=query, start=start)
            rows = payload.get("items")
            if not isinstance(rows, list):
                raise ValueError("Naver news payload does not include items")

            if not rows:
                break

            for row in rows:
                if not isinstance(row, dict):
                    continue

                candidate = self._to_candidate(row=row, query=query)
                if candidate is None:
                    continue

                if candidate.published_at and not self._is_in_window(
                    value=candidate.published_at,
                    window_start=window_start,
                    window_end=window_end,
                ):
                    continue

                if cursor and candidate.published_at and candidate.published_at <= cursor:
                    continue

                records.append(candidate)
                if candidate.published_at and (next_cursor is None or candidate.published_at > next_cursor):
                    next_cursor = candidate.published_at

            if len(rows) < self.display:
                break

        logger.info(
            "naver_news_fetch_success",
            extra={"query": query, "record_count": len(records), "next_cursor": next_cursor},
        )
        return ProviderFetchBatch(
            records=records,
            next_cursor=next_cursor,
            metadata={
                "query": query,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
            },
        )

    def _request_page(self, *, query: str, start: int) -> dict[str, Any]:
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "naver_news_fetch_attempt",
                    extra={"query": query, "start": start, "attempt": attempt},
                )
                response = self._do_request(query=query, start=start)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("Naver news response is not a JSON object")
                return payload
            except (httpx.HTTPError, json.JSONDecodeError, ValueError) as error:
                last_error = error
                logger.warning(
                    "naver_news_fetch_retry",
                    extra={"query": query, "start": start, "attempt": attempt, "error": str(error)},
                )
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * (2 ** (attempt - 1)))

        raise RuntimeError("Failed to fetch Naver news after retries") from last_error

    def _do_request(self, *, query: str, start: int) -> httpx.Response:
        url = f"{self.base_url}{self.search_path}"
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }
        params = {
            "query": query,
            "display": self.display,
            "start": start,
            "sort": "date",
        }

        if self._http_client is not None:
            return self._http_client.get(url, params=params, headers=headers, timeout=self.timeout_seconds)
        with httpx.Client() as client:
            return client.get(url, params=params, headers=headers, timeout=self.timeout_seconds)

    def _to_candidate(self, *, row: dict[str, Any], query: str) -> RawDocumentCandidate | None:
        title = strip_html(self._as_text(row.get("title")))
        summary = strip_html(self._as_text(row.get("description")))
        original_link = self._as_text(row.get("originallink"))
        link = self._as_text(row.get("link"))
        source_url = original_link or link
        canonical_url = canonicalize_url(source_url)

        normalized_title_hash = title_hash(title)
        dedup_key = news_dedup_key(
            canonical_url=canonical_url,
            normalized_title_hash=normalized_title_hash,
        )

        published_at = self._parse_pub_date(self._as_text(row.get("pubDate")))
        publisher = self._extract_publisher(row=row, source_url=source_url)

        if not title and not canonical_url:
            logger.warning(
                "naver_news_row_skipped",
                extra={"reason": "missing_title_and_url", "row": row},
            )
            return None

        return RawDocumentCandidate(
            provider="NAVER_NEWS",
            provider_document_id=None,
            document_type="NEWS_CANDIDATE",
            title=title,
            summary=summary,
            publisher=publisher,
            source_url=source_url,
            canonical_url=canonical_url,
            published_at=published_at,
            receipt_at=None,
            report_type=None,
            company_ref=None,
            company_id=None,
            query_text=query,
            dedup_type="NEWS_URL_TITLE" if dedup_key else None,
            dedup_key=dedup_key,
            publisher_key=normalize_publisher_key(publisher),
            provider_metadata={
                "query": query,
                "originallink": original_link,
                "link": link,
                "pub_date_raw": row.get("pubDate"),
            },
            raw_payload=self._safe_payload_snapshot(row),
        )

    def _parse_pub_date(self, raw_value: str | None) -> str | None:
        if raw_value is None:
            return None

        candidate = raw_value.strip()
        if not candidate:
            return None

        try:
            parsed = parsedate_to_datetime(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        except (TypeError, ValueError):
            logger.warning("naver_news_datetime_parse_failed", extra={"raw_value": raw_value})
            return None

    def _extract_publisher(self, *, row: dict[str, Any], source_url: str | None) -> str | None:
        publisher = self._normalize_publisher(self._as_text(row.get("publisher")))
        if publisher:
            return publisher
        if not source_url:
            return None

        host = urlparse(source_url).netloc.lower()
        normalized_host = host[4:] if host.startswith("www.") else host

        for suffix, mapped_publisher in _HOST_PUBLISHER_MAP.items():
            if normalized_host == suffix or normalized_host.endswith(f".{suffix}"):
                return mapped_publisher

        return normalized_host or None

    def _is_in_window(self, *, value: str, window_start: datetime, window_end: datetime) -> bool:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        lower = window_start.astimezone(timezone.utc)
        upper = window_end.astimezone(timezone.utc)
        return lower <= parsed.astimezone(timezone.utc) <= upper

    def _as_text(self, value: Any) -> str | None:
        if value is None:
            return None
        candidate = str(value).strip()
        return candidate or None

    def _normalize_publisher(self, value: str | None) -> str | None:
        if value is None:
            return None
        compact = _WHITESPACE_RE.sub(" ", value).strip()
        if not compact:
            return None
        return compact

    def _safe_payload_snapshot(self, row: dict[str, Any]) -> dict[str, Any]:
        snapshot: dict[str, Any] = {}
        lowered = {str(key).lower(): key for key in row.keys()}
        for safe_key in _SAFE_RAW_KEYS:
            raw_key = lowered.get(safe_key.lower())
            if raw_key is None:
                continue
            snapshot[safe_key] = row.get(raw_key)
        return snapshot
