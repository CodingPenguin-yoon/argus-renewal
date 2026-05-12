from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from ...config.env import Settings
from ..db import get_connection, resolve_db_path, utcnow_iso
from ..storage import ArgusV2Storage
from .kis_derivatives import KisDomesticDerivativesService
from .kis_auth import KisAuthClient, KisAuthError
from .kis_option_chain import KisOptionChainService


KST = timezone(timedelta(hours=9))
DEFAULT_KIS_TOKEN_CACHE_PATH = "data/kis_token_cache.json"


@dataclass(frozen=True)
class KisLiveProviderResult:
    provider_key: str
    status: str
    run_id: int | None
    observed_count: int
    sample_count: int
    derivatives_snapshot_count: int
    option_chain_snapshot_count: int
    error: str | None = None


@dataclass(frozen=True)
class KisLiveSmokeResult:
    db_path: str
    trade_date: str
    snapshot_time: str
    token_status: str
    token_source: str | None
    providers: list[KisLiveProviderResult]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_kis_live_smoke(
    *,
    settings: Settings,
    trade_date: date | None = None,
    snapshot_time: datetime | None = None,
    include_derivatives: bool = True,
    include_option_chain: bool = True,
    token_cache_path: str | None = None,
    http_client: httpx.Client | None = None,
) -> KisLiveSmokeResult:
    resolved_trade_date = trade_date or datetime.now(KST).date()
    resolved_snapshot_time = (snapshot_time or datetime.now(timezone.utc)).astimezone(timezone.utc)
    providers: list[KisLiveProviderResult] = []

    needs_token = _provider_needs_token(settings, include_derivatives=include_derivatives, include_option_chain=include_option_chain)
    token = None
    token_status = "not_required"
    token_source = None

    if needs_token:
        try:
            token = KisAuthClient(
                base_url=settings.kis_base_url,
                token_path=settings.kis_token_path,
                app_key=settings.kis_app_key,
                app_secret=settings.kis_app_secret,
                timeout_seconds=settings.market_briefing_timeout_seconds,
                cache_path=token_cache_path or str(resolve_db_path(settings.kis_token_cache_path or DEFAULT_KIS_TOKEN_CACHE_PATH)),
                http_client=http_client,
            ).issue_access_token()
            token_status = "ready"
            token_source = "cache" if token.raw.get("cache") else "issued"
        except KisAuthError as error:
            token_status = "failed"
            with get_connection(settings.db_path) as connection:
                storage = ArgusV2Storage(connection)
                if include_derivatives:
                    providers.append(
                        _persist_failed_run(
                            storage=storage,
                            provider_key="kis_derivatives",
                            provider_label="KIS 국내파생",
                            endpoint=settings.kis_domestic_derivatives_path,
                            error=error,
                        )
                    )
                if include_option_chain:
                    providers.append(
                        _persist_failed_run(
                            storage=storage,
                            provider_key="kis_option_chain",
                            provider_label="KIS 옵션체인",
                            endpoint=settings.kis_option_chain_path,
                            error=error,
                        )
                    )
            return KisLiveSmokeResult(
                db_path=str(resolve_db_path(settings.db_path)),
                trade_date=resolved_trade_date.isoformat(),
                snapshot_time=_snapshot_iso(resolved_snapshot_time),
                token_status=token_status,
                token_source=token_source,
                providers=providers,
            )

    access_token = token.access_token if token is not None else ""

    with get_connection(settings.db_path) as connection:
        storage = ArgusV2Storage(connection)

        if include_derivatives:
            providers.append(
                _fetch_and_store_derivatives(
                    settings=settings,
                    storage=storage,
                    access_token=access_token,
                    trade_date=resolved_trade_date,
                    snapshot_time=resolved_snapshot_time,
                    http_client=http_client,
                )
            )

        if include_option_chain:
            providers.append(
                _fetch_and_store_option_chain(
                    settings=settings,
                    storage=storage,
                    access_token=access_token,
                    trade_date=resolved_trade_date,
                    snapshot_time=resolved_snapshot_time,
                    http_client=http_client,
                )
            )

    return KisLiveSmokeResult(
        db_path=str(resolve_db_path(settings.db_path)),
        trade_date=resolved_trade_date.isoformat(),
        snapshot_time=_snapshot_iso(resolved_snapshot_time),
        token_status=token_status,
        token_source=token_source,
        providers=providers,
    )


def _provider_needs_token(
    settings: Settings,
    *,
    include_derivatives: bool,
    include_option_chain: bool,
) -> bool:
    providers = []
    if include_derivatives:
        providers.append(settings.kis_domestic_derivatives_provider)
    if include_option_chain:
        providers.append(settings.kis_option_chain_provider)
    return any((provider or "").strip().lower() == "api" for provider in providers)


