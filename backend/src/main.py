from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config.env import get_settings
from .domains.health.router import create_health_router
from .krx.app_header.router import create_app_header_router
from .krx.app import create_krx_app
from .krx.global_events.router import create_global_events_router
from .krx.market_news.router import create_market_news_router
from .shared.errors import unhandled_exception_handler

settings = get_settings()

app = FastAPI(title="Argus Backend", version="0.1.0")
app.add_exception_handler(Exception, unhandled_exception_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(create_app_header_router())
app.include_router(create_health_router(settings.news_provider))
app.include_router(create_market_news_router())
app.include_router(create_global_events_router())
app.mount("/api/krx", create_krx_app())
