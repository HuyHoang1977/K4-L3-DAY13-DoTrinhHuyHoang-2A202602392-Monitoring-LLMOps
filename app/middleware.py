from __future__ import annotations

import re
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

REQUEST_ID_HEADER = "x-request-id"
RESPONSE_TIME_HEADER = "x-response-time-ms"

# Inbound ids are attacker-controlled, so only allow a short, header-safe charset.
# Anything else (spaces, CR/LF, control chars) is replaced by a freshly generated id.
_INBOUND_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def new_request_id() -> str:
    """Generate a correlation id in the canonical ``req-<8-char-hex>`` format."""
    return f"req-{uuid.uuid4().hex[:8]}"


def resolve_request_id(raw: str | None) -> str:
    """Reuse a well-formed inbound ``x-request-id``, otherwise mint a new one."""
    if raw and _INBOUND_ID_RE.match(raw):
        return raw
    return new_request_id()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Clear contextvars first so nothing leaks in from a previous request
        # (or from the thread pool that served it).
        clear_contextvars()

        correlation_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))

        # Bind the correlation_id to structlog contextvars
        bind_contextvars(correlation_id=correlation_id)

        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            clear_contextvars()

        # Add the correlation_id and processing time to response headers
        response.headers[REQUEST_ID_HEADER] = correlation_id
        response_time_ms = (time.perf_counter() - start) * 1000
        response.headers[RESPONSE_TIME_HEADER] = str(int(response_time_ms))

        return response
