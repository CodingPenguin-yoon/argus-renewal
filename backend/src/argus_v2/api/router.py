from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ...config.env import Settings, get_settings
from ..contracts import MarketDashboard, NewsFeedItem, NewsFeedResponse
from ..dashboard import build_dashboard_from_storage
from ..db import get_connection
from ..judgement import build_market_judgement
from ..providers import build_mock_dashboard_inputs
from ..providers.context_inputs import ArgusNewsTriggerService, KST
from ..storage import ArgusV2Storage


def create_argus_v2_router() -> APIRouter:
    router = APIRouter(prefix="/api/argus/v2", tags=["argus-v2"])

    @router.get("/dashboard", response_model=MarketDashboard)
    async def market_dashboard(settings: Settings = Depends(get_settings)) -> MarketDashboard:
        with get_connection(settings.db_path) as connection:
            live_dashboard = build_dashboard_from_storage(ArgusV2Storage(connection))
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

    @router.get("/news-feed", response_model=NewsFeedResponse)
    async def news_feed(settings: Settings = Depends(get_settings)) -> NewsFeedResponse:
        snapshot_time = datetime.now(timezone.utc).replace(microsecond=0)
        provider = (settings.argus_news_feed_provider or settings.argus_news_triggers_provider).strip().lower()
        service = ArgusNewsTriggerService(
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
        )
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
