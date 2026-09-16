"""Request-context middleware.

Binds a request_id (from an inbound X-Request-ID header, or freshly
generated) to structlog's contextvars for the lifetime of the request, so
every log line emitted while handling it -- across however many layers --
carries the same request_id. Also logs one line per completed request
with method/path/status/duration, which is enough to reconstruct request
volume and latency without a separate APM tool.
"""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = structlog.get_logger("threshold.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        request_id = request_id[:100]
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        response = await call_next(request)
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
