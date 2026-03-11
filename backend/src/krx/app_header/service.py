from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo

from ...config.env import Settings
from ..derivatives.service import DerivativesDashboardService
from ..market.data import events as krx_events
from ..news.data import news_items as krx_news_items

logger = logging.getLogger(__name__)

MarketCode = Literal["krx"]


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _sorted_news(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: _parse_iso_datetime(item.get("published_at")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )


def _sorted_events(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: _parse_iso_datetime(item.get("event_date")) or datetime.max.replace(tzinfo=timezone.utc),
    )


def _phase_for_market(market: MarketCode) -> str:
    zone = ZoneInfo("Asia/Seoul")
    now = datetime.now(zone)
    minutes = now.hour * 60 + now.minute

    if minutes < 9 * 60:
        return "pre-open"
    if minutes < 15 * 60 + 30:
        return "live"
    return "post-close"


def _supporting_point(
    text: str,
    source_key: str,
    source_label: str,
    source_url: str | None = None,
) -> dict[str, str | None]:
    return {
        "text": text,
        "source_key": source_key,
        "source_label": source_label,
        "source_url": source_url,
    }


class AppHeaderService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def get_header(self, *, market: MarketCode) -> dict[str, Any]:
        payload = self._build_krx_header()

        logger.info(
            "app_header_generated %s",
            json.dumps(
                {
                    "market": market,
                    "coverage_state": payload["source_coverage"]["state"],
                    "coverage_ratio": payload["source_coverage"]["coverage_ratio"],
                    "breaking": payload["breaking_news"] is not None,
                },
                ensure_ascii=False,
            ),
        )
        return payload

    def _build_krx_header(self) -> dict[str, Any]:
        latest_news = self._capture_source(
            market="krx",
            source_key="news",
            label="뉴스 해석",
            source_name="Argus KRX Desk",
            source_url="https://example.com/krx/news",
            fetcher=lambda: _sorted_news(list(krx_news_items)),
        )
        upcoming_events = self._capture_source(
            market="krx",
            source_key="events",
            label="시장 이벤트",
            source_name="Argus Event Calendar",
            source_url="https://example.com/krx/events",
            fetcher=lambda: _sorted_events(list(krx_events)),
        )
        derivatives_summary = self._capture_source(
            market="krx",
            source_key="derivatives",
            label="파생 신호",
            source_name="KRX_DERIVATIVES",
            source_url=None,
            fetcher=lambda: DerivativesDashboardService.from_settings(self.settings).get_summary(),
        )

        news_items = latest_news["data"] if isinstance(latest_news["data"], list) else []
        event_items = upcoming_events["data"] if isinstance(upcoming_events["data"], list) else []
        derivatives = derivatives_summary["data"] if isinstance(derivatives_summary["data"], dict) else None

        tone_line = self._build_krx_tone_line(derivatives=derivatives, news_items=news_items)
        supporting_points = self._build_krx_supporting_points(
            derivatives=derivatives,
            news_items=news_items,
            event_items=event_items,
        )
        updated_at = self._latest_timestamp(
            [
                latest_news["updated_at"],
                upcoming_events["updated_at"],
                derivatives_summary["updated_at"],
            ]
        )

        coverage_items = [
            latest_news["coverage_item"],
            upcoming_events["coverage_item"],
            derivatives_summary["coverage_item"],
        ]

        return {
            "market": "krx",
            "market_tone_line": tone_line,
            "supporting_points": supporting_points,
            "phase": _phase_for_market("krx"),
            "updated_at": updated_at,
            "source_coverage": self._build_source_coverage(coverage_items),
            "breaking_news": self._build_breaking_news(
                market="krx",
                news_items=news_items,
                default_scope="한국 증시",
            ),
        }

    def _build_krx_tone_line(
        self,
        *,
        derivatives: dict[str, Any] | None,
        news_items: list[dict[str, Any]],
    ) -> str:
        if derivatives and derivatives.get("explanation_text"):
            return str(derivatives["explanation_text"])

        lead_news = news_items[0] if news_items else None
        if lead_news and lead_news.get("why_it_matters"):
            return f"{lead_news['why_it_matters']} 관련 해석이 오늘 국내 증시 분위기를 주도하고 있습니다."

        return "국내 증시는 외국인 포지션과 거시 뉴스 해석을 함께 확인해야 하는 구간입니다."

    def _build_krx_supporting_points(
        self,
        *,
        derivatives: dict[str, Any] | None,
        news_items: list[dict[str, Any]],
        event_items: list[dict[str, Any]],
    ) -> list[dict[str, str | None]]:
        points: list[dict[str, str | None]] = []

        if derivatives:
            directional_bias = str(derivatives.get("directional_bias") or "neutral")
            confidence_bucket = str(derivatives.get("confidence_bucket") or "low")
            directional_label = {
                "bullish": "상방 우위",
                "bearish": "하방 우위",
                "neutral": "중립",
            }.get(directional_bias, "중립")
            confidence_label = {
                "high": "높은",
                "medium": "중간",
                "low": "낮은",
            }.get(confidence_bucket, "낮은")
            points.append(
                _supporting_point(
                    f"파생 해석은 {directional_label}이며 현재 신뢰도는 {confidence_label} 수준입니다.",
                    "derivatives",
                    "KRX_DERIVATIVES",
                )
            )

            night_futures = derivatives.get("night_futures") or {}
            if night_futures.get("snapshot_time"):
                signal = {
                    "gap_up": "갭상승",
                    "gap_down": "갭하락",
                    "flat": "갭중립",
                    None: "중립",
                }.get(night_futures.get("signal"), "중립")
                points.append(
                    _supporting_point(
                        f"야간선물 스냅샷은 {signal} 신호를 보여주고 있습니다.",
                        "derivatives",
                        night_futures.get("source_name") or "KRX_DERIVATIVES",
                        night_futures.get("source_url"),
                    )
                )

        for news in news_items:
            if len(points) >= 3:
                break
            why_it_matters = str(news.get("why_it_matters") or "").strip()
            if not why_it_matters:
                continue
            points.append(
                _supporting_point(
                    why_it_matters,
                    "news",
                    news.get("source") or "Argus KRX Desk",
                    news.get("source_url"),
                )
            )

        if len(points) < 3 and event_items:
            next_event = event_items[0]
            points.append(
                _supporting_point(
                    f"가까운 일정으로는 {next_event['title']}이(가) 예정돼 있습니다.",
                    "events",
                    "Argus Event Calendar",
                )
            )

        return points[:3]

    def _capture_source(
        self,
        *,
        market: MarketCode,
        source_key: str,
        label: str,
        source_name: str,
        source_url: str | None,
        fetcher,
    ) -> dict[str, Any]:
        try:
            data = fetcher()
            status = self._infer_status(source_key=source_key, data=data)
            updated_at = self._infer_updated_at(data=data)
            coverage_item = {
                "key": source_key,
                "label": label,
                "status": status,
                "source_name": source_name,
                "source_url": source_url,
                "updated_at": updated_at,
            }
            return {
                "data": data,
                "coverage_item": coverage_item,
                "updated_at": updated_at,
            }
        except Exception as exc:
            logger.warning(
                "app_header_source_failed %s",
                json.dumps(
                    {
                        "market": market,
                        "source_key": source_key,
                        "error": exc.__class__.__name__,
                    },
                    ensure_ascii=False,
                ),
            )
            return {
                "data": None,
                "coverage_item": {
                    "key": source_key,
                    "label": label,
                    "status": "missing",
                    "source_name": source_name,
                    "source_url": source_url,
                    "updated_at": None,
                },
                "updated_at": None,
            }

    def _infer_status(self, *, source_key: str, data: Any) -> str:
        if not data:
            return "missing"

        if source_key == "derivatives" and isinstance(data, dict):
            coverage = data.get("source_coverage") or {}
            coverage_ratio = float(coverage.get("coverage_ratio") or 0.0)
            if coverage_ratio >= 0.8:
                return "available"
            if coverage_ratio > 0:
                return "partial"
            return "missing"

        if isinstance(data, list):
            return "available" if data else "missing"

        return "available"

    def _infer_updated_at(self, *, data: Any) -> str | None:
        if isinstance(data, list) and data:
            for key in ("published_at", "event_date", "updated_at"):
                candidate = data[0].get(key)
                if candidate:
                    return str(candidate)
            return None

        if isinstance(data, dict):
            for key in ("last_updated_at", "updated_at", "date"):
                candidate = data.get(key)
                if candidate:
                    return str(candidate)
            coverage = data.get("source_coverage") or {}
            sections = coverage.get("sections") or []
            candidates = [section.get("updated_at") for section in sections if section.get("updated_at")]
            return self._latest_timestamp(candidates)

        return None

    def _build_source_coverage(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        expected_sources = len(items)
        available_sources = sum(1 for item in items if item["status"] == "available")
        partial_sources = sum(1 for item in items if item["status"] == "partial")
        coverage_ratio = round(
            (available_sources + partial_sources * 0.5) / expected_sources,
            3,
        ) if expected_sources else 0.0

        if available_sources == expected_sources and partial_sources == 0:
            state = "full"
            summary = "모든 핵심 소스가 반영되었습니다."
        elif available_sources or partial_sources:
            state = "partial"
            summary = f"{available_sources + partial_sources}/{expected_sources}개 소스 반영, 일부 지연이 있습니다."
        else:
            state = "empty"
            summary = "헤더 구성을 위한 소스를 아직 확보하지 못했습니다."

        return {
            "state": state,
            "coverage_ratio": coverage_ratio,
            "available_sources": available_sources,
            "expected_sources": expected_sources,
            "summary": summary,
            "items": items,
        }

    def _build_breaking_news(
        self,
        *,
        market: MarketCode,
        news_items: list[dict[str, Any]],
        default_scope: str,
    ) -> dict[str, Any] | None:
        if not news_items:
            return None

        now = datetime.now(timezone.utc)
        for item in news_items:
            published_at = _parse_iso_datetime(item.get("published_at"))
            if item.get("importance") != "high":
                continue
            if published_at is None:
                continue
            if (now - published_at).total_seconds() > 4 * 60 * 60:
                continue
            return {
                "label": "속보",
                "headline": item["title"],
                "why_it_matters_one_line": item.get("why_it_matters") or item.get("summary") or "",
                "impact_scope": default_scope,
                "related_tab_link": f"/{market}/news",
                "source_name": item.get("source"),
                "source_url": item.get("source_url"),
                "published_at": item.get("published_at"),
            }

        return None

    def _latest_timestamp(self, candidates: list[str | None]) -> str | None:
        parsed_candidates = [_parse_iso_datetime(candidate) for candidate in candidates if candidate]
        parsed_candidates = [candidate for candidate in parsed_candidates if candidate is not None]
        if not parsed_candidates:
            return None
        return max(parsed_candidates).isoformat()
