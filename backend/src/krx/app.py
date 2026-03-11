from fastapi import FastAPI

from .router import create_krx_router
from ..shared.errors import unhandled_exception_handler


def create_krx_app() -> FastAPI:
    app = FastAPI(title="Argus Backend KRX", version="0.1.0")
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(create_krx_router())
    return app
