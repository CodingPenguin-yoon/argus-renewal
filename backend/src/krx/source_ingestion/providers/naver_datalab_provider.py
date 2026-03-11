from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrendKeywordGroup:
    group_name: str
    keywords: list[str]


@dataclass(frozen=True)
class TrendScore:
    group_name: str
    latest_ratio: float
    average_ratio: float
    latest_period: str | None
    datapoint_count: int


@dataclass(frozen=True)
class TrendScoreBatch:
    scores: dict[str, TrendScore]
    disabled_reason: str | None = None


class NaverDatalabTrendProvider:
    def __init__(
        self,
        *,
        enabled: bool,
        client_id: str | None,
        client_secret: str | None,
        base_url: str,
        search_path: str,
        time_unit: str = "date",
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
        self.time_unit = time_unit
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._http_client = http_client

    def is_enabled(self) -> tuple[bool, str | None]:
        if not self.enabled:
            return False, "feature_flag_disabled"
        if not self.client_id or not self.client_secret:
            return False, "missing_naver_datalab_credentials"
        return True, None

    def fetch_interest_scores(
        self,
        *,
        start_date: date,
        end_date: date,
        groups: list[TrendKeywordGroup],
    ) -> TrendScoreBatch:
        enabled, reason = self.is_enabled()
        if not enabled:
            logger.info("naver_datalab_provider_disabled", extra={"reason": reason})
            return TrendScoreBatch(scores={}, disabled_reason=reason)

        if not groups:
            return TrendScoreBatch(scores={})

        payload = self._request(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            groups=groups,
        )
        results = payload.get("results")
        if not isinstance(results, list):
            raise ValueError("Naver Datalab response does not include results")

        scores: dict[str, TrendScore] = {}
        for row in results:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "").strip()
            if not title:
                continue
            data_points = row.get("data")
            if not isinstance(data_points, list):
                continue

            numeric_points: list[tuple[str | None, float]] = []
            for point in data_points:
                if not isinstance(point, dict):
                    continue
                ratio = point.get("ratio")
                try:
                    ratio_value = float(ratio)
                except (TypeError, ValueError):
                    continue
                numeric_points.append((str(point.get("period") or "").strip() or None, ratio_value))

            if not numeric_points:
                continue

            latest_period, latest_ratio = numeric_points[-1]
            average_ratio = sum(value for _, value in numeric_points) / len(numeric_points)
            scores[title] = TrendScore(
                group_name=title,
                latest_ratio=latest_ratio,
                average_ratio=average_ratio,
                latest_period=latest_period,
                datapoint_count=len(numeric_points),
            )

        logger.info(
            "naver_datalab_fetch_success",
            extra={
                "group_count": len(groups),
                "score_count": len(scores),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
        )
        return TrendScoreBatch(scores=scores)

    def _request(
        self,
        *,
        start_date: str,
        end_date: str,
        groups: list[TrendKeywordGroup],
    ) -> dict[str, Any]:
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "naver_datalab_fetch_attempt",
                    extra={
                        "attempt": attempt,
                        "group_count": len(groups),
                        "start_date": start_date,
                        "end_date": end_date,
                    },
                )
                response = self._do_request(start_date=start_date, end_date=end_date, groups=groups)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("Naver Datalab response is not a JSON object")
                return payload
            except (httpx.HTTPError, json.JSONDecodeError, ValueError) as error:
                last_error = error
                logger.warning(
                    "naver_datalab_fetch_retry",
                    extra={"attempt": attempt, "error": str(error), "group_count": len(groups)},
                )
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * (2 ** (attempt - 1)))

        raise RuntimeError("Failed to fetch Naver Datalab search trends after retries") from last_error

    def _do_request(
        self,
        *,
        start_date: str,
        end_date: str,
        groups: list[TrendKeywordGroup],
    ) -> httpx.Response:
        url = f"{self.base_url}{self.search_path}"
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
            "Content-Type": "application/json",
        }
        payload = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": self.time_unit,
            "keywordGroups": [
                {
                    "groupName": group.group_name,
                    "keywords": group.keywords,
                }
                for group in groups
            ],
        }

        if self._http_client is not None:
            return self._http_client.post(url, headers=headers, json=payload, timeout=self.timeout_seconds)
        with httpx.Client() as client:
            return client.post(url, headers=headers, json=payload, timeout=self.timeout_seconds)