def _fetch_and_store_derivatives(
    *,
    settings: Settings,
    storage: ArgusV2Storage,
    access_token: str,
    trade_date: date,
    snapshot_time: datetime,
    http_client: httpx.Client | None,
) -> KisLiveProviderResult:
    provider_key = "kis_derivatives"
    endpoint = settings.kis_domestic_derivatives_path
    try:
        batch = KisDomesticDerivativesService(
            provider=settings.kis_domestic_derivatives_provider,
            file_path=settings.kis_domestic_derivatives_file_path,
            base_url=settings.kis_base_url,
            endpoint_path=endpoint,
            app_key=settings.kis_app_key,
            app_secret=settings.kis_app_secret,
            access_token=access_token,
            timeout_seconds=settings.market_briefing_timeout_seconds,
            max_retries=settings.market_briefing_max_retries,
            backoff_seconds=settings.market_briefing_backoff_seconds,
            response_paths=settings.kis_domestic_derivatives_response_paths,
            query_params_json=settings.kis_domestic_derivatives_query_params_json,
            field_alias_map_json=settings.kis_domestic_derivatives_field_alias_map_json,
            tr_id=settings.kis_domestic_derivatives_tr_id,
            http_client=http_client,
        ).fetch_pre_open_snapshots(trade_date=trade_date, snapshot_time=snapshot_time)
        persisted = storage.save_provider_batch(
            provider_key=provider_key,
            provider_label="KIS 국내파생",
            endpoint=endpoint,
            batch=batch,
        )
        return KisLiveProviderResult(
            provider_key=provider_key,
            status=persisted.status,
            run_id=persisted.run_id,
            observed_count=persisted.observed_count,
            sample_count=len(persisted.sample_ids),
            derivatives_snapshot_count=len(persisted.derivatives_snapshot_ids),
            option_chain_snapshot_count=len(persisted.option_chain_snapshot_ids),
        )
    except Exception as error:
        return _persist_failed_run(
            storage=storage,
            provider_key=provider_key,
            provider_label="KIS 국내파생",
            endpoint=endpoint,
            error=error,
        )


def _fetch_and_store_option_chain(
    *,
    settings: Settings,
    storage: ArgusV2Storage,
    access_token: str,
    trade_date: date,
    snapshot_time: datetime,
    http_client: httpx.Client | None,
) -> KisLiveProviderResult:
    provider_key = "kis_option_chain"
    endpoint = settings.kis_option_chain_path
    try:
        batch = KisOptionChainService(
            provider=settings.kis_option_chain_provider,
            file_path=settings.kis_option_chain_file_path,
            base_url=settings.kis_base_url,
            endpoint_path=endpoint,
            app_key=settings.kis_app_key,
            app_secret=settings.kis_app_secret,
            access_token=access_token,
            timeout_seconds=settings.market_briefing_timeout_seconds,
            max_retries=settings.market_briefing_max_retries,
            backoff_seconds=settings.market_briefing_backoff_seconds,
            response_paths=settings.kis_option_chain_response_paths,
            query_params_json=settings.kis_option_chain_query_params_json,
            field_alias_map_json=settings.kis_option_chain_field_alias_map_json,
            tr_id=settings.kis_option_chain_tr_id,
            expiry_month=settings.kis_option_chain_expiry_month,
            expiry_list_path=settings.kis_option_list_path,
            expiry_list_response_paths=settings.kis_option_list_response_paths,
            expiry_list_query_params_json=settings.kis_option_list_query_params_json,
            expiry_list_tr_id=settings.kis_option_list_tr_id,
            expected_level_count=settings.kis_option_chain_expected_level_count,
            stale_after_seconds=settings.kis_option_chain_stale_after_seconds,
            http_client=http_client,
        ).fetch_option_chain_snapshot(trade_date=trade_date, snapshot_time=snapshot_time)
        persisted = storage.save_provider_batch(
            provider_key=provider_key,
            provider_label="KIS 옵션체인",
            endpoint=endpoint,
            batch=batch,
        )
        return KisLiveProviderResult(
            provider_key=provider_key,
            status=persisted.status,
            run_id=persisted.run_id,
            observed_count=persisted.observed_count,
            sample_count=len(persisted.sample_ids),
            derivatives_snapshot_count=len(persisted.derivatives_snapshot_ids),
            option_chain_snapshot_count=len(persisted.option_chain_snapshot_ids),
        )
    except Exception as error:
        return _persist_failed_run(
            storage=storage,
            provider_key=provider_key,
            provider_label="KIS 옵션체인",
            endpoint=endpoint,
            error=error,
        )


def _persist_failed_run(
    *,
    storage: ArgusV2Storage,
    provider_key: str,
    provider_label: str,
    endpoint: str,
    error: Exception,
) -> KisLiveProviderResult:
    run_id = storage.start_provider_run(
        provider_key=provider_key,
        provider_label=provider_label,
        endpoint=endpoint,
        started_at=utcnow_iso(),
    )
    storage.finish_provider_run(
        run_id=run_id,
        status="failed",
        observed_count=0,
        error=_safe_error_message(error),
    )
    return KisLiveProviderResult(
        provider_key=provider_key,
        status="failed",
        run_id=run_id,
        observed_count=0,
        sample_count=0,
        derivatives_snapshot_count=0,
        option_chain_snapshot_count=0,
        error=_safe_error_message(error),
    )


def _safe_error_message(error: Exception) -> str:
    text = str(error)
    for marker in ("appkey", "appsecret", "authorization", "access_token", "token"):
        text = text.replace(marker, "[redacted]")
    if not text:
        return error.__class__.__name__
    return f"{error.__class__.__name__}: {text[:500]}"


def _snapshot_iso(snapshot_time: datetime) -> str:
    return snapshot_time.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
