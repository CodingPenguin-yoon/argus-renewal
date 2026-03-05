from fastapi import APIRouter


def create_health_router(provider: str) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "backend", "provider": provider}

    return router
