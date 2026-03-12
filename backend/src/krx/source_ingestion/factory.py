from __future__ import annotations

from ...config.env import Settings
from ..global_events.factory import create_global_events_service as _create_global_events_service
from .company_report_service import CompanyReportService
from .briefing_signal_service import MarketBriefingSignalService
from .briefing_service import MarketBriefingInputService
from .event_service import EventNormalizationService
from .factory_extensions import load_raw_ingestion_factory_extensions
from .llm import DisabledLLMExtractionProvider, OpenAICompatibleLLMExtractionProvider
from .report_llm import (
    DisabledCompanyReportNarrativeProvider,
    OpenAICompatibleCompanyReportProvider,
)
from .providers import (
    DartDisclosureProvider,
    KisDomesticDerivativesService,
    KisMarketBreadthService,
    KisNightFuturesService,
    KrxDerivativesReferenceService,
    MkRssNewsProvider,
    NaverNewsProvider,
)
from .service import RawDocumentIngestionService


def _parse_csv_values(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def create_raw_document_ingestion_service(settings: Settings) -> RawDocumentIngestionService:
    extensions = load_raw_ingestion_factory_extensions(settings)
    return RawDocumentIngestionService(
        db_path=settings.db_path,
        dart_provider=DartDisclosureProvider(
            api_key=settings.dart_api_key,
            list_url=settings.dart_disclosure_list_url,
            material_only=getattr(settings, "dart_material_only", True),
            include_patterns=_parse_csv_values(getattr(settings, "dart_material_include_patterns", None)) or None,
            exclude_patterns=_parse_csv_values(getattr(settings, "dart_material_exclude_patterns", None)) or None,
            page_count=settings.dart_disclosure_page_count,
            timeout_seconds=settings.raw_ingestion_timeout_seconds,
            max_retries=settings.raw_ingestion_max_retries,
            backoff_seconds=settings.raw_ingestion_backoff_seconds,
        ),
        mk_rss_provider=MkRssNewsProvider(
            enabled=getattr(settings, "mk_rss_enabled", False),
            feed_urls=_parse_csv_values(
                getattr(
                    settings,
                    "mk_rss_feed_urls",
                    "https://www.mk.co.kr/rss/30100041/,https://www.mk.co.kr/rss/50200011/",
                ),
            ),
            timeout_seconds=settings.raw_ingestion_timeout_seconds,
            max_retries=settings.raw_ingestion_max_retries,
            backoff_seconds=settings.raw_ingestion_backoff_seconds,
        ),
        naver_provider=NaverNewsProvider(
            enabled=settings.naver_news_enabled,
            client_id=settings.naver_news_client_id,
            client_secret=settings.naver_news_client_secret,
            base_url=settings.naver_news_base_url,
            search_path=settings.naver_news_search_path,
            company_query_template=settings.naver_news_company_query_template,
            theme_query_template=settings.naver_news_theme_query_template,
            display=settings.naver_news_display,
            page_limit=settings.naver_news_page_limit,
            timeout_seconds=settings.raw_ingestion_timeout_seconds,
            max_retries=settings.raw_ingestion_max_retries,
            backoff_seconds=settings.raw_ingestion_backoff_seconds,
        ),
        extra_disclosure_provider_descriptors=extensions.disclosure_provider_descriptors,
        extra_news_provider_descriptors=extensions.news_provider_descriptors,
    )


def create_event_normalization_service(settings: Settings) -> EventNormalizationService:
    return EventNormalizationService(
        db_path=settings.db_path,
        llm_provider=create_event_llm_provider(settings),
        low_confidence_threshold=settings.event_pipeline_low_confidence_threshold,
    )


def create_event_llm_provider(settings: Settings):
    provider = settings.event_pipeline_llm_provider.strip().lower()
    enabled = settings.event_pipeline_llm_enabled

    if not enabled or provider in {"", "disabled"}:
        return DisabledLLMExtractionProvider()

    if provider in {"openai", "openai_compatible"}:
        return OpenAICompatibleLLMExtractionProvider(
            enabled=True,
            base_url=settings.event_pipeline_llm_base_url,
            api_key=settings.event_pipeline_llm_api_key,
            model=settings.event_pipeline_llm_model,
            timeout_seconds=settings.event_pipeline_llm_timeout_seconds,
            max_retries=settings.event_pipeline_llm_max_retries,
            backoff_seconds=settings.event_pipeline_llm_backoff_seconds,
        )

    return DisabledLLMExtractionProvider()


def create_market_briefing_input_service(settings: Settings) -> MarketBriefingInputService:
    return MarketBriefingInputService(
        db_path=settings.db_path,
        kis_market_breadth_service=KisMarketBreadthService(
            provider=settings.kis_market_breadth_provider,
            file_path=settings.kis_market_breadth_file_path,
            base_url=settings.kis_base_url,
            endpoint_path=settings.kis_market_breadth_path,
            app_key=settings.kis_app_key,
            app_secret=settings.kis_app_secret,
            access_token=settings.kis_access_token,
            timeout_seconds=settings.market_briefing_timeout_seconds,
            max_retries=settings.market_briefing_max_retries,
            backoff_seconds=settings.market_briefing_backoff_seconds,
            response_paths=settings.kis_market_breadth_response_paths,
            query_params_json=settings.kis_market_breadth_query_params_json,
            field_alias_map_json=settings.kis_market_breadth_field_alias_map_json,
            tr_id=settings.kis_market_breadth_tr_id,
        ),
        kis_domestic_derivatives_service=KisDomesticDerivativesService(
            provider=settings.kis_domestic_derivatives_provider,
            file_path=settings.kis_domestic_derivatives_file_path,
            base_url=settings.kis_base_url,
            endpoint_path=settings.kis_domestic_derivatives_path,
            app_key=settings.kis_app_key,
            app_secret=settings.kis_app_secret,
            access_token=settings.kis_access_token,
            timeout_seconds=settings.market_briefing_timeout_seconds,
            max_retries=settings.market_briefing_max_retries,
            backoff_seconds=settings.market_briefing_backoff_seconds,
            response_paths=settings.kis_domestic_derivatives_response_paths,
            query_params_json=settings.kis_domestic_derivatives_query_params_json,
            field_alias_map_json=settings.kis_domestic_derivatives_field_alias_map_json,
            tr_id=settings.kis_domestic_derivatives_tr_id,
        ),
        kis_night_futures_service=KisNightFuturesService(
            provider=settings.kis_night_futures_provider,
            file_path=settings.kis_night_futures_file_path,
            base_url=settings.kis_base_url,
            endpoint_path=settings.kis_night_futures_path,
            app_key=settings.kis_app_key,
            app_secret=settings.kis_app_secret,
            access_token=settings.kis_access_token,
            timeout_seconds=settings.market_briefing_timeout_seconds,
            max_retries=settings.market_briefing_max_retries,
            backoff_seconds=settings.market_briefing_backoff_seconds,
            response_paths=settings.kis_night_futures_response_paths,
            query_params_json=settings.kis_night_futures_query_params_json,
            field_alias_map_json=settings.kis_night_futures_field_alias_map_json,
            tr_id=settings.kis_night_futures_tr_id,
        ),
        krx_derivatives_reference_service=KrxDerivativesReferenceService(
            provider=settings.krx_derivatives_reference_provider,
            file_path=settings.krx_derivatives_reference_file_path,
            base_url=settings.krx_derivatives_reference_base_url,
            endpoint_path=settings.krx_derivatives_reference_path,
            api_key=settings.krx_derivatives_reference_api_key,
            timeout_seconds=settings.market_briefing_timeout_seconds,
            max_retries=settings.market_briefing_max_retries,
            backoff_seconds=settings.market_briefing_backoff_seconds,
            response_paths=settings.krx_derivatives_reference_response_paths,
            query_params_json=settings.krx_derivatives_reference_query_params_json,
            field_alias_map_json=settings.krx_derivatives_reference_field_alias_map_json,
        ),
    )


def create_market_briefing_signal_service(settings: Settings) -> MarketBriefingSignalService:
    return MarketBriefingSignalService(
        db_path=settings.db_path,
        signal_enabled=settings.market_briefing_signal_enabled,
        market_scope=settings.market_briefing_signal_market_scope,
        rules_json=settings.market_briefing_signal_rules_json,
    )


def create_company_report_service(settings: Settings) -> CompanyReportService:
    seed_stock_codes = []
    if settings.company_report_seed_stock_codes:
        seed_stock_codes = [
            value.strip()
            for value in settings.company_report_seed_stock_codes.split(",")
            if value.strip()
        ]

    return CompanyReportService(
        db_path=settings.db_path,
        llm_provider=create_company_report_llm_provider(settings),
        pipeline_enabled=settings.company_report_pipeline_enabled,
        market_scope=settings.company_report_market_scope,
        default_universe_key=settings.company_report_universe_key,
        default_universe_name=settings.company_report_universe_name,
        default_universe_target_size=settings.company_report_universe_target_size,
        seed_stock_codes=seed_stock_codes,
        event_lookback_days=settings.company_report_event_lookback_days,
        disclosure_lookback_days=settings.company_report_disclosure_lookback_days,
        price_lookback_days=settings.company_report_price_lookback_days,
    )


def create_global_events_service(settings: Settings):
    return _create_global_events_service(settings)


def create_company_report_llm_provider(settings: Settings):
    provider = settings.company_report_llm_provider.strip().lower()
    enabled = settings.company_report_llm_enabled

    if not enabled or provider in {"", "disabled"}:
        return DisabledCompanyReportNarrativeProvider()

    if provider in {"openai", "openai_compatible"}:
        return OpenAICompatibleCompanyReportProvider(
            enabled=True,
            base_url=settings.company_report_llm_base_url,
            api_key=settings.company_report_llm_api_key,
            model=settings.company_report_llm_model,
            timeout_seconds=settings.company_report_llm_timeout_seconds,
            max_retries=settings.company_report_llm_max_retries,
            backoff_seconds=settings.company_report_llm_backoff_seconds,
        )

    return DisabledCompanyReportNarrativeProvider()
