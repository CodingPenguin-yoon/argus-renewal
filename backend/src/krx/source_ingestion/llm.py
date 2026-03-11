from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
import time
from typing import Protocol

import httpx

from .event_taxonomy import EVENT_TAXONOMY, normalize_event_type

logger = logging.getLogger(__name__)

_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


@dataclass(frozen=True)
class LLMCompanyImpact:
    company_id: int
    impact_tier: str
    reason: str
    confidence: float


@dataclass(frozen=True)
class LLMExtractionRequest:
    raw_document_id: int
    normalized_text: str
    candidate_companies: list[dict[str, object]]
    taxonomy: list[str]


@dataclass(frozen=True)
class LLMExtractionResponse:
    event_type: str
    summary: str
    sentiment: str
    companies: list[LLMCompanyImpact]
    risk_flags: list[str]
    confidence: float
    raw_output: dict[str, object]


class LLMExtractionProvider(Protocol):
    provider_name: str

    def is_enabled(self) -> tuple[bool, str | None]:
        ...

    def model_name(self) -> str | None:
        ...

    def extract_event(self, request: LLMExtractionRequest) -> LLMExtractionResponse | None:
        ...


class DisabledLLMExtractionProvider:
    provider_name = "disabled"

    def is_enabled(self) -> tuple[bool, str | None]:
        return False, "feature_flag_disabled"

    def model_name(self) -> str | None:
        return None

    def extract_event(self, request: LLMExtractionRequest) -> LLMExtractionResponse | None:
        _ = request
        return None


class OpenAICompatibleLLMExtractionProvider:
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

    def extract_event(self, request: LLMExtractionRequest) -> LLMExtractionResponse | None:
        enabled, reason = self.is_enabled()
        if not enabled:
            logger.info(
                "event_llm_provider_disabled",
                extra={"reason": reason, "raw_document_id": request.raw_document_id},
            )
            return None

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "event_llm_extract_attempt",
                    extra={
                        "attempt": attempt,
                        "raw_document_id": request.raw_document_id,
                        "provider": self.provider_name,
                        "model": self.model,
                    },
                )
                payload = self._request_completion(request)
                return self._parse_completion(payload)
            except Exception as error:  # noqa: BLE001
                last_error = error
                logger.warning(
                    "event_llm_extract_retry",
                    extra={
                        "attempt": attempt,
                        "raw_document_id": request.raw_document_id,
                        "error": str(error),
                    },
                )
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * (2 ** (attempt - 1)))

        raise RuntimeError("Failed to extract event via LLM after retries") from last_error

    def _request_completion(self, request: LLMExtractionRequest) -> dict[str, object]:
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        system_prompt = (
            "You are a market event parser. Return JSON only with schema: "
            "{event_type, summary, sentiment, companies, risk_flags, confidence}. "
            "Use facts only from input text and candidate companies."
        )
        user_payload = {
            "taxonomy": request.taxonomy,
            "candidate_companies": request.candidate_companies,
            "document": request.normalized_text,
            "contract": {
                "event_type": "string",
                "summary": "string",
                "sentiment": "positive|negative|neutral|mixed",
                "companies": [
                    {
                        "company_id": "integer",
                        "impact_tier": "direct|indirect|theme",
                        "reason": "string",
                        "confidence": "0.0-1.0",
                    }
                ],
                "risk_flags": ["string"],
                "confidence": "0.0-1.0",
            },
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
            raise ValueError("LLM completion payload is not an object")
        return payload

    def _parse_completion(self, payload: dict[str, object]) -> LLMExtractionResponse:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("LLM completion payload missing choices")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError("LLM completion first choice is not an object")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("LLM completion message missing")

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("LLM completion content missing")

        output = self._parse_content_json(content)

        event_type = normalize_event_type(str(output.get("event_type") or "").strip())
        if event_type is None or event_type not in EVENT_TAXONOMY:
            raise ValueError("LLM completion event_type invalid")

        summary = str(output.get("summary") or "").strip()
        if not summary:
            raise ValueError("LLM completion summary missing")

        sentiment = str(output.get("sentiment") or "neutral").strip().lower()
        if sentiment not in {"positive", "negative", "neutral", "mixed"}:
            sentiment = "neutral"

        raw_companies = output.get("companies")
        companies: list[LLMCompanyImpact] = []
        if isinstance(raw_companies, list):
            for item in raw_companies:
                if not isinstance(item, dict):
                    continue
                try:
                    company_id = int(item.get("company_id"))
                except (TypeError, ValueError):
                    continue

                impact_tier = str(item.get("impact_tier") or "").strip().lower()
                if impact_tier not in {"direct", "indirect", "theme"}:
                    continue

                reason = str(item.get("reason") or "").strip() or "llm_extracted"
                confidence = _normalize_confidence(item.get("confidence"), default=0.5)
                companies.append(
                    LLMCompanyImpact(
                        company_id=company_id,
                        impact_tier=impact_tier,
                        reason=reason,
                        confidence=confidence,
                    )
                )

        risk_flags = output.get("risk_flags")
        normalized_risk_flags: list[str] = []
        if isinstance(risk_flags, list):
            normalized_risk_flags = [str(item).strip() for item in risk_flags if str(item).strip()]

        confidence = _normalize_confidence(output.get("confidence"), default=0.5)

        return LLMExtractionResponse(
            event_type=event_type,
            summary=summary,
            sentiment=sentiment,
            companies=companies,
            risk_flags=normalized_risk_flags,
            confidence=confidence,
            raw_output=output,
        )

    def _parse_content_json(self, content: str) -> dict[str, object]:
        candidate = content.strip()
        block_match = _JSON_BLOCK_RE.search(candidate)
        if block_match:
            candidate = block_match.group(1).strip()

        payload = json.loads(candidate)
        if not isinstance(payload, dict):
            raise ValueError("LLM completion JSON content is not an object")
        return payload


def _normalize_confidence(value: object, *, default: float) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = default
    return max(0.0, min(1.0, score))
