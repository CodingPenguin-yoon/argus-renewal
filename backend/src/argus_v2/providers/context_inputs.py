from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import html
import json
import logging
import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlparse

import httpx

from ...config.env import Settings
from ..db import get_connection, resolve_db_path, utcnow_iso
from ..storage import ArgusV2Storage
from .kis_common import as_float, load_json_file, pick_float, pick_text
from .kis_auth import KisAuthClient
from .kis_market_reaction import KisMarketReactionService
from .models import (
    BriefingProviderBatch,
    MarketReactionSectorRecord,
    MarketReactionSnapshotRecord,
    NewsTriggerRecord,
)


logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

DEFAULT_RSS_URLS = (
    "https://www.mk.co.kr/rss/30100041/",
    "https://www.mk.co.kr/rss/50200011/",
)
DEFAULT_NAVER_BASE_URL = "https://openapi.naver.com"
DEFAULT_NAVER_NEWS_PATH = "/v1/search/news.json"
DEFAULT_DART_BASE_URL = "https://opendart.fss.or.kr"
DEFAULT_DART_LIST_PATH = "/api/list.json"
DEFAULT_KIS_TOKEN_CACHE_PATH = "data/kis_token_cache.json"
KIS_MARKET_REACTION_PROVIDERS = {"kis", "kis_api", "kis_index"}
DEFAULT_NEWS_AI_BASE_URL = "https://api.openai.com"
DEFAULT_NEWS_AI_CHAT_PATH = "/v1/chat/completions"
DEFAULT_GEMINI_NEWS_AI_BASE_URL = "https://generativelanguage.googleapis.com"
DEFAULT_GEMINI_NEWS_AI_PATH = "/v1beta/models/{model}:generateContent"
NEWS_AI_SYSTEM_PROMPT = (
    "You classify Korean market news for a KOSPI/KOSDAQ derivatives dashboard. "
    "Return JSON only. Do not recommend trades. Do not invent causal links. "
    "If the item is weakly related, promotional, or source credibility is unclear, set should_use=false."
)
NEWS_AI_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "should_use",
        "impact",
        "relevance_score",
        "connection_strength",
        "affected_factors",
        "summary",
        "reason",
        "confidence",
    ],
    "properties": {
        "should_use": {"type": "boolean"},
        "impact": {"type": "string", "enum": ["positive", "neutral", "negative"]},
        "relevance_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "connection_strength": {"type": "string", "enum": ["strong", "medium", "weak", "unclear"]},
        "affected_factors": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
        "summary": {"type": "string", "maxLength": 160},
        "reason": {"type": "string", "maxLength": 240},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
}
GEMINI_NEWS_AI_DECISION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "should_use": {"type": "BOOLEAN"},
        "impact": {"type": "STRING", "enum": ["positive", "neutral", "negative"]},
        "relevance_score": {"type": "INTEGER"},
        "connection_strength": {"type": "STRING", "enum": ["strong", "medium", "weak", "unclear"]},
        "affected_factors": {"type": "ARRAY", "items": {"type": "STRING"}},
        "summary": {"type": "STRING"},
        "reason": {"type": "STRING"},
        "confidence": {"type": "STRING", "enum": ["high", "medium", "low"]},
    },
    "required": list(NEWS_AI_DECISION_SCHEMA["required"]),
    "propertyOrdering": list(NEWS_AI_DECISION_SCHEMA["required"]),
}


@dataclass(frozen=True)
class ContextProviderResult:
    provider_key: str
    status: str
    run_id: int | None
    observed_count: int
    sample_count: int
    market_reaction_snapshot_count: int
    news_trigger_count: int
    error: str | None = None


@dataclass(frozen=True)
class ContextCollectionResult:
    db_path: str
    trade_date: str
    snapshot_time: str
    providers: list[ContextProviderResult]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NewsAiSmokeResult:
    provider: str
    model: str
    status: str
    should_use: bool
    impact: str
    relevance_score: int
    connection_strength: str
    confidence: str
    reason: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ArgusMarketReactionService:
    def __init__(self, *, provider: str, file_path: str | None = None) -> None:
        self.provider = provider.strip().lower()
        self.file_path = file_path

    def fetch_snapshot(self, *, trade_date: date, snapshot_time: datetime | None = None) -> BriefingProviderBatch:
        enabled, reason = self.is_enabled()
        if not enabled:
            return BriefingProviderBatch(records=[], disabled_reason=reason)

        snapshot_iso = _snapshot_iso(snapshot_time or datetime.now(timezone.utc))
        if self.provider == "mock":
            return BriefingProviderBatch(
                records=[_mock_market_reaction(trade_date=trade_date, snapshot_time=snapshot_iso)],
                metadata={"provider": "mock"},
            )

        payload = load_json_file(self.file_path or "")
        row = _pick_dated_payload(payload=payload, trade_date=trade_date)
        return BriefingProviderBatch(
            records=[self._normalize_file_row(row=row, trade_date=trade_date, snapshot_time=snapshot_iso)],
            metadata={"provider": "file", "file_path": self.file_path},
        )

    def is_enabled(self) -> tuple[bool, str | None]:
        if self.provider in {"", "disabled"}:
            return False, "feature_flag_disabled"
        if self.provider == "mock":
            return True, None
        if self.provider == "file":
            return (True, None) if self.file_path else (False, "missing_file_path")
        return False, f"unsupported_provider:{self.provider}"

    def _normalize_file_row(
        self,
        *,
        row: dict[str, Any],
        trade_date: date,
        snapshot_time: str,
    ) -> MarketReactionSnapshotRecord:
        source = pick_text(row, ("source_name", "source")) or "argus_v2.market_reaction_file"
        observed_at = pick_text(row, ("snapshot_time", "observed_at")) or snapshot_time
        return MarketReactionSnapshotRecord(
            source_name=source,
            trade_date=pick_text(row, ("trade_date", "date")) or trade_date.isoformat(),
            snapshot_time=observed_at,
            kospi_change_rate=pick_float(row, ("kospi_change_rate", "kospi", "kospi_rate")),
            kosdaq_change_rate=pick_float(row, ("kosdaq_change_rate", "kosdaq", "kosdaq_rate")),
            kospi200_futures_change_rate=pick_float(row, ("kospi200_futures_change_rate", "futures_change_rate")),
            advancing_count=_as_int(row.get("advancing_count") or row.get("advancers")),
            declining_count=_as_int(row.get("declining_count") or row.get("decliners")),
            spot_foreign_net_buy=pick_float(row, ("spot_foreign_net_buy", "foreign_spot_net_buy", "foreign_net_buy")),
            spot_institution_net_buy=pick_float(
                row,
                ("spot_institution_net_buy", "institution_spot_net_buy", "institution_net_buy"),
            ),
            spot_individual_net_buy=pick_float(row, ("spot_individual_net_buy", "individual_spot_net_buy", "individual_net_buy")),
            summary=pick_text(row, ("summary", "memo")) or "",
            freshness_state=pick_text(row, ("freshness_state", "freshness")) or "partial",
            source_url=pick_text(row, ("source_url", "url")),
            source_record_id=pick_text(row, ("source_record_id", "id")),
            raw_payload=row,
            strong_sectors=_sector_records(row.get("strong_sectors"), role="strong", observed_at=observed_at, source=source),
            weak_sectors=_sector_records(row.get("weak_sectors"), role="weak", observed_at=observed_at, source=source),
        )


