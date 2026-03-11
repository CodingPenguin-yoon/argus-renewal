from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, timedelta
from html import unescape
from html.parser import HTMLParser
import json
import logging
from pathlib import Path
import re
import time as time_module
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from .models import (
    GlobalEventCoverageSnapshot,
    GlobalEventReleaseCandidate,
    GlobalEventScheduleCandidate,
    GlobalEventVendorBatch,
)

logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")
_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_DEFAULT_IMPORTANCE = {
    "FOMC": "high",
    "CPI": "high",
    "PCE": "high",
    "PAYROLLS": "high",
    "ECB": "high",
    "BOJ": "high",
    "EARNINGS": "high",
    "OIL": "medium",
}

_WHY_IT_MATTERS = {
    "FOMC": "연준의 금리 경로와 점도표 변화는 달러, 미 국채금리, 외국인 수급을 통해 한국 성장주와 반도체 변동성을 키울 수 있습니다.",
    "CPI": "미국 물가가 예상보다 높으면 금리 인하 지연 우려가 커져 원화와 외국인 수급, 반도체 밸류에이션에 부담을 줄 수 있습니다.",
    "PCE": "연준이 중시하는 물가 지표여서 금리 경로와 달러 방향성을 다시 가격에 반영시키며 한국 증시 위험선호에 영향을 줄 수 있습니다.",
    "PAYROLLS": "고용이 강하면 금리 인하 기대가 늦춰질 수 있고, 약하면 경기둔화 우려가 부각돼 한국 수출주와 외국인 흐름이 민감하게 반응할 수 있습니다.",
    "ECB": "ECB 톤 변화는 유럽 성장 및 글로벌 달러 흐름에 영향을 주며, 한국 증시의 위험선호와 환율 민감도를 자극할 수 있습니다.",
    "BOJ": "BOJ 정책 변화는 엔화와 글로벌 캐리 트레이드에 충격을 줄 수 있어 원/엔, 외국인 수급, 수출주 변동성에 연결됩니다.",
    "EARNINGS": "대형 기술주 실적과 가이던스는 AI·반도체 투자 심리를 재가격화해 국내 반도체와 장비주의 단기 방향성에 영향을 줄 수 있습니다.",
    "OIL": "유가 관련 이벤트는 원자재 가격과 인플레이션 기대를 통해 한국 항공·정유·화학 업종 마진과 환율 민감도에 영향을 줄 수 있습니다.",
}

_TITLE_LABELS = {
    "FOMC": "FOMC 정례회의",
    "CPI": "미국 CPI",
    "PCE": "미국 PCE 물가",
    "PAYROLLS": "미국 비농업고용",
    "ECB": "ECB 통화정책회의",
    "BOJ": "BOJ 금융정책결정회의",
    "EARNINGS": "대형 기술주 실적",
    "OIL": "원유/원자재 촉매 이벤트",
}

_CATEGORY_MAP = {
    "FOMC": "central_bank",
    "ECB": "central_bank",
    "BOJ": "central_bank",
    "CPI": "inflation",
    "PCE": "inflation",
    "PAYROLLS": "labor",
    "EARNINGS": "earnings",
    "OIL": "commodities",
}


class _LineHTMLParser(HTMLParser):
    _BLOCK_TAGS = {
        "p",
        "div",
        "br",
        "li",
        "ul",
        "ol",
        "tr",
        "table",
        "thead",
        "tbody",
        "td",
        "th",
        "section",
        "article",
        "header",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    }

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        _ = attrs
        if tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        self.parts.append(data)


def _html_to_lines(payload: str) -> list[str]:
    parser = _LineHTMLParser()
    parser.feed(payload)
    raw_text = unescape("".join(parser.parts))
    return [re.sub(r"\s+", " ", line).strip() for line in raw_text.splitlines() if line.strip()]


def _load_text_file(file_path: str) -> str:
    source = Path(file_path)
    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source}")
    return source.read_text(encoding="utf-8-sig")


def _load_json_file(file_path: str) -> Any:
    return json.loads(_load_text_file(file_path))


def _fetch_text_with_retries(
    *,
    url: str,
    timeout_seconds: float,
    max_retries: int,
    backoff_seconds: float,
    http_client: httpx.Client | None,
    log_prefix: str,
) -> tuple[str, int]:
    last_error: Exception | None = None
    for attempt in range(1, max(1, max_retries) + 1):
        try:
            if http_client is not None:
                response = http_client.get(url, timeout=timeout_seconds)
            else:
                with httpx.Client() as client:
                    response = client.get(url, timeout=timeout_seconds)
            response.raise_for_status()
            return response.text, attempt - 1
        except (httpx.HTTPError, UnicodeDecodeError) as error:
            last_error = error
            logger.warning(
                f"{log_prefix}_retry",
                extra={"attempt": attempt, "url": url, "error": str(error)},
            )
            if attempt < max(1, max_retries):
                time_module.sleep(backoff_seconds * (2 ** (attempt - 1)))
    raise RuntimeError(f"{log_prefix}_failed_after_retries") from last_error


def _fetch_json_with_retries(
    *,
    url: str,
    params: dict[str, Any] | None,
    timeout_seconds: float,
    max_retries: int,
    backoff_seconds: float,
    http_client: httpx.Client | None,
    headers: dict[str, str] | None = None,
    log_prefix: str,
) -> tuple[Any, int]:
    last_error: Exception | None = None
    for attempt in range(1, max(1, max_retries) + 1):
        try:
            if http_client is not None:
                response = http_client.get(url, params=params, headers=headers, timeout=timeout_seconds)
            else:
                with httpx.Client() as client:
                    response = client.get(url, params=params, headers=headers, timeout=timeout_seconds)
            response.raise_for_status()
            return response.json(), attempt - 1
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as error:
            last_error = error
            logger.warning(
                f"{log_prefix}_retry",
                extra={"attempt": attempt, "url": url, "error": str(error)},
            )
            if attempt < max(1, max_retries):
                time_module.sleep(backoff_seconds * (2 ** (attempt - 1)))
    raise RuntimeError(f"{log_prefix}_failed_after_retries") from last_error


