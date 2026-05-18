from __future__ import annotations

from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends

from ...config.env import Settings, get_settings
from ..contracts import FuturesQuoteResponse, MarketDashboard, NewsFeedItem, NewsFeedResponse, OptionQuotesResponse
from ..dashboard import build_dashboard_from_storage, build_futures_quote_from_storage, build_option_quotes_from_storage
from ..db import get_connection
from ..judgement import build_market_judgement
from ..providers import build_mock_dashboard_inputs
from ..providers.context_inputs import KST, build_news_feed_service
from ..storage import ArgusV2Storage


def create_argus_v2_router() -> APIRouter:
    router = APIRouter(prefix="/api/argus/v2", tags=["argus-v2"])

    @router.get("/dashboard", response_model=MarketDashboard)
    async def market_dashboard(settings: Settings = Depends(get_settings)) -> MarketDashboard:
        with get_connection(settings.db_path) as connection:
            live_dashboard = build_dashboard_from_storage(ArgusV2Storage(connection), settings=settings)
        if live_dashboard is not None:
            return live_dashboard

        derivatives, triggers, reaction, provider_health = build_mock_dashboard_inputs(
            kis_app_key_set=bool(settings.kis_app_key),
            kis_app_secret_set=bool(settings.kis_app_secret),
        )
        live_provider_missing = any(item.key == "kis_derivatives" and item.status == "missing" for item in provider_health)
        judgement = build_market_judgement(
            derivatives,
            triggers,
            reaction,
            live_provider_missing=live_provider_missing,
        )
        return MarketDashboard(
            as_of=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            session_phase="live",
            derivatives=derivatives,
            triggers=triggers,
            reaction=reaction,
            judgement=judgement,
            provider_health=provider_health,
        )

    @router.get("/option-quotes", response_model=OptionQuotesResponse)
    async def option_quotes(settings: Settings = Depends(get_settings)) -> OptionQuotesResponse:
        with get_connection(settings.db_path) as connection:
            return build_option_quotes_from_storage(ArgusV2Storage(connection))

    @router.get("/futures", response_model=FuturesQuoteResponse)
    async def futures(settings: Settings = Depends(get_settings)) -> FuturesQuoteResponse:
        with get_connection(settings.db_path) as connection:
            return build_futures_quote_from_storage(ArgusV2Storage(connection))

    @router.get("/news-feed", response_model=NewsFeedResponse)
    async def news_feed(settings: Settings = Depends(get_settings)) -> NewsFeedResponse:
        snapshot_time = datetime.now(timezone.utc).replace(microsecond=0)
        provider = (settings.argus_news_feed_provider or settings.argus_news_triggers_provider).strip().lower()
        with get_connection(settings.db_path) as connection:
            storage = ArgusV2Storage(connection)
            stored_items = storage.get_latest_news_feed_items(limit=settings.argus_news_feed_limit)
            stored_run = storage.get_latest_provider_run("v2_news_feed")
        if stored_items:
            return _news_feed_response_from_storage(
                items=stored_items,
                run=stored_run,
                fallback_provider=provider or "rss",
                snapshot_time=snapshot_time,
            )

        service = build_news_feed_service(settings=settings)
        try:
            batch = service.fetch_feed(
                trade_date=snapshot_time.astimezone(KST).date(),
                snapshot_time=snapshot_time,
            )
        except Exception as error:
            return NewsFeedResponse(
                as_of=snapshot_time.isoformat(),
                provider=provider or "disabled",
                status="missing",
                observed_count=0,
                error=str(error),
                items=[],
            )

        if batch.disabled_reason:
            return NewsFeedResponse(
                as_of=snapshot_time.isoformat(),
                provider=provider or "disabled",
                status="missing",
                observed_count=0,
                error=batch.disabled_reason,
                items=[],
            )

        items = [
            NewsFeedItem(
                id=record.id,
                title=record.title,
                summary=record.summary,
                source=record.source,
                published_at=record.published_at,
                source_url=record.source_url,
                freshness=record.freshness,
            )
            for record in batch.records
        ]
        return NewsFeedResponse(
            as_of=snapshot_time.isoformat(),
            provider=str(batch.metadata.get("provider") or provider or "rss"),
            status="fresh" if items else "partial",
            observed_count=len(items),
            items=items,
        )

    return router


def _news_feed_response_from_storage(
    *,
    items: list[dict],
    run: dict | None,
    fallback_provider: str,
    snapshot_time: datetime,
) -> NewsFeedResponse:
    metadata = _json_object((run or {}).get("metadata_json"))
    provider = str(metadata.get("provider") or fallback_provider)
    as_of = str((run or {}).get("finished_at") or (run or {}).get("started_at") or snapshot_time.isoformat())
    return NewsFeedResponse(
        as_of=as_of,
        provider=provider,
        status=_run_status_to_freshness(str((run or {}).get("status") or "success")),
        observed_count=len(items),
        error=str(run["error"]) if run and run.get("error") else None,
        items=[
            NewsFeedItem(
                id=str(item.get("external_id") or item.get("id") or ""),
                title=str(item.get("title") or ""),
                summary=str(item.get("summary") or ""),
                source=str(item.get("source_name") or "argus_v2.news_feed"),
                published_at=item.get("published_at"),
                source_url=item.get("source_url"),
                freshness=_valid_freshness(str(item.get("freshness_state") or "partial")),
            )
            for item in items
        ],
    )


def _json_object(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _run_status_to_freshness(status: str) -> str:
    if status == "success":
        return "fresh"
    if status == "partial":
        return "partial"
    return "missing"


def _valid_freshness(value: str) -> str:
    return value if value in {"fresh", "partial", "stale", "missing"} else "partial"
