from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hmac
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from ...config.env import get_settings
from .factory import (
    create_company_report_service,
    create_event_normalization_service,
    create_global_events_service,
    create_market_briefing_input_service,
    create_market_briefing_signal_service,
    create_raw_document_ingestion_service,
)


def _require_krx_admin_auth(
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
) -> None:
    settings = get_settings()
    expected_key = (settings.krx_admin_api_key or "").strip()
    if not expected_key:
        return

    provided_key = (x_admin_key or "").strip()
    if not provided_key or not hmac.compare_digest(provided_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin key",
        )


def _default_trade_date_kst() -> date:
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst).date()


def create_krx_raw_documents_admin_router() -> APIRouter:
    router = APIRouter(prefix="/admin/raw-documents", tags=["krx-raw-documents-admin"])

    @router.get("")
    async def list_raw_documents(
        limit: int = Query(default=50, ge=1, le=500),
        provider: Optional[str] = Query(default=None),
        include_duplicates: bool = Query(default=False),
    ) -> dict[str, list[dict]]:
        settings = get_settings()
        service = create_raw_document_ingestion_service(settings)
        return {
            "items": service.list_raw_documents(
                limit=limit,
                provider=provider,
                include_duplicates=include_duplicates,
            )
        }

    @router.get("/fetch-runs")
    async def list_fetch_runs(
        limit: int = Query(default=50, ge=1, le=500),
        provider: Optional[str] = Query(default=None),
    ) -> dict[str, list[dict]]:
        settings = get_settings()
        service = create_raw_document_ingestion_service(settings)
        return {"items": service.list_fetch_runs(limit=limit, provider=provider)}

    return router


def create_krx_event_pipeline_admin_router() -> APIRouter:
    router = APIRouter(
        prefix="/admin/events",
        tags=["krx-events-admin"],
        dependencies=[Depends(_require_krx_admin_auth)],
    )

    @router.post("/sync")
    async def sync_events(
        limit: int = Query(default=200, ge=1, le=2000),
        include_llm: Optional[bool] = Query(default=None),
    ) -> dict:
        settings = get_settings()
        if not settings.event_pipeline_enabled:
            return {
                "run_id": None,
                "status": "SKIPPED_DISABLED",
                "processed_count": 0,
                "created_event_count": 0,
                "updated_event_count": 0,
                "review_enqueued_count": 0,
                "failed_count": 0,
                "include_llm": False,
                "reason": "event_pipeline_feature_flag_disabled",
            }

        service = create_event_normalization_service(settings)
        effective_include_llm = settings.event_pipeline_include_llm if include_llm is None else include_llm
        result = service.normalize_pending_documents(limit=limit, include_llm=effective_include_llm)
        return {
            "run_id": result.run_id,
            "status": result.status,
            "processed_count": result.processed_count,
            "created_event_count": result.created_event_count,
            "updated_event_count": result.updated_event_count,
            "review_enqueued_count": result.review_enqueued_count,
            "failed_count": result.failed_count,
            "include_llm": effective_include_llm,
        }

    @router.get("/review-queue")
    async def list_review_queue(
        limit: int = Query(default=100, ge=1, le=500),
        status: Optional[str] = Query(default=None),
    ) -> dict[str, list[dict]]:
        settings = get_settings()
        service = create_event_normalization_service(settings)
        return {"items": service.list_review_queue(limit=limit, status=status)}

    @router.post("/review-queue/{event_id}/approve")
    async def approve_event(
        event_id: int,
        reviewer: str = Query(default="ops"),
        note: Optional[str] = Query(default=None),
    ) -> dict:
        settings = get_settings()
        service = create_event_normalization_service(settings)
        return {
            "item": service.apply_review_decision(
                event_id=event_id,
                decision="approve",
                reviewer=reviewer,
                note=note,
            )
        }

    @router.post("/review-queue/{event_id}/reject")
    async def reject_event(
        event_id: int,
        reviewer: str = Query(default="ops"),
        note: Optional[str] = Query(default=None),
    ) -> dict:
        settings = get_settings()
        service = create_event_normalization_service(settings)
        return {
            "item": service.apply_review_decision(
                event_id=event_id,
                decision="reject",
                reviewer=reviewer,
                note=note,
            )
        }

    return router


