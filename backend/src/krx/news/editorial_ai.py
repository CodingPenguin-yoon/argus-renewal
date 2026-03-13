from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import time
from typing import Any, Protocol

import httpx

logger = logging.getLogger(__name__)

_STORY_STATES = {"NEW", "ONGOING", "DISCLOSURE_CONFIRMED"}
_IMPORTANCE_LABELS = {"high", "medium", "low"}


@dataclass(frozen=True)
class NewsEditorialAIRequest:
    cluster_key: str
    title: str
    one_line_summary: str
    why_it_matters: str
    market_impact: str
    market_scope: str
    primary_region: str
    event_type: str
    event_subtype: str
    impact_direction: str
    impact_horizon: str
    source_type: str
    trust_score: float
    materiality_score: float
    novelty_score: float
    cross_source_score: float
    attention_score: float
    evidence_count: int
    direct_company_names: list[str]
    direct_company_tickers: list[str]
    sector_tags: list[str]
    keyword_tags: list[str]
    evidence: list[dict[str, Any]]


@dataclass(frozen=True)
class NewsEditorialAIResponse:
    story_state: str
    importance_label: str
    editorial_reason: str
    editorial_boost: float
    confidence: float
    raw_output: dict[str, Any]


class NewsEditorialAIProvider(Protocol):
    provider_name: str

    def is_enabled(self) -> tuple[bool, str | None]:
        ...

    def model_name(self) -> str | None:
        ...

    def enrich(self, request: NewsEditorialAIRequest) -> NewsEditorialAIResponse | None:
        ...


class DisabledNewsEditorialAIProvider:
    provider_name = "disabled"

    def is_enabled(self) -> tuple[bool, str | None]:
        return False, "feature_flag_disabled"

    def model_name(self) -> str | None:
        return None

    def enrich(self, request: NewsEditorialAIRequest) -> NewsEditorialAIResponse | None:
        _ = request
        return None


class OpenAICompatibleNewsEditorialAIProvider:
    provider_name = "openai_compatible"

    def __init__(
        self,
        *,
        enabled: bool,
        base_url: str | None,
        api_key: str | None,
        model: str | None,
        timeout_seconds: float,
        max_retries: int,
        backoff_seconds: float,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.enabled = enabled
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = (api_key or "").strip()
        self.model = (model or "").strip()
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(1, max_retries)
        self.backoff_seconds = max(0.0, backoff_seconds)
        self._http_client = http_client

    def is_enabled(self) -> tuple[bool, str | None]:
        if not self.enabled:
            return False, "feature_flag_disabled"
        if not self.base_url:
            return False, "missing_llm_base_url"
        if not self.api_key:
            return False, "missing_llm_api_key"
        if not self.model:
            return False, "missing_llm_model"
        return True, None

    def model_name(self) -> str | None:
        return self.model or None

    def enrich(self, request: NewsEditorialAIRequest) -> NewsEditorialAIResponse | None:
        enabled, reason = self.is_enabled()
        if not enabled:
            logger.info(
                "news_editorial_ai_disabled",
                extra={"reason": reason, "cluster_key": request.cluster_key},
            )
            return None

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                payload = self._request_completion(request)
                return self._parse_completion(payload)
            except Exception as error:  # noqa: BLE001
                last_error = error
                logger.warning(
                    "news_editorial_ai_retry",
                    extra={
                        "attempt": attempt,
                        "cluster_key": request.cluster_key,
                        "error": str(error),
                    },
                )
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * (2 ** (attempt - 1)))

        raise RuntimeError("Failed to enrich news editorial card via AI after retries") from last_error

    def _request_completion(self, request: NewsEditorialAIRequest) -> dict[str, Any]:
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        system_prompt = (
            "You are an editorial assistant for a Korean market-news product. "
            "Return JSON only with schema: "
            "{story_state, importance_label, editorial_reason, editorial_boost, confidence}. "
            "story_state must be one of NEW, ONGOING, DISCLOSURE_CONFIRMED. "
            "importance_label must be one of high, medium, low. "
            "editorial_boost must be between -0.08 and 0.12. "
            "Use the provided evidence only."
        )
        user_payload = {
            "cluster": {
                "cluster_key": request.cluster_key,
                "title": request.title,
                "one_line_summary": request.one_line_summary,
                "why_it_matters": request.why_it_matters,
                "market_impact": request.market_impact,
                "market_scope": request.market_scope,
                "primary_region": request.primary_region,
                "event_type": request.event_type,
                "event_subtype": request.event_subtype,
                "impact_direction": request.impact_direction,
                "impact_horizon": request.impact_horizon,
                "source_type": request.source_type,
                "trust_score": request.trust_score,
                "materiality_score": request.materiality_score,
                "novelty_score": request.novelty_score,
                "cross_source_score": request.cross_source_score,
                "attention_score": request.attention_score,
                "evidence_count": request.evidence_count,
                "direct_company_names": request.direct_company_names,
                "direct_company_tickers": request.direct_company_tickers,
                "sector_tags": request.sector_tags,
                "keyword_tags": request.keyword_tags,
                "evidence": request.evidence,
            }
        }
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
        }
        if self._http_client is not None:
            response = self._http_client.post(url, headers=headers, json=body, timeout=self.timeout_seconds)
        else:
            with httpx.Client() as client:
                response = client.post(url, headers=headers, json=body, timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("news editorial completion payload is not an object")
        return payload

    def _parse_completion(self, payload: dict[str, Any]) -> NewsEditorialAIResponse:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("news editorial completion payload missing choices")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError("news editorial completion first choice is not an object")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("news editorial completion message missing")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("news editorial completion content missing")
        output = json.loads(content)
        if not isinstance(output, dict):
            raise ValueError("news editorial completion output is not an object")

        story_state = str(output.get("story_state") or "NEW").strip().upper()
        if story_state not in _STORY_STATES:
            story_state = "NEW"
        importance_label = str(output.get("importance_label") or "medium").strip().lower()
        if importance_label not in _IMPORTANCE_LABELS:
            importance_label = "medium"
        editorial_reason = str(output.get("editorial_reason") or "").strip()
        confidence = _normalize_confidence(output.get("confidence"), default=0.5)
        editorial_boost = _normalize_boost(output.get("editorial_boost"))

        return NewsEditorialAIResponse(
            story_state=story_state,
            importance_label=importance_label,
            editorial_reason=editorial_reason,
            editorial_boost=editorial_boost,
            confidence=confidence,
            raw_output=output,
        )


def _normalize_confidence(value: object, *, default: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, numeric))


def _normalize_boost(value: object) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(-0.08, min(0.12, numeric))
