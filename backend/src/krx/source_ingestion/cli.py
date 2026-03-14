from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import logging
from pathlib import Path
from typing import Any

from ...config.env import get_settings
from ..news.factory import create_news_product_service
from .factory import (
    create_company_report_service,
    create_event_normalization_service,
    create_global_events_service,
    create_market_briefing_input_service,
    create_market_briefing_signal_service,
    create_raw_document_ingestion_service,
)
from .providers import TrendKeywordGroup
from .schedule import resolve_news_automation_cadence

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

DEFAULT_NEWS_AUTOMATION_NORMALIZE_LIMIT = 200


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _as_result_payload(result) -> dict[str, Any]:
    return {
        "run_id": result.run_id,
        "status": result.status,
        "provider": result.provider,
        "source_kind": result.source_kind,
        "source_key": result.source_key,
        "processed_count": result.processed_count,
        "inserted_count": result.inserted_count,
        "duplicate_count": result.duplicate_count,
        "failed_count": result.failed_count,
        "cursor_before": result.cursor_before,
        "cursor_after": result.cursor_after,
        "error_message": result.error_message,
    }


def _as_event_result_payload(result) -> dict[str, Any]:
    return {
        "run_id": result.run_id,
        "status": result.status,
        "processed_count": result.processed_count,
        "created_event_count": result.created_event_count,
        "updated_event_count": result.updated_event_count,
        "review_enqueued_count": result.review_enqueued_count,
        "failed_count": result.failed_count,
    }


def _as_briefing_result_payload(result) -> dict[str, Any]:
    return {
        "run_id": result.run_id,
        "status": result.status,
        "job_name": result.job_name,
        "mode": result.mode,
        "trade_date": result.trade_date,
        "start_date": result.start_date,
        "end_date": result.end_date,
        "processed_provider_count": result.processed_provider_count,
        "success_provider_count": result.success_provider_count,
        "failed_provider_count": result.failed_provider_count,
        "skipped_provider_count": result.skipped_provider_count,
        "inserted_count": result.inserted_count,
        "updated_count": result.updated_count,
        "provider_results": result.provider_results,
        "error_message": result.error_message,
    }


def _as_signal_briefing_payload(result) -> dict[str, Any]:
    return {
        "briefing_id": result.briefing_id,
        "trade_date": result.trade_date,
        "market_scope": result.market_scope,
        "directional_bias": result.directional_bias,
        "gap_bias": result.gap_bias,
        "volatility_bias": result.volatility_bias,
        "confidence_bucket": result.confidence_bucket,
        "total_score": result.total_score,
        "volatility_score": result.volatility_score,
        "explanation_ko": result.explanation_ko,
        "json_payload": result.json_payload,
        "markdown_summary": result.markdown_summary,
        "notification_payload": result.notification_payload,
        "components": result.components,
        "generated_at": result.generated_at,
    }


def _as_signal_backtest_payload(result) -> dict[str, Any]:
    return {
        "backtest_id": result.backtest_id,
        "briefing_id": result.briefing_id,
        "trade_date": result.trade_date,
        "evaluation_date": result.evaluation_date,
        "predicted_directional_bias": result.predicted_directional_bias,
        "actual_directional_bias": result.actual_directional_bias,
        "predicted_gap_bias": result.predicted_gap_bias,
        "actual_gap_bias": result.actual_gap_bias,
        "predicted_volatility_bias": result.predicted_volatility_bias,
        "actual_volatility_bias": result.actual_volatility_bias,
        "directional_hit": result.directional_hit,
        "gap_hit": result.gap_hit,
        "volatility_hit": result.volatility_hit,
        "hit_rate": result.hit_rate,
        "confusion_summary": result.confusion_summary,
        "score_distribution": result.score_distribution,
        "metrics": result.metrics,
    }


def _as_company_report_run_payload(result) -> dict[str, Any]:
    return {
        "run_id": result.run_id,
        "batch_run_key": result.batch_run_key,
        "universe_key": result.universe_key,
        "company_id": result.company_id,
        "trade_date": result.trade_date,
        "status": result.status,
        "report_id": result.report_id,
        "generation_method": result.generation_method,
        "llm_provider": result.llm_provider,
        "llm_model": result.llm_model,
        "error_message": result.error_message,
    }


def _as_company_report_batch_payload(result) -> dict[str, Any]:
    return {
        "batch_run_key": result.batch_run_key,
        "universe_key": result.universe_key,
        "trade_date": result.trade_date,
        "run_mode": result.run_mode,
        "total_count": result.total_count,
        "success_count": result.success_count,
        "partial_success_count": result.partial_success_count,
        "failed_count": result.failed_count,
        "skipped_count": result.skipped_count,
        "items": result.items,
        "error_message": result.error_message,
    }


def _as_global_events_sync_payload(result) -> dict[str, Any]:
    return {
        "status": result.status,
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "schedule_upserted": result.schedule_upserted,
        "release_upserted": result.release_upserted,
        "impacts_upserted": result.impacts_upserted,
        "provider_results": result.provider_results,
        "error_message": result.error_message,
    }


def _default_trade_date_kst() -> date:
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst).date()


def _resolve_trade_date(value: date | None) -> date:
    return value or _default_trade_date_kst()


def _parse_csv_values(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_csv_int_values(value: str | None) -> list[int]:
    parsed: list[int] = []
    for item in _parse_csv_values(value):
        try:
            parsed.append(int(item))
        except ValueError as error:
            raise SystemExit(f"Invalid integer in CSV list: {item}") from error
    return parsed


def _resolve_window(days: int) -> tuple[datetime, datetime]:
    window_end = datetime.now(timezone.utc)
    window_start = window_end - timedelta(days=max(days, 1))
    return window_start, window_end


def _sample_news_record(item) -> dict[str, Any]:
    return {
        "provider": item.provider,
        "provider_document_id": item.provider_document_id,
        "title": item.title,
        "publisher": item.publisher,
        "published_at": item.published_at,
        "source_url": item.source_url,
        "canonical_url": item.canonical_url,
        "summary": item.summary,
        "query_text": item.query_text,
    }


def _parse_trend_groups(values: list[str]) -> list[TrendKeywordGroup]:
    groups: list[TrendKeywordGroup] = []
    for raw_value in values:
        group_name, separator, raw_keywords = raw_value.partition("=")
        if not separator:
            raise SystemExit("Trend group must use the format GROUP=keyword1,keyword2")

        normalized_group_name = group_name.strip()
        keywords = [item.strip() for item in raw_keywords.split(",") if item.strip()]
        if not normalized_group_name or not keywords:
            raise SystemExit("Trend group must include a group name and at least one keyword")

        groups.append(TrendKeywordGroup(group_name=normalized_group_name, keywords=keywords))

    if not groups:
        raise SystemExit("Provide at least one --group")
    return groups


def _load_json_items(input_path: str) -> list[dict[str, Any]]:
    source = Path(input_path)
    if not source.exists():
        raise SystemExit(f"Input file not found: {source}")

    payload = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict) and isinstance(payload.get("items"), list):
        items = payload["items"]
    else:
        raise SystemExit("Input JSON must be a list or an object with items[]")

    normalized: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            normalized.append(item)
    return normalized


