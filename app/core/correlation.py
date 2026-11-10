"""Correlation ID tracking across request-response cycles."""

import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.access")

CORRELATION_ID_HEADER = "X-Correlation-ID"

_correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    """Get the current request correlation ID from context."""
    return _correlation_id_ctx.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set the current request correlation ID in context."""
    _correlation_id_ctx.set(correlation_id)


def generate_correlation_id() -> str:
    """Generate a unique correlation ID."""
    return uuid.uuid4().hex


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware ensuring each request has a correlation ID for observability."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        header_correlation_id = request.headers.get(CORRELATION_ID_HEADER)
        correlation_id = header_correlation_id or generate_correlation_id()

        set_correlation_id(correlation_id)

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "Request completed: %s %s -> %d in %.2fms",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            response.headers[CORRELATION_ID_HEADER] = correlation_id
            return response
        except Exception:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "Request failed: %s %s in %.2fms",
                request.method,
                request.url.path,
                duration_ms,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            raise
