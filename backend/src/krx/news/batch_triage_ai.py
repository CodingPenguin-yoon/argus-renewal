from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import time
from typing import Any, Protocol

import httpx

logger = logging.getLogger(__name__)

_MARKET_SCOPES = {"kr_market", "global_market", "sector", "company", "ignore"}
_PRIMARY_REGIONS = {"KR", "GLOBAL"}
_IMPORTANCE_LABELS = {"high", "medium", "low"}
_IMPACT_DIRECTIONS = {"positive", "negative", "mixed", "neutral"}


@dataclass(frozen=True)
class NewsBatchTriageRequestItem:
    raw_document_id: int
    provider: str
    document_type: str
    title: str
    summary: str
    publisher: str
    query_text: str
    company_name: str
    primary_stock_code: str
    market_classification: str
    is_duplicate: bool
    duplicate_of_document_id: int | None
    deterministic_scope: str
    deterministic_region: str
    deterministic_importance: str
    deterministic_direction: str
    deterministic_reason: str


@dataclass(frozen=True)
class NewsBatchTriageResponseItem:
    raw_document_id: int
    market_scope: str
    primary_region: str
    importance_label: str
    impact_direction: str
    reason_short: str
    confidence: float
    raw_output: dict[str, Any]


class NewsBatchTriageProvider(Protocol):
    provider_name: str

    def is_enabled(self) -> tuple[bool, str | None]:
        ...

    def model_name(self) -> str | None:
        ...

    def triage(self, request_items: list[NewsBatchTriageRequestItem]) -> dict[int, NewsBatchTriageResponseItem]:
        ...


class DisabledNewsBatchTriageProvider:
    provider_name = "disabled"

    def is_enabled(self) -> tuple[bool, str | None]:
        return False, "feature_flag_disabled"

    def model_name(self) -> str | None:
        return None

    def triage(self, request_items: list[NewsBatchTriageRequestItem]) -> dict[int, NewsBatchTriageResponseItem]:
        _ = request_items
        return {}


class OpenAICompatibleNewsBatchTriageProvider:
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

    def triage(self, request_items: list[NewsBatchTriageRequestItem]) -> dict[int, NewsBatchTriageResponseItem]:
        if not request_items:
            return {}

        enabled, reason = self.is_enabled()
        if not enabled:
            logger.info(
                "news_batch_triage_ai_disabled",
                extra={"reason": reason, "request_count": len(request_items)},
            )
            return {}

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                payload = self._request_completion(request_items)
                return self._parse_completion(payload)
            except Exception as error:  # noqa: BLE001
                last_error = error
                logger.warning(
                    "news_batch_triage_ai_retry",
                    extra={"attempt": attempt, "request_count": len(request_items), "error": str(error)},
                )
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * (2 ** (attempt - 1)))

        raise RuntimeError("Failed to batch-triage news items via AI after retries") from last_error

    def _request_completion(self, request_items: list[NewsBatchTriageRequestItem]) -> dict[str, Any]:
        url = self._chat_completions_url()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        system_prompt = (
            "You are the first-stage triage model for a Korean market-news product. "
            "Return JSON only with schema {items:[{raw_document_id, market_scope, primary_region, "
            "importance_label, impact_direction, reason_short, confidence}]}. "
            "market_scope must be one of kr_market, global_market, sector, company, ignore. "
            "primary_region must be one of KR, GLOBAL. "
            "importance_label must be one of high, medium, low. "
            "impact_direction must be one of positive, negative, mixed, neutral. "
            "reason_short must be a short Korean sentence. "
            "confidence must be between 0 and 1. "
            "Use the deterministic hints as defaults when evidence is weak."
        )
        user_payload = {
            "items": [
                {
                    "raw_document_id": item.raw_document_id,
                    "provider": item.provider,
                    "document_type": item.document_type,
                    "title": item.title,
                    "summary": item.summary,
                    "publisher": item.publisher,
                    "query_text": item.query_text,
                    "company_name": item.company_name,
                    "primary_stock_code": item.primary_stock_code,
                    "market_classification": item.market_classification,
                    "is_duplicate": item.is_duplicate,
                    "duplicate_of_document_id": item.duplicate_of_document_id,
                    "deterministic_guess": {
                        "market_scope": item.deterministic_scope,
                        "primary_region": item.deterministic_region,
                        "importance_label": item.deterministic_importance,
                        "impact_direction": item.deterministic_direction,
                        "reason_short": item.deterministic_reason,
                    },
                }
                for item in request_items
            ]
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
            raise ValueError("news batch triage completion payload is not an object")
        return payload

    def _chat_completions_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        if self.base_url.endswith("/openai") or self.base_url.endswith("/openai/v1") or self.base_url.endswith("/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/v1/chat/completions"

    def _parse_completion(self, payload: dict[str, Any]) -> dict[int, NewsBatchTriageResponseItem]:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("news batch triage completion payload missing choices")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError("news batch triage completion first choice is not an object")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("news batch triage completion message missing")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("news batch triage completion content missing")
        output = json.loads(content)
        if not isinstance(output, dict):
            raise ValueError("news batch triage completion output is not an object")
        raw_items = output.get("items")
        if not isinstance(raw_items, list):
            raise ValueError("news batch triage completion items missing")

        results: dict[int, NewsBatchTriageResponseItem] = {}
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            try:
                raw_document_id = int(raw_item.get("raw_document_id"))
            except (TypeError, ValueError):
                continue
            market_scope = _normalize_enum(raw_item.get("market_scope"), allowed=_MARKET_SCOPES, default="ignore")
            primary_region = _normalize_enum(raw_item.get("primary_region"), allowed=_PRIMARY_REGIONS, default="KR")
            importance_label = _normalize_enum(
                raw_item.get("importance_label"),
                allowed=_IMPORTANCE_LABELS,
                default="medium",
            )
            impact_direction = _normalize_enum(
                raw_item.get("impact_direction"),
                allowed=_IMPACT_DIRECTIONS,
                default="neutral",
            )
            reason_short = str(raw_item.get("reason_short") or "").strip()
            results[raw_document_id] = NewsBatchTriageResponseItem(
                raw_document_id=raw_document_id,
                market_scope=market_scope,
                primary_region=primary_region,
                importance_label=importance_label,
                impact_direction=impact_direction,
                reason_short=reason_short,
                confidence=_normalize_confidence(raw_item.get("confidence")),
                raw_output=raw_item,
            )
        return results


def _normalize_enum(value: object, *, allowed: set[str], default: str) -> str:
    normalized = str(value or "").strip()
    return normalized if normalized in allowed else default


def _normalize_confidence(value: object) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, numeric))