def _sync_dart(days: int, backfill: bool) -> None:
    settings = get_settings()
    service = create_raw_document_ingestion_service(settings)
    result = service.sync_dart_disclosures_last_days(days=days, backfill=backfill)
    _print_json(_as_result_payload(result))


def _list_ingestion_providers() -> None:
    settings = get_settings()
    service = create_raw_document_ingestion_service(settings)
    payload = service.list_supported_ingestion_providers()
    _print_json(payload)


def _backfill_publishers(*, limit: int | None, all_rows: bool) -> None:
    settings = get_settings()
    service = create_raw_document_ingestion_service(settings)
    payload = service.backfill_publisher_registry(
        limit=limit,
        only_missing=not all_rows,
    )
    _print_json(payload)


def _sync_disclosures(*, provider: str, days: int, backfill: bool) -> None:
    settings = get_settings()
    service = create_raw_document_ingestion_service(settings)
    result = service.sync_disclosures_last_days(
        provider=provider,
        days=days,
        backfill=backfill,
    )
    _print_json(_as_result_payload(result))


def _sync_news_companies(
    *,
    company_ids: list[int],
    company_names: list[str],
    days: int,
    backfill: bool,
) -> None:
    if not company_ids and not company_names:
        raise SystemExit("Provide at least one --company-id or --company-name")

    settings = get_settings()
    service = create_raw_document_ingestion_service(settings)
    results = service.sync_news_candidates_for_companies_last_days(
        company_ids=company_ids,
        company_names=company_names,
        days=days,
        backfill=backfill,
    )
    _print_json(
        {
            "runs": [_as_result_payload(result) for result in results],
            "run_count": len(results),
        }
    )


def _sync_news_themes(*, keywords: list[str], days: int, backfill: bool) -> None:
    normalized_keywords = [keyword.strip() for keyword in keywords if keyword.strip()]
    if not normalized_keywords:
        raise SystemExit("Provide at least one --keyword")

    settings = get_settings()
    service = create_raw_document_ingestion_service(settings)
    results = service.sync_news_candidates_for_themes_last_days(
        keywords=normalized_keywords,
        days=days,
        backfill=backfill,
    )
    _print_json(
        {
            "runs": [_as_result_payload(result) for result in results],
            "run_count": len(results),
        }
    )


def _sync_news(
    *,
    providers: list[str],
    scope: str,
    company_ids: list[int],
    company_names: list[str],
    keywords: list[str],
    days: int,
    backfill: bool,
) -> None:
    settings = get_settings()
    service = create_raw_document_ingestion_service(settings)

    if scope == "companies":
        if not company_ids and not company_names:
            raise SystemExit("Provide at least one --company-id or --company-name")
        results = service.sync_news_candidates_for_companies_last_days(
            company_ids=company_ids,
            company_names=company_names,
            days=days,
            backfill=backfill,
            providers=providers,
        )
    else:
        normalized_keywords = [keyword.strip() for keyword in keywords if keyword.strip()]
        if not normalized_keywords:
            raise SystemExit("Provide at least one --keyword")
        results = service.sync_news_candidates_for_themes_last_days(
            keywords=normalized_keywords,
            days=days,
            backfill=backfill,
            providers=providers,
        )

    _print_json(
        {
            "runs": [_as_result_payload(result) for result in results],
            "run_count": len(results),
            "providers": providers,
            "scope": scope,
        }
    )


def _probe_news_provider(
    *,
    provider: str,
    query: str,
    days: int,
    sample_limit: int,
) -> None:
    settings = get_settings()
    service = create_raw_document_ingestion_service(settings)
    window_start, window_end = _resolve_window(days)
    normalized_provider = provider.strip().upper()

    provider_map = {
        "MK_RSS": service.mk_rss_provider,
        "NAVER_NEWS": service.naver_provider,
    }
    selected_provider = provider_map.get(normalized_provider)
    if selected_provider is None:
        raise SystemExit(f"Unsupported raw news probe provider: {provider}")

    try:
        batch = selected_provider.fetch_news(
            query=query,
            window_start=window_start,
            window_end=window_end,
            cursor=None,
        )
        _print_json(
            {
                "provider": normalized_provider,
                "query": query,
                "status": "SKIPPED_DISABLED" if batch.disabled_reason else "SUCCESS",
                "disabled_reason": batch.disabled_reason,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "record_count": len(batch.records),
                "sample_limit": sample_limit,
                "next_cursor": batch.next_cursor,
                "metadata": batch.metadata,
                "samples": [_sample_news_record(item) for item in batch.records[:sample_limit]],
            }
        )
    except Exception as error:
        _print_json(
            {
                "provider": normalized_provider,
                "query": query,
                "status": "FAILED",
                "error_message": str(error),
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "record_count": 0,
                "sample_limit": sample_limit,
                "samples": [],
            }
        )
        raise SystemExit(1) from error


def _probe_trend_provider(
    *,
    provider: str,
    groups: list[str],
    days: int,
    sample_limit: int,
) -> None:
    normalized_provider = provider.strip().upper()
    if normalized_provider != "NAVER_DATALAB":
        raise SystemExit(f"Unsupported trend probe provider: {provider}")

    settings = get_settings()
    service = create_news_product_service(settings)
    datalab_provider = service.datalab_provider
    end_date = _default_trade_date_kst()
    start_date = end_date - timedelta(days=max(days, 1))
    parsed_groups = _parse_trend_groups(groups)

    try:
        batch = datalab_provider.fetch_interest_scores(
            start_date=start_date,
            end_date=end_date,
            groups=parsed_groups,
        )
        score_items = [
            {
                "group_name": score.group_name,
                "latest_ratio": score.latest_ratio,
                "average_ratio": score.average_ratio,
                "latest_period": score.latest_period,
                "datapoint_count": score.datapoint_count,
            }
            for score in batch.scores.values()
        ]
        _print_json(
            {
                "provider": normalized_provider,
                "status": "SKIPPED_DISABLED" if batch.disabled_reason else "SUCCESS",
                "disabled_reason": batch.disabled_reason,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "group_count": len(parsed_groups),
                "score_count": len(score_items),
                "sample_limit": sample_limit,
                "samples": score_items[:sample_limit],
            }
        )
    except Exception as error:
        _print_json(
            {
                "provider": normalized_provider,
                "status": "FAILED",
                "error_message": str(error),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "group_count": len(parsed_groups),
                "score_count": 0,
                "sample_limit": sample_limit,
                "samples": [],
            }
        )
        raise SystemExit(1) from error


