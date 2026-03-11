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
class CompanyReportLLMRequest:
    company_id: int
    trade_date: str
    company_profile: dict[str, Any]
    input_payload: dict[str, Any]


@dataclass(frozen=True)
class CompanyReportLLMResponse:
    one_line_status: str
    recent_key_events: list[str]
    flow_summary: str
    technical_context_summary: str
    bull_points: list[str]
    bear_points: list[str]
    watch_items: list[str]
    confidence_score: float
    confidence_bucket: str
    confidence_rationale: str
    raw_output: dict[str, Any]


class CompanyReportNarrativeProvider(Protocol):
    provider_name: str

    def is_enabled(self) -> tuple[bool, str | None]:
        ...

    def model_name(self) -> str | None:
        ...

    def generate_report(self, request: CompanyReportLLMRequest) -> CompanyReportLLMResponse | None:
        ...


class DisabledCompanyReportNarrativeProvider:
    provider_name = "disabled"

    def is_enabled(self) -> tuple[bool, str | None]:
        return False, "feature_flag_disabled"

    def model_name(self) -> str | None:
        return None

    def generate_report(self, request: CompanyReportLLMRequest) -> CompanyReportLLMResponse | None:
        _ = request
        return None


class OpenAICompatibleCompanyReportProvider:
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

    def generate_report(self, request: CompanyReportLLMRequest) -> CompanyReportLLMResponse | None:
        enabled, reason = self.is_enabled()
        if not enabled:
            logger.info(
                "company_report_llm_provider_disabled",
                extra={
                    "reason": reason,
                    "company_id": request.company_id,
                    "trade_date": request.trade_date,
                },
            )
            return None

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "company_report_llm_attempt",
                    extra={
                        "attempt": attempt,
                        "company_id": request.company_id,
                        "trade_date": request.trade_date,
                        "provider": self.provider_name,
                        "model": self.model,
                    },
                )
                payload = self._request_completion(request)
                return self._parse_completion(payload)
            except Exception as error:  # noqa: BLE001
                last_error = error
                logger.warning(
                    "company_report_llm_retry",
                    extra={
                        "attempt": attempt,
                        "company_id": request.company_id,
                        "trade_date": request.trade_date,
                        "error": str(error),
                    },
                )
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * (2 ** (attempt - 1)))

        raise RuntimeError("Failed to generate company report via LLM after retries") from last_error

    def _request_completion(self, request: CompanyReportLLMRequest) -> dict[str, Any]:
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        system_prompt = (
            "You are a Korean equity reporting assistant. "
            "Use only provided evidence and do not invent facts. "
            "Do not provide investment advice or buy/sell instructions. "
            "Return JSON only with this schema: "
            "{one_line_status, recent_key_events[], flow_summary, technical_context_summary, "
            "bull_points[], bear_points[], watch_items[], confidence{score,bucket,rationale}}."
        )
        user_payload = {
            "trade_date": request.trade_date,
            "company": request.company_profile,
            "inputs": request.input_payload,
            "constraints": {
                "language": "ko",
                "max_items_per_list": 4,
                "must_be_source_grounded": True,
                "forbidden": ["매수", "매도", "목표주가", "투자 추천"],
            },
        }

        body = {
            "model": self.model,
            "temperature": 0.1,
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

    def _parse_completion(self, payload: dict[str, Any]) -> CompanyReportLLMResponse:
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
        one_line_status = str(output.get("one_line_status") or "데이터 기반 상태 요약 생성 실패").strip()
        flow_summary = str(output.get("flow_summary") or "수급 데이터가 제한적입니다.").strip()
        technical_context_summary = str(
            output.get("technical_context_summary") or "기술적/맥락 데이터가 제한적입니다."
        ).strip()

        if not one_line_status:
            raise ValueError("LLM completion one_line_status missing")

        recent_key_events = _normalize_str_list(output.get("recent_key_events"), max_items=4)
        bull_points = _normalize_str_list(output.get("bull_points"), max_items=4)
        bear_points = _normalize_str_list(output.get("bear_points"), max_items=4)
        watch_items = _normalize_str_list(output.get("watch_items"), max_items=4)

        confidence = output.get("confidence")
        confidence_score = 0.5
        confidence_bucket = "medium"
        confidence_rationale = "llm_generated"

        if isinstance(confidence, dict):
            confidence_score = _normalize_score(confidence.get("score"), default=0.5)
            confidence_bucket = _normalize_bucket(
                str(confidence.get("bucket") or "medium").strip().lower(),
                confidence_score,
            )
            confidence_rationale = str(confidence.get("rationale") or "llm_generated").strip() or "llm_generated"

        return CompanyReportLLMResponse(
            one_line_status=one_line_status,
            recent_key_events=recent_key_events,
            flow_summary=flow_summary,
            technical_context_summary=technical_context_summary,
            bull_points=bull_points,
            bear_points=bear_points,
            watch_items=watch_items,
            confidence_score=confidence_score,
            confidence_bucket=confidence_bucket,
            confidence_rationale=confidence_rationale,
            raw_output=output,
        )

    def _parse_content_json(self, content: str) -> dict[str, Any]:
        candidate = content.strip()
        block_match = _JSON_BLOCK_RE.search(candidate)
        if block_match:
            candidate = block_match.group(1).strip()

        payload = json.loads(candidate)
        if not isinstance(payload, dict):
            raise ValueError("LLM completion JSON content is not an object")
        return payload


def _normalize_str_list(value: object, *, max_items: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [str(item).strip() for item in value if str(item).strip()]
    return items[:max(0, max_items)]


def _normalize_score(value: object, *, default: float) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = default
    return max(0.0, min(1.0, score))


def _normalize_bucket(value: str, score: float) -> str:
    if value in {"low", "medium", "high"}:
        return value
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"
