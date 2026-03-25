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


def _dedupe_text_items(items: list[str], *, limit: int | None = None) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        normalized = " ".join(text.split()).casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(text)
        if limit is not None and len(deduped) >= limit:
            break
    return deduped


def _normalize_briefing_summary(text: str) -> str:
    normalized = text.replace("\r\n", "\n").strip()
    normalized = "\n\n".join(
        paragraph.strip()
        for paragraph in normalized.split("\n\n")
        if paragraph.strip()
    )
    return normalized


@dataclass(frozen=True)
class NewsEditorialAICurrentSurface:
    surface_key: str
    lead_card_id: str | None
    title: str
    one_line_summary: str
    ranking_score: float
    importance_label: str
    story_state: str
    editorial_reason: str | None
    market_scope: str
    primary_region: str
    published_at: str | None


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
class NewsEditorialAICompareRequest:
    current_surfaces: list[NewsEditorialAICurrentSurface]
    candidates: list[NewsEditorialAIRequest]


@dataclass(frozen=True)
class NewsEditorialAIBriefingLink:
    card_id: str
    surface_key: str
    title: str
    one_line_summary: str
    why_it_matters: str
    market_scope: str
    primary_region: str
    importance_label: str
    ranking_score: float
    published_at: str | None
    source_url: str | None
    publisher: str | None


@dataclass(frozen=True)
class NewsEditorialAIBriefingRequest:
    updated_at: str
    links: list[NewsEditorialAIBriefingLink]


@dataclass(frozen=True)
class NewsEditorialAIResponse:
    story_state: str
    importance_label: str
    editorial_reason: str
    editorial_boost: float
    confidence: float
    raw_output: dict[str, Any]


@dataclass(frozen=True)
class NewsEditorialAIBriefingResponse:
    headline: str
    summary: str
    key_points: list[str]
    confidence: float
    raw_output: dict[str, Any]


class NewsEditorialAIProvider(Protocol):
    provider_name: str

    def is_enabled(self) -> tuple[bool, str | None]:
        ...

    def model_name(self) -> str | None:
        ...

    def compare(self, request: NewsEditorialAICompareRequest) -> dict[str, NewsEditorialAIResponse]:
        ...

    def enrich(self, request: NewsEditorialAIRequest) -> NewsEditorialAIResponse | None:
        ...

    def compose_briefing(self, request: NewsEditorialAIBriefingRequest) -> NewsEditorialAIBriefingResponse | None:
        ...


