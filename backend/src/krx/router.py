from fastapi import APIRouter

from .company_master.router import create_krx_company_master_admin_router
from .derivatives.router import create_krx_derivatives_router
from .market.router import create_krx_market_router
from .market_signal.router import create_krx_market_signal_router
from .news.router import create_krx_news_router
from .source_ingestion.router import (
    create_krx_company_report_admin_router,
    create_krx_event_pipeline_admin_router,
    create_krx_global_events_admin_router,
    create_krx_market_briefing_admin_router,
    create_krx_market_signal_admin_router,
    create_krx_raw_documents_admin_router,
)


def create_krx_router() -> APIRouter:
    router = APIRouter(tags=["krx"])
    router.include_router(create_krx_market_router())
    router.include_router(create_krx_market_signal_router())
    router.include_router(create_krx_derivatives_router())
    router.include_router(create_krx_news_router())
    router.include_router(create_krx_company_master_admin_router())
    router.include_router(create_krx_raw_documents_admin_router())
    router.include_router(create_krx_event_pipeline_admin_router())
    router.include_router(create_krx_market_briefing_admin_router())
    router.include_router(create_krx_market_signal_admin_router())
    router.include_router(create_krx_company_report_admin_router())
    router.include_router(create_krx_global_events_admin_router())
    return router
