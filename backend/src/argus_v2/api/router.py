from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ...config.env import Settings, get_settings
from ..contracts import MarketDashboard
from ..dashboard import build_dashboard_from_storage
from ..db import get_connection
from ..judgement import build_market_judgement
from ..providers import build_mock_dashboard_inputs
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

    return router
