from __future__ import annotations

from ...config.env import Settings
from ..source_ingestion.providers import NaverDatalabTrendProvider
from .editorial_ai import (
    DisabledNewsEditorialAIProvider,
    OpenAICompatibleNewsEditorialAIProvider,
)
from .service import NewsProductService


def create_news_product_service(settings: Settings) -> NewsProductService:
    editorial_provider = DisabledNewsEditorialAIProvider()
    if settings.news_product_editorial_ai_provider == "openai_compatible":
        editorial_provider = OpenAICompatibleNewsEditorialAIProvider(
            enabled=settings.news_product_editorial_ai_enabled,
            base_url=settings.news_product_editorial_ai_base_url,
            api_key=settings.news_product_editorial_ai_api_key,
            model=settings.news_product_editorial_ai_model,
            timeout_seconds=settings.news_product_editorial_ai_timeout_seconds,
            max_retries=settings.news_product_editorial_ai_max_retries,
            backoff_seconds=settings.news_product_editorial_ai_backoff_seconds,
        )

    return NewsProductService(
        db_path=settings.db_path,
        datalab_provider=NaverDatalabTrendProvider(
            enabled=settings.naver_datalab_enabled,
            client_id=settings.naver_datalab_client_id,
            client_secret=settings.naver_datalab_client_secret,
            base_url=settings.naver_datalab_base_url,
            search_path=settings.naver_datalab_search_path,
            time_unit=settings.naver_datalab_time_unit,
            timeout_seconds=settings.raw_ingestion_timeout_seconds,
            max_retries=settings.raw_ingestion_max_retries,
            backoff_seconds=settings.raw_ingestion_backoff_seconds,
        ),
        lookback_days=settings.news_product_lookback_days,
        card_limit=settings.news_product_card_limit,
        representative_evidence_limit=settings.news_product_representative_evidence_limit,
        refresh_ttl_seconds=settings.news_product_refresh_ttl_seconds,
        datalab_window_days=settings.news_product_datalab_window_days,
        editorial_ai_provider=editorial_provider,
        editorial_ai_candidate_limit=settings.news_product_editorial_ai_candidate_limit,
        editorial_ai_min_editorial_score=settings.news_product_editorial_ai_min_editorial_score,
    )
