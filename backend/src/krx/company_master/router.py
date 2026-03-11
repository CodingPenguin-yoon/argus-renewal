from fastapi import APIRouter, Query

from ...config.env import get_settings
from .service import CompanyMasterService


def create_krx_company_master_admin_router() -> APIRouter:
    router = APIRouter(prefix="/admin/company-mappings", tags=["krx-company-master-admin"])

    @router.get("/summary")
    async def mapping_summary(
        recent_limit: int = Query(default=20, ge=1, le=100),
    ) -> dict:
        settings = get_settings()
        service = CompanyMasterService(db_path=settings.db_path)
        return service.get_mapping_summary(recent_limit=recent_limit)

    @router.get("/unresolved")
    async def unresolved_mappings(
        limit: int = Query(default=200, ge=1, le=2000),
    ) -> dict:
        settings = get_settings()
        service = CompanyMasterService(db_path=settings.db_path)
        items = service.get_unresolved_mappings(limit=limit)
        return {"count": len(items), "items": items}

    @router.get("/manual-overrides")
    async def manual_overrides(
        limit: int = Query(default=200, ge=1, le=2000),
    ) -> dict:
        settings = get_settings()
        service = CompanyMasterService(db_path=settings.db_path)
        items = service.list_manual_overrides(limit=limit)
        return {"count": len(items), "items": items}

    return router
