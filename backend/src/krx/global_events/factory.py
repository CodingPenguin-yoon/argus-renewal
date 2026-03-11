from __future__ import annotations

from ...config.env import Settings
from .adapters import (
    BeaActualDataAdapter,
    BeaScheduleAdapter,
    BlsActualDataAdapter,
    BlsScheduleAdapter,
    BojCalendarAdapter,
    EcbCalendarAdapter,
    FedCalendarAdapter,
    OptionalVendorCalendarAdapter,
)
from .impact_llm import DisabledGlobalEventImpactProvider, OpenAICompatibleGlobalEventImpactProvider
from .service import GlobalEventsService


def create_global_event_impact_provider(settings: Settings):
    provider = settings.global_events_llm_provider.strip().lower()
    enabled = settings.global_events_llm_enabled

    if not enabled or provider in {"", "disabled"}:
        return DisabledGlobalEventImpactProvider()

    if provider in {"openai", "openai_compatible"}:
        return OpenAICompatibleGlobalEventImpactProvider(
            enabled=True,
            base_url=settings.global_events_llm_base_url,
            api_key=settings.global_events_llm_api_key,
            model=settings.global_events_llm_model,
            timeout_seconds=settings.global_events_llm_timeout_seconds,
            max_retries=settings.global_events_llm_max_retries,
            backoff_seconds=settings.global_events_llm_backoff_seconds,
        )

    return DisabledGlobalEventImpactProvider()


def create_global_events_service(settings: Settings) -> GlobalEventsService:
    schedule_adapters = [
        FedCalendarAdapter(
            url=settings.global_events_fed_calendar_url,
            timeout_seconds=settings.global_events_timeout_seconds,
            max_retries=settings.global_events_max_retries,
            backoff_seconds=settings.global_events_backoff_seconds,
        ),
        BlsScheduleAdapter(
            url=settings.global_events_bls_calendar_url,
            timeout_seconds=settings.global_events_timeout_seconds,
            max_retries=settings.global_events_max_retries,
            backoff_seconds=settings.global_events_backoff_seconds,
        ),
        BeaScheduleAdapter(
            url=settings.global_events_bea_schedule_url,
            timeout_seconds=settings.global_events_timeout_seconds,
            max_retries=settings.global_events_max_retries,
            backoff_seconds=settings.global_events_backoff_seconds,
        ),
        EcbCalendarAdapter(
            url=settings.global_events_ecb_calendar_url,
            timeout_seconds=settings.global_events_timeout_seconds,
            max_retries=settings.global_events_max_retries,
            backoff_seconds=settings.global_events_backoff_seconds,
        ),
        BojCalendarAdapter(
            url=settings.global_events_boj_calendar_url,
            timeout_seconds=settings.global_events_timeout_seconds,
            max_retries=settings.global_events_max_retries,
            backoff_seconds=settings.global_events_backoff_seconds,
        ),
    ]

    release_adapters = [
        BlsActualDataAdapter(
            api_url=settings.global_events_bls_api_url,
            timeout_seconds=settings.global_events_timeout_seconds,
            max_retries=settings.global_events_max_retries,
            backoff_seconds=settings.global_events_backoff_seconds,
        ),
        BeaActualDataAdapter(
            pce_url=settings.global_events_bea_pce_url,
            timeout_seconds=settings.global_events_timeout_seconds,
            max_retries=settings.global_events_max_retries,
            backoff_seconds=settings.global_events_backoff_seconds,
        ),
    ]

    vendor_adapter = OptionalVendorCalendarAdapter(
        provider=settings.global_events_vendor_provider,
        file_path=settings.global_events_vendor_file_path,
        base_url=settings.global_events_vendor_base_url,
        schedule_path=settings.global_events_vendor_schedule_path,
        api_key=settings.global_events_vendor_api_key,
        timeout_seconds=settings.global_events_timeout_seconds,
        max_retries=settings.global_events_max_retries,
        backoff_seconds=settings.global_events_backoff_seconds,
        is_required=settings.global_events_vendor_required,
    )

    return GlobalEventsService(
        db_path=settings.db_path,
        schedule_adapters=schedule_adapters,
        release_adapters=release_adapters,
        vendor_adapter=vendor_adapter,
        impact_provider=create_global_event_impact_provider(settings),
        sync_enabled=settings.global_events_sync_enabled,
        release_lookback_days=settings.global_events_release_lookback_days,
    )
