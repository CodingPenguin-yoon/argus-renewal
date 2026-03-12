from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import re
import time
from typing import Any

import httpx

from ..models import ProviderFetchBatch, RawDocumentCandidate
from ..normalize import dart_dedup_key

logger = logging.getLogger(__name__)

_LEADING_DART_MODIFIER_RE = re.compile(r"^\[[^\]]+\]")

DART_DEFAULT_INCLUDE_PATTERNS = (
    "사업보고서",
    "반기보고서",
    "분기보고서",
    "매출액또는손익구조",
    "영업(잠정)실적",
    "주요사항보고서",
    "최대주주변경",
    "최대주주등소유주식변동신고서",
    "주식등의대량보유상황보고서",
    "유상증자결정",
    "무상증자결정",
    "전환사채권발행결정",
    "신주인수권부사채권발행결정",
    "교환사채권발행결정",
    "감자결정",
    "주식병합결정",
    "주식분할결정",
    "자기주식취득결정",
    "자기주식처분결정",
    "타법인주식및출자증권취득결정",
    "타법인주식및출자증권처분결정",
    "유형자산취득결정",
    "유형자산처분결정",
    "단일판매ㆍ공급계약체결",
    "단일판매ㆍ공급계약해지",
    "현금ㆍ현물배당결정",
    "소송등의제기",
    "소송등의판결ㆍ결정",
    "회생절차개시신청",
    "회생절차개시결정",
    "부도발생",
    "영업정지",
    "해산사유발생",
    "횡령ㆍ배임",
)

DART_DEFAULT_EXCLUDE_PATTERNS = (
    "주주총회소집공고",
    "주주총회소집결의",
    "주주총회집중일개최사유신고",
    "의결권대리행사권유참고서류",
    "감사보고서제출",
    "감사보고서",
    "효력발생안내",
    "일괄신고추가서류",
    "증권발행실적보고서",
    "현금ㆍ현물배당을위한주주명부폐쇄",
)


