from fastapi import FastAPI
from sqlalchemy import text

from app.api.v1 import jobs, runs, searches
from app.artifacts.store import MinioArtifactStore
from app.core.config import get_settings
from app.core.logging import configure_logging, request_id_middleware
from app.core.queue import get_arq_pool
from app.db import session as session_module


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.app_env)

    app = FastAPI(title="Job Scraper API")
    app.middleware("http")(request_id_middleware)

    app.include_router(searches.router, prefix=settings.api_prefix)
    app.include_router(runs.router, prefix=settings.api_prefix)
    app.include_router(jobs.router, prefix=settings.api_prefix)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        async with session_module._session_factory() as session:
            await session.execute(text("SELECT 1"))

        arq_pool = await get_arq_pool()
        await arq_pool.ping()

        store = MinioArtifactStore(settings)
        if not store.check_connectivity():
            return {"status": "degraded", "reason": "artifact store unreachable"}

        return {"status": "ok"}

    return app