def create_krx_market_briefing_admin_router() -> APIRouter:
    router = APIRouter(
        prefix="/admin/briefing-inputs",
        tags=["krx-briefing-inputs-admin"],
        dependencies=[Depends(_require_krx_admin_auth)],
    )

    @router.get("/runs")
    async def list_briefing_runs(
        limit: int = Query(default=50, ge=1, le=500),
        status: Optional[str] = Query(default=None),
        job_name: Optional[str] = Query(default=None),
    ) -> dict[str, list[dict]]:
        settings = get_settings()
        service = create_market_briefing_input_service(settings)
        items = service.list_runs(limit=limit, status=status, job_name=job_name)
        return {"items": items}

    @router.get("/provider-health-checks")
    async def list_provider_health_checks(
        limit: int = Query(default=100, ge=1, le=1000),
        run_id: Optional[int] = Query(default=None),
        provider_name: Optional[str] = Query(default=None),
        status: Optional[str] = Query(default=None),
    ) -> dict[str, list[dict]]:
        settings = get_settings()
        service = create_market_briefing_input_service(settings)
        items = service.list_provider_health_checks(
            limit=limit,
            run_id=run_id,
            provider_name=provider_name,
            status=status,
        )
        return {"items": items}

    @router.get("/market-daily-factors")
    async def list_market_daily_factors(
        limit: int = Query(default=100, ge=1, le=1000),
        trade_date: Optional[str] = Query(default=None),
        source_name: Optional[str] = Query(default=None),
    ) -> dict[str, list[dict]]:
        settings = get_settings()
        service = create_market_briefing_input_service(settings)
        items = service.list_market_daily_factors(
            limit=limit,
            trade_date=trade_date,
            source_name=source_name,
        )
        return {"items": items}

    @router.get("/market-intraday-snapshots")
    async def list_market_intraday_snapshots(
        limit: int = Query(default=200, ge=1, le=2000),
        trade_date: Optional[str] = Query(default=None),
        session_type: Optional[str] = Query(default=None),
        source_name: Optional[str] = Query(default=None),
    ) -> dict[str, list[dict]]:
        settings = get_settings()
        service = create_market_briefing_input_service(settings)
        items = service.list_market_intraday_snapshots(
            limit=limit,
            trade_date=trade_date,
            session_type=session_type,
            source_name=source_name,
        )
        return {"items": items}

    @router.get("/derivatives-daily-metrics")
    async def list_derivatives_daily_metrics(
        limit: int = Query(default=100, ge=1, le=1000),
        trade_date: Optional[str] = Query(default=None),
        source_name: Optional[str] = Query(default=None),
    ) -> dict[str, list[dict]]:
        settings = get_settings()
        service = create_market_briefing_input_service(settings)
        items = service.list_derivatives_daily_metrics(
            limit=limit,
            trade_date=trade_date,
            source_name=source_name,
        )
        return {"items": items}

    return router


