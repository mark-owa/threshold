from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.approvals import router as approvals_router
from app.api.auth import router as auth_router
from app.api.demo import router as demo_router
from app.api.ops import router as ops_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.db.session import engine

settings = get_settings()
settings.validate_runtime_secrets()
configure_logging()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="AI Operations Automation Platform for SMBs.",
    )

    app.add_middleware(RequestContextMiddleware)
    app.include_router(auth_router)
    app.include_router(ops_router)
    app.include_router(approvals_router)
    app.include_router(demo_router)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["system"])
    def health() -> dict:
        """Liveness probe: is the process up. Does not touch the DB."""
        return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}

    @app.get("/ready", tags=["system"])
    def ready() -> JSONResponse:
        """Readiness probe: can we actually serve traffic (DB reachable)."""
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return JSONResponse(status_code=200, content={"status": "ready"})
        except Exception:  # noqa: BLE001 - readiness probes must not raise
            return JSONResponse(status_code=503, content={"status": "not_ready"})

    return app


app = create_app()
