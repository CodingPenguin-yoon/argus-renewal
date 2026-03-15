from __future__ import annotations

from ...config.env import Settings
from .providers import FredRatesProvider
from .service import MacroReferenceService


def create_macro_reference_service(settings: Settings) -> MacroReferenceService:
    return MacroReferenceService(
        fred_rates_provider=FredRatesProvider(
            provider=settings.fred_provider,
            file_path=settings.fred_file_path,
            base_url=settings.fred_base_url,
            series_observations_path=settings.fred_observations_path,
            api_key=settings.fred_api_key,
            timeout_seconds=settings.fred_timeout_seconds,
            max_retries=settings.fred_max_retries,
            backoff_seconds=settings.fred_backoff_seconds,
        ),
        series_ids=settings.fred_series_ids,
    )
