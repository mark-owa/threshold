from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text

from app.api.approvals import router as approvals_router
from app.api.auth import router as auth_router
from app.api.commercial import router as commercial_router
from app.api.demo import router as demo_router
from app.api.ops import router as ops_router
from app.api.organizations import router as organizations_router
from app.api.workspace import router as workspace_router
from app.api.webhooks import router as webhooks_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import (
    RateLimitMiddleware,
    RequestContextMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.db.session import SessionLocal, engine
from app.models import OutboxMessage
from app.models.enums import OutboxStatus

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
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.include_router(auth_router)
    app.include_router(commercial_router)
    app.include_router(ops_router)
    app.include_router(organizations_router)
    app.include_router(workspace_router)
    app.include_router(webhooks_router)
    app.include_router(approvals_router)
    app.include_router(demo_router)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _live_payload() -> dict:
        return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}

    @app.get("/health", tags=["system"])
    @app.get("/health/live", tags=["system"])
    def health() -> dict:
        """Liveness probe: is the API process up."""
        return _live_payload()

    def _readiness_payload() -> tuple[int, dict]:
        components = {"database": "unknown", "redis": "unknown"}
        backlog = None
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            components["database"] = "ok"
            db = SessionLocal()
            try:
                backlog = db.scalar(
                    select(func.count())
                    .select_from(OutboxMessage)
                    .where(OutboxMessage.status.in_([OutboxStatus.PENDING, OutboxStatus.FAILED]))
                ) or 0
            finally:
                db.close()
        except Exception:
            components["database"] = "unavailable"

        try:
            import redis
            client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
            client.ping()
            components["redis"] = "ok"
        except Exception:
            components["redis"] = "unavailable"

        ready = all(value == "ok" for value in components.values())
        return (
            200 if ready else 503,
            {
                "status": "ready" if ready else "not_ready",
                "components": components,
                "outbox_pending": backlog,
            },
        )

    @app.get("/ready", tags=["system"])
    @app.get("/health/ready", tags=["system"])
    def ready() -> JSONResponse:
        status_code, payload = _readiness_payload()
        return JSONResponse(status_code=status_code, content=payload)

    return app


app = create_app()
