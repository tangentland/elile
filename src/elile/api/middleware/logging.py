"""Request logging middleware for audit trail."""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs all HTTP requests to the audit trail.

    Captures request metadata at the start and response metadata at the end,
    logging both for compliance and debugging purposes.

    Note: This middleware uses Python logging rather than AuditLogger to avoid
    database operations in the middleware layer. For compliance audit events,
    use the AuditLogger directly in route handlers.
    """

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Process request and log request/response."""
        start_time = time.perf_counter()

        # Capture request metadata
        request_meta = self._capture_request_metadata(request)

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log request completion
        self._log_request(request, response, request_meta, duration_ms)

        return response

    def _capture_request_metadata(self, request: Request) -> dict:
        """Capture metadata from the incoming request."""
        return {
            "method": request.method,
            "path": request.url.path,
            "query": str(request.url.query) if request.url.query else None,
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("User-Agent"),
            "content_length": request.headers.get("Content-Length"),
        }

    def _get_client_ip(self, request: Request) -> str | None:
        """Extract client IP from request, considering proxy headers."""
        # Check X-Forwarded-For first (for reverse proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take first IP in the chain (original client)
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP (common alternative)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client
        if request.client:
            return request.client.host

        return None

    def _log_request(
        self,
        request: Request,
        response: Response,
        request_meta: dict,
        duration_ms: float,
    ) -> None:
        """Log the completed request."""
        import logging

        logger = logging.getLogger("elile.api.requests")

        # Get request ID if available
        request_id = "unknown"
        if hasattr(request.state, "request_id"):
            request_id = str(request.state.request_id)

        # Get tenant ID if available
        tenant_id = None
        if hasattr(request.state, "tenant_id"):
            tenant_id = str(request.state.tenant_id)

        # Determine log level based on status code
        status_code = response.status_code
        if status_code >= 500:
            log_level = logging.ERROR
        elif status_code >= 400:
            log_level = logging.WARNING
        else:
            log_level = logging.INFO

        # Format log message
        log_data = {
            "request_id": request_id,
            "tenant_id": tenant_id,
            "method": request_meta["method"],
            "path": request_meta["path"],
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "client_ip": request_meta["client_ip"],
            "user_agent": request_meta["user_agent"],
        }

        logger.log(
            log_level,
            f"{request_meta['method']} {request_meta['path']} "
            f"-> {status_code} ({duration_ms:.2f}ms)",
            extra=log_data,
        )
