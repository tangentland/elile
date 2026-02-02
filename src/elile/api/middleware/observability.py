"""Observability middleware for metrics and tracing."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from elile.observability.metrics import record_http_request
from elile.observability.tracing import (
    SpanKindType,
    add_span_attributes,
    add_span_event,
    create_span,
    record_exception,
)

if TYPE_CHECKING:
    pass


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware that collects metrics and traces for HTTP requests.

    This middleware:
    - Records Prometheus metrics for request duration, count, and sizes
    - Creates OpenTelemetry spans for request tracing
    - Adds request attributes to spans for debugging
    - Excludes health and metrics endpoints to avoid noise
    """

    # Paths to exclude from metrics/tracing
    EXCLUDED_PATHS = {"/health", "/health/db", "/health/ready", "/metrics"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with observability instrumentation."""
        # Skip excluded paths
        path = request.url.path
        if path in self.EXCLUDED_PATHS:
            return await call_next(request)

        # Normalize path for metrics (replace IDs with placeholders)
        normalized_path = self._normalize_path(path)
        method = request.method

        start_time = time.perf_counter()
        request_size = self._get_content_length(request)

        # Create span for the request
        span_name = f"HTTP {method} {normalized_path}"

        with create_span(span_name, kind=SpanKindType.SERVER):
            # Add request attributes
            add_span_attributes(
                http_method=method,
                http_url=str(request.url),
                http_target=path,
                http_route=normalized_path,
                http_scheme=request.url.scheme,
                http_host=request.url.hostname,
                http_user_agent=request.headers.get("User-Agent"),
                http_client_ip=self._get_client_ip(request),
            )

            # Add tenant and request IDs if available
            if hasattr(request.state, "tenant_id"):
                add_span_attributes(tenant_id=str(request.state.tenant_id))
            if hasattr(request.state, "request_id"):
                add_span_attributes(request_id=str(request.state.request_id))

            try:
                # Process request
                response = await call_next(request)

                # Record success metrics
                duration = time.perf_counter() - start_time
                response_size = self._get_response_size(response)

                add_span_attributes(http_status_code=response.status_code)
                add_span_event(
                    "request_completed",
                    {"duration_ms": round(duration * 1000, 2)},
                )

                record_http_request(
                    method=method,
                    endpoint=normalized_path,
                    status_code=response.status_code,
                    duration_seconds=duration,
                    request_size=request_size,
                    response_size=response_size,
                )

                return response

            except Exception as e:
                # Record error metrics
                duration = time.perf_counter() - start_time
                record_exception(e)
                add_span_attributes(http_status_code=500)

                record_http_request(
                    method=method,
                    endpoint=normalized_path,
                    status_code=500,
                    duration_seconds=duration,
                    request_size=request_size,
                )
                raise

    def _normalize_path(self, path: str) -> str:
        """Normalize path by replacing UUIDs and IDs with placeholders.

        This prevents high-cardinality metrics from unique IDs.

        Args:
            path: Original request path.

        Returns:
            Normalized path with placeholders.
        """
        import re

        # Replace UUIDs
        path = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "{id}",
            path,
            flags=re.IGNORECASE,
        )

        # Replace numeric IDs in path segments
        path = re.sub(r"/\d+(?=/|$)", "/{id}", path)

        return path

    def _get_client_ip(self, request: Request) -> str | None:
        """Extract client IP from request."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        if request.client:
            return request.client.host

        return None

    def _get_content_length(self, request: Request) -> int | None:
        """Get request content length."""
        content_length = request.headers.get("Content-Length")
        if content_length:
            try:
                return int(content_length)
            except ValueError:
                pass
        return None

    def _get_response_size(self, response: Response) -> int | None:
        """Get response content length."""
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                return int(content_length)
            except ValueError:
                pass
        return None
