from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from ..models import ProviderFetchBatch, RawDocumentCandidate
from ..normalize import canonicalize_url, news_dedup_key, strip_html, title_hash

logger = logging.getLogger(__name__)

_SAFE_RAW_KEYS = (
    "id",
    "news_id",
    "doc_id",
    "_id",
    "newsid",
    "title",
    "headline",
    "news_title",
    "url",
    "link",
    "originallink",
    "news_url",
    "publisher",
    "provider",
    "source",
    "press",
    "summary",
    "snippet",
    "description",
    "lead",
    "published_at",
    "published",
    "publish_date",
    "date",
    "reg_dt",
)


def _pick(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    lowered = {str(key).lower(): value for key, value in payload.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value is None:
            continue
        as_text = str(value).strip()
        if as_text:
            return as_text
    return None


class BigKindsNewsProvider:
    def __init__(
        self,
        *,
        enabled: bool,
        api_key: str | None,
        base_url: str,
        search_path: str,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        page_size: int = 100,
        page_limit: int = 5,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.enabled = enabled
        self.api_key = (api_key or "").strip()
        self.base_url = base_url.rstrip("/")
        self.search_path = search_path
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.page_size = page_size
        self.page_limit = page_limit
        self._http_client = http_client

    def is_enabled(self) -> tuple[bool, str | None]:
        if not self.enabled:
            return False, "feature_flag_disabled"
        if not self.api_key:
            return False, "missing_bigkinds_api_key"
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
                "bigkinds_provider_disabled",
                extra={"reason": reason, "query": query},
            )
            return ProviderFetchBatch(records=[], next_cursor=cursor, disabled_reason=reason)

        records: list[RawDocumentCandidate] = []
        next_cursor = cursor

        for page_no in range(1, self.page_limit + 1):
            payload = self._request_page(
                query=query,
                window_start=window_start,
                window_end=window_end,
                page_no=page_no,
            )
            rows = self._extract_rows(payload)
            if not rows:
                break

            for row in rows:
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

            if len(rows) < self.page_size:
                break

        logger.info(
            "bigkinds_fetch_success",
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

    def _request_page(
        self,
        *,
        query: str,
        window_start: datetime,
        window_end: datetime,
        page_no: int,
    ) -> dict[str, Any]:
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "bigkinds_fetch_attempt",
                    extra={"query": query, "page_no": page_no, "attempt": attempt},
                )
                response = self._do_request(
                    query=query,
                    window_start=window_start,
                    window_end=window_end,
                    page_no=page_no,
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("BigKinds response is not a JSON object")
                return payload
            except (httpx.HTTPError, json.JSONDecodeError, ValueError) as error:
                last_error = error
                logger.warning(
                    "bigkinds_fetch_retry",
                    extra={"query": query, "page_no": page_no, "attempt": attempt, "error": str(error)},
                )
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * (2 ** (attempt - 1)))

        raise RuntimeError("Failed to fetch BigKinds news after retries") from last_error

    def _do_request(
        self,
        *,
        query: str,
        window_start: datetime,
        window_end: datetime,
        page_no: int,
    ) -> httpx.Response:
        url = f"{self.base_url}{self.search_path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "query": query,
            "from": window_start.date().isoformat(),
            "to": window_end.date().isoformat(),
            "page": page_no,
            "size": self.page_size,
        }

        if self._http_client is not None:
            return self._http_client.post(url, headers=headers, json=payload, timeout=self.timeout_seconds)
        with httpx.Client() as client:
            return client.post(url, headers=headers, json=payload, timeout=self.timeout_seconds)

    def _extract_rows(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows = self._find_document_list(payload)
        if rows is None:
            raise ValueError("BigKinds payload did not include a document array")
        return [item for item in rows if isinstance(item, dict)]

    def _find_document_list(self, node: Any) -> list[Any] | None:
        if isinstance(node, list):
            if node and all(isinstance(item, dict) for item in node):
                return node
            for item in node:
                resolved = self._find_document_list(item)
                if resolved is not None:
                    return resolved
            return None

        if not isinstance(node, dict):
            return None

        prioritized_keys = (
            "documents",
            "document_list",
            "items",
            "news",
            "data",
            "result",
            "return_object",
        )
        for key in prioritized_keys:
            if key not in node:
                continue
            resolved = self._find_document_list(node[key])
            if resolved is not None:
                return resolved

        for value in node.values():
            if not isinstance(value, (dict, list)):
                continue
            resolved = self._find_document_list(value)
            if resolved is not None:
                return resolved

        return None

    def _to_candidate(self, *, row: dict[str, Any], query: str) -> RawDocumentCandidate | None:
        title_raw = _pick(row, ("title", "headline", "news_title"))
        source_url_raw = _pick(row, ("url", "link", "originallink", "news_url"))
        source_id = _pick(row, ("id", "news_id", "doc_id", "_id", "newsid"))
        publisher = _pick(row, ("publisher", "provider", "source", "press"))
        summary_raw = _pick(row, ("summary", "snippet", "description", "lead"))
        published_raw = _pick(row, ("published_at", "published", "publish_date", "date", "reg_dt"))

        title = strip_html(title_raw)
        summary = strip_html(summary_raw)
        canonical_url = canonicalize_url(source_url_raw)
        normalized_title_hash = title_hash(title)
        dedup_key = news_dedup_key(
            canonical_url=canonical_url,
            normalized_title_hash=normalized_title_hash,
        )
        if publisher is None and source_url_raw:
            publisher = urlparse(source_url_raw).netloc or None

        published_at = self._parse_datetime(published_raw)

        if not title and not canonical_url:
            logger.warning(
                "bigkinds_row_skipped",
                extra={"reason": "missing_title_and_url", "row": row},
            )
            return None

        return RawDocumentCandidate(
            provider="BIGKINDS",
            provider_document_id=source_id,
            document_type="NEWS_CANDIDATE",
            title=title,
            summary=summary,
            publisher=publisher,
            source_url=source_url_raw,
            canonical_url=canonical_url,
            published_at=published_at,
            receipt_at=None,
            report_type=None,
            company_ref=None,
            company_id=None,
            query_text=query,
            dedup_type="NEWS_URL_TITLE" if dedup_key else None,
            dedup_key=dedup_key,
            provider_metadata={
                "query": query,
                "published_raw": published_raw,
                "provider_document_id": source_id,
            },
            raw_payload=self._safe_payload_snapshot(row),
        )

    def _parse_datetime(self, raw_value: str | None) -> str | None:
        if raw_value is None:
            return None

        candidate = raw_value.strip()
        if not candidate:
            return None

        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        except ValueError:
            pass

        if candidate.isdigit():
            timestamp = int(candidate)
            if timestamp > 10_000_000_000:
                timestamp = int(timestamp / 1000)
            parsed = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            return parsed.replace(microsecond=0).isoformat().replace("+00:00", "Z")

        for pattern in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y%m%d%H%M%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(candidate, pattern).replace(tzinfo=timezone.utc)
                return parsed.isoformat().replace("+00:00", "Z")
            except ValueError:
                continue

        logger.warning("bigkinds_datetime_parse_failed", extra={"raw_value": raw_value})
        return None

    def _safe_payload_snapshot(self, row: dict[str, Any]) -> dict[str, Any]:
        snapshot: dict[str, Any] = {}
        lowered = {str(key).lower(): key for key in row.keys()}
        for safe_key in _SAFE_RAW_KEYS:
            raw_key = lowered.get(safe_key.lower())
            if raw_key is None:
                continue
            snapshot[safe_key] = row.get(raw_key)
        return snapshot

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
