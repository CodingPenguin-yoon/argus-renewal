from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config.env import get_settings
from .domains.health.router import create_health_router
from .domains.news.factory import create_news_provider
from .domains.news.router import create_news_router
from .domains.news.service import NewsService
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

news_provider = create_news_provider(settings.news_provider)
news_service = NewsService(news_provider)

app.include_router(create_health_router(settings.news_provider))
app.include_router(create_news_router(news_service))
