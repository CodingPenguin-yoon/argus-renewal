from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import logging
import re
import time
from typing import Any
import xml.etree.ElementTree as ET

import httpx

from ...publisher_registry import normalize_publisher_display_name, normalize_publisher_key
from ..models import ProviderFetchBatch, RawDocumentCandidate
from ..normalize import canonicalize_url, news_dedup_key, strip_html, title_hash

logger = logging.getLogger(__name__)

_MEDIA_NAMESPACE = {"media": "http://search.yahoo.com/mrss/"}
_QUERY_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]{2,}")
_IGNORED_QUERY_TOKENS = {"or", "and", "증시", "뉴스"}


class MkRssNewsProvider:
    def __init__(
        self,
        *,
        enabled: bool,
        feed_urls: list[str] | tuple[str, ...],
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.enabled = enabled
        self.feed_urls = tuple(url.strip() for url in feed_urls if str(url).strip())
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._http_client = http_client

    def is_enabled(self) -> tuple[bool, str | None]:
        if not self.enabled:
            return False, "feature_flag_disabled"
        if not self.feed_urls:
            return False, "missing_feed_urls"
        return True, None

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
                "mk_rss_provider_disabled",
                extra={"reason": reason, "query": query},
            )
            return ProviderFetchBatch(records=[], next_cursor=cursor, disabled_reason=reason)

        records: list[RawDocumentCandidate] = []
        next_cursor = cursor

        for feed_url in self.feed_urls:
            feed_title, rows = self._request_feed(feed_url=feed_url)
            for row in rows:
                candidate = self._to_candidate(
                    row=row,
                    feed_url=feed_url,
                    feed_title=feed_title,
                    query=query,
                )
                if candidate is None:
                    continue

                if query and not self._matches_query(candidate=candidate, query=query):
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

        records.sort(
            key=lambda item: self._sort_key(item.published_at),
            reverse=True,
        )

        logger.info(
            "mk_rss_fetch_success",
            extra={
                "query": query,
                "record_count": len(records),
                "next_cursor": next_cursor,
                "feed_count": len(self.feed_urls),
            },
        )
        return ProviderFetchBatch(
            records=records,
            next_cursor=next_cursor,
            metadata={
                "query": query,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "feed_urls": list(self.feed_urls),
            },
        )

    def _request_feed(self, *, feed_url: str) -> tuple[str | None, list[ET.Element]]:
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "mk_rss_fetch_attempt",
                    extra={"feed_url": feed_url, "attempt": attempt},
                )
                response = self._do_request(feed_url=feed_url)
                response.raise_for_status()
                return self._parse_feed(xml_text=response.text)
            except (httpx.HTTPError, ET.ParseError, ValueError) as error:
                last_error = error
                logger.warning(
                    "mk_rss_fetch_retry",
                    extra={"feed_url": feed_url, "attempt": attempt, "error": str(error)},
                )
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * (2 ** (attempt - 1)))

        raise RuntimeError(f"Failed to fetch MK RSS feed after retries: {feed_url}") from last_error

    def _do_request(self, *, feed_url: str) -> httpx.Response:
        headers = {"User-Agent": "ArgusRenewal/0.1 (+https://github.com/CodingPenguin-yoon/argus-renewal)"}
        if self._http_client is not None:
            return self._http_client.get(feed_url, headers=headers, timeout=self.timeout_seconds)
        with httpx.Client() as client:
            return client.get(feed_url, headers=headers, timeout=self.timeout_seconds)

    def _parse_feed(self, *, xml_text: str) -> tuple[str | None, list[ET.Element]]:
        root = ET.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            raise ValueError("MK RSS payload does not contain channel")
        return channel.findtext("title"), list(channel.findall("item"))

    def _to_candidate(
        self,
        *,
        row: ET.Element,
        feed_url: str,
        feed_title: str | None,
        query: str,
    ) -> RawDocumentCandidate | None:
        title = strip_html(row.findtext("title"))
        summary = strip_html(row.findtext("description"))
        source_url = strip_html(row.findtext("link"))
        canonical_url = canonicalize_url(source_url)
        provider_document_id = strip_html(row.findtext("no"))
        category = strip_html(row.findtext("category"))
        publisher = normalize_publisher_display_name(strip_html(row.findtext("author")) or "매일경제")
        publisher_key = normalize_publisher_key(publisher)
        published_at_raw = strip_html(row.findtext("pubDate"))
        published_at = self._parse_pub_date(published_at_raw)
        image_url = self._extract_image_url(row)

        normalized_title_hash = title_hash(title)
        dedup_key = news_dedup_key(
            canonical_url=canonical_url,
            normalized_title_hash=normalized_title_hash,
        )

        if not title and not canonical_url:
            logger.warning(
                "mk_rss_row_skipped",
                extra={"reason": "missing_title_and_url", "feed_url": feed_url},
            )
            return None

        raw_payload = {
            "no": provider_document_id,
            "title": title,
            "link": source_url,
            "category": category,
            "author": publisher,
            "pubDate": published_at_raw,
            "description": summary,
        }
        if image_url:
            raw_payload["image_url"] = image_url

        return RawDocumentCandidate(
            provider="MK_RSS",
            provider_document_id=provider_document_id,
            document_type="NEWS_CANDIDATE",
            title=title,
            summary=summary,
            publisher=publisher,
            publisher_key=publisher_key,
            source_url=source_url,
            canonical_url=canonical_url,
            published_at=published_at,
            receipt_at=None,
            report_type=category,
            company_ref=None,
            company_id=None,
            query_text=query,
            dedup_type="NEWS_URL_TITLE",
            dedup_key=dedup_key,
            provider_metadata={
                "query": query,
                "feed_url": feed_url,
                "feed_title": strip_html(feed_title),
                "category": category,
                "pub_date_raw": published_at_raw,
                "image_url": image_url,
            },
            raw_payload=raw_payload,
        )

    def _extract_image_url(self, row: ET.Element) -> str | None:
        media = row.find("media:content", _MEDIA_NAMESPACE)
        if media is None:
            return None
        value = media.attrib.get("url")
        return str(value).strip() or None if value is not None else None

    def _matches_query(self, *, candidate: RawDocumentCandidate, query: str) -> bool:
        tokens = [
            token.casefold()
            for token in _QUERY_TOKEN_RE.findall(query)
            if token.casefold() not in _IGNORED_QUERY_TOKENS
        ]
        if not tokens:
            return True

        haystack = " ".join(
            value
            for value in (
                candidate.title,
                candidate.summary,
                candidate.report_type,
                candidate.publisher,
            )
            if value
        ).casefold()
        return all(token in haystack for token in tokens)

    def _parse_pub_date(self, raw_value: str | None) -> str | None:
        if not raw_value:
            return None

        try:
            parsed = parsedate_to_datetime(raw_value)
        except (TypeError, ValueError):
            logger.warning("mk_rss_datetime_parse_failed", extra={"raw_value": raw_value})
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def _is_in_window(self, *, value: str, window_start: datetime, window_end: datetime) -> bool:
        try:
            published_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return True
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        return window_start <= published_at <= window_end

    def _sort_key(self, value: str | None) -> float:
        if not value:
            return 0.0
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0