def _backfill(
    *,
    start_date: date,
    end_date: date,
    provider_scope: str,
    company_ids: list[int],
    company_names: list[str],
    keywords: list[str],
) -> None:
    include_dart = provider_scope in {"all", "dart"}
    include_news = provider_scope in {"all", "news"}

    settings = get_settings()
    service = create_raw_document_ingestion_service(settings)
    results = service.backfill_by_date_range(
        start_date=start_date,
        end_date=end_date,
        include_dart=include_dart,
        include_news=include_news,
        company_ids=company_ids,
        company_names=company_names,
        keywords=keywords,
    )
    _print_json(
        {
            "runs": [_as_result_payload(result) for result in results],
            "run_count": len(results),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
    )


def _build_sync_scheduled_payload(settings) -> dict[str, Any]:
    service = create_raw_document_ingestion_service(settings)
    days = max(1, settings.raw_ingestion_schedule_days)
    disclosure_providers = _parse_csv_values(getattr(settings, "raw_ingestion_schedule_disclosure_providers", None))
    company_news_providers = _parse_csv_values(getattr(settings, "raw_ingestion_schedule_company_news_providers", None))
    theme_news_providers = _parse_csv_values(getattr(settings, "raw_ingestion_schedule_theme_news_providers", None))
    company_ids = _parse_csv_int_values(getattr(settings, "raw_ingestion_schedule_company_ids", None))
    company_names = _parse_csv_values(getattr(settings, "raw_ingestion_schedule_company_names", None))
    theme_keywords = _parse_csv_values(getattr(settings, "raw_ingestion_schedule_theme_keywords", None))

    results = []
    if disclosure_providers:
        for provider in disclosure_providers:
            results.append(service.sync_disclosures_last_days(provider=provider, days=days, backfill=False))
    elif getattr(settings, "raw_ingestion_schedule_include_dart", False):
        results.append(service.sync_dart_disclosures_last_days(days=days, backfill=False))

    if (getattr(settings, "raw_ingestion_schedule_include_company_news", False) or company_news_providers) and (
        company_ids or company_names
    ):
        results.extend(
            service.sync_news_candidates_for_companies_last_days(
                company_ids=company_ids,
                company_names=company_names,
                days=days,
                backfill=False,
                providers=company_news_providers or None,
            )
        )

    if (getattr(settings, "raw_ingestion_schedule_include_theme_news", False) or theme_news_providers) and theme_keywords:
        results.extend(
            service.sync_news_candidates_for_themes_last_days(
                keywords=theme_keywords,
                days=days,
                backfill=False,
                providers=theme_news_providers or None,
            )
        )

    failed_runs = [result for result in results if result.status == "FAILED"]
    disabled_runs = [result for result in results if result.status == "SKIPPED_DISABLED"]
    success_runs = [result for result in results if result.status == "SUCCESS"]

    return {
        "runs": [_as_result_payload(result) for result in results],
        "run_count": len(results),
        "schedule_days": days,
        "disclosure_providers": disclosure_providers,
        "company_news_providers": company_news_providers,
        "theme_news_providers": theme_news_providers,
        "company_ids": company_ids,
        "company_names": company_names,
        "theme_keywords": theme_keywords,
        "success_count": len(success_runs),
        "disabled_count": len(disabled_runs),
        "failed_count": len(failed_runs),
    }


def _sync_scheduled() -> None:
    payload = _build_sync_scheduled_payload(get_settings())
    _print_json(payload)

    if payload["failed_count"]:
        raise SystemExit(1)


def _sync_global_events(*, start_date: date | None, end_date: date | None) -> None:
    settings = get_settings()
    service = create_global_events_service(settings)
    kst_today = _default_trade_date_kst()
    resolved_start = start_date or (kst_today - timedelta(days=settings.global_events_schedule_lookback_days))
    resolved_end = end_date or (kst_today + timedelta(days=settings.global_events_schedule_lookahead_days))
    result = service.sync(start_date=resolved_start, end_date=resolved_end)
    _print_json(
        {
            **_as_global_events_sync_payload(result),
            "start_date": resolved_start.isoformat(),
            "end_date": resolved_end.isoformat(),
        }
    )
    if result.status == "FAILED":
        raise SystemExit(1)


def _build_normalize_events_payload(settings, *, limit: int, include_llm: bool | None) -> dict[str, Any]:
    if not settings.event_pipeline_enabled:
        return {
            "status": "SKIPPED_DISABLED",
            "reason": "event_pipeline_feature_flag_disabled",
            "run_id": None,
            "processed_count": 0,
            "created_event_count": 0,
            "updated_event_count": 0,
            "review_enqueued_count": 0,
            "failed_count": 0,
        }

    service = create_event_normalization_service(settings)
    effective_include_llm = settings.event_pipeline_include_llm if include_llm is None else include_llm
    result = service.normalize_pending_documents(
        limit=limit,
        include_llm=effective_include_llm,
    )
    return {
        **_as_event_result_payload(result),
        "include_llm": effective_include_llm,
        "low_confidence_threshold": settings.event_pipeline_low_confidence_threshold,
    }


def _normalize_events(*, limit: int, include_llm: bool | None) -> None:
    payload = _build_normalize_events_payload(get_settings(), limit=limit, include_llm=include_llm)
    _print_json(payload)


def _refresh_news_product_materialization(settings, *, force: bool) -> dict[str, Any]:
    service = create_news_product_service(settings)
    service.refresh_materialized(force=force)
    coverage = service.get_coverage()
    return {
        "status": "SUCCESS",
        "force": force,
        "coverage_state": coverage.get("state"),
        "coverage_updated_at": coverage.get("updated_at"),
    }


def _resolve_news_refresh_mode(settings) -> str:
    mode = str(getattr(settings, "raw_ingestion_automation_refresh_mode", "smart") or "smart").strip().lower()
    if mode in {"smart", "force", "skip"}:
        return mode
    return "smart"


def _build_news_refresh_payload(settings) -> dict[str, Any]:
    mode = _resolve_news_refresh_mode(settings)
    if mode == "skip":
        return {"status": "SKIPPED", "mode": mode}

    force = mode == "force"
    payload = _refresh_news_product_materialization(settings, force=force)
    return {
        **payload,
        "mode": mode,
    }


def _run_news_automation(*, now: datetime | None = None) -> None:
    settings = get_settings()
    decision = resolve_news_automation_cadence(
        now=now or datetime.now(timezone.utc),
        timezone_name=settings.raw_ingestion_automation_timezone,
        market_open_time=settings.raw_ingestion_automation_market_open_time,
        market_close_time=settings.raw_ingestion_automation_market_close_time,
        post_close_end_time=settings.raw_ingestion_automation_post_close_end_time,
        weekdays=settings.raw_ingestion_automation_weekdays,
        market_open_interval_minutes=settings.raw_ingestion_automation_market_open_interval_minutes,
        post_close_interval_minutes=settings.raw_ingestion_automation_post_close_interval_minutes,
        off_hours_interval_minutes=settings.raw_ingestion_automation_off_hours_interval_minutes,
        holiday_dates=getattr(settings, "raw_ingestion_automation_holiday_dates", None),
    )
    if not decision.should_run:
        _print_json(
            {
                "status": "SKIPPED_CADENCE",
                "phase": decision.phase,
                "cadence_minutes": decision.cadence_minutes,
                "timezone": decision.timezone_name,
                "evaluated_at": decision.local_now.isoformat(),
                "next_due_at": decision.next_due_at.isoformat(),
            }
        )
        return

    sync_payload = _build_sync_scheduled_payload(settings)
    if sync_payload["failed_count"]:
        _print_json(
            {
                "status": "FAILED",
                "phase": decision.phase,
                "cadence_minutes": decision.cadence_minutes,
                "timezone": decision.timezone_name,
                "executed_at": decision.local_now.isoformat(),
                "sync": sync_payload,
            }
        )
        raise SystemExit(1)

    normalize_payload = _build_normalize_events_payload(
        settings,
        limit=DEFAULT_NEWS_AUTOMATION_NORMALIZE_LIMIT,
        include_llm=None,
    )
    if normalize_payload.get("status") == "FAILED" or normalize_payload.get("failed_count"):
        _print_json(
            {
                "status": "FAILED",
                "phase": decision.phase,
                "cadence_minutes": decision.cadence_minutes,
                "timezone": decision.timezone_name,
                "executed_at": decision.local_now.isoformat(),
                "sync": sync_payload,
                "normalize": normalize_payload,
            }
        )
        raise SystemExit(1)

    refresh_payload = _build_news_refresh_payload(settings)
    _print_json(
        {
            "status": "SUCCESS",
            "phase": decision.phase,
            "cadence_minutes": decision.cadence_minutes,
            "timezone": decision.timezone_name,
            "executed_at": decision.local_now.isoformat(),
            "sync": sync_payload,
            "normalize": normalize_payload,
            "refresh": refresh_payload,
        }
    )


def _list_event_review_queue(*, limit: int, status: str | None) -> None:
    settings = get_settings()
    service = create_event_normalization_service(settings)
    items = service.list_review_queue(limit=limit, status=status)
    _print_json({"count": len(items), "items": items})


def _review_event(*, event_id: int, decision: str, reviewer: str, note: str | None) -> None:
    settings = get_settings()
    service = create_event_normalization_service(settings)
    item = service.apply_review_decision(
        event_id=event_id,
        decision=decision,
        reviewer=reviewer,
        note=note,
    )
    _print_json({"item": item})


def _collect_briefing_eod(*, trade_date: date | None) -> None:
    settings = get_settings()
    service = create_market_briefing_input_service(settings)
    result = service.collect_end_of_day_factors(trade_date=_resolve_trade_date(trade_date))
    _print_json(_as_briefing_result_payload(result))
    if result.status == "FAILED":
        raise SystemExit(1)


def _collect_briefing_night(*, trade_date: date | None) -> None:
    settings = get_settings()
    service = create_market_briefing_input_service(settings)
    result = service.collect_night_session_snapshots(trade_date=_resolve_trade_date(trade_date))
    _print_json(_as_briefing_result_payload(result))
    if result.status == "FAILED":
        raise SystemExit(1)


def _collect_briefing_pre_open(*, trade_date: date | None) -> None:
    settings = get_settings()
    service = create_market_briefing_input_service(settings)
    result = service.collect_pre_open_snapshots(trade_date=_resolve_trade_date(trade_date))
    _print_json(_as_briefing_result_payload(result))
    if result.status == "FAILED":
        raise SystemExit(1)


def _backfill_briefing_inputs(
    *,
    start_date: date,
    end_date: date,
    include_end_of_day: bool,
    include_night_session: bool,
    include_pre_open: bool,
) -> None:
    settings = get_settings()
    service = create_market_briefing_input_service(settings)
    results = service.backfill_by_date_range(
        start_date=start_date,
        end_date=end_date,
        include_end_of_day=include_end_of_day,
        include_night_session=include_night_session,
        include_pre_open=include_pre_open,
    )
    _print_json(
        {
            "runs": [_as_briefing_result_payload(result) for result in results],
            "run_count": len(results),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
    )
    if any(result.status == "FAILED" for result in results):
        raise SystemExit(1)


def _import_krx_derivatives_reference(*, trade_date: date, input_path: str) -> None:
    settings = get_settings()
    service = create_market_briefing_input_service(settings)
    result = service.manual_import_krx_derivatives_reference(
        trade_date=trade_date,
        input_path=input_path,
    )
    _print_json(_as_briefing_result_payload(result))
    if result.status == "FAILED":
        raise SystemExit(1)


def _generate_market_signal_briefing(*, trade_date: date | None, mode: str) -> None:
    settings = get_settings()
    service = create_market_briefing_signal_service(settings)
    result = service.generate_briefing(trade_date=_resolve_trade_date(trade_date), mode=mode)
    _print_json(_as_signal_briefing_payload(result))


def _backtest_market_signal_briefing(*, trade_date: date) -> None:
    settings = get_settings()
    service = create_market_briefing_signal_service(settings)
    try:
        result = service.backtest_briefing(trade_date=trade_date)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    _print_json(_as_signal_backtest_payload(result))


def _backtest_market_signal_range(*, start_date: date, end_date: date) -> None:
    settings = get_settings()
    service = create_market_briefing_signal_service(settings)
    if end_date < start_date:
        raise SystemExit("--end-date must be on or after --start-date")
    results = service.backtest_date_range(start_date=start_date, end_date=end_date)
    _print_json(
        {
            "items": [_as_signal_backtest_payload(item) for item in results],
            "count": len(results),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
    )


def _ensure_company_report_universe(
    *,
    universe_key: str | None,
    universe_name: str | None,
    target_size: int | None,
    seed_stock_codes: list[str],
) -> None:
    settings = get_settings()
    service = create_company_report_service(settings)
    universe = service.ensure_universe(
        universe_key=universe_key,
        universe_name=universe_name,
        target_size=target_size,
        selection_mode="MIXED",
        description="KRX large-cap nightly report coverage universe",
    )

    sync_result: dict[str, Any] | None = None
    if seed_stock_codes:
        sync_result = service.sync_universe_members(
            universe_key=universe["universe_key"],
            stock_codes=seed_stock_codes,
            replace=True,
            member_source="MANUAL",
            note="seeded from CLI",
        )

    _print_json(
        {
            "universe": universe,
            "seed_sync": sync_result,
        }
    )


def _sync_company_report_universe_members(
    *,
    universe_key: str | None,
    replace: bool,
    stock_codes: list[str],
    company_ids: list[int],
) -> None:
    settings = get_settings()
    service = create_company_report_service(settings)
    result = service.sync_universe_members(
        universe_key=universe_key,
        stock_codes=stock_codes,
        company_ids=company_ids,
        replace=replace,
        member_source="MANUAL",
        note="updated from CLI",
    )
    _print_json({"item": result})


def _list_company_report_universes(*, limit: int, include_inactive: bool) -> None:
    settings = get_settings()
    service = create_company_report_service(settings)
    items = service.list_universes(limit=limit, include_inactive=include_inactive)
    _print_json({"count": len(items), "items": items})


def _list_company_report_universe_members(*, universe_key: str | None, include_inactive: bool, limit: int) -> None:
    settings = get_settings()
    service = create_company_report_service(settings)
    items = service.list_universe_members(
        universe_key=universe_key,
        include_inactive=include_inactive,
        limit=limit,
    )
    _print_json({"count": len(items), "items": items})


def _generate_company_reports_nightly(
    *,
    trade_date: date | None,
    universe_key: str | None,
    max_companies: int | None,
) -> None:
    settings = get_settings()
    service = create_company_report_service(settings)
    result = service.generate_nightly_reports(
        trade_date=_resolve_trade_date(trade_date),
        universe_key=universe_key,
        mode="SCHEDULED",
        max_companies=max_companies,
    )
    _print_json(_as_company_report_batch_payload(result))
    if result.failed_count > 0:
        raise SystemExit(1)


def _generate_company_report_single(
    *,
    company_id: int,
    trade_date: date | None,
    universe_key: str | None,
) -> None:
    settings = get_settings()
    service = create_company_report_service(settings)
    result = service.generate_single_company_report(
        company_id=company_id,
        trade_date=_resolve_trade_date(trade_date),
        universe_key=universe_key,
        mode="RERUN_SINGLE",
    )
    _print_json(_as_company_report_run_payload(result))
    if result.status == "FAILED":
        raise SystemExit(1)


def _rerun_failed_company_reports(
    *,
    trade_date: date | None,
    universe_key: str | None,
    reference_batch_run_key: str | None,
) -> None:
    settings = get_settings()
    service = create_company_report_service(settings)
    result = service.rerun_failed_subset(
        trade_date=_resolve_trade_date(trade_date),
        universe_key=universe_key,
        reference_batch_run_key=reference_batch_run_key,
    )
    _print_json(_as_company_report_batch_payload(result))
    if result.failed_count > 0:
        raise SystemExit(1)


def _list_company_report_runs(
    *,
    limit: int,
    universe_key: str | None,
    batch_run_key: str | None,
    trade_date: date | None,
    status: str | None,
    company_id: int | None,
) -> None:
    settings = get_settings()
    service = create_company_report_service(settings)
    items = service.list_report_runs(
        limit=limit,
        universe_key=universe_key,
        batch_run_key=batch_run_key,
        trade_date=trade_date.isoformat() if trade_date else None,
        status=status,
        company_id=company_id,
    )
    _print_json({"count": len(items), "items": items})


def _latest_company_report(
    *,
    company_id: int,
    universe_key: str | None,
    trade_date: date | None,
) -> None:
    settings = get_settings()
    service = create_company_report_service(settings)
    item = service.get_latest_report_for_company(
        company_id=company_id,
        universe_key=universe_key,
        trade_date=trade_date.isoformat() if trade_date else None,
    )
    _print_json({"item": item})


def _company_report_history(*, company_id: int, universe_key: str | None, limit: int) -> None:
    settings = get_settings()
    service = create_company_report_service(settings)
    items = service.list_report_history_for_company(
        company_id=company_id,
        universe_key=universe_key,
        limit=limit,
    )
    _print_json({"count": len(items), "items": items})


def _latest_universe_reports(
    *,
    universe_key: str | None,
    trade_date: date | None,
    limit: int,
) -> None:
    settings = get_settings()
    service = create_company_report_service(settings)
    items = service.list_latest_reports_for_universe(
        universe_key=universe_key,
        trade_date=trade_date.isoformat() if trade_date else None,
        limit=limit,
    )
    _print_json({"count": len(items), "items": items})


def _import_company_daily_prices(
    *,
    company_id: int,
    input_path: str,
    source_name: str,
    source_url: str | None,
) -> None:
    items = _load_json_items(input_path)
    settings = get_settings()
    service = create_company_report_service(settings)
    result = service.import_company_daily_prices(
        company_id=company_id,
        items=items,
        source_name=source_name,
        source_url=source_url,
    )
    _print_json({"item": result})


def _import_company_investor_flows(
    *,
    company_id: int,
    input_path: str,
    source_name: str,
    source_url: str | None,
) -> None:
    items = _load_json_items(input_path)
    settings = get_settings()
    service = create_company_report_service(settings)
    result = service.import_company_investor_flows(
        company_id=company_id,
        items=items,
        source_name=source_name,
        source_url=source_url,
    )
    _print_json({"item": result})


def _import_company_financial_snapshots(
    *,
    company_id: int,
    input_path: str,
    source_name: str,
    source_url: str | None,
) -> None:
    items = _load_json_items(input_path)
    settings = get_settings()
    service = create_company_report_service(settings)
    result = service.import_company_financial_snapshots(
        company_id=company_id,
        items=items,
        source_name=source_name,
        source_url=source_url,
    )
    _print_json({"item": result})


def _list_company_daily_prices(*, company_id: int, limit: int) -> None:
    settings = get_settings()
    service = create_company_report_service(settings)
    items = service.list_company_daily_prices(company_id=company_id, limit=limit)
    _print_json({"count": len(items), "items": items})


def _list_company_investor_flows(*, company_id: int, limit: int) -> None:
    settings = get_settings()
    service = create_company_report_service(settings)
    items = service.list_company_investor_flows(company_id=company_id, limit=limit)
    _print_json({"count": len(items), "items": items})


def _list_company_financial_snapshots(*, company_id: int, limit: int) -> None:
    settings = get_settings()
    service = create_company_report_service(settings)
    items = service.list_company_financial_snapshots(company_id=company_id, limit=limit)
    _print_json({"count": len(items), "items": items})


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"Invalid date format: {value}") from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Argus KRX raw source ingestion jobs")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "list-ingestion-providers",
        help="List supported disclosure/news ingestion providers and capabilities",
    )

    backfill_publishers_parser = subparsers.add_parser(
        "backfill-publishers",
        help="Normalize publisher keys and populate publisher registry from raw documents",
    )
    backfill_publishers_parser.add_argument("--limit", type=int, default=None)
    backfill_publishers_parser.add_argument("--all", action="store_true")

    dart_parser = subparsers.add_parser("sync-dart", help="Sync DART disclosures for the last N days")
    dart_parser.add_argument("--days", type=int, default=1)
    dart_parser.add_argument("--backfill", action="store_true")

    disclosures_parser = subparsers.add_parser(
        "sync-disclosures",
        help="Sync one disclosure provider for the last N days",
    )
    disclosures_parser.add_argument("--provider", required=True)
    disclosures_parser.add_argument("--days", type=int, default=1)
    disclosures_parser.add_argument("--backfill", action="store_true")

    companies_parser = subparsers.add_parser(
        "sync-news-companies",
        help="Sync news candidates for specific companies",
    )
    companies_parser.add_argument("--company-id", type=int, action="append", default=[])
    companies_parser.add_argument("--company-name", action="append", default=[])
    companies_parser.add_argument("--days", type=int, default=1)
    companies_parser.add_argument("--backfill", action="store_true")

    themes_parser = subparsers.add_parser(
        "sync-news-themes",
        help="Sync news candidates for market themes or keywords",
    )
    themes_parser.add_argument("--keyword", action="append", default=[])
    themes_parser.add_argument("--days", type=int, default=1)
    themes_parser.add_argument("--backfill", action="store_true")

    sync_news_parser = subparsers.add_parser(
        "sync-news",
        help="Sync selected news providers for companies or themes",
    )
    sync_news_parser.add_argument("--provider", action="append", required=True)
    sync_news_parser.add_argument("--scope", choices=["companies", "themes"], required=True)
    sync_news_parser.add_argument("--company-id", type=int, action="append", default=[])
    sync_news_parser.add_argument("--company-name", action="append", default=[])
    sync_news_parser.add_argument("--keyword", action="append", default=[])
    sync_news_parser.add_argument("--days", type=int, default=1)
    sync_news_parser.add_argument("--backfill", action="store_true")

    probe_news_parser = subparsers.add_parser(
        "probe-news-provider",
        help="Read-only probe for a raw news provider without writing to the DB",
    )
    probe_news_parser.add_argument("--provider", required=True, choices=["NAVER_NEWS", "MK_RSS"])
    probe_news_parser.add_argument("--query", required=True)
    probe_news_parser.add_argument("--days", type=int, default=1)
    probe_news_parser.add_argument("--sample-limit", type=int, default=10)

    probe_trend_parser = subparsers.add_parser(
        "probe-trend-provider",
        help="Read-only probe for a trend provider without writing to the DB",
    )
    probe_trend_parser.add_argument("--provider", required=True, choices=["NAVER_DATALAB"])
    probe_trend_parser.add_argument(
        "--group",
        action="append",
        default=[],
        help="Trend group in the form GROUP=keyword1,keyword2",
    )
    probe_trend_parser.add_argument("--days", type=int, default=7)
    probe_trend_parser.add_argument("--sample-limit", type=int, default=10)

    backfill_parser = subparsers.add_parser(
        "backfill",
        help="Backfill raw source documents by date range",
    )
    backfill_parser.add_argument("--start-date", required=True, type=_parse_date)
    backfill_parser.add_argument("--end-date", required=True, type=_parse_date)
    backfill_parser.add_argument(
        "--provider-scope",
        choices=["all", "dart", "news"],
        default="all",
    )
    backfill_parser.add_argument("--company-id", type=int, action="append", default=[])
    backfill_parser.add_argument("--company-name", action="append", default=[])
    backfill_parser.add_argument("--keyword", action="append", default=[])

    subparsers.add_parser(
        "sync-scheduled",
        help="Run default scheduled incremental sync using RAW_INGESTION_SCHEDULE_* env values",
    )
    subparsers.add_parser(
        "run-news-automation",
        help="Run session-aware news automation using scheduler cadence env values",
    )

    global_events_parser = subparsers.add_parser(
        "sync-global-events",
        help="Sync overseas macro catalyst schedules/releases for the KRX global-events tab",
    )
    global_events_parser.add_argument("--start-date", type=_parse_date)
    global_events_parser.add_argument("--end-date", type=_parse_date)

    briefing_eod_parser = subparsers.add_parser(
        "collect-briefing-eod",
        help="Collect end-of-day market briefing factors",
    )
    briefing_eod_parser.add_argument("--trade-date", type=_parse_date)

    briefing_night_parser = subparsers.add_parser(
        "collect-briefing-night",
        help="Collect night-session futures snapshots for market briefing",
    )
    briefing_night_parser.add_argument("--trade-date", type=_parse_date)

    briefing_pre_open_parser = subparsers.add_parser(
        "collect-briefing-preopen",
        help="Collect pre-open derivatives snapshots for market briefing",
    )
    briefing_pre_open_parser.add_argument("--trade-date", type=_parse_date)

    briefing_backfill_parser = subparsers.add_parser(
        "backfill-briefing",
        help="Backfill market briefing inputs by date range",
    )
    briefing_backfill_parser.add_argument("--start-date", required=True, type=_parse_date)
    briefing_backfill_parser.add_argument("--end-date", required=True, type=_parse_date)
    briefing_backfill_parser.add_argument("--skip-end-of-day", action="store_true")
    briefing_backfill_parser.add_argument("--skip-night-session", action="store_true")
    briefing_backfill_parser.add_argument("--skip-pre-open", action="store_true")

    briefing_manual_import_parser = subparsers.add_parser(
        "import-briefing-krx-reference",
        help="Manual import for KRX derivatives reference metrics",
    )
    briefing_manual_import_parser.add_argument("--trade-date", required=True, type=_parse_date)
    briefing_manual_import_parser.add_argument("--input", required=True)

    signal_generate_parser = subparsers.add_parser(
        "generate-market-briefing",
        help="Generate deterministic KRX pre-market briefing from stored factors",
    )
    signal_generate_parser.add_argument("--trade-date", type=_parse_date)
    signal_generate_parser.add_argument(
        "--mode",
        choices=["SCHEDULED", "MANUAL", "BACKFILL"],
        default="MANUAL",
    )

    signal_backtest_parser = subparsers.add_parser(
        "backtest-market-briefing",
        help="Backtest one generated market briefing against next-session outcome",
    )
    signal_backtest_parser.add_argument("--trade-date", required=True, type=_parse_date)

    signal_backtest_range_parser = subparsers.add_parser(
        "backtest-market-briefing-range",
        help="Backtest generated market briefings by date range",
    )
    signal_backtest_range_parser.add_argument("--start-date", required=True, type=_parse_date)
    signal_backtest_range_parser.add_argument("--end-date", required=True, type=_parse_date)

    normalize_events_parser = subparsers.add_parser(
        "normalize-events",
        help="Normalize raw documents into market events",
    )
    normalize_events_parser.add_argument("--limit", type=int, default=200)
    llm_toggle_group = normalize_events_parser.add_mutually_exclusive_group()
    llm_toggle_group.add_argument("--include-llm", action="store_true")
    llm_toggle_group.add_argument("--no-llm", action="store_true")

    review_queue_parser = subparsers.add_parser(
        "list-event-review-queue",
        help="List low-confidence events that require human review",
    )
    review_queue_parser.add_argument("--limit", type=int, default=100)
    review_queue_parser.add_argument("--status", type=str, default=None)

    review_event_parser = subparsers.add_parser(
        "review-event",
        help="Approve or reject a normalized event from the review queue",
    )
    review_event_parser.add_argument("--event-id", type=int, required=True)
    review_event_parser.add_argument("--decision", choices=["approve", "reject"], required=True)
    review_event_parser.add_argument("--reviewer", default="ops")
    review_event_parser.add_argument("--note", default=None)

    ensure_universe_parser = subparsers.add_parser(
        "ensure-report-universe",
        help="Create or update KRX company report universe",
    )
    ensure_universe_parser.add_argument("--universe-key", default=None)
    ensure_universe_parser.add_argument("--universe-name", default=None)
    ensure_universe_parser.add_argument("--target-size", type=int, default=None)
    ensure_universe_parser.add_argument("--seed-stock-code", action="append", default=[])

    sync_universe_members_parser = subparsers.add_parser(
        "sync-report-universe-members",
        help="Sync universe members by stock codes and/or company ids",
    )
    sync_universe_members_parser.add_argument("--universe-key", default=None)
    sync_universe_members_parser.add_argument("--replace", action="store_true")
    sync_universe_members_parser.add_argument("--stock-code", action="append", default=[])
    sync_universe_members_parser.add_argument("--company-id", type=int, action="append", default=[])

    list_universes_parser = subparsers.add_parser(
        "list-report-universes",
        help="List configured company report universes",
    )
    list_universes_parser.add_argument("--limit", type=int, default=20)
    list_universes_parser.add_argument("--include-inactive", action="store_true")

    list_universe_members_parser = subparsers.add_parser(
        "list-report-universe-members",
        help="List company members in a report universe",
    )
    list_universe_members_parser.add_argument("--universe-key", default=None)
    list_universe_members_parser.add_argument("--limit", type=int, default=300)
    list_universe_members_parser.add_argument("--include-inactive", action="store_true")

    generate_nightly_parser = subparsers.add_parser(
        "generate-company-reports-nightly",
        help="Generate nightly company reports for a universe",
    )
    generate_nightly_parser.add_argument("--trade-date", type=_parse_date)
    generate_nightly_parser.add_argument("--universe-key", default=None)
    generate_nightly_parser.add_argument("--max-companies", type=int, default=None)

    generate_single_parser = subparsers.add_parser(
        "generate-company-report",
        help="Generate report for one company and one date",
    )
    generate_single_parser.add_argument("--company-id", required=True, type=int)
    generate_single_parser.add_argument("--trade-date", type=_parse_date)
    generate_single_parser.add_argument("--universe-key", default=None)

    rerun_failed_parser = subparsers.add_parser(
        "rerun-failed-company-reports",
        help="Rerun only failed company report rows from a reference batch",
    )
    rerun_failed_parser.add_argument("--trade-date", type=_parse_date)
    rerun_failed_parser.add_argument("--universe-key", default=None)
    rerun_failed_parser.add_argument("--reference-batch-run-key", default=None)

    list_runs_parser = subparsers.add_parser(
        "list-company-report-runs",
        help="List company report run history",
    )
    list_runs_parser.add_argument("--limit", type=int, default=100)
    list_runs_parser.add_argument("--universe-key", default=None)
    list_runs_parser.add_argument("--batch-run-key", default=None)
    list_runs_parser.add_argument("--trade-date", type=_parse_date)
    list_runs_parser.add_argument("--status", default=None)
    list_runs_parser.add_argument("--company-id", type=int, default=None)

    latest_company_report_parser = subparsers.add_parser(
        "latest-company-report",
        help="Get latest report for one company",
    )
    latest_company_report_parser.add_argument("--company-id", required=True, type=int)
    latest_company_report_parser.add_argument("--universe-key", default=None)
    latest_company_report_parser.add_argument("--trade-date", type=_parse_date)

    history_company_report_parser = subparsers.add_parser(
        "company-report-history",
        help="Get report history for one company",
    )
    history_company_report_parser.add_argument("--company-id", required=True, type=int)
    history_company_report_parser.add_argument("--universe-key", default=None)
    history_company_report_parser.add_argument("--limit", type=int, default=50)

    latest_universe_reports_parser = subparsers.add_parser(
        "latest-universe-reports",
        help="Get latest reports for all companies in a universe",
    )
    latest_universe_reports_parser.add_argument("--universe-key", default=None)
    latest_universe_reports_parser.add_argument("--trade-date", type=_parse_date)
    latest_universe_reports_parser.add_argument("--limit", type=int, default=100)

    import_daily_prices_parser = subparsers.add_parser(
        "import-company-daily-prices",
        help="Import optional company OHLCV rows from JSON",
    )
    import_daily_prices_parser.add_argument("--company-id", required=True, type=int)
    import_daily_prices_parser.add_argument("--input", required=True)
    import_daily_prices_parser.add_argument("--source-name", default="MANUAL_IMPORT")
    import_daily_prices_parser.add_argument("--source-url", default=None)

    import_investor_flows_parser = subparsers.add_parser(
        "import-company-investor-flows",
        help="Import optional company investor flow rows from JSON",
    )
    import_investor_flows_parser.add_argument("--company-id", required=True, type=int)
    import_investor_flows_parser.add_argument("--input", required=True)
    import_investor_flows_parser.add_argument("--source-name", default="MANUAL_IMPORT")
    import_investor_flows_parser.add_argument("--source-url", default=None)

    import_financial_snapshots_parser = subparsers.add_parser(
        "import-company-financial-snapshots",
        help="Import optional company financial snapshot rows from JSON",
    )
    import_financial_snapshots_parser.add_argument("--company-id", required=True, type=int)
    import_financial_snapshots_parser.add_argument("--input", required=True)
    import_financial_snapshots_parser.add_argument("--source-name", default="MANUAL_IMPORT")
    import_financial_snapshots_parser.add_argument("--source-url", default=None)

    list_daily_prices_parser = subparsers.add_parser(
        "list-company-daily-prices",
        help="List company OHLCV rows stored for reports",
    )
    list_daily_prices_parser.add_argument("--company-id", required=True, type=int)
    list_daily_prices_parser.add_argument("--limit", type=int, default=100)

    list_investor_flows_parser = subparsers.add_parser(
        "list-company-investor-flows",
        help="List company investor flow rows stored for reports",
    )
    list_investor_flows_parser.add_argument("--company-id", required=True, type=int)
    list_investor_flows_parser.add_argument("--limit", type=int, default=100)

    list_financial_snapshots_parser = subparsers.add_parser(
        "list-company-financial-snapshots",
        help="List company financial snapshots stored for reports",
    )
    list_financial_snapshots_parser.add_argument("--company-id", required=True, type=int)
    list_financial_snapshots_parser.add_argument("--limit", type=int, default=50)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "list-ingestion-providers":
        _list_ingestion_providers()
        return

    if args.command == "backfill-publishers":
        _backfill_publishers(limit=args.limit, all_rows=args.all)
        return

    if args.command == "sync-dart":
        _sync_dart(days=args.days, backfill=args.backfill)
        return

    if args.command == "sync-disclosures":
        _sync_disclosures(provider=args.provider, days=args.days, backfill=args.backfill)
        return

    if args.command == "sync-news-companies":
        _sync_news_companies(
            company_ids=args.company_id,
            company_names=args.company_name,
            days=args.days,
            backfill=args.backfill,
        )
        return

    if args.command == "sync-news-themes":
        _sync_news_themes(keywords=args.keyword, days=args.days, backfill=args.backfill)
        return

    if args.command == "sync-news":
        _sync_news(
            providers=args.provider,
            scope=args.scope,
            company_ids=args.company_id,
            company_names=args.company_name,
            keywords=args.keyword,
            days=args.days,
            backfill=args.backfill,
        )
        return

    if args.command == "probe-news-provider":
        _probe_news_provider(
            provider=args.provider,
            query=args.query,
            days=args.days,
            sample_limit=args.sample_limit,
        )
        return

    if args.command == "probe-trend-provider":
        _probe_trend_provider(
            provider=args.provider,
            groups=args.group,
            days=args.days,
            sample_limit=args.sample_limit,
        )
        return

    if args.command == "backfill":
        if args.end_date < args.start_date:
            raise SystemExit("--end-date must be on or after --start-date")
        _backfill(
            start_date=args.start_date,
            end_date=args.end_date,
            provider_scope=args.provider_scope,
            company_ids=args.company_id,
            company_names=args.company_name,
            keywords=args.keyword,
        )
        return

    if args.command == "sync-scheduled":
        _sync_scheduled()
        return

    if args.command == "run-news-automation":
        _run_news_automation()
        return

    if args.command == "sync-global-events":
        _sync_global_events(start_date=args.start_date, end_date=args.end_date)
        return

    if args.command == "collect-briefing-eod":
        _collect_briefing_eod(trade_date=args.trade_date)
        return

    if args.command == "collect-briefing-night":
        _collect_briefing_night(trade_date=args.trade_date)
        return

    if args.command == "collect-briefing-preopen":
        _collect_briefing_pre_open(trade_date=args.trade_date)
        return

    if args.command == "backfill-briefing":
        if args.end_date < args.start_date:
            raise SystemExit("--end-date must be on or after --start-date")
        _backfill_briefing_inputs(
            start_date=args.start_date,
            end_date=args.end_date,
            include_end_of_day=not args.skip_end_of_day,
            include_night_session=not args.skip_night_session,
            include_pre_open=not args.skip_pre_open,
        )
        return

    if args.command == "import-briefing-krx-reference":
        _import_krx_derivatives_reference(
            trade_date=args.trade_date,
            input_path=args.input,
        )
        return

    if args.command == "generate-market-briefing":
        _generate_market_signal_briefing(trade_date=args.trade_date, mode=args.mode)
        return

    if args.command == "backtest-market-briefing":
        _backtest_market_signal_briefing(trade_date=args.trade_date)
        return

    if args.command == "backtest-market-briefing-range":
        _backtest_market_signal_range(start_date=args.start_date, end_date=args.end_date)
        return

    if args.command == "normalize-events":
        include_llm: bool | None = None
        if args.include_llm:
            include_llm = True
        if args.no_llm:
            include_llm = False
        _normalize_events(limit=args.limit, include_llm=include_llm)
        return

    if args.command == "list-event-review-queue":
        _list_event_review_queue(limit=args.limit, status=args.status)
        return

    if args.command == "review-event":
        _review_event(
            event_id=args.event_id,
            decision=args.decision,
            reviewer=args.reviewer,
            note=args.note,
        )
        return

    if args.command == "ensure-report-universe":
        _ensure_company_report_universe(
            universe_key=args.universe_key,
            universe_name=args.universe_name,
            target_size=args.target_size,
            seed_stock_codes=args.seed_stock_code,
        )
        return

    if args.command == "sync-report-universe-members":
        _sync_company_report_universe_members(
            universe_key=args.universe_key,
            replace=args.replace,
            stock_codes=args.stock_code,
            company_ids=args.company_id,
        )
        return

    if args.command == "list-report-universes":
        _list_company_report_universes(limit=args.limit, include_inactive=args.include_inactive)
        return

    if args.command == "list-report-universe-members":
        _list_company_report_universe_members(
            universe_key=args.universe_key,
            include_inactive=args.include_inactive,
            limit=args.limit,
        )
        return

    if args.command == "generate-company-reports-nightly":
        _generate_company_reports_nightly(
            trade_date=args.trade_date,
            universe_key=args.universe_key,
            max_companies=args.max_companies,
        )
        return

    if args.command == "generate-company-report":
        _generate_company_report_single(
            company_id=args.company_id,
            trade_date=args.trade_date,
            universe_key=args.universe_key,
        )
        return

    if args.command == "rerun-failed-company-reports":
        _rerun_failed_company_reports(
            trade_date=args.trade_date,
            universe_key=args.universe_key,
            reference_batch_run_key=args.reference_batch_run_key,
        )
        return

    if args.command == "list-company-report-runs":
        _list_company_report_runs(
            limit=args.limit,
            universe_key=args.universe_key,
            batch_run_key=args.batch_run_key,
            trade_date=args.trade_date,
            status=args.status,
            company_id=args.company_id,
        )
        return

    if args.command == "latest-company-report":
        _latest_company_report(
            company_id=args.company_id,
            universe_key=args.universe_key,
            trade_date=args.trade_date,
        )
        return

    if args.command == "company-report-history":
        _company_report_history(
            company_id=args.company_id,
            universe_key=args.universe_key,
            limit=args.limit,
        )
        return

    if args.command == "latest-universe-reports":
        _latest_universe_reports(
            universe_key=args.universe_key,
            trade_date=args.trade_date,
            limit=args.limit,
        )
        return

    if args.command == "import-company-daily-prices":
        _import_company_daily_prices(
            company_id=args.company_id,
            input_path=args.input,
            source_name=args.source_name,
            source_url=args.source_url,
        )
        return

    if args.command == "import-company-investor-flows":
        _import_company_investor_flows(
            company_id=args.company_id,
            input_path=args.input,
            source_name=args.source_name,
            source_url=args.source_url,
        )
        return

    if args.command == "import-company-financial-snapshots":
        _import_company_financial_snapshots(
            company_id=args.company_id,
            input_path=args.input,
            source_name=args.source_name,
            source_url=args.source_url,
        )
        return

    if args.command == "list-company-daily-prices":
        _list_company_daily_prices(company_id=args.company_id, limit=args.limit)
        return

    if args.command == "list-company-investor-flows":
        _list_company_investor_flows(company_id=args.company_id, limit=args.limit)
        return

    if args.command == "list-company-financial-snapshots":
        _list_company_financial_snapshots(company_id=args.company_id, limit=args.limit)
        return

    raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
