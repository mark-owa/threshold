"""HTTP request hardening and request-context middleware."""

from __future__ import annotations

import ipaddress
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import get_settings

logger = structlog.get_logger("threshold.request")
settings = get_settings()


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))[:100]
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.exception(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                error_type=type(exc).__name__,
            )
            raise
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds browser-facing defense-in-depth headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        if settings.APP_ENV in {"staging", "production"}:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.url.path.startswith(f"{settings.API_V1_PREFIX}/auth"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejects oversized HTTP request bodies before endpoint parsing."""

    async def dispatch(self, request: Request, call_next):
        raw_length = request.headers.get("content-length")
        if raw_length:
            try:
                if int(raw_length) > settings.MAX_REQUEST_BODY_BYTES:
                    return JSONResponse(status_code=413, content={"detail": "Request body too large"})
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length"})
        return await call_next(request)


def _client_key(request: Request) -> str:
    # Do not trust X-Forwarded-For here unless a trusted reverse proxy is configured
    # to rewrite the socket peer. request.client is the safest default.
    host = request.client.host if request.client else "unknown"
    if settings.TRUST_PROXY_HEADERS:
        # Safe only when the API is reachable exclusively through a trusted
        # reverse proxy that overwrites X-Real-IP (the supplied prod Compose does).
        forwarded = request.headers.get("x-real-ip", "").strip()
        if forwarded:
            host = forwarded
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        return host[:128]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed fixed-window limiter for public/authentication endpoints.

    It intentionally fails open if Redis is unavailable so a cache outage does not
    become a total API outage. Authentication still performs credential checks.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        limit = settings.RATE_LIMIT_PER_MINUTE
        if path.endswith("/auth/login") or path.endswith("/auth/register") or path.endswith("/auth/join"):
            limit = settings.AUTH_RATE_LIMIT_PER_MINUTE
        elif "/webhook" in path or path.endswith("/webhooks/shopify"):
            limit = settings.WEBHOOK_RATE_LIMIT_PER_MINUTE
        elif not path.startswith(settings.API_V1_PREFIX):
            return await call_next(request)

        try:
            import redis

            bucket = int(time.time() // 60)
            key = f"threshold:ratelimit:{_client_key(request)}:{path}:{bucket}"
            client = redis.Redis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=0.25,
                socket_timeout=0.25,
                decode_responses=True,
            )
            count = client.incr(key)
            if count == 1:
                client.expire(key, 70)
            if count > limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests"},
                    headers={"Retry-After": "60"},
                )
        except Exception as exc:  # pragma: no cover - availability fallback
            logger.warning("rate_limit_unavailable", error=type(exc).__name__)

        return await call_next(request)