def _parse_month_name(text: str) -> int | None:
    return _MONTHS.get(text.strip().lower().rstrip("."))


def _parse_month_year(text: str) -> tuple[int, int] | None:
    match = re.search(r"\b([A-Za-z]{3,9})\.?\s+(\d{4})\b", text)
    if not match:
        return None
    month = _parse_month_name(match.group(1))
    if month is None:
        return None
    return int(match.group(2)), month


def _parse_date_value(text: str, *, default_year: int | None = None) -> date | None:
    cleaned = text.replace(",", " ").replace("  ", " ").strip()
    named_match = re.search(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:\s+(\d{4}))?\b", cleaned)
    if named_match:
        month = _parse_month_name(named_match.group(1))
        if month is None:
            return None
        year = int(named_match.group(3)) if named_match.group(3) else default_year
        if year is None:
            return None
        return date(year, month, int(named_match.group(2)))

    euro_match = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})\b", cleaned)
    if not euro_match:
        return None
    month = _parse_month_name(euro_match.group(2))
    if month is None:
        return None
    return date(int(euro_match.group(3)), month, int(euro_match.group(1)))


def _parse_time_value(text: str) -> tuple[int, int] | None:
    match = re.search(r"\b(\d{1,2}):(\d{2})\s*([AaPp])\.?\s*[Mm]\.?\b", text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    suffix = match.group(3).lower()
    if suffix == "p" and hour != 12:
        hour += 12
    if suffix == "a" and hour == 12:
        hour = 0
    return hour, minute


def _to_period(value: date) -> str:
    return value.strftime("%Y-%m")


def _previous_month(period: str) -> str:
    year, month = [int(part) for part in period.split("-")]
    anchor = date(year, month, 1)
    previous = anchor - timedelta(days=1)
    return previous.strftime("%Y-%m")


def _two_months_back(period: str) -> str:
    return _previous_month(_previous_month(period))


def _local_to_utc_iso(value: datetime) -> str:
    return value.astimezone(ZoneInfo("UTC")).replace(microsecond=0).isoformat()


def _local_to_kst_iso(value: datetime) -> str:
    return value.astimezone(_KST).replace(microsecond=0).isoformat()


def _sort_at_kst(event_date_local: date, event_datetime_local: datetime | None) -> str:
    if event_datetime_local is not None:
        return _local_to_kst_iso(event_datetime_local)
    fallback = datetime(event_date_local.year, event_date_local.month, event_date_local.day, 0, 0, tzinfo=_KST)
    return fallback.replace(microsecond=0).isoformat()


def _default_why_it_matters(event_type: str, title: str | None = None) -> str:
    value = _WHY_IT_MATTERS.get(event_type)
    if value:
        return value
    return f"{title or '해외 이벤트'} 결과는 달러·금리·위험선호를 통해 한국 증시 변동성에 영향을 줄 수 있습니다."


def _default_title(event_type: str, title: str | None = None) -> str:
    if title:
        return title
    return _TITLE_LABELS.get(event_type, event_type)


def _default_importance(event_type: str) -> str:
    return _DEFAULT_IMPORTANCE.get(event_type, "medium")


def _coverage_status(available_count: int, expected_count: int) -> tuple[str, float]:
    if expected_count <= 0:
        return "available", 1.0
    ratio = round(min(max(available_count / expected_count, 0.0), 1.0), 4)
    if ratio >= 0.999:
        return "available", ratio
    if ratio > 0:
        return "partial", ratio
    return "missing", ratio


def _make_coverage(
    *,
    source_key: str,
    source_name: str,
    source_kind: str,
    is_required: bool,
    available_count: int,
    expected_count: int,
    event_types: list[str],
    source_url: str | None,
    note: str | None,
    retries: int,
) -> GlobalEventCoverageSnapshot:
    status, ratio = _coverage_status(available_count, expected_count)
    now = datetime.now(ZoneInfo("UTC")).replace(microsecond=0).isoformat()
    return GlobalEventCoverageSnapshot(
        source_key=source_key,
        source_name=source_name,
        source_kind=source_kind,
        is_required=is_required,
        status=status,
        available_count=available_count,
        expected_count=expected_count,
        coverage_ratio=ratio,
        event_types=event_types,
        last_synced_at=now,
        last_success_at=now if status != "missing" else None,
        source_url=source_url,
        note=note,
        metadata={"retry_count": retries},
    )


def _parse_ics_payload(payload: str, *, default_timezone: str) -> list[dict[str, Any]]:
    unfolded: list[str] = []
    for raw_line in payload.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)

    events: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in unfolded:
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current:
                events.append(current)
            current = None
            continue
        if current is None or ":" not in line:
            continue

        key_part, value = line.split(":", 1)
        segments = key_part.split(";")
        key = segments[0].upper()
        params: dict[str, str] = {}
        for segment in segments[1:]:
            if "=" not in segment:
                continue
            param_key, param_value = segment.split("=", 1)
            params[param_key.upper()] = param_value

        if key in {"DTSTART", "DTEND"}:
            current[key.lower()] = _parse_ics_datetime(value.strip(), params.get("TZID") or default_timezone)
        else:
            current[key.lower()] = value.strip()
    return events


