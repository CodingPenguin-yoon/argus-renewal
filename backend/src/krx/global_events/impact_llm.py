from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
import time
from typing import Any, Protocol

import httpx

logger = logging.getLogger(__name__)

_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


@dataclass(frozen=True)
class GlobalEventImpactRequest:
    event_key: str
    title: str
    category: str
    country: str
    why_it_matters_ko: str
    status: str
    importance: str | None
    release: dict[str, Any]
    provenance: dict[str, Any]


@dataclass(frozen=True)
class GlobalEventImpactResponse:
    summary_ko: str
    tone: str
    impact_channels: list[str]
    raw_output: dict[str, Any]


class GlobalEventImpactProvider(Protocol):
    provider_name: str

    def is_enabled(self) -> tuple[bool, str | None]:
        ...

    def model_name(self) -> str | None:
        ...

    def generate_impact(
        self,
        request: GlobalEventImpactRequest,
    ) -> GlobalEventImpactResponse | None:
        ...


class DisabledGlobalEventImpactProvider:
    provider_name = "disabled"

    def is_enabled(self) -> tuple[bool, str | None]:
        return False, "feature_flag_disabled"

    def model_name(self) -> str | None:
        return None

    def generate_impact(self, request: GlobalEventImpactRequest) -> GlobalEventImpactResponse | None:
        _ = request
        return None


class OpenAICompatibleGlobalEventImpactProvider:
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

    def generate_impact(self, request: GlobalEventImpactRequest) -> GlobalEventImpactResponse | None:
        enabled, reason = self.is_enabled()
        if not enabled:
            logger.info(
                "global_event_llm_disabled",
                extra={"reason": reason, "event_key": request.event_key},
            )
            return None

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "global_event_llm_attempt",
                    extra={
                        "attempt": attempt,
                        "event_key": request.event_key,
                        "provider": self.provider_name,
                        "model": self.model,
                    },
                )
                payload = self._request_completion(request)
                return self._parse_completion(payload)
            except Exception as error:  # noqa: BLE001
                last_error = error
                logger.warning(
                    "global_event_llm_retry",
                    extra={"attempt": attempt, "event_key": request.event_key, "error": str(error)},
                )
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * (2 ** (attempt - 1)))

        raise RuntimeError("Failed to generate global-event impact via LLM after retries") from last_error

    def _request_completion(self, request: GlobalEventImpactRequest) -> dict[str, Any]:
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        system_prompt = (
            "You are a Korean macro catalyst analyst. "
            "Use only supplied fields and do not invent facts. "
            "Return JSON only with schema {summary_ko, tone, impact_channels}."
        )
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(request.__dict__, ensure_ascii=False)},
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

    def _parse_completion(self, payload: dict[str, Any]) -> GlobalEventImpactResponse:
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

        candidate = content.strip()
        block_match = _JSON_BLOCK_RE.search(candidate)
        if block_match:
            candidate = block_match.group(1)

        output = json.loads(candidate)
        if not isinstance(output, dict):
            raise ValueError("LLM output is not an object")

        summary_ko = str(output.get("summary_ko") or "").strip()
        if not summary_ko:
            raise ValueError("summary_ko missing")

        tone = str(output.get("tone") or "neutral").strip().lower()
        if tone not in {"risk_on", "risk_off", "hawkish", "dovish", "neutral", "mixed"}:
            tone = "neutral"

        impact_channels: list[str] = []
        raw_channels = output.get("impact_channels")
        if isinstance(raw_channels, list):
            for item in raw_channels:
                text = str(item).strip()
                if text:
                    impact_channels.append(text)

        return GlobalEventImpactResponse(
            summary_ko=summary_ko,
            tone=tone,
            impact_channels=impact_channels,
            raw_output=output,
        )