class ArgusNewsTriggerService:
    def __init__(
        self,
        *,
        provider: str,
        file_path: str | None = None,
        rss_urls: str | None = None,
        query: str | None = None,
        limit: int = 8,
        lookback_hours: int = 24,
        naver_client_id: str | None = None,
        naver_client_secret: str | None = None,
        naver_base_url: str = DEFAULT_NAVER_BASE_URL,
        naver_search_path: str = DEFAULT_NAVER_NEWS_PATH,
        naver_display: int = 20,
        naver_page_limit: int = 2,
        news_ai_provider: str = "disabled",
        news_ai_base_url: str = DEFAULT_NEWS_AI_BASE_URL,
        news_ai_chat_path: str = DEFAULT_NEWS_AI_CHAT_PATH,
        news_ai_api_key: str | None = None,
        news_ai_model: str | None = None,
        news_ai_timeout_seconds: float | None = None,
        dart_api_key: str | None = None,
        dart_base_url: str = DEFAULT_DART_BASE_URL,
        dart_list_path: str = DEFAULT_DART_LIST_PATH,
        dart_corp_cls: str = "Y,K",
        dart_pblntf_ty: str = "B,I",
        dart_lookback_days: int = 1,
        dart_page_count: int = 50,
        macro_events_provider: str = "disabled",
        macro_events_file_path: str | None = None,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.provider = provider.strip().lower()
        self.file_path = file_path
        self.rss_urls = _split_csv(rss_urls) or list(DEFAULT_RSS_URLS)
        self.query_terms = _split_csv(query)
        self.limit = max(1, limit)
        self.lookback_hours = max(1, lookback_hours)
        self.naver_client_id = (naver_client_id or "").strip()
        self.naver_client_secret = (naver_client_secret or "").strip()
        self.naver_base_url = naver_base_url.rstrip("/")
        self.naver_search_path = naver_search_path
        self.naver_display = max(1, min(naver_display, 100))
        self.naver_page_limit = max(1, naver_page_limit)
        self.news_ai_provider = news_ai_provider.strip().lower()
        if self.news_ai_provider in {"gemini", "google_gemini"} and news_ai_base_url == DEFAULT_NEWS_AI_BASE_URL:
            news_ai_base_url = DEFAULT_GEMINI_NEWS_AI_BASE_URL
        if self.news_ai_provider in {"gemini", "google_gemini"} and news_ai_chat_path == DEFAULT_NEWS_AI_CHAT_PATH:
            news_ai_chat_path = DEFAULT_GEMINI_NEWS_AI_PATH
        self.news_ai_base_url = news_ai_base_url.rstrip("/")
        self.news_ai_chat_path = news_ai_chat_path
        self.news_ai_api_key = (news_ai_api_key or "").strip()
        self.news_ai_model = (news_ai_model or "").strip()
        self.news_ai_timeout_seconds = max(1.0, news_ai_timeout_seconds or timeout_seconds)
        self.dart_api_key = (dart_api_key or "").strip()
        self.dart_base_url = dart_base_url.rstrip("/")
        self.dart_list_path = dart_list_path
        self.dart_corp_cls = _split_csv(dart_corp_cls)
        self.dart_pblntf_ty = _split_csv(dart_pblntf_ty)
        self.dart_lookback_days = max(1, dart_lookback_days)
        self.dart_page_count = max(1, min(dart_page_count, 100))
        self.macro_events_provider = macro_events_provider.strip().lower()
        self.macro_events_file_path = macro_events_file_path
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(1, max_retries)
        self.backoff_seconds = max(0.0, backoff_seconds)
        self._http_client = http_client

    def fetch_triggers(self, *, trade_date: date, snapshot_time: datetime | None = None) -> BriefingProviderBatch:
        enabled, reason = self.is_enabled()
        if not enabled:
            return BriefingProviderBatch(records=[], disabled_reason=reason)

        snapshot_at = (snapshot_time or datetime.now(timezone.utc)).astimezone(timezone.utc)
        provider, records, metadata = self._fetch_raw_records(trade_date=trade_date, snapshot_time=snapshot_at)
        return self._records_batch(records=records, provider=provider, metadata=metadata)

    def fetch_feed(self, *, trade_date: date, snapshot_time: datetime | None = None) -> BriefingProviderBatch:
        enabled, reason = self.is_enabled()
        if not enabled:
            return BriefingProviderBatch(records=[], disabled_reason=reason)

        snapshot_at = (snapshot_time or datetime.now(timezone.utc)).astimezone(timezone.utc)
        provider, records, metadata = self._fetch_raw_records(trade_date=trade_date, snapshot_time=snapshot_at)
        return self._feed_batch(records=records, provider=provider, metadata=metadata)

    def _fetch_raw_records(
        self,
        *,
        trade_date: date,
        snapshot_time: datetime,
    ) -> tuple[str, list[NewsTriggerRecord], dict[str, Any]]:
        if self.provider == "mock":
            return "mock", _mock_news_triggers(snapshot_time=_snapshot_iso(snapshot_time)), {}
        if self.provider == "file":
            payload = load_json_file(self.file_path or "")
            rows = _pick_news_rows(payload=payload, trade_date=trade_date)
            records = [self._normalize_file_row(row=row, index=index, snapshot_time=snapshot_time) for index, row in enumerate(rows)]
            return "file", records, {"file_path": self.file_path, "row_count": len(rows)}
        if self.provider == "naver":
            return "naver", self._fetch_naver_records(snapshot_time=snapshot_time), {}
        if self.provider == "dart":
            return "dart", self._fetch_dart_records(trade_date=trade_date), {}
        if self.provider == "macro":
            return "macro", self._fetch_macro_records(trade_date=trade_date, snapshot_time=snapshot_time), {}
        if self.provider == "hybrid":
            records = []
            if self.rss_urls:
                records.extend(self._fetch_rss_records(snapshot_time=snapshot_time))
            if self.naver_client_id and self.naver_client_secret:
                records.extend(self._fetch_naver_records(snapshot_time=snapshot_time))
            if self.dart_api_key:
                records.extend(self._fetch_dart_records(trade_date=trade_date))
            records.extend(self._fetch_macro_records(trade_date=trade_date, snapshot_time=snapshot_time))
            return "hybrid", records, {}

        return "rss", self._fetch_rss_records(snapshot_time=snapshot_time), {}

    def is_enabled(self) -> tuple[bool, str | None]:
        if self.provider in {"", "disabled"}:
            return False, "feature_flag_disabled"
        if self.provider == "mock":
            return True, None
        if self.provider == "file":
            return (True, None) if self.file_path else (False, "missing_file_path")
        if self.provider == "rss":
            return (True, None) if self.rss_urls else (False, "missing_rss_urls")
        if self.provider == "naver":
            if not self.naver_client_id or not self.naver_client_secret:
                return False, "missing_naver_credentials"
            return True, None
        if self.provider == "dart":
            return (True, None) if self.dart_api_key else (False, "missing_dart_api_key")
        if self.provider == "macro":
            return self._macro_events_enabled()
        if self.provider == "hybrid":
            macro_enabled, _ = self._macro_events_enabled()
            if self.rss_urls or (self.naver_client_id and self.naver_client_secret) or self.dart_api_key or macro_enabled:
                return True, None
            return False, "missing_hybrid_sources"
        return False, f"unsupported_provider:{self.provider}"

    def _macro_events_enabled(self) -> tuple[bool, str | None]:
        if self.macro_events_provider in {"", "disabled"}:
            return False, "feature_flag_disabled"
        if self.macro_events_provider == "mock":
            return True, None
        if self.macro_events_provider == "file":
            return (True, None) if self.macro_events_file_path else (False, "missing_macro_file_path")
        return False, f"unsupported_macro_provider:{self.macro_events_provider}"

    def _records_batch(
        self,
        *,
        records: list[NewsTriggerRecord],
        provider: str,
        metadata: dict[str, Any] | None = None,
    ) -> BriefingProviderBatch:
        candidates = self._ai_candidate_records(records=records, provider=provider)
        enriched = [self._with_ai_enrichment(record) for record in candidates]
        ranked = _deduplicate_triggers(enriched)
        selected = [record for record in ranked if _ai_should_use_from_raw(record)]
        selected.sort(
            key=lambda item: (
                _ai_relevance_score_from_raw(item),
                _ai_confidence_rank(item),
                item.published_at or "",
            ),
            reverse=True,
        )
        limited = selected[: self.limit]
        return BriefingProviderBatch(
            records=limited,
            metadata={
                "provider": provider,
                "feed_urls": self.rss_urls if provider in {"rss", "hybrid"} else [],
                "query_terms": self.query_terms,
                "semantic_filter": "ai_enrichment",
                "news_ai_provider": self.news_ai_provider or "disabled",
                "input_count": len(records),
                "ai_candidate_count": len(candidates),
                "ai_enriched_count": len(enriched),
                "ai_selected_count": len(selected),
                "ai_error_count": sum(1 for record in enriched if _ai_reason_from_raw(record).startswith("news_ai_error:")),
                "ai_disabled_count": sum(1 for record in enriched if _ai_reason_from_raw(record) == "news_ai_disabled"),
                "filtered_count": len(limited),
                "expected_count": len(limited),
                **(metadata or {}),
            },
        )

    def _feed_batch(
        self,
        *,
        records: list[NewsTriggerRecord],
        provider: str,
        metadata: dict[str, Any] | None = None,
    ) -> BriefingProviderBatch:
        ranked = _deduplicate_triggers(records)
        ranked.sort(key=lambda item: (item.published_at or "", item.title), reverse=True)
        limited = ranked[: self.limit]
        return BriefingProviderBatch(
            records=limited,
            metadata={
                "provider": provider,
                "feed_urls": self.rss_urls if provider in {"rss", "hybrid"} else [],
                "query_terms": self.query_terms,
                "semantic_filter": "none",
                "input_count": len(records),
                "filtered_count": len(limited),
                "expected_count": len(limited),
                **(metadata or {}),
            },
        )

    def _ai_candidate_records(self, *, records: list[NewsTriggerRecord], provider: str) -> list[NewsTriggerRecord]:
        ranked = list(records)
        ranked.sort(key=lambda record: record.published_at or "", reverse=True)

        if provider in {"rss", "hybrid", "naver"} and self.query_terms:
            matched = [record for record in ranked if _record_matches_query_terms(record=record, query_terms=self.query_terms)]
            if matched:
                ranked = matched

        candidate_multiplier = 2 if self.query_terms else 3
        candidate_limit = min(max(self.limit * candidate_multiplier, self.limit), 12)
        return ranked[:candidate_limit]

    def _with_ai_enrichment(self, record: NewsTriggerRecord) -> NewsTriggerRecord:
        raw_payload = record.raw_payload if isinstance(record.raw_payload, dict) else {}
        explicit_decision = _extract_news_ai_decision(raw_payload)
        if explicit_decision is not None:
            return _apply_news_ai_decision(record=record, decision=explicit_decision, provider="explicit")

        if self.news_ai_provider in {"", "disabled"}:
            return _apply_news_ai_decision(
                record=record,
                decision=_no_news_ai_decision(reason="news_ai_disabled"),
                provider="disabled",
            )

        if self.news_ai_provider in {"openai", "openai_compatible", "gemini", "google_gemini"}:
            try:
                return _apply_news_ai_decision(
                    record=record,
                    decision=self._request_news_ai_decision(record),
                    provider=self.news_ai_provider,
                )
            except Exception as error:
                logger.warning("news_ai_enrichment_failed title=%r error=%s", record.title, error)
                return _apply_news_ai_decision(
                    record=record,
                    decision=_no_news_ai_decision(reason=f"news_ai_error:{error.__class__.__name__}"),
                    provider=self.news_ai_provider,
                )

        return _apply_news_ai_decision(
            record=record,
            decision=_no_news_ai_decision(reason=f"unsupported_news_ai_provider:{self.news_ai_provider}"),
            provider=self.news_ai_provider or "disabled",
        )

    def _request_news_ai_decision(self, record: NewsTriggerRecord) -> dict[str, Any]:
        if not self.news_ai_api_key:
            raise ValueError("missing_news_ai_api_key")
        if not self.news_ai_model:
            raise ValueError("missing_news_ai_model")
        if self.news_ai_provider in {"gemini", "google_gemini"}:
            return self._request_gemini_news_ai_decision(record)
        return self._request_openai_compatible_news_ai_decision(record)

    def _request_openai_compatible_news_ai_decision(self, record: NewsTriggerRecord) -> dict[str, Any]:
        url = f"{self.news_ai_base_url}{self.news_ai_chat_path}"
        headers = {
            "Authorization": f"Bearer {self.news_ai_api_key}",
            "Content-Type": "application/json",
        }
        request_payload = {
            "model": self.news_ai_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": NEWS_AI_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": (
                                "Decide whether this item should affect today's Korean index/options market read. "
                                "Use source credibility, macro/index relevance, derivative relevance, and actual market linkage. "
                                "Ignore promotions, stock-picking content, entertainment, and weakly related items."
                            ),
                            "output_schema": {
                                **NEWS_AI_DECISION_SCHEMA,
                                "description": "Return one JSON object matching this schema.",
                            },
                            "news": {
                                "title": record.title,
                                "summary": record.summary,
                                "source": record.source,
                                "source_url": record.source_url,
                                "published_at": record.published_at,
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        payload = self._post_json(url=url, headers=headers, payload=request_payload)
        return _parse_news_ai_response(payload)

    def _request_gemini_news_ai_decision(self, record: NewsTriggerRecord) -> dict[str, Any]:
        path = self.news_ai_chat_path.format(model=self.news_ai_model)
        url = f"{self.news_ai_base_url}{path}"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.news_ai_api_key,
        }
        request_payload = {
            "systemInstruction": {"parts": [{"text": NEWS_AI_SYSTEM_PROMPT}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "task": (
                                        "Decide whether this item should affect today's Korean index/options market read. "
                                        "Use source credibility, macro/index relevance, derivative relevance, and actual market linkage. "
                                        "Ignore promotions, stock-picking content, entertainment, and weakly related items."
                                    ),
                                    "news": {
                                        "title": record.title,
                                        "summary": record.summary,
                                        "source": record.source,
                                        "source_url": record.source_url,
                                        "published_at": record.published_at,
                                    },
                                },
                                ensure_ascii=False,
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseSchema": GEMINI_NEWS_AI_DECISION_SCHEMA,
            },
        }
        payload = self._post_json(url=url, headers=headers, payload=request_payload)
        return _parse_news_ai_response(payload)

    def _post_json(self, *, url: str, headers: dict[str, str], payload: dict[str, Any]) -> Any:
        if self._http_client is not None:
            response = self._http_client.post(url, headers=headers, json=payload, timeout=self.news_ai_timeout_seconds)
        else:
            with httpx.Client() as client:
                response = client.post(url, headers=headers, json=payload, timeout=self.news_ai_timeout_seconds)
        response.raise_for_status()
        return response.json()

    def _normalize_file_row(self, *, row: dict[str, Any], index: int, snapshot_time: datetime) -> NewsTriggerRecord:
        title = pick_text(row, ("title", "headline")) or f"뉴스 트리거 {index + 1}"
        summary = pick_text(row, ("summary", "description", "memo")) or ""
        published_at = pick_text(row, ("published_at", "pub_date", "observed_at")) or _snapshot_iso(snapshot_time)
        return NewsTriggerRecord(
            id=pick_text(row, ("id", "external_id", "source_record_id")) or _stable_trigger_id(title=title, published_at=published_at),
            title=title,
            summary=summary,
            impact=_valid_impact(pick_text(row, ("impact", "tone")) or "neutral"),
            source=pick_text(row, ("source", "source_name", "publisher")) or "argus_v2.news_trigger_file",
            published_at=published_at,
            connection_strength=_valid_connection_strength(pick_text(row, ("connection_strength", "strength")) or "unclear"),
            freshness=pick_text(row, ("freshness", "freshness_state")) or "partial",
            source_url=pick_text(row, ("source_url", "url", "link")),
            raw_payload=row,
        )

    def _fetch_rss_records(self, *, snapshot_time: datetime) -> list[NewsTriggerRecord]:
        cutoff = snapshot_time - timedelta(hours=self.lookback_hours)
        records: list[NewsTriggerRecord] = []
        for feed_url in self.rss_urls:
            feed_title, items = self._request_feed(feed_url=feed_url)
            for item in items:
                record = self._rss_item_to_record(item=item, feed_url=feed_url, feed_title=feed_title)
                if record is None:
                    continue
                published_at = _parse_iso(record.published_at)
                if published_at is not None and published_at < cutoff:
                    continue
                records.append(record)

        records.sort(key=lambda item: item.published_at or "", reverse=True)
        return records

    def _fetch_naver_records(self, *, snapshot_time: datetime) -> list[NewsTriggerRecord]:
        cutoff = snapshot_time - timedelta(hours=self.lookback_hours)
        records: list[NewsTriggerRecord] = []
        queries = self.query_terms or ["코스피"]
        for query in queries:
            for page_index in range(self.naver_page_limit):
                start = 1 + page_index * self.naver_display
                payload = self._request_naver_page(query=query, start=start)
                rows = payload.get("items")
                if not isinstance(rows, list):
                    raise ValueError("naver_news_items_missing")
                if not rows:
                    break
                for index, row in enumerate(rows):
                    if not isinstance(row, dict):
                        continue
                    record = self._naver_item_to_record(row=row, query=query, index=index)
                    if record is None:
                        continue
                    published_at = _parse_iso(record.published_at)
                    if published_at is not None and published_at < cutoff:
                        continue
                    records.append(record)
                if len(rows) < self.naver_display:
                    break
        return records

    def _request_naver_page(self, *, query: str, start: int) -> dict[str, Any]:
        url = f"{self.naver_base_url}{self.naver_search_path}"
        headers = {
            "X-Naver-Client-Id": self.naver_client_id,
            "X-Naver-Client-Secret": self.naver_client_secret,
        }
        params = {
            "query": query,
            "display": str(self.naver_display),
            "start": str(start),
            "sort": "date",
        }
        payload = self._request_json(url=url, headers=headers, params=params)
        if not isinstance(payload, dict):
            raise ValueError("naver_news_payload_invalid")
        return payload

    def _naver_item_to_record(self, *, row: dict[str, Any], query: str, index: int) -> NewsTriggerRecord | None:
        title = _strip_html(_as_text(row.get("title")))
        summary = _strip_html(_as_text(row.get("description")))
        link = _as_text(row.get("originallink")) or _as_text(row.get("link"))
        published_at = _parse_rss_date(_as_text(row.get("pubDate")))
        if not title and not link:
            return None
        published_value = _snapshot_iso(published_at) if published_at is not None else None
        return NewsTriggerRecord(
            id=_stable_trigger_id(title=title or f"naver-{index}", published_at=published_value or link or query),
            title=title or link or f"Naver news {index + 1}",
            summary=summary,
            impact="neutral",
            source=_source_from_url(link or "naver.com"),
            published_at=published_value,
            connection_strength="unclear",
            freshness="fresh",
            source_url=link,
            raw_payload={
                "title": row.get("title"),
                "originallink": row.get("originallink"),
                "link": row.get("link"),
                "description": row.get("description"),
                "pubDate": row.get("pubDate"),
                "query": query,
            },
        )

    def _fetch_dart_records(self, *, trade_date: date) -> list[NewsTriggerRecord]:
        start_date = trade_date - timedelta(days=self.dart_lookback_days - 1)
        records: list[NewsTriggerRecord] = []
        corp_classes = self.dart_corp_cls or [""]
        disclosure_types = self.dart_pblntf_ty or [""]
        for corp_cls in corp_classes:
            for disclosure_type in disclosure_types:
                payload = self._request_dart_page(
                    start_date=start_date,
                    end_date=trade_date,
                    corp_cls=corp_cls,
                    disclosure_type=disclosure_type,
                )
                rows = payload.get("list") if isinstance(payload, dict) else None
                if rows is None and isinstance(payload, dict) and str(payload.get("status")) in {"013", "014"}:
                    continue
                if not isinstance(rows, list):
                    raise ValueError("dart_list_missing")
                for row in rows:
                    if isinstance(row, dict):
                        records.append(self._dart_row_to_record(row=row))
        return records

    def _fetch_macro_records(self, *, trade_date: date, snapshot_time: datetime) -> list[NewsTriggerRecord]:
        enabled, _ = self._macro_events_enabled()
        if not enabled:
            return []
        if self.macro_events_provider == "mock":
            return _mock_macro_triggers(snapshot_time=_snapshot_iso(snapshot_time))

        payload = load_json_file(self.macro_events_file_path or "")
        rows = _pick_macro_rows(payload=payload, trade_date=trade_date)
        return [
            self._macro_row_to_record(row=row, index=index, snapshot_time=snapshot_time)
            for index, row in enumerate(rows)
        ]

    def _macro_row_to_record(self, *, row: dict[str, Any], index: int, snapshot_time: datetime) -> NewsTriggerRecord:
        observed_at = pick_text(row, ("observed_at", "published_at", "event_time")) or _snapshot_iso(snapshot_time)
        event_type = pick_text(row, ("event_type", "type", "category")) or "macro"
        title = pick_text(row, ("title", "name", "event_name")) or f"매크로 이벤트 {index + 1}"
        value = pick_text(row, ("value", "actual"))
        unit = pick_text(row, ("unit",))
        previous = pick_text(row, ("previous", "prev"))
        summary = pick_text(row, ("summary", "description", "memo"))
        if not summary:
            current_text = f"{value}{unit or ''}" if value else "값 미수신"
            previous_text = f", 이전 {previous}" if previous else ""
            summary = f"{event_type}: 현재 {current_text}{previous_text}"
        return NewsTriggerRecord(
            id=pick_text(row, ("id", "external_id", "source_record_id")) or _stable_trigger_id(title=title, published_at=observed_at),
            title=title,
            summary=summary,
            impact=_valid_impact(pick_text(row, ("impact", "tone")) or "neutral"),
            source=pick_text(row, ("source", "source_name")) or "ARGUS_MACRO_EVENT",
            published_at=observed_at,
            connection_strength=_valid_connection_strength(pick_text(row, ("connection_strength", "strength")) or "unclear"),
            freshness=pick_text(row, ("freshness", "freshness_state")) or "fresh",
            source_url=pick_text(row, ("source_url", "url")),
            raw_payload=row,
        )

    def _request_dart_page(
        self,
        *,
        start_date: date,
        end_date: date,
        corp_cls: str,
        disclosure_type: str,
    ) -> dict[str, Any]:
        url = f"{self.dart_base_url}{self.dart_list_path}"
        params = {
            "crtfc_key": self.dart_api_key,
            "bgn_de": start_date.strftime("%Y%m%d"),
            "end_de": end_date.strftime("%Y%m%d"),
            "last_reprt_at": "N",
            "corp_cls": corp_cls,
            "pblntf_ty": disclosure_type,
            "sort": "date",
            "sort_mth": "desc",
            "page_no": "1",
            "page_count": str(self.dart_page_count),
        }
        payload = self._request_json(url=url, headers={}, params={key: value for key, value in params.items() if value})
        if not isinstance(payload, dict):
            raise ValueError("dart_payload_invalid")
        return payload

    def _dart_row_to_record(self, *, row: dict[str, Any]) -> NewsTriggerRecord:
        corp_name = pick_text(row, ("corp_name", "corp")) or "공시회사"
        report_name = pick_text(row, ("report_nm", "report_name")) or "공시"
        receipt_no = pick_text(row, ("rcept_no", "receipt_no")) or _stable_trigger_id(title=corp_name, published_at=report_name)
        receipt_date = pick_text(row, ("rcept_dt", "receipt_date"))
        published_at = _dart_date_to_iso(receipt_date)
        title = f"{corp_name} {report_name}"
        summary = f"DART 공시: {report_name}"
        viewer_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}" if receipt_no else None
        return NewsTriggerRecord(
            id=f"dart-{receipt_no}",
            title=title,
            summary=summary,
            impact="neutral",
            source="DART",
            published_at=published_at,
            connection_strength="unclear",
            freshness="fresh",
            source_url=viewer_url,
            raw_payload={
                "corp_name": row.get("corp_name"),
                "corp_code": row.get("corp_code"),
                "stock_code": row.get("stock_code"),
                "corp_cls": row.get("corp_cls"),
                "report_nm": row.get("report_nm"),
                "rcept_no": row.get("rcept_no"),
                "rcept_dt": row.get("rcept_dt"),
                "flr_nm": row.get("flr_nm"),
                "rm": row.get("rm"),
            },
        )

    def _request_json(self, *, url: str, headers: dict[str, str], params: dict[str, str]) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._do_json_request(url=url, headers=headers, params=params)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as error:
                last_error = error
                if attempt < self.max_retries and self.backoff_seconds > 0:
                    import time

                    time.sleep(self.backoff_seconds)
        raise RuntimeError(f"json_fetch_failed:{url}") from last_error

    def _do_json_request(self, *, url: str, headers: dict[str, str], params: dict[str, str]) -> httpx.Response:
        if self._http_client is not None:
            return self._http_client.get(url, headers=headers, params=params, timeout=self.timeout_seconds)
        with httpx.Client() as client:
            return client.get(url, headers=headers, params=params, timeout=self.timeout_seconds)

    def _request_feed(self, *, feed_url: str) -> tuple[str | None, list[ET.Element]]:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._do_request(feed_url=feed_url)
                response.raise_for_status()
                root = ET.fromstring(response.text)
                channel = root.find("channel")
                if channel is None:
                    raise ValueError("rss_channel_missing")
                return channel.findtext("title"), list(channel.findall("item"))
            except (httpx.HTTPError, ET.ParseError, ValueError) as error:
                last_error = error
                if attempt < self.max_retries and self.backoff_seconds > 0:
                    import time

                    time.sleep(self.backoff_seconds)
        raise RuntimeError(f"rss_fetch_failed:{feed_url}") from last_error

    def _do_request(self, *, feed_url: str) -> httpx.Response:
        headers = {"User-Agent": "ArgusRenewal/0.1"}
        if self._http_client is not None:
            return self._http_client.get(feed_url, headers=headers, timeout=self.timeout_seconds)
        with httpx.Client() as client:
            return client.get(feed_url, headers=headers, timeout=self.timeout_seconds)

    def _rss_item_to_record(
        self,
        *,
        item: ET.Element,
        feed_url: str,
        feed_title: str | None,
    ) -> NewsTriggerRecord | None:
        title = _strip_html(item.findtext("title"))
        link = _strip_html(item.findtext("link"))
        summary = _strip_html(item.findtext("description"))
        published_at = _parse_rss_date(item.findtext("pubDate"))
        if not title and not link:
            return None
        source = _strip_html(feed_title) or _source_from_url(link or feed_url)
        published_value = _snapshot_iso(published_at) if published_at is not None else None
        return NewsTriggerRecord(
            id=_stable_trigger_id(title=title, published_at=published_value or link or feed_url),
            title=title or link,
            summary=summary,
            impact="neutral",
            source=source,
            published_at=published_value,
            connection_strength="unclear",
            freshness="fresh",
            source_url=link or feed_url,
            raw_payload={
                "title": title,
                "link": link,
                "description": summary,
                "pubDate": item.findtext("pubDate"),
                "feed_url": feed_url,
                "feed_title": feed_title,
            },
        )


def run_context_collection(
    *,
    settings: Settings,
    trade_date: date | None = None,
    snapshot_time: datetime | None = None,
    include_market_reaction: bool = True,
    include_news_triggers: bool = True,
    market_reaction_provider: str | None = None,
    news_triggers_provider: str | None = None,
    http_client: httpx.Client | None = None,
) -> ContextCollectionResult:
    resolved_trade_date = trade_date or datetime.now(KST).date()
    resolved_snapshot_time = (snapshot_time or datetime.now(timezone.utc)).astimezone(timezone.utc)
    providers: list[ContextProviderResult] = []

    with get_connection(settings.db_path) as connection:
        storage = ArgusV2Storage(connection)
        if include_market_reaction:
            providers.append(
                _fetch_and_store_market_reaction(
                    settings=settings,
                    storage=storage,
                    trade_date=resolved_trade_date,
                    snapshot_time=resolved_snapshot_time,
                    provider_override=market_reaction_provider,
                    http_client=http_client,
                )
            )
        if include_news_triggers:
            providers.append(
                _fetch_and_store_news_triggers(
                    settings=settings,
                    storage=storage,
                    trade_date=resolved_trade_date,
                    snapshot_time=resolved_snapshot_time,
                    provider_override=news_triggers_provider,
                    http_client=http_client,
                )
            )

    return ContextCollectionResult(
        db_path=str(resolve_db_path(settings.db_path)),
        trade_date=resolved_trade_date.isoformat(),
        snapshot_time=_snapshot_iso(resolved_snapshot_time),
        providers=providers,
    )


def run_news_ai_smoke(
    *,
    settings: Settings,
    title: str = "FOMC 금리 경계와 환율 상승",
    summary: str = "미국 국채금리와 달러 강세가 위험자산에 부담입니다.",
    source: str = "Reuters",
    source_url: str = "https://www.reuters.com/markets/rates-bonds/",
    http_client: httpx.Client | None = None,
) -> NewsAiSmokeResult:
    provider = settings.argus_news_ai_provider.strip().lower()
    model = settings.argus_news_ai_model or settings.argus_gemini_model or settings.gemini_model or ""
    api_key = settings.argus_news_ai_api_key or settings.argus_gemini_api_key or settings.gemini_api_key
    service = ArgusNewsTriggerService(
        provider="rss",
        news_ai_provider=provider,
        news_ai_base_url=settings.argus_news_ai_base_url,
        news_ai_chat_path=settings.argus_news_ai_chat_path,
        news_ai_api_key=api_key,
        news_ai_model=model,
        news_ai_timeout_seconds=settings.argus_news_ai_timeout_seconds,
        http_client=http_client,
    )
    record = NewsTriggerRecord(
        id="news-ai-smoke",
        title=title,
        summary=summary,
        impact="neutral",
        source=source,
        published_at=utcnow_iso(),
        connection_strength="unclear",
        freshness="fresh",
        source_url=source_url,
        raw_payload={"provider": "news_ai_smoke"},
    )
    enriched = service._with_ai_enrichment(record)
    raw_payload = enriched.raw_payload if isinstance(enriched.raw_payload, dict) else {}
    ai_payload = raw_payload.get("_argus_ai") if isinstance(raw_payload.get("_argus_ai"), dict) else {}
    reason = _as_text(ai_payload.get("reason")) or ""
    failed = reason.startswith("news_ai_error:") or reason in {
        "news_ai_disabled",
        "missing_news_ai_api_key",
        "missing_news_ai_model",
    }
    return NewsAiSmokeResult(
        provider=provider or "disabled",
        model=model,
        status="failed" if failed else "success",
        should_use=bool(ai_payload.get("should_use")),
        impact=_valid_impact(_as_text(ai_payload.get("impact")) or "neutral"),
        relevance_score=_bounded_int(ai_payload.get("relevance_score"), minimum=0, maximum=100),
        connection_strength=_valid_connection_strength(_as_text(ai_payload.get("connection_strength")) or "unclear"),
        confidence=_valid_confidence(_as_text(ai_payload.get("confidence")) or "low"),
        reason=reason,
        summary=_as_text(ai_payload.get("summary")) or enriched.summary,
    )


def build_news_feed_service(
    *,
    settings: Settings,
    provider_override: str | None = None,
    http_client: httpx.Client | None = None,
) -> ArgusNewsTriggerService:
    provider = (provider_override or settings.argus_news_feed_provider or settings.argus_news_triggers_provider).strip().lower()
    return ArgusNewsTriggerService(
        provider=provider,
        file_path=settings.argus_news_triggers_file_path,
        rss_urls=settings.argus_news_feed_rss_urls or settings.argus_news_triggers_rss_urls,
        query=settings.argus_news_feed_query or settings.argus_news_triggers_query,
        limit=settings.argus_news_feed_limit,
        lookback_hours=settings.argus_news_feed_lookback_hours,
        naver_client_id=settings.argus_news_naver_client_id,
        naver_client_secret=settings.argus_news_naver_client_secret,
        naver_base_url=settings.argus_news_naver_base_url,
        naver_search_path=settings.argus_news_naver_search_path,
        naver_display=settings.argus_news_naver_display,
        naver_page_limit=settings.argus_news_naver_page_limit,
        news_ai_provider="disabled",
        dart_api_key=settings.argus_disclosure_dart_api_key,
        dart_base_url=settings.argus_disclosure_dart_base_url,
        dart_list_path=settings.argus_disclosure_dart_list_path,
        dart_corp_cls=settings.argus_disclosure_dart_corp_cls,
        dart_pblntf_ty=settings.argus_disclosure_dart_pblntf_ty,
        dart_lookback_days=settings.argus_disclosure_dart_lookback_days,
        dart_page_count=settings.argus_disclosure_dart_page_count,
        macro_events_provider=settings.argus_macro_events_provider,
        macro_events_file_path=settings.argus_macro_events_file_path,
        timeout_seconds=settings.market_briefing_timeout_seconds,
        max_retries=settings.market_briefing_max_retries,
        backoff_seconds=settings.market_briefing_backoff_seconds,
        http_client=http_client,
    )


def _fetch_and_store_market_reaction(
    *,
    settings: Settings,
    storage: ArgusV2Storage,
    trade_date: date,
    snapshot_time: datetime,
    provider_override: str | None,
    http_client: httpx.Client | None,
) -> ContextProviderResult:
    provider_key = "v2_market_reaction"
    provider = (provider_override or settings.argus_market_reaction_provider).strip().lower()
    endpoint = provider_override or settings.argus_market_reaction_provider
    try:
        if provider in KIS_MARKET_REACTION_PROVIDERS:
            token = KisAuthClient(
                base_url=settings.kis_base_url,
                token_path=settings.kis_token_path,
                app_key=settings.kis_app_key,
                app_secret=settings.kis_app_secret,
                timeout_seconds=settings.market_briefing_timeout_seconds,
                cache_path=str(resolve_db_path(settings.kis_token_cache_path or DEFAULT_KIS_TOKEN_CACHE_PATH)),
                http_client=http_client,
            ).issue_access_token()
            endpoint = settings.argus_market_reaction_index_price_path
            batch = KisMarketReactionService(
                base_url=settings.kis_base_url,
                index_price_path=settings.argus_market_reaction_index_price_path,
                index_price_tr_id=settings.argus_market_reaction_index_price_tr_id,
                category_price_path=settings.argus_market_reaction_category_price_path,
                category_price_tr_id=settings.argus_market_reaction_category_price_tr_id,
                investor_time_path=settings.argus_market_reaction_investor_time_path,
                investor_time_tr_id=settings.argus_market_reaction_investor_time_tr_id,
                investor_amount_multiplier=settings.argus_market_reaction_investor_amount_multiplier,
                app_key=settings.kis_app_key,
                app_secret=settings.kis_app_secret,
                access_token=token.access_token,
                timeout_seconds=settings.market_briefing_timeout_seconds,
                max_retries=settings.market_briefing_max_retries,
                backoff_seconds=settings.market_briefing_backoff_seconds,
                sector_limit=settings.argus_market_reaction_sector_limit,
                http_client=http_client,
            ).fetch_snapshot(trade_date=trade_date, snapshot_time=snapshot_time)
        else:
            batch = ArgusMarketReactionService(
                provider=provider,
                file_path=settings.argus_market_reaction_file_path,
            ).fetch_snapshot(trade_date=trade_date, snapshot_time=snapshot_time)
        persisted = storage.save_provider_batch(
            provider_key=provider_key,
            provider_label="v2 현물 반응",
            endpoint=endpoint,
            batch=batch,
        )
        return ContextProviderResult(
            provider_key=provider_key,
            status=persisted.status,
            run_id=persisted.run_id,
            observed_count=persisted.observed_count,
            sample_count=len(persisted.sample_ids),
            market_reaction_snapshot_count=len(persisted.market_reaction_snapshot_ids),
            news_trigger_count=len(persisted.news_trigger_ids),
        )
    except Exception as error:
        return _persist_failed_context_run(
            storage=storage,
            provider_key=provider_key,
            provider_label="v2 현물 반응",
            endpoint=endpoint,
            error=error,
        )


def _fetch_and_store_news_triggers(
    *,
    settings: Settings,
    storage: ArgusV2Storage,
    trade_date: date,
    snapshot_time: datetime,
    provider_override: str | None,
    http_client: httpx.Client | None,
) -> ContextProviderResult:
    provider_key = "v2_news_triggers"
    try:
        batch = ArgusNewsTriggerService(
            provider=provider_override or settings.argus_news_triggers_provider,
            file_path=settings.argus_news_triggers_file_path,
            rss_urls=settings.argus_news_triggers_rss_urls,
            query=settings.argus_news_triggers_query,
            limit=settings.argus_news_triggers_limit,
            lookback_hours=settings.argus_news_triggers_lookback_hours,
            naver_client_id=settings.argus_news_naver_client_id,
            naver_client_secret=settings.argus_news_naver_client_secret,
            naver_base_url=settings.argus_news_naver_base_url,
            naver_search_path=settings.argus_news_naver_search_path,
            naver_display=settings.argus_news_naver_display,
            naver_page_limit=settings.argus_news_naver_page_limit,
            news_ai_provider=settings.argus_news_ai_provider,
            news_ai_base_url=settings.argus_news_ai_base_url,
            news_ai_chat_path=settings.argus_news_ai_chat_path,
            news_ai_api_key=settings.argus_news_ai_api_key or settings.argus_gemini_api_key or settings.gemini_api_key,
            news_ai_model=settings.argus_news_ai_model or settings.argus_gemini_model or settings.gemini_model,
            news_ai_timeout_seconds=settings.argus_news_ai_timeout_seconds,
            dart_api_key=settings.argus_disclosure_dart_api_key,
            dart_base_url=settings.argus_disclosure_dart_base_url,
            dart_list_path=settings.argus_disclosure_dart_list_path,
            dart_corp_cls=settings.argus_disclosure_dart_corp_cls,
            dart_pblntf_ty=settings.argus_disclosure_dart_pblntf_ty,
            dart_lookback_days=settings.argus_disclosure_dart_lookback_days,
            dart_page_count=settings.argus_disclosure_dart_page_count,
            macro_events_provider=settings.argus_macro_events_provider,
            macro_events_file_path=settings.argus_macro_events_file_path,
            timeout_seconds=settings.market_briefing_timeout_seconds,
            max_retries=settings.market_briefing_max_retries,
            backoff_seconds=settings.market_briefing_backoff_seconds,
            http_client=http_client,
        ).fetch_triggers(trade_date=trade_date, snapshot_time=snapshot_time)
        persisted = storage.save_provider_batch(
            provider_key=provider_key,
            provider_label="v2 뉴스 트리거",
            endpoint=provider_override or settings.argus_news_triggers_provider,
            batch=batch,
        )
        return ContextProviderResult(
            provider_key=provider_key,
            status=persisted.status,
            run_id=persisted.run_id,
            observed_count=persisted.observed_count,
            sample_count=len(persisted.sample_ids),
            market_reaction_snapshot_count=len(persisted.market_reaction_snapshot_ids),
            news_trigger_count=len(persisted.news_trigger_ids),
        )
    except Exception as error:
        return _persist_failed_context_run(
            storage=storage,
            provider_key=provider_key,
            provider_label="v2 뉴스 트리거",
            endpoint=provider_override or settings.argus_news_triggers_provider,
            error=error,
        )


def _persist_failed_context_run(
    *,
    storage: ArgusV2Storage,
    provider_key: str,
    provider_label: str,
    endpoint: str,
    error: Exception,
) -> ContextProviderResult:
    run_id = storage.start_provider_run(
        provider_key=provider_key,
        provider_label=provider_label,
        endpoint=endpoint,
        started_at=utcnow_iso(),
    )
    safe_error = f"{error.__class__.__name__}: {str(error)[:500]}" if str(error) else error.__class__.__name__
    storage.finish_provider_run(run_id=run_id, status="failed", observed_count=0, error=safe_error)
    return ContextProviderResult(
        provider_key=provider_key,
        status="failed",
        run_id=run_id,
        observed_count=0,
        sample_count=0,
        market_reaction_snapshot_count=0,
        news_trigger_count=0,
        error=safe_error,
    )


def _mock_market_reaction(*, trade_date: date, snapshot_time: str) -> MarketReactionSnapshotRecord:
    return MarketReactionSnapshotRecord(
        source_name="mock.market.reaction",
        trade_date=trade_date.isoformat(),
        snapshot_time=snapshot_time,
        kospi_change_rate=-0.18,
        kosdaq_change_rate=0.12,
        kospi200_futures_change_rate=-0.34,
        advancing_count=432,
        declining_count=511,
        spot_foreign_net_buy=-82_000_000_000,
        spot_institution_net_buy=34_000_000_000,
        spot_individual_net_buy=48_000_000_000,
        summary="지수는 약하지만 반도체가 버티며 하방 압력을 제한합니다.",
        freshness_state="partial",
        raw_payload={"provider": "mock"},
        strong_sectors=[
            MarketReactionSectorRecord(
                name="반도체",
                change_rate=1.15,
                reason="미국 AI/반도체 모멘텀 반영",
                tone="positive",
                source="mock.market.reaction",
                observed_at=snapshot_time,
            )
        ],
        weak_sectors=[
            MarketReactionSectorRecord(
                name="금융",
                change_rate=-0.62,
                reason="금리 변동성 확대 구간",
                tone="negative",
                source="mock.market.reaction",
                observed_at=snapshot_time,
            )
        ],
    )


def _mock_news_triggers(*, snapshot_time: str) -> list[NewsTriggerRecord]:
    return [
        NewsTriggerRecord(
            id="mock-rates",
            title="미국 금리 상승 경계",
            summary="밤사이 금리 상승은 위험자산과 원화에는 부담으로 해석됩니다.",
            impact="negative",
            source="mock.news.macro",
            published_at=snapshot_time,
            connection_strength="medium",
            freshness="partial",
            raw_payload={
                "provider": "mock",
                "ai_enrichment": {
                    "should_use": True,
                    "impact": "negative",
                    "relevance_score": 80,
                    "connection_strength": "medium",
                    "summary": "미국 금리 상승은 위험자산과 원화에 부담입니다.",
                    "reason": "한국장 개장 전 지수와 성장주 심리에 직접 연결됩니다.",
                    "confidence": "medium",
                },
            },
        ),
        NewsTriggerRecord(
            id="mock-chip",
            title="반도체 상대 강세",
            summary="지수 영향도가 큰 반도체가 하락 압력을 일부 상쇄합니다.",
            impact="positive",
            source="mock.news.sector",
            published_at=snapshot_time,
            connection_strength="medium",
            freshness="partial",
            raw_payload={
                "provider": "mock",
                "ai_enrichment": {
                    "should_use": True,
                    "impact": "positive",
                    "relevance_score": 72,
                    "connection_strength": "medium",
                    "summary": "반도체 상대 강세가 지수 하방 압력을 일부 상쇄합니다.",
                    "reason": "국내 지수 영향도가 큰 업종 흐름입니다.",
                    "confidence": "medium",
                },
            },
        ),
    ]


def _mock_macro_triggers(*, snapshot_time: str) -> list[NewsTriggerRecord]:
    return [
        NewsTriggerRecord(
            id="mock-macro-us-yield",
            title="미국 10년물 금리 상승",
            summary="미국 국채금리 상승은 성장주와 원화에는 부담으로 해석합니다.",
            impact="negative",
            source="mock.macro.rates",
            published_at=snapshot_time,
            connection_strength="strong",
            freshness="partial",
            raw_payload={
                "provider": "mock_macro",
                "event_type": "rates",
                "ai_enrichment": {
                    "should_use": True,
                    "impact": "negative",
                    "relevance_score": 88,
                    "connection_strength": "strong",
                    "summary": "미국 10년물 금리 상승은 성장주와 원화에 부담입니다.",
                    "reason": "해외 금리 변화는 한국장 선물·현물 위험선호에 직접 연결됩니다.",
                    "confidence": "high",
                },
            },
        ),
        NewsTriggerRecord(
            id="mock-macro-us-tech",
            title="나스닥 반도체 강세",
            summary="미국 기술주와 반도체 강세는 국내 반도체 대형주에 우호적입니다.",
            impact="positive",
            source="mock.macro.us_equity",
            published_at=snapshot_time,
            connection_strength="medium",
            freshness="partial",
            raw_payload={
                "provider": "mock_macro",
                "event_type": "us_equity",
                "ai_enrichment": {
                    "should_use": True,
                    "impact": "positive",
                    "relevance_score": 74,
                    "connection_strength": "medium",
                    "summary": "나스닥 반도체 강세는 국내 반도체 대형주에 우호적입니다.",
                    "reason": "국내 지수 비중 업종의 해외 선행 흐름입니다.",
                    "confidence": "medium",
                },
            },
        ),
    ]


def _pick_dated_payload(*, payload: Any, trade_date: date) -> dict[str, Any]:
    if isinstance(payload, dict):
        dated = payload.get(trade_date.isoformat())
        if isinstance(dated, dict):
            return dated
        item = payload.get("item")
        if isinstance(item, dict):
            return item
        if _looks_like_reaction_row(payload):
            return payload
    raise ValueError("market_reaction_file_payload_invalid")


def _pick_news_rows(*, payload: Any, trade_date: date) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        dated = payload.get(trade_date.isoformat())
        if isinstance(dated, list):
            return [item for item in dated if isinstance(item, dict)]
        for key in ("triggers", "items", "data"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
    return []


def _pick_macro_rows(*, payload: Any, trade_date: date) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        dated = payload.get(trade_date.isoformat())
        if isinstance(dated, list):
            return [item for item in dated if isinstance(item, dict)]
        for key in ("events", "macro_events", "items", "data"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
    return []


def _looks_like_reaction_row(payload: dict[str, Any]) -> bool:
    return any(key in payload for key in ("kospi_change_rate", "kosdaq_change_rate", "strong_sectors", "weak_sectors"))


def _sector_records(payload: Any, *, role: str, observed_at: str, source: str) -> list[MarketReactionSectorRecord]:
    if not isinstance(payload, list):
        return []
    records = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = pick_text(item, ("name", "sector", "theme"))
        if not name:
            continue
        records.append(
            MarketReactionSectorRecord(
                name=name,
                change_rate=pick_float(item, ("change_rate", "rate", "change")),
                reason=pick_text(item, ("reason", "summary", "memo")) or "",
                tone=_valid_impact(pick_text(item, ("tone", "impact")) or ("positive" if role == "strong" else "negative")),
                source=pick_text(item, ("source", "source_name")) or source,
                observed_at=pick_text(item, ("observed_at", "snapshot_time")) or observed_at,
            )
        )
    return records


def _extract_news_ai_decision(raw_payload: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("ai_enrichment", "argus_ai_enrichment", "_argus_ai"):
        value = raw_payload.get(key)
        if isinstance(value, dict):
            return value

    explicit_keys = {
        "should_use",
        "relevance_score",
        "importance_score",
        "impact",
        "tone",
        "connection_strength",
        "strength",
        "ai_summary",
        "ai_reason",
        "confidence",
    }
    if not any(key in raw_payload for key in explicit_keys):
        return None

    return {
        "should_use": raw_payload.get("should_use"),
        "impact": raw_payload.get("impact") or raw_payload.get("tone"),
        "relevance_score": raw_payload.get("relevance_score") or raw_payload.get("importance_score"),
        "connection_strength": raw_payload.get("connection_strength") or raw_payload.get("strength"),
        "affected_factors": raw_payload.get("affected_factors") or raw_payload.get("factors") or [],
        "summary": raw_payload.get("ai_summary") or raw_payload.get("summary"),
        "reason": raw_payload.get("ai_reason") or raw_payload.get("reason") or raw_payload.get("memo"),
        "confidence": raw_payload.get("confidence"),
    }


def _parse_news_ai_response(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("news_ai_response_invalid")

    content: str | None = None
    if isinstance(payload.get("output_text"), str):
        content = payload["output_text"]
    else:
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            first_choice = choices[0]
            if isinstance(first_choice, dict):
                message = first_choice.get("message")
                if isinstance(message, dict) and isinstance(message.get("content"), str):
                    content = message["content"]
        candidates = payload.get("candidates")
        if content is None and isinstance(candidates, list) and candidates:
            first_candidate = candidates[0]
            if isinstance(first_candidate, dict):
                candidate_content = first_candidate.get("content")
                if isinstance(candidate_content, dict):
                    parts = candidate_content.get("parts")
                    if isinstance(parts, list):
                        text_parts = [part.get("text") for part in parts if isinstance(part, dict) and isinstance(part.get("text"), str)]
                        content = "".join(text_parts) if text_parts else None

    if not content:
        raise ValueError("news_ai_content_missing")

    try:
        decision = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError("news_ai_json_invalid") from error

    if not isinstance(decision, dict):
        raise ValueError("news_ai_json_not_object")
    return decision


def _apply_news_ai_decision(*, record: NewsTriggerRecord, decision: dict[str, Any], provider: str) -> NewsTriggerRecord:
    normalized = _normalize_news_ai_decision(decision)
    raw_payload = record.raw_payload if isinstance(record.raw_payload, dict) else {}
    enriched_raw_payload = {
        **raw_payload,
        "_argus_ai": {
            "provider": provider,
            "should_use": normalized["should_use"],
            "impact": normalized["impact"],
            "relevance_score": normalized["relevance_score"],
            "connection_strength": normalized["connection_strength"],
            "affected_factors": normalized["affected_factors"],
            "summary": normalized["summary"],
            "reason": normalized["reason"],
            "confidence": normalized["confidence"],
        },
        "_argus_ai_provider": provider,
        "_argus_ai_should_use": normalized["should_use"],
        "_argus_ai_relevance_score": normalized["relevance_score"],
        "_argus_ai_confidence": normalized["confidence"],
    }
    return replace(
        record,
        summary=normalized["summary"] or record.summary,
        impact=normalized["impact"] if normalized["should_use"] else "neutral",
        connection_strength=normalized["connection_strength"] if normalized["should_use"] else "unclear",
        raw_payload=enriched_raw_payload,
    )


def _normalize_news_ai_decision(decision: dict[str, Any]) -> dict[str, Any]:
    score = _bounded_int(decision.get("relevance_score"), minimum=0, maximum=100)
    explicit_should_use = _as_bool(decision.get("should_use"))
    should_use = (explicit_should_use if explicit_should_use is not None else True) and score > 0
    if not should_use:
        score = 0

    connection_strength = _valid_connection_strength(_as_text(decision.get("connection_strength")) or "")
    if connection_strength == "unclear" and score > 0:
        connection_strength = _strength_from_relevance(score)

    return {
        "should_use": should_use,
        "impact": _valid_impact(_as_text(decision.get("impact")) or "neutral"),
        "relevance_score": score,
        "connection_strength": connection_strength,
        "affected_factors": _as_text_list(decision.get("affected_factors"), limit=6),
        "summary": _as_text(decision.get("summary")) or "",
        "reason": _as_text(decision.get("reason")) or "",
        "confidence": _valid_confidence(_as_text(decision.get("confidence")) or "low"),
    }


def _no_news_ai_decision(*, reason: str) -> dict[str, Any]:
    return {
        "should_use": False,
        "impact": "neutral",
        "relevance_score": 0,
        "connection_strength": "unclear",
        "affected_factors": [],
        "summary": "",
        "reason": reason,
        "confidence": "low",
    }


def _ai_should_use_from_raw(record: NewsTriggerRecord) -> bool:
    raw_payload = record.raw_payload if isinstance(record.raw_payload, dict) else {}
    return bool(raw_payload.get("_argus_ai_should_use"))


def _ai_relevance_score_from_raw(record: NewsTriggerRecord) -> int:
    raw_payload = record.raw_payload if isinstance(record.raw_payload, dict) else {}
    value = raw_payload.get("_argus_ai_relevance_score")
    return int(value) if isinstance(value, int) else 0


def _ai_confidence_rank(record: NewsTriggerRecord) -> int:
    raw_payload = record.raw_payload if isinstance(record.raw_payload, dict) else {}
    value = _as_text(raw_payload.get("_argus_ai_confidence")) or "low"
    return {"high": 3, "medium": 2, "low": 1}.get(value, 0)


def _ai_reason_from_raw(record: NewsTriggerRecord) -> str:
    raw_payload = record.raw_payload if isinstance(record.raw_payload, dict) else {}
    ai_payload = raw_payload.get("_argus_ai")
    if not isinstance(ai_payload, dict):
        return ""
    return _as_text(ai_payload.get("reason")) or ""


def _strength_from_relevance(score: int) -> str:
    if score >= 80:
        return "strong"
    if score >= 45:
        return "medium"
    if score > 0:
        return "weak"
    return "unclear"


def _deduplicate_triggers(records: list[NewsTriggerRecord]) -> list[NewsTriggerRecord]:
    best_by_key: dict[str, NewsTriggerRecord] = {}
    for record in records:
        key = _trigger_dedupe_key(record)
        current = best_by_key.get(key)
        if current is not None and _trigger_rank(current) >= _trigger_rank(record):
            continue
        best_by_key[key] = record
    return list(best_by_key.values())


def _trigger_dedupe_key(record: NewsTriggerRecord) -> str:
    title_key = _normalize_dedupe_text(record.title)
    date_key = (record.published_at or "")[:10]
    if title_key:
        return f"title:{title_key}:{date_key}"
    return f"source:{(record.source_url or record.id or '').casefold()}"


def _trigger_rank(record: NewsTriggerRecord) -> tuple[int, int, str]:
    return (
        _ai_relevance_score_from_raw(record),
        _ai_confidence_rank(record),
        record.published_at or "",
    )


def _record_matches_query_terms(*, record: NewsTriggerRecord, query_terms: list[str]) -> bool:
    haystack = f"{record.title} {record.summary}".casefold()
    return any(term.casefold() in haystack for term in query_terms)


def _normalize_dedupe_text(value: str) -> str:
    normalized = re.sub(r"\[[^\]]+\]|\([^\)]+\)", " ", value.casefold())
    return re.sub(r"[^0-9a-z가-힣]+", "", normalized)


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _valid_impact(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"positive", "neutral", "negative"}:
        return normalized
    return "neutral"


def _valid_connection_strength(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"strong", "medium", "weak", "unclear"}:
        return normalized
    return "unclear"


def _valid_confidence(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"high", "medium", "low"}:
        return normalized
    return "low"


def _bounded_int(value: Any, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return minimum
    return max(minimum, min(maximum, parsed))


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return None


def _as_text_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [_as_text(item) for item in value]
    return [item for item in items if item][:limit]


def _stable_trigger_id(*, title: str, published_at: str) -> str:
    import hashlib

    digest = hashlib.sha1(f"{title}|{published_at}".encode("utf-8")).hexdigest()[:12]
    return f"trigger-{digest}"


def _source_from_url(value: str) -> str:
    host = urlparse(value).netloc
    return host.replace("www.", "") or "rss"


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _strip_html(value: str | None) -> str:
    if value is None:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _parse_rss_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _dart_date_to_iso(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if len(text) != 8 or not text.isdigit():
        return None
    parsed = datetime(int(text[:4]), int(text[4:6]), int(text[6:8]), 0, 0, tzinfo=KST)
    return _snapshot_iso(parsed)


def _snapshot_iso(snapshot_time: datetime) -> str:
    return snapshot_time.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_int(value: Any) -> int | None:
    parsed = as_float(value)
    return int(parsed) if parsed is not None else None