def _parse_ics_datetime(value: str, tzid: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        parsed = datetime.strptime(text, "%Y%m%dT%H%M%SZ")
        return parsed.replace(tzinfo=ZoneInfo("UTC"))
    if "T" in text:
        parsed = datetime.strptime(text, "%Y%m%dT%H%M%S" if len(text) == 15 else "%Y%m%dT%H%M")
        return parsed.replace(tzinfo=ZoneInfo(tzid))
    parsed_date = datetime.strptime(text, "%Y%m%d").date()
    return datetime(parsed_date.year, parsed_date.month, parsed_date.day, 0, 0, tzinfo=ZoneInfo(tzid))


def _bls_period_from_summary(summary: str, event_date: date) -> str:
    parsed = _parse_month_year(summary)
    if parsed is not None:
        year, month = parsed
        return f"{year:04d}-{month:02d}"
    return _previous_month(_to_period(event_date))


def _parse_range_with_year(line: str, current_year: int | None = None) -> tuple[date, date] | None:
    text = line.replace("–", "-").replace("—", "-")

    match = re.search(
        r"\b([A-Za-z]{3,9})\s+(\d{1,2})\s*[-/]\s*(?:(?:([A-Za-z]{3,9})\s+)?(\d{1,2}))\b",
        text,
    )
    if match and current_year is not None:
        month_one = _parse_month_name(match.group(1))
        month_two = _parse_month_name(match.group(3) or match.group(1))
        if month_one and month_two:
            start = date(current_year, month_one, int(match.group(2)))
            end_year = current_year + 1 if month_two < month_one else current_year
            end = date(end_year, month_two, int(match.group(4)))
            return start, end

    match = re.search(r"\b(\d{1,2})\s*[-/]\s*(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\b", text)
    if match:
        month = _parse_month_name(match.group(3))
        if month:
            start = date(int(match.group(4)), month, int(match.group(1)))
            end = date(int(match.group(4)), month, int(match.group(2)))
            return start, end
    return None


class FedCalendarAdapter:
    source_key = "FED_CALENDAR"
    source_name = "Federal Reserve FOMC Calendar"

    def __init__(
        self,
        *,
        url: str,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        http_client: httpx.Client | None = None,
        file_path: str | None = None,
        is_required: bool = True,
    ) -> None:
        self.source_url = url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._http_client = http_client
        self.file_path = file_path
        self.is_required = is_required

    def fetch(self, *, start_date: date, end_date: date) -> tuple[list[GlobalEventScheduleCandidate], GlobalEventCoverageSnapshot]:
        retries = 0
        if self.file_path:
            payload = _load_text_file(self.file_path)
        else:
            payload, retries = _fetch_text_with_retries(
                url=self.source_url,
                timeout_seconds=self.timeout_seconds,
                max_retries=self.max_retries,
                backoff_seconds=self.backoff_seconds,
                http_client=self._http_client,
                log_prefix="fed_calendar_fetch",
            )

        lines = _html_to_lines(payload)
        current_year: int | None = None
        candidates: list[GlobalEventScheduleCandidate] = []

        for line in lines:
            year_match = re.search(r"\b(20\d{2})\s+FOMC\b", line, re.IGNORECASE)
            if year_match:
                current_year = int(year_match.group(1))
                continue

            if "meeting" in line.lower() or "conference" in line.lower():
                continue

            parsed_range = _parse_range_with_year(line, current_year=current_year)
            if not parsed_range:
                continue
            _, meeting_end = parsed_range
            if meeting_end < start_date or meeting_end > end_date:
                continue

            candidates.append(
                GlobalEventScheduleCandidate(
                    event_key=f"FED:FOMC:{meeting_end.isoformat()}",
                    source_key=self.source_key,
                    source_event_id=meeting_end.isoformat(),
                    event_type="FOMC",
                    title=_default_title("FOMC"),
                    category=_CATEGORY_MAP["FOMC"],
                    country="US",
                    event_date_local=meeting_end,
                    event_datetime_local=None,
                    event_time_precision="date",
                    source_timezone="America/New_York",
                    reference_period=None,
                    status="scheduled",
                    importance=_default_importance("FOMC"),
                    importance_source="rule_based",
                    why_it_matters_ko=_default_why_it_matters("FOMC"),
                    source_name=self.source_name,
                    source_url=self.source_url,
                    provenance={"parsed_line": line},
                )
            )

        coverage = _make_coverage(
            source_key=self.source_key,
            source_name=self.source_name,
            source_kind="schedule",
            is_required=self.is_required,
            available_count=len(candidates),
            expected_count=max(len(candidates), 1),
            event_types=["FOMC"],
            source_url=self.source_url,
            note=None if candidates else "no_fomc_events_detected",
            retries=retries,
        )
        return candidates, coverage


class BlsScheduleAdapter:
    source_key = "BLS_SCHEDULE"
    source_name = "BLS Release Calendar"

    def __init__(
        self,
        *,
        url: str,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        http_client: httpx.Client | None = None,
        file_path: str | None = None,
        is_required: bool = True,
    ) -> None:
        self.source_url = url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._http_client = http_client
        self.file_path = file_path
        self.is_required = is_required

    def fetch(self, *, start_date: date, end_date: date) -> tuple[list[GlobalEventScheduleCandidate], GlobalEventCoverageSnapshot]:
        retries = 0
        if self.file_path:
            payload = _load_text_file(self.file_path)
        else:
            payload, retries = _fetch_text_with_retries(
                url=self.source_url,
                timeout_seconds=self.timeout_seconds,
                max_retries=self.max_retries,
                backoff_seconds=self.backoff_seconds,
                http_client=self._http_client,
                log_prefix="bls_schedule_fetch",
            )

        events = _parse_ics_payload(payload, default_timezone="America/New_York")
        candidates: list[GlobalEventScheduleCandidate] = []
        event_types_seen: set[str] = set()

        for item in events:
            summary = str(item.get("summary") or "")
            summary_upper = summary.upper()
            event_type: str | None = None
            title: str | None = None

            if "CONSUMER PRICE INDEX" in summary_upper:
                event_type = "CPI"
                title = _default_title("CPI")
            elif "EMPLOYMENT SITUATION" in summary_upper:
                event_type = "PAYROLLS"
                title = _default_title("PAYROLLS")

            if event_type is None:
                continue

            start_dt = item.get("dtstart")
            if not isinstance(start_dt, datetime):
                continue
            local_dt = start_dt.astimezone(ZoneInfo("America/New_York"))
            if local_dt.date() < start_date or local_dt.date() > end_date:
                continue

            reference_period = _bls_period_from_summary(
                f"{summary} {item.get('description') or ''}",
                local_dt.date(),
            )
            event_types_seen.add(event_type)
            candidates.append(
                GlobalEventScheduleCandidate(
                    event_key=f"BLS:{event_type}:{reference_period}",
                    source_key=self.source_key,
                    source_event_id=str(item.get("uid") or reference_period),
                    event_type=event_type,
                    title=title,
                    category=_CATEGORY_MAP[event_type],
                    country="US",
                    event_date_local=local_dt.date(),
                    event_datetime_local=local_dt,
                    event_time_precision="time",
                    source_timezone="America/New_York",
                    reference_period=reference_period,
                    status="scheduled",
                    importance=_default_importance(event_type),
                    importance_source="rule_based",
                    why_it_matters_ko=_default_why_it_matters(event_type),
                    source_name=self.source_name,
                    source_url=self.source_url,
                    provenance={"summary": summary, "description": item.get("description")},
                )
            )

        coverage = _make_coverage(
            source_key=self.source_key,
            source_name=self.source_name,
            source_kind="schedule",
            is_required=self.is_required,
            available_count=len(candidates),
            expected_count=max(len(candidates), 1),
            event_types=sorted(event_types_seen),
            source_url=self.source_url,
            note=None if candidates else "no_bls_events_detected",
            retries=retries,
        )
        return candidates, coverage


class BlsActualDataAdapter:
    source_key = "BLS_ACTUAL"
    source_name = "BLS Public Data API"

    def __init__(
        self,
        *,
        api_url: str,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        http_client: httpx.Client | None = None,
        is_required: bool = True,
    ) -> None:
        self.source_url = api_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._http_client = http_client
        self.is_required = is_required

    def fetch(self, *, events: list[dict[str, Any]]) -> tuple[list[GlobalEventReleaseCandidate], GlobalEventCoverageSnapshot]:
        relevant = [item for item in events if item.get("event_type") in {"CPI", "PAYROLLS"}]
        if not relevant:
            return [], _make_coverage(
                source_key=self.source_key,
                source_name=self.source_name,
                source_kind="release",
                is_required=self.is_required,
                available_count=0,
                expected_count=0,
                event_types=["CPI", "PAYROLLS"],
                source_url=self.source_url,
                note="no_relevant_events",
                retries=0,
            )

        years: set[int] = set()
        for item in relevant:
            period = str(item.get("reference_period") or "")
            if not period:
                continue
            year = int(period.split("-")[0])
            years.update({year - 1, year, year + 1})

        start_year = min(years)
        end_year = max(years)
        cpi_series, cpi_retries = self._fetch_series("CUUR0000SA0", start_year=start_year, end_year=end_year)
        payroll_series, payroll_retries = self._fetch_series("CES0000000001", start_year=start_year, end_year=end_year)
        unemployment_series, unemployment_retries = self._fetch_series("LNS14000000", start_year=start_year, end_year=end_year)

        candidates: list[GlobalEventReleaseCandidate] = []
        now_utc = datetime.now(ZoneInfo("UTC"))
        for item in relevant:
            event_type = str(item.get("event_type"))
            event_key = str(item.get("event_key"))
            reference_period = str(item.get("reference_period") or "")
            scheduled_utc = item.get("event_time_utc")
            scheduled_at = None
            if isinstance(scheduled_utc, str) and scheduled_utc:
                try:
                    scheduled_at = datetime.fromisoformat(scheduled_utc.replace("Z", "+00:00"))
                except ValueError:
                    scheduled_at = None
            is_released = scheduled_at is None or scheduled_at <= now_utc

            if event_type == "CPI":
                actual_value = self._compute_yoy(cpi_series, reference_period)
                previous_period = _previous_month(reference_period)
                previous_value = self._compute_yoy(cpi_series, previous_period)
                release_state = "released" if actual_value is not None and is_released else "actual_pending"
                candidates.append(
                    GlobalEventReleaseCandidate(
                        event_key=event_key,
                        metric_code="headline_cpi_yoy",
                        release_state=release_state,
                        unit="pct",
                        previous_value=previous_value,
                        previous_display=_format_pct(previous_value),
                        actual_value=actual_value,
                        actual_display=_format_pct(actual_value),
                        source_name=self.source_name,
                        source_url=self.source_url,
                        actual_released_at=scheduled_at.replace(microsecond=0).isoformat() if scheduled_at and actual_value is not None else None,
                        provenance={"series_id": "CUUR0000SA0", "reference_period": reference_period},
                    )
                )
                continue

            actual_value = self._compute_payroll_change(payroll_series, reference_period)
            previous_period = _previous_month(reference_period)
            previous_value = self._compute_payroll_change(payroll_series, previous_period)
            release_state = "released" if actual_value is not None and is_released else "actual_pending"
            candidates.append(
                GlobalEventReleaseCandidate(
                    event_key=event_key,
                    metric_code="nonfarm_payroll_change",
                    release_state=release_state,
                    unit="k_jobs",
                    previous_value=previous_value,
                    previous_display=_format_k_jobs(previous_value),
                    actual_value=actual_value,
                    actual_display=_format_k_jobs(actual_value),
                    source_name=self.source_name,
                    source_url=self.source_url,
                    actual_released_at=scheduled_at.replace(microsecond=0).isoformat() if scheduled_at and actual_value is not None else None,
                    provenance={
                        "series_id": "CES0000000001",
                        "unemployment_series_id": "LNS14000000",
                        "reference_period": reference_period,
                        "unemployment_rate": unemployment_series.get(reference_period),
                        "previous_unemployment_rate": unemployment_series.get(previous_period),
                    },
                )
            )

        retries = cpi_retries + payroll_retries + unemployment_retries
        coverage = _make_coverage(
            source_key=self.source_key,
            source_name=self.source_name,
            source_kind="release",
            is_required=self.is_required,
            available_count=sum(1 for item in candidates if item.actual_value is not None or item.previous_value is not None),
            expected_count=len(relevant),
            event_types=["CPI", "PAYROLLS"],
            source_url=self.source_url,
            note=None,
            retries=retries,
        )
        return candidates, coverage

    def _fetch_series(self, series_id: str, *, start_year: int, end_year: int) -> tuple[dict[str, float], int]:
        payload, retries = _fetch_json_with_retries(
            url=f"{self.source_url}/{series_id}",
            params={"startyear": start_year, "endyear": end_year},
            timeout_seconds=self.timeout_seconds,
            max_retries=self.max_retries,
            backoff_seconds=self.backoff_seconds,
            http_client=self._http_client,
            log_prefix="bls_actual_fetch",
        )
        results = payload.get("Results") if isinstance(payload, dict) else None
        series_list = results.get("series") if isinstance(results, dict) else None
        if not isinstance(series_list, list) or not series_list:
            raise ValueError("BLS API payload missing series")
        data = series_list[0].get("data")
        if not isinstance(data, list):
            raise ValueError("BLS API payload missing data rows")

        values: dict[str, float] = {}
        for row in data:
            if not isinstance(row, dict):
                continue
            period = str(row.get("period") or "")
            if not re.fullmatch(r"M\d{2}", period):
                continue
            raw_value = str(row.get("value") or "").replace(",", "").strip()
            if not raw_value:
                continue
            try:
                value = float(raw_value)
            except ValueError:
                continue
            values[f"{int(row['year']):04d}-{int(period[1:]):02d}"] = value
        return values, retries

    def _compute_yoy(self, series: dict[str, float], period: str) -> float | None:
        current = series.get(period)
        if current is None:
            return None
        year, month = [int(part) for part in period.split("-")]
        previous_year = series.get(f"{year - 1:04d}-{month:02d}")
        if previous_year is None or abs(previous_year) < 1e-12:
            return None
        return round(((current - previous_year) / previous_year) * 100.0, 2)

    def _compute_payroll_change(self, series: dict[str, float], period: str) -> float | None:
        current = series.get(period)
        previous = series.get(_previous_month(period))
        if current is None or previous is None:
            return None
        return round(current - previous, 1)


class BeaScheduleAdapter:
    source_key = "BEA_SCHEDULE"
    source_name = "BEA Release Schedule"

    def __init__(
        self,
        *,
        url: str,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        http_client: httpx.Client | None = None,
        file_path: str | None = None,
        is_required: bool = True,
    ) -> None:
        self.source_url = url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._http_client = http_client
        self.file_path = file_path
        self.is_required = is_required

    def fetch(self, *, start_date: date, end_date: date) -> tuple[list[GlobalEventScheduleCandidate], GlobalEventCoverageSnapshot]:
        retries = 0
        if self.file_path:
            payload = _load_text_file(self.file_path)
        else:
            payload, retries = _fetch_text_with_retries(
                url=self.source_url,
                timeout_seconds=self.timeout_seconds,
                max_retries=self.max_retries,
                backoff_seconds=self.backoff_seconds,
                http_client=self._http_client,
                log_prefix="bea_schedule_fetch",
            )

        lines = _html_to_lines(payload)
        candidates: list[GlobalEventScheduleCandidate] = []
        for index, line in enumerate(lines):
            if "Personal Income and Outlays" not in line:
                continue

            context = " ".join(lines[max(0, index - 1) : min(len(lines), index + 3)])
            release_date = _parse_date_value(context)
            if release_date is None or release_date < start_date or release_date > end_date:
                continue

            time_value = _parse_time_value(context)
            event_dt = None
            precision = "date"
            if time_value is not None:
                event_dt = datetime(
                    release_date.year,
                    release_date.month,
                    release_date.day,
                    time_value[0],
                    time_value[1],
                    tzinfo=ZoneInfo("America/New_York"),
                )
                precision = "time"

            parsed_period = _parse_month_year(line) or _parse_month_year(context)
            if parsed_period is not None:
                reference_period = f"{parsed_period[0]:04d}-{parsed_period[1]:02d}"
            else:
                reference_period = _previous_month(_to_period(release_date))

            candidates.append(
                GlobalEventScheduleCandidate(
                    event_key=f"BEA:PCE:{reference_period}",
                    source_key=self.source_key,
                    source_event_id=reference_period,
                    event_type="PCE",
                    title=_default_title("PCE"),
                    category=_CATEGORY_MAP["PCE"],
                    country="US",
                    event_date_local=release_date,
                    event_datetime_local=event_dt,
                    event_time_precision=precision,
                    source_timezone="America/New_York",
                    reference_period=reference_period,
                    status="scheduled",
                    importance=_default_importance("PCE"),
                    importance_source="rule_based",
                    why_it_matters_ko=_default_why_it_matters("PCE"),
                    source_name=self.source_name,
                    source_url=self.source_url,
                    provenance={"context": context},
                )
            )

        coverage = _make_coverage(
            source_key=self.source_key,
            source_name=self.source_name,
            source_kind="schedule",
            is_required=self.is_required,
            available_count=len(candidates),
            expected_count=max(len(candidates), 1),
            event_types=["PCE"],
            source_url=self.source_url,
            note=None if candidates else "no_bea_pce_schedule_detected",
            retries=retries,
        )
        return candidates, coverage


class BeaActualDataAdapter:
    source_key = "BEA_ACTUAL"
    source_name = "BEA PCE Price Index"

    def __init__(
        self,
        *,
        pce_url: str,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        http_client: httpx.Client | None = None,
        file_path: str | None = None,
        is_required: bool = True,
    ) -> None:
        self.source_url = pce_url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._http_client = http_client
        self.file_path = file_path
        self.is_required = is_required

    def fetch(self, *, events: list[dict[str, Any]]) -> tuple[list[GlobalEventReleaseCandidate], GlobalEventCoverageSnapshot]:
        relevant = [item for item in events if item.get("event_type") == "PCE"]
        if not relevant:
            return [], _make_coverage(
                source_key=self.source_key,
                source_name=self.source_name,
                source_kind="release",
                is_required=self.is_required,
                available_count=0,
                expected_count=0,
                event_types=["PCE"],
                source_url=self.source_url,
                note="no_relevant_events",
                retries=0,
            )

        retries = 0
        if self.file_path:
            payload = _load_text_file(self.file_path)
        else:
            payload, retries = _fetch_text_with_retries(
                url=self.source_url,
                timeout_seconds=self.timeout_seconds,
                max_retries=self.max_retries,
                backoff_seconds=self.backoff_seconds,
                http_client=self._http_client,
                log_prefix="bea_actual_fetch",
            )

        lines = _html_to_lines(payload)
        values = self._extract_pce_values(lines)
        now_utc = datetime.now(ZoneInfo("UTC"))
        candidates: list[GlobalEventReleaseCandidate] = []
        for item in relevant:
            event_key = str(item.get("event_key"))
            reference_period = str(item.get("reference_period") or "")
            scheduled_utc = item.get("event_time_utc")
            scheduled_at = None
            if isinstance(scheduled_utc, str) and scheduled_utc:
                try:
                    scheduled_at = datetime.fromisoformat(scheduled_utc.replace("Z", "+00:00"))
                except ValueError:
                    scheduled_at = None
            actual_value = values.get(reference_period)
            previous_value = values.get(_previous_month(reference_period))
            release_state = "released" if actual_value is not None and (scheduled_at is None or scheduled_at <= now_utc) else "actual_pending"
            candidates.append(
                GlobalEventReleaseCandidate(
                    event_key=event_key,
                    metric_code="headline_pce_yoy",
                    release_state=release_state,
                    unit="pct",
                    previous_value=previous_value,
                    previous_display=_format_pct(previous_value),
                    actual_value=actual_value,
                    actual_display=_format_pct(actual_value),
                    source_name=self.source_name,
                    source_url=self.source_url,
                    actual_released_at=scheduled_at.replace(microsecond=0).isoformat() if scheduled_at and actual_value is not None else None,
                    provenance={"reference_period": reference_period},
                )
            )

        coverage = _make_coverage(
            source_key=self.source_key,
            source_name=self.source_name,
            source_kind="release",
            is_required=self.is_required,
            available_count=sum(1 for item in candidates if item.actual_value is not None or item.previous_value is not None),
            expected_count=len(relevant),
            event_types=["PCE"],
            source_url=self.source_url,
            note=None,
            retries=retries,
        )
        return candidates, coverage

    def _extract_pce_values(self, lines: list[str]) -> dict[str, float]:
        values: dict[str, float] = {}
        for index, line in enumerate(lines):
            period = _parse_month_year(line)
            if period is None:
                continue

            candidate_text = line
            if "%" not in candidate_text and index + 1 < len(lines):
                candidate_text = f"{candidate_text} {lines[index + 1]}"
            match = re.search(r"([+-]?\d+(?:\.\d+)?)\s*%", candidate_text)
            if not match:
                continue

            year, month = period
            try:
                values[f"{year:04d}-{month:02d}"] = float(match.group(1))
            except ValueError:
                continue
        return values


class EcbCalendarAdapter:
    source_key = "ECB_CALENDAR"
    source_name = "ECB Governing Council Calendar"

    def __init__(
        self,
        *,
        url: str,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        http_client: httpx.Client | None = None,
        file_path: str | None = None,
        is_required: bool = True,
    ) -> None:
        self.source_url = url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._http_client = http_client
        self.file_path = file_path
        self.is_required = is_required

    def fetch(self, *, start_date: date, end_date: date) -> tuple[list[GlobalEventScheduleCandidate], GlobalEventCoverageSnapshot]:
        retries = 0
        if self.file_path:
            payload = _load_text_file(self.file_path)
        else:
            payload, retries = _fetch_text_with_retries(
                url=self.source_url,
                timeout_seconds=self.timeout_seconds,
                max_retries=self.max_retries,
                backoff_seconds=self.backoff_seconds,
                http_client=self._http_client,
                log_prefix="ecb_calendar_fetch",
            )

        lines = _html_to_lines(payload)
        candidates: list[GlobalEventScheduleCandidate] = []
        for line in lines:
            if "Monetary policy meeting" not in line:
                continue
            parsed_range = _parse_range_with_year(line)
            if not parsed_range:
                continue
            _, meeting_end = parsed_range
            if meeting_end < start_date or meeting_end > end_date:
                continue
            event_dt = datetime(meeting_end.year, meeting_end.month, meeting_end.day, 14, 15, tzinfo=ZoneInfo("Europe/Brussels"))
            candidates.append(
                GlobalEventScheduleCandidate(
                    event_key=f"ECB:RATE:{meeting_end.isoformat()}",
                    source_key=self.source_key,
                    source_event_id=meeting_end.isoformat(),
                    event_type="ECB",
                    title=_default_title("ECB"),
                    category=_CATEGORY_MAP["ECB"],
                    country="EU",
                    event_date_local=meeting_end,
                    event_datetime_local=event_dt,
                    event_time_precision="time",
                    source_timezone="Europe/Brussels",
                    reference_period=None,
                    status="scheduled",
                    importance=_default_importance("ECB"),
                    importance_source="rule_based",
                    why_it_matters_ko=_default_why_it_matters("ECB"),
                    source_name=self.source_name,
                    source_url=self.source_url,
                    provenance={"parsed_line": line, "release_time_local": "14:15"},
                )
            )

        coverage = _make_coverage(
            source_key=self.source_key,
            source_name=self.source_name,
            source_kind="schedule",
            is_required=self.is_required,
            available_count=len(candidates),
            expected_count=max(len(candidates), 1),
            event_types=["ECB"],
            source_url=self.source_url,
            note=None if candidates else "no_ecb_meetings_detected",
            retries=retries,
        )
        return candidates, coverage


class BojCalendarAdapter:
    source_key = "BOJ_CALENDAR"
    source_name = "BOJ Monetary Policy Meeting Schedule"

    def __init__(
        self,
        *,
        url: str,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        http_client: httpx.Client | None = None,
        file_path: str | None = None,
        is_required: bool = True,
    ) -> None:
        self.source_url = url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._http_client = http_client
        self.file_path = file_path
        self.is_required = is_required

    def fetch(self, *, start_date: date, end_date: date) -> tuple[list[GlobalEventScheduleCandidate], GlobalEventCoverageSnapshot]:
        retries = 0
        if self.file_path:
            payload = _load_text_file(self.file_path)
        else:
            payload, retries = _fetch_text_with_retries(
                url=self.source_url,
                timeout_seconds=self.timeout_seconds,
                max_retries=self.max_retries,
                backoff_seconds=self.backoff_seconds,
                http_client=self._http_client,
                log_prefix="boj_calendar_fetch",
            )

        lines = _html_to_lines(payload)
        candidates: list[GlobalEventScheduleCandidate] = []
        current_year: int | None = None
        for line in lines:
            year_match = re.search(r"\b(20\d{2})\b", line)
            if year_match and "meeting" not in line.lower():
                current_year = int(year_match.group(1))
            parsed_range = _parse_range_with_year(line, current_year=current_year)
            if not parsed_range:
                continue
            _, meeting_end = parsed_range
            if meeting_end < start_date or meeting_end > end_date:
                continue
            candidates.append(
                GlobalEventScheduleCandidate(
                    event_key=f"BOJ:MPM:{meeting_end.isoformat()}",
                    source_key=self.source_key,
                    source_event_id=meeting_end.isoformat(),
                    event_type="BOJ",
                    title=_default_title("BOJ"),
                    category=_CATEGORY_MAP["BOJ"],
                    country="JP",
                    event_date_local=meeting_end,
                    event_datetime_local=None,
                    event_time_precision="date",
                    source_timezone="Asia/Tokyo",
                    reference_period=None,
                    status="scheduled",
                    importance=_default_importance("BOJ"),
                    importance_source="rule_based",
                    why_it_matters_ko=_default_why_it_matters("BOJ"),
                    source_name=self.source_name,
                    source_url=self.source_url,
                    provenance={"parsed_line": line},
                )
            )

        coverage = _make_coverage(
            source_key=self.source_key,
            source_name=self.source_name,
            source_kind="schedule",
            is_required=self.is_required,
            available_count=len(candidates),
            expected_count=max(len(candidates), 1),
            event_types=["BOJ"],
            source_url=self.source_url,
            note=None if candidates else "no_boj_meetings_detected",
            retries=retries,
        )
        return candidates, coverage


class OptionalVendorCalendarAdapter:
    source_key = "VENDOR_GLOBAL_EVENTS"
    source_name = "Configured Global Events Vendor"

    def __init__(
        self,
        *,
        provider: str,
        file_path: str | None,
        base_url: str | None,
        schedule_path: str | None,
        api_key: str | None,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        http_client: httpx.Client | None = None,
        is_required: bool = False,
    ) -> None:
        self.provider = (provider or "disabled").strip().lower()
        self.file_path = file_path
        self.base_url = (base_url or "").rstrip("/")
        self.schedule_path = (schedule_path or "").strip()
        self.api_key = (api_key or "").strip()
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._http_client = http_client
        self.is_required = is_required
        self.source_url = self.file_path or (f"{self.base_url}{self.schedule_path}" if self.base_url and self.schedule_path else None)

    def fetch(self, *, start_date: date, end_date: date) -> GlobalEventVendorBatch:
        enabled, reason = self._is_enabled()
        if not enabled:
            return GlobalEventVendorBatch(
                schedules=[],
                releases=[],
                coverage=_make_coverage(
                    source_key=self.source_key,
                    source_name=self.source_name,
                    source_kind="vendor",
                    is_required=self.is_required,
                    available_count=0,
                    expected_count=1 if self.is_required else 0,
                    event_types=["EARNINGS"],
                    source_url=self.source_url,
                    note=reason,
                    retries=0,
                ),
            )

        retries = 0
        if self.provider == "file":
            payload = _load_json_file(self.file_path or "")
        else:
            payload, retries = _fetch_json_with_retries(
                url=self.source_url or "",
                params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
                timeout_seconds=self.timeout_seconds,
                max_retries=self.max_retries,
                backoff_seconds=self.backoff_seconds,
                http_client=self._http_client,
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else None,
                log_prefix="global_event_vendor_fetch",
            )

        schedules, releases = self._parse_payload(payload)
        coverage = _make_coverage(
            source_key=self.source_key,
            source_name=self.source_name,
            source_kind="vendor",
            is_required=self.is_required,
            available_count=len(schedules) + len(releases),
            expected_count=max(len(schedules) + len(releases), 1),
            event_types=sorted({item.event_type for item in schedules}),
            source_url=self.source_url,
            note=None if schedules or releases else "vendor_returned_no_events",
            retries=retries,
        )
        return GlobalEventVendorBatch(schedules=schedules, releases=releases, coverage=coverage)

    def _is_enabled(self) -> tuple[bool, str | None]:
        if self.provider in {"", "disabled"}:
            return False, "feature_flag_disabled"
        if self.provider == "file":
            if not self.file_path:
                return False, "missing_vendor_file_path"
            return True, None
        if self.provider == "api":
            if not self.base_url or not self.schedule_path:
                return False, "missing_vendor_url"
            return True, None
        return False, f"unsupported_vendor_provider:{self.provider}"

    def _parse_payload(self, payload: Any) -> tuple[list[GlobalEventScheduleCandidate], list[GlobalEventReleaseCandidate]]:
        if isinstance(payload, dict):
            raw_schedules = payload.get("schedules")
            raw_releases = payload.get("releases")
            if raw_schedules is None and isinstance(payload.get("items"), list):
                raw_schedules = payload.get("items")
            if raw_releases is None and isinstance(payload.get("items"), list):
                raw_releases = payload.get("items")
        elif isinstance(payload, list):
            raw_schedules = payload
            raw_releases = payload
        else:
            raise ValueError("Vendor payload must be an object or list")

        schedules: list[GlobalEventScheduleCandidate] = []
        releases: list[GlobalEventReleaseCandidate] = []

        for item in raw_schedules or []:
            if not isinstance(item, dict):
                continue
            candidate = self._parse_schedule_item(item)
            if candidate is not None:
                schedules.append(candidate)

        for item in raw_releases or []:
            if not isinstance(item, dict):
                continue
            candidate = self._parse_release_item(item)
            if candidate is not None:
                releases.append(candidate)

        return schedules, releases

    def _parse_schedule_item(self, item: dict[str, Any]) -> GlobalEventScheduleCandidate | None:
        event_type = str(item.get("event_type") or "").strip().upper() or "EARNINGS"
        title = str(item.get("title") or _default_title(event_type)).strip()
        event_time = str(item.get("event_time") or "").strip()
        timezone_name = str(item.get("timezone") or "America/New_York").strip() or "America/New_York"
        local_dt = None
        event_date_local = None
        precision = "date"
        if event_time:
            try:
                parsed = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
                local_dt = parsed if parsed.tzinfo else parsed.replace(tzinfo=ZoneInfo(timezone_name))
                local_dt = local_dt.astimezone(ZoneInfo(timezone_name))
                event_date_local = local_dt.date()
                precision = "time"
            except ValueError:
                local_dt = None
        if event_date_local is None:
            date_text = str(item.get("event_date") or "").strip()
            if not date_text:
                return None
            try:
                event_date_local = date.fromisoformat(date_text)
            except ValueError:
                return None

        event_key = str(item.get("event_key") or "").strip()
        if not event_key:
            symbol = str(item.get("symbol") or item.get("company") or title).strip().replace(" ", "_").upper()
            event_key = f"VENDOR:{event_type}:{symbol}:{event_date_local.isoformat()}"

        return GlobalEventScheduleCandidate(
            event_key=event_key,
            source_key=self.source_key,
            source_event_id=str(item.get("id") or item.get("event_id") or event_key),
            event_type=event_type,
            title=title,
            category=str(item.get("category") or _CATEGORY_MAP.get(event_type, "earnings")),
            country=str(item.get("country") or "US"),
            event_date_local=event_date_local,
            event_datetime_local=local_dt,
            event_time_precision=precision,
            source_timezone=timezone_name,
            reference_period=str(item.get("reference_period") or "") or None,
            status=str(item.get("status") or "scheduled"),
            importance=str(item.get("importance") or _default_importance(event_type)),
            importance_source="vendor",
            why_it_matters_ko=str(item.get("why_it_matters_ko") or _default_why_it_matters(event_type, title)),
            source_name=str(item.get("source_name") or self.source_name),
            source_url=str(item.get("source_url") or self.source_url or "") or None,
            source_updated_at=str(item.get("source_updated_at") or "") or None,
            provenance={"vendor_item": item},
            raw_payload=item,
        )

    def _parse_release_item(self, item: dict[str, Any]) -> GlobalEventReleaseCandidate | None:
        event_key = str(item.get("event_key") or "").strip()
        if not event_key:
            return None
        actual_value = _as_float(item.get("actual"))
        forecast_value = _as_float(item.get("forecast"))
        surprise_value = _as_float(item.get("surprise"))
        previous_value = _as_float(item.get("previous"))
        return GlobalEventReleaseCandidate(
            event_key=event_key,
            metric_code=str(item.get("metric_code") or "headline"),
            release_state=str(item.get("release_state") or ("released" if actual_value is not None else "forecast_pending")),
            unit=str(item.get("unit") or "") or None,
            previous_value=previous_value,
            previous_display=str(item.get("previous_display") or item.get("previous") or "") or None,
            forecast_value=forecast_value,
            forecast_display=str(item.get("forecast_display") or item.get("forecast") or "") or None,
            actual_value=actual_value,
            actual_display=str(item.get("actual_display") or item.get("actual") or "") or None,
            surprise_value=surprise_value,
            surprise_display=str(item.get("surprise_display") or item.get("surprise") or "") or None,
            source_name=str(item.get("source_name") or self.source_name),
            source_url=str(item.get("source_url") or self.source_url or "") or None,
            source_record_id=str(item.get("source_record_id") or item.get("id") or "") or None,
            actual_released_at=str(item.get("actual_released_at") or "") or None,
            provenance={"vendor_item": item},
        )


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "--", "N/A", "null", "None"}:
        return None
    if text.endswith("%"):
        text = text[:-1].strip()
    if text.startswith("+"):
        text = text[1:]
    try:
        return float(text)
    except ValueError:
        return None


def _format_pct(value: float | None) -> str | None:
    if value is None:
        return None
    return f"{value:.2f}%"


def _format_k_jobs(value: float | None) -> str | None:
    if value is None:
        return None
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}k"


def candidate_to_payload(candidate: GlobalEventScheduleCandidate) -> dict[str, Any]:
    payload = asdict(candidate)
    payload["event_date_local"] = candidate.event_date_local.isoformat()
    payload["event_datetime_local"] = candidate.event_datetime_local.isoformat() if candidate.event_datetime_local else None
    payload["event_time_utc"] = _local_to_utc_iso(candidate.event_datetime_local) if candidate.event_datetime_local else None
    payload["event_time_kst"] = _local_to_kst_iso(candidate.event_datetime_local) if candidate.event_datetime_local else None
    payload["event_date_kst"] = candidate.event_date_local.isoformat() if candidate.event_datetime_local is None else candidate.event_datetime_local.astimezone(_KST).date().isoformat()
    payload["sort_at_kst"] = _sort_at_kst(candidate.event_date_local, candidate.event_datetime_local)
    return payload