class DartDisclosureProvider:
    def __init__(
        self,
        *,
        api_key: str | None,
        list_url: str,
        material_only: bool = True,
        include_patterns: tuple[str, ...] | list[str] | None = None,
        exclude_patterns: tuple[str, ...] | list[str] | None = None,
        page_count: int = 100,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.list_url = list_url
        self.material_only = material_only
        self.include_patterns = tuple(
            pattern.strip()
            for pattern in (include_patterns or DART_DEFAULT_INCLUDE_PATTERNS)
            if str(pattern).strip()
        )
        self.exclude_patterns = tuple(
            pattern.strip()
            for pattern in (exclude_patterns or DART_DEFAULT_EXCLUDE_PATTERNS)
            if str(pattern).strip()
        )
        self.page_count = page_count
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._http_client = http_client

    def is_enabled(self) -> tuple[bool, str | None]:
        if not self.api_key:
            return False, "missing_dart_api_key"
        return True, None

    def fetch_disclosures(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
        cursor: str | None,
    ) -> ProviderFetchBatch:
        enabled, reason = self.is_enabled()
        if not enabled:
            logger.info(
                "dart_disclosure_provider_disabled",
                extra={"reason": reason},
            )
            return ProviderFetchBatch(records=[], next_cursor=cursor, disabled_reason=reason)

        start_day = window_start.astimezone(timezone.utc).strftime("%Y%m%d")
        end_day = window_end.astimezone(timezone.utc).strftime("%Y%m%d")

        page_no = 1
        total_page = 1
        raw_rows: list[dict[str, Any]] = []

        while page_no <= total_page:
            payload = self._request_page(start_day=start_day, end_day=end_day, page_no=page_no)
            status = str(payload.get("status") or "")
            message = str(payload.get("message") or "")

            if status == "013":
                logger.info(
                    "dart_disclosure_no_data",
                    extra={"start_day": start_day, "end_day": end_day, "page_no": page_no},
                )
                break

            if status != "000":
                raise ValueError(f"DART disclosure API failed: status={status}, message={message}")

            page_value = payload.get("total_page")
            try:
                total_page = int(page_value) if page_value is not None else 1
            except (TypeError, ValueError):
                total_page = 1

            rows = payload.get("list") or []
            if not isinstance(rows, list):
                raise ValueError("DART disclosure payload does not include list array")

            for row in rows:
                if isinstance(row, dict):
                    raw_rows.append(row)

            page_no += 1

        ordered_rows = sorted(raw_rows, key=self._cursor_tuple)
        records: list[RawDocumentCandidate] = []
        next_cursor = cursor
        filtered_count = 0

        for row in ordered_rows:
            row_cursor = self._make_cursor(row)
            if cursor and row_cursor and row_cursor <= cursor:
                continue

            if row_cursor and (next_cursor is None or row_cursor > next_cursor):
                next_cursor = row_cursor

            if self.material_only and not self._is_material_report(row):
                filtered_count += 1
                continue

            candidate = self._to_candidate(row)
            if candidate is None:
                continue

            records.append(candidate)

        logger.info(
            "dart_disclosure_fetch_success",
            extra={
                "start_day": start_day,
                "end_day": end_day,
                "record_count": len(records),
                "filtered_count": filtered_count,
                "next_cursor": next_cursor,
            },
        )
        return ProviderFetchBatch(
            records=records,
            next_cursor=next_cursor,
            metadata={
                "start_day": start_day,
                "end_day": end_day,
                "total_pages": total_page,
                "material_only": self.material_only,
                "filtered_count": filtered_count,
            },
        )

    def _request_page(self, *, start_day: str, end_day: str, page_no: int) -> dict[str, Any]:
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "dart_disclosure_fetch_attempt",
                    extra={
                        "attempt": attempt,
                        "page_no": page_no,
                        "start_day": start_day,
                        "end_day": end_day,
                    },
                )
                response = self._do_request(start_day=start_day, end_day=end_day, page_no=page_no)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("DART disclosure response is not a JSON object")
                return payload
            except (httpx.HTTPError, json.JSONDecodeError, ValueError) as error:
                last_error = error
                logger.warning(
                    "dart_disclosure_fetch_retry",
                    extra={
                        "attempt": attempt,
                        "page_no": page_no,
                        "error": str(error),
                    },
                )
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * (2 ** (attempt - 1)))

        raise RuntimeError("Failed to fetch DART disclosures after retries") from last_error

    def _do_request(self, *, start_day: str, end_day: str, page_no: int) -> httpx.Response:
        params = {
            "crtfc_key": self.api_key,
            "bgn_de": start_day,
            "end_de": end_day,
            "page_no": page_no,
            "page_count": self.page_count,
        }
        if self._http_client is not None:
            return self._http_client.get(self.list_url, params=params, timeout=self.timeout_seconds)
        with httpx.Client() as client:
            return client.get(self.list_url, params=params, timeout=self.timeout_seconds)

    def _to_candidate(self, row: dict[str, Any]) -> RawDocumentCandidate | None:
        provider_document_id = str(row.get("rcept_no") or "").strip() or None
        title = str(row.get("report_nm") or "").strip() or None
        corp_code = str(row.get("corp_code") or "").strip() or None
        corp_name = str(row.get("corp_name") or "").strip() or None
        receipt_day = str(row.get("rcept_dt") or "").strip() or None

        if provider_document_id is None:
            logger.warning("dart_disclosure_missing_receipt_no", extra={"row": row})
            return None

        source_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={provider_document_id}"

        receipt_at: str | None = None
        if receipt_day and len(receipt_day) == 8 and receipt_day.isdigit():
            parsed_day = datetime.strptime(receipt_day, "%Y%m%d").replace(tzinfo=timezone.utc)
            receipt_at = parsed_day.isoformat().replace("+00:00", "Z")

        dedup_key = dart_dedup_key(provider_document_id)
        company_ref = corp_code or corp_name

        return RawDocumentCandidate(
            provider="DART",
            provider_document_id=provider_document_id,
            document_type="DISCLOSURE",
            title=title,
            summary=None,
            publisher="DART",
            source_url=source_url,
            canonical_url=source_url,
            published_at=receipt_at,
            receipt_at=receipt_at,
            report_type=title,
            company_ref=company_ref,
            company_id=None,
            query_text=None,
            dedup_type="PROVIDER_ID" if dedup_key else None,
            dedup_key=dedup_key,
            publisher_key="DART",
            provider_metadata={
                "corp_code": corp_code,
                "corp_name": corp_name,
                "corp_cls": row.get("corp_cls"),
                "flr_nm": row.get("flr_nm"),
                "rm": row.get("rm"),
                "rcept_dt": receipt_day,
            },
            raw_payload=row,
        )

    def _cursor_tuple(self, row: dict[str, Any]) -> tuple[str, str]:
        receipt_day = str(row.get("rcept_dt") or "")
        receipt_no = str(row.get("rcept_no") or "")
        return receipt_day, receipt_no

    def _make_cursor(self, row: dict[str, Any]) -> str | None:
        receipt_day = str(row.get("rcept_dt") or "").strip()
        receipt_no = str(row.get("rcept_no") or "").strip()
        if not receipt_day or not receipt_no:
            return None
        return f"{receipt_day}:{receipt_no}"

    def _is_material_report(self, row: dict[str, Any]) -> bool:
        normalized_title = self._normalize_report_title(str(row.get("report_nm") or ""))
        if not normalized_title:
            return False

        if any(pattern in normalized_title for pattern in self.exclude_patterns):
            return False

        return any(pattern in normalized_title for pattern in self.include_patterns)

    def _normalize_report_title(self, report_name: str) -> str:
        normalized = str(report_name or "").strip()
        while True:
            updated = _LEADING_DART_MODIFIER_RE.sub("", normalized, count=1).strip()
            if updated == normalized:
                break
            normalized = updated
        return normalized