class DisabledNewsEditorialAIProvider:
    provider_name = "disabled"

    def is_enabled(self) -> tuple[bool, str | None]:
        return False, "feature_flag_disabled"

    def model_name(self) -> str | None:
        return None

    def compare(self, request: NewsEditorialAICompareRequest) -> dict[str, NewsEditorialAIResponse]:
        _ = request
        return {}

    def enrich(self, request: NewsEditorialAIRequest) -> NewsEditorialAIResponse | None:
        _ = request
        return None

    def compose_briefing(self, request: NewsEditorialAIBriefingRequest) -> NewsEditorialAIBriefingResponse | None:
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

    def compare(self, request: NewsEditorialAICompareRequest) -> dict[str, NewsEditorialAIResponse]:
        enabled, reason = self.is_enabled()
        if not enabled:
            logger.info(
                "news_editorial_ai_disabled",
                extra={"reason": reason, "candidate_count": len(request.candidates)},
            )
            return {}
        if not request.candidates:
            return {}

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                payload = self._request_compare_completion(request)
                return self._parse_compare_completion(payload)
            except Exception as error:  # noqa: BLE001
                last_error = error
                logger.warning(
                    "news_editorial_ai_retry",
                    extra={
                        "attempt": attempt,
                        "candidate_count": len(request.candidates),
                        "error": str(error),
                    },
                )
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * (2 ** (attempt - 1)))

        raise RuntimeError("Failed to compare news editorial candidates via AI after retries") from last_error

    def enrich(self, request: NewsEditorialAIRequest) -> NewsEditorialAIResponse | None:
        responses = self.compare(
            NewsEditorialAICompareRequest(
                current_surfaces=[],
                candidates=[request],
            )
        )
        return responses.get(request.cluster_key)

    def compose_briefing(self, request: NewsEditorialAIBriefingRequest) -> NewsEditorialAIBriefingResponse | None:
        enabled, reason = self.is_enabled()
        if not enabled:
            logger.info(
                "news_editorial_ai_briefing_disabled",
                extra={"reason": reason, "link_count": len(request.links)},
            )
            return None
        if not request.links:
            return None

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                payload = self._request_briefing_completion(request)
                return self._parse_briefing_completion(payload)
            except Exception as error:  # noqa: BLE001
                last_error = error
                logger.warning(
                    "news_editorial_ai_briefing_retry",
                    extra={
                        "attempt": attempt,
                        "link_count": len(request.links),
                        "error": str(error),
                    },
                )
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * (2 ** (attempt - 1)))

        raise RuntimeError("Failed to compose rolling news briefing via AI after retries") from last_error

    def _request_compare_completion(self, request: NewsEditorialAICompareRequest) -> dict[str, Any]:
        url = self._chat_completions_url()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        system_prompt = (
            "You are an editorial assistant for a Korean market-news product. "
            "Compare the current active surfaces against the provided top candidates. "
            "Return JSON only with schema: "
            "{items:[{cluster_key, story_state, importance_label, editorial_reason, editorial_boost, confidence}]}. "
            "story_state must be one of NEW, ONGOING, DISCLOSURE_CONFIRMED. "
            "importance_label must be one of high, medium, low. "
            "editorial_boost must be between -0.08 and 0.12. "
            "Use the provided evidence only. "
            "Only include candidates that deserve an explicit editorial override."
        )
        user_payload = {
            "current_surfaces": [
                {
                    "surface_key": surface.surface_key,
                    "lead_card_id": surface.lead_card_id,
                    "title": surface.title,
                    "one_line_summary": surface.one_line_summary,
                    "ranking_score": surface.ranking_score,
                    "importance_label": surface.importance_label,
                    "story_state": surface.story_state,
                    "editorial_reason": surface.editorial_reason,
                    "market_scope": surface.market_scope,
                    "primary_region": surface.primary_region,
                    "published_at": surface.published_at,
                }
                for surface in request.current_surfaces
            ],
            "candidates": [
                {
                    "cluster_key": candidate.cluster_key,
                    "title": candidate.title,
                    "one_line_summary": candidate.one_line_summary,
                    "why_it_matters": candidate.why_it_matters,
                    "market_impact": candidate.market_impact,
                    "market_scope": candidate.market_scope,
                    "primary_region": candidate.primary_region,
                    "event_type": candidate.event_type,
                    "event_subtype": candidate.event_subtype,
                    "impact_direction": candidate.impact_direction,
                    "impact_horizon": candidate.impact_horizon,
                    "source_type": candidate.source_type,
                    "trust_score": candidate.trust_score,
                    "materiality_score": candidate.materiality_score,
                    "novelty_score": candidate.novelty_score,
                    "cross_source_score": candidate.cross_source_score,
                    "attention_score": candidate.attention_score,
                    "evidence_count": candidate.evidence_count,
                    "direct_company_names": candidate.direct_company_names,
                    "direct_company_tickers": candidate.direct_company_tickers,
                    "sector_tags": candidate.sector_tags,
                    "keyword_tags": candidate.keyword_tags,
                    "evidence": candidate.evidence,
                }
                for candidate in request.candidates
            ],
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
        return self._post_completion(url, headers, body)

    def _request_briefing_completion(self, request: NewsEditorialAIBriefingRequest) -> dict[str, Any]:
        url = self._chat_completions_url()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        system_prompt = (
            "You are an editorial briefing assistant for a Korean market-news product. "
            "Write a live market report in Korean using only the provided linked stories. "
            "Return JSON only with schema: "
            "{headline, summary, key_points, confidence}. "
            "headline must be a concise Korean report title. "
            "summary must be a readable Korean market report body with 3 short paragraphs separated by \\n\\n, "
            "using 5 to 8 sentences total. "
            "Paragraph 1 should explain the main market takeaway. "
            "Paragraph 2 should explain why it matters for the Korean market right now. "
            "Paragraph 3 should explain what to keep watching next, including global or disclosure spillover when present. "
            "Do not use bullet prefixes inside summary. "
            "Do not mechanically repeat unreadable filing-style headlines; paraphrase them into plain Korean market language. "
            "key_points must contain 2 to 4 distinct Korean focus lines without repeating the same title or sentence. "
            "Do not invent facts, URLs, or companies that are not present in the input."
        )
        user_payload = {
            "updated_at": request.updated_at,
            "links": [
                {
                    "card_id": link.card_id,
                    "surface_key": link.surface_key,
                    "title": link.title,
                    "one_line_summary": link.one_line_summary,
                    "why_it_matters": link.why_it_matters,
                    "market_scope": link.market_scope,
                    "primary_region": link.primary_region,
                    "importance_label": link.importance_label,
                    "ranking_score": link.ranking_score,
                    "published_at": link.published_at,
                    "source_url": link.source_url,
                    "publisher": link.publisher,
                }
                for link in request.links
            ],
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
        return self._post_completion(url, headers, body)

    def _post_completion(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
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

    def _chat_completions_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        if self.base_url.endswith("/openai") or self.base_url.endswith("/openai/v1") or self.base_url.endswith("/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/v1/chat/completions"

    def _parse_compare_completion(self, payload: dict[str, Any]) -> dict[str, NewsEditorialAIResponse]:
        output = _parse_completion_output(payload, error_prefix="news editorial")
        items = output.get("items")
        if not isinstance(items, list):
            single_cluster_key = str(output.get("cluster_key") or "").strip()
            single_response = self._parse_response_item(output)
            if not single_cluster_key or single_response is None:
                return {}
            return {single_cluster_key: single_response}

        responses: dict[str, NewsEditorialAIResponse] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            cluster_key = str(item.get("cluster_key") or "").strip()
            if not cluster_key:
                continue
            response = self._parse_response_item(item)
            if response is None:
                continue
            responses[cluster_key] = response
        return responses

    def _parse_response_item(self, output: dict[str, Any]) -> NewsEditorialAIResponse | None:
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

    def _parse_briefing_completion(self, payload: dict[str, Any]) -> NewsEditorialAIBriefingResponse:
        output = _parse_completion_output(payload, error_prefix="news briefing")
        headline = str(output.get("headline") or "").strip()
        summary = _normalize_briefing_summary(str(output.get("summary") or ""))
        raw_key_points = output.get("key_points")
        if not headline:
            raise ValueError("news briefing completion headline missing")
        if not summary:
            raise ValueError("news briefing completion summary missing")
        key_points: list[str] = []
        if isinstance(raw_key_points, list):
            key_points = _dedupe_text_items([str(item) for item in raw_key_points], limit=4)
        confidence = _normalize_confidence(output.get("confidence"), default=0.5)
        return NewsEditorialAIBriefingResponse(
            headline=headline,
            summary=summary,
            key_points=key_points,
            confidence=confidence,
            raw_output=output,
        )


def _parse_completion_output(payload: dict[str, Any], *, error_prefix: str) -> dict[str, Any]:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError(f"{error_prefix} completion payload missing choices")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise ValueError(f"{error_prefix} completion first choice is not an object")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise ValueError(f"{error_prefix} completion message missing")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError(f"{error_prefix} completion content missing")
    output = json.loads(content)
    if not isinstance(output, dict):
        raise ValueError(f"{error_prefix} completion output is not an object")
    return output


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