def create_krx_market_signal_admin_router() -> APIRouter:
    router = APIRouter(
        prefix="/admin/briefings",
        tags=["krx-briefings-admin"],
        dependencies=[Depends(_require_krx_admin_auth)],
    )

    @router.post("/generate")
    async def generate_briefing(
        trade_date: Optional[date] = Query(default=None),
        mode: str = Query(default="MANUAL"),
    ) -> dict:
        settings = get_settings()
        service = create_market_briefing_signal_service(settings)
        target_date = trade_date or _default_trade_date_kst()
        result = service.generate_briefing(trade_date=target_date, mode=mode)
        return {
            "item": {
                "briefing_id": result.briefing_id,
                "trade_date": result.trade_date,
                "market_scope": result.market_scope,
                "directional_bias": result.directional_bias,
                "gap_bias": result.gap_bias,
                "volatility_bias": result.volatility_bias,
                "confidence_bucket": result.confidence_bucket,
                "total_score": result.total_score,
                "volatility_score": result.volatility_score,
                "generated_at": result.generated_at,
                "json_payload": result.json_payload,
                "markdown_summary": result.markdown_summary,
                "notification_payload": result.notification_payload,
                "components": result.components,
            }
        }

    @router.post("/backtest")
    async def backtest_briefing(
        trade_date: date = Query(...),
    ) -> dict:
        settings = get_settings()
        service = create_market_briefing_signal_service(settings)
        try:
            result = service.backtest_briefing(trade_date=trade_date)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

        return {
            "item": {
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
        }

    @router.post("/backtest/range")
    async def backtest_briefing_range(
        start_date: date = Query(...),
        end_date: date = Query(...),
    ) -> dict[str, list[dict]]:
        settings = get_settings()
        service = create_market_briefing_signal_service(settings)
        results = service.backtest_date_range(start_date=start_date, end_date=end_date)
        return {
            "items": [
                {
                    "backtest_id": item.backtest_id,
                    "briefing_id": item.briefing_id,
                    "trade_date": item.trade_date,
                    "evaluation_date": item.evaluation_date,
                    "predicted_directional_bias": item.predicted_directional_bias,
                    "actual_directional_bias": item.actual_directional_bias,
                    "predicted_gap_bias": item.predicted_gap_bias,
                    "actual_gap_bias": item.actual_gap_bias,
                    "predicted_volatility_bias": item.predicted_volatility_bias,
                    "actual_volatility_bias": item.actual_volatility_bias,
                    "directional_hit": item.directional_hit,
                    "gap_hit": item.gap_hit,
                    "volatility_hit": item.volatility_hit,
                    "hit_rate": item.hit_rate,
                    "confusion_summary": item.confusion_summary,
                    "score_distribution": item.score_distribution,
                    "metrics": item.metrics,
                }
                for item in results
            ]
        }

    @router.get("/latest")
    async def latest_briefing(
        trade_date: Optional[date] = Query(default=None),
    ) -> dict:
        settings = get_settings()
        service = create_market_briefing_signal_service(settings)
        item = service.get_latest_briefing(trade_date=trade_date.isoformat() if trade_date else None)
        return {"item": item}

    @router.get("/history")
    async def briefing_history(
        limit: int = Query(default=50, ge=1, le=500),
        start_date: Optional[date] = Query(default=None),
        end_date: Optional[date] = Query(default=None),
    ) -> dict[str, list[dict]]:
        settings = get_settings()
        service = create_market_briefing_signal_service(settings)
        items = service.list_briefings(
            limit=limit,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
        )
        return {"items": items}

    @router.get("/{trade_date}/components")
    async def briefing_components(
        trade_date: date,
    ) -> dict[str, list[dict]]:
        settings = get_settings()
        service = create_market_briefing_signal_service(settings)
        items = service.list_components_by_date(trade_date=trade_date.isoformat())
        return {"items": items}

    @router.get("/{trade_date}")
    async def briefing_detail(
        trade_date: date,
    ) -> dict:
        settings = get_settings()
        service = create_market_briefing_signal_service(settings)
        item = service.get_briefing_detail(trade_date=trade_date.isoformat())
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Briefing not found")
        return {"item": item}

    return router


def create_krx_global_events_admin_router() -> APIRouter:
    router = APIRouter(
        prefix="/admin/global-events",
        tags=["krx-global-events-admin"],
        dependencies=[Depends(_require_krx_admin_auth)],
    )

    @router.post("/sync")
    async def sync_global_events(
        start_date: Optional[date] = Query(default=None),
        end_date: Optional[date] = Query(default=None),
    ) -> dict:
        settings = get_settings()
        service = create_global_events_service(settings)
        kst_today = _default_trade_date_kst()
        resolved_start = start_date or (kst_today - timedelta(days=settings.global_events_schedule_lookback_days))
        resolved_end = end_date or (kst_today + timedelta(days=settings.global_events_schedule_lookahead_days))
        result = service.sync(start_date=resolved_start, end_date=resolved_end)
        return {
            "item": {
                "status": result.status,
                "started_at": result.started_at,
                "finished_at": result.finished_at,
                "schedule_upserted": result.schedule_upserted,
                "release_upserted": result.release_upserted,
                "impacts_upserted": result.impacts_upserted,
                "provider_results": result.provider_results,
                "error_message": result.error_message,
            }
        }

    return router


def create_krx_company_report_admin_router() -> APIRouter:
    router = APIRouter(
        prefix="/admin/company-reports",
        tags=["krx-company-reports-admin"],
        dependencies=[Depends(_require_krx_admin_auth)],
    )

    @router.get("/universes")
    async def list_universes(
        limit: int = Query(default=20, ge=1, le=200),
        include_inactive: bool = Query(default=False),
    ) -> dict[str, list[dict]]:
        settings = get_settings()
        service = create_company_report_service(settings)
        items = service.list_universes(limit=limit, include_inactive=include_inactive)
        return {"items": items}

    @router.post("/universes/{universe_key}/members")
    async def sync_universe_members(
        universe_key: str,
        replace: bool = Query(default=True),
        stock_code: list[str] = Query(default=[]),
        company_id: list[int] = Query(default=[]),
    ) -> dict:
        settings = get_settings()
        service = create_company_report_service(settings)
        item = service.sync_universe_members(
            universe_key=universe_key,
            stock_codes=stock_code,
            company_ids=company_id,
            replace=replace,
            member_source="MANUAL",
        )
        return {"item": item}

    @router.post("/generate-nightly")
    async def generate_nightly_reports(
        trade_date: Optional[date] = Query(default=None),
        universe_key: Optional[str] = Query(default=None),
        max_companies: Optional[int] = Query(default=None, ge=1, le=200),
    ) -> dict:
        settings = get_settings()
        service = create_company_report_service(settings)
        target_date = trade_date or _default_trade_date_kst()
        result = service.generate_nightly_reports(
            trade_date=target_date,
            universe_key=universe_key,
            mode="SCHEDULED",
            max_companies=max_companies,
        )
        return {"item": result.__dict__}

    @router.post("/generate-company")
    async def generate_single_company(
        company_id: int = Query(..., ge=1),
        trade_date: Optional[date] = Query(default=None),
        universe_key: Optional[str] = Query(default=None),
    ) -> dict:
        settings = get_settings()
        service = create_company_report_service(settings)
        target_date = trade_date or _default_trade_date_kst()
        result = service.generate_single_company_report(
            company_id=company_id,
            trade_date=target_date,
            universe_key=universe_key,
            mode="RERUN_SINGLE",
        )
        return {"item": result.__dict__}

    @router.post("/rerun-failed")
    async def rerun_failed_reports(
        trade_date: Optional[date] = Query(default=None),
        universe_key: Optional[str] = Query(default=None),
        reference_batch_run_key: Optional[str] = Query(default=None),
    ) -> dict:
        settings = get_settings()
        service = create_company_report_service(settings)
        target_date = trade_date or _default_trade_date_kst()
        result = service.rerun_failed_subset(
            trade_date=target_date,
            universe_key=universe_key,
            reference_batch_run_key=reference_batch_run_key,
        )
        return {"item": result.__dict__}

    @router.get("/runs")
    async def list_report_runs(
        limit: int = Query(default=100, ge=1, le=1000),
        universe_key: Optional[str] = Query(default=None),
        batch_run_key: Optional[str] = Query(default=None),
        trade_date: Optional[date] = Query(default=None),
        status: Optional[str] = Query(default=None),
        company_id: Optional[int] = Query(default=None),
    ) -> dict[str, list[dict]]:
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
        return {"items": items}

    @router.get("/inputs/daily-prices/{company_id}")
    async def list_company_daily_prices(
        company_id: int,
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, list[dict]]:
        settings = get_settings()
        service = create_company_report_service(settings)
        items = service.list_company_daily_prices(company_id=company_id, limit=limit)
        return {"items": items}

    @router.get("/inputs/investor-flows/{company_id}")
    async def list_company_investor_flows(
        company_id: int,
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, list[dict]]:
        settings = get_settings()
        service = create_company_report_service(settings)
        items = service.list_company_investor_flows(company_id=company_id, limit=limit)
        return {"items": items}

    @router.get("/inputs/financial-snapshots/{company_id}")
    async def list_company_financial_snapshots(
        company_id: int,
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, list[dict]]:
        settings = get_settings()
        service = create_company_report_service(settings)
        items = service.list_company_financial_snapshots(company_id=company_id, limit=limit)
        return {"items": items}

    @router.get("/company/{company_id}/latest")
    async def latest_company_report(
        company_id: int,
        universe_key: Optional[str] = Query(default=None),
        trade_date: Optional[date] = Query(default=None),
    ) -> dict:
        settings = get_settings()
        service = create_company_report_service(settings)
        item = service.get_latest_report_for_company(
            company_id=company_id,
            universe_key=universe_key,
            trade_date=trade_date.isoformat() if trade_date else None,
        )
        return {"item": item}

    @router.get("/company/{company_id}/history")
    async def company_report_history(
        company_id: int,
        universe_key: Optional[str] = Query(default=None),
        limit: int = Query(default=50, ge=1, le=300),
    ) -> dict[str, list[dict]]:
        settings = get_settings()
        service = create_company_report_service(settings)
        items = service.list_report_history_for_company(
            company_id=company_id,
            universe_key=universe_key,
            limit=limit,
        )
        return {"items": items}

    @router.get("/universe/{universe_key}/latest")
    async def universe_latest_reports(
        universe_key: str,
        trade_date: Optional[date] = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, list[dict]]:
        settings = get_settings()
        service = create_company_report_service(settings)
        items = service.list_latest_reports_for_universe(
            universe_key=universe_key,
            trade_date=trade_date.isoformat() if trade_date else None,
            limit=limit,
        )
        return {"items": items}

    return router
