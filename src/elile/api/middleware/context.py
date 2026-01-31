"""Request context middleware for propagating context through the request lifecycle."""

from typing import Callable
from uuid import UUID, uuid7

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from elile.core.context import (
    ActorType,
    CacheScope,
    create_context,
    request_context,
)


# Paths that don't require request context
SKIP_CONTEXT_PATHS = {
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware that sets up RequestContext for each request.

    Uses the ContextVar-based context management to propagate request
    context through async call chains.

    Requires:
        request.state.tenant_id: Set by TenantValidationMiddleware
        request.state.actor_id: Set by AuthenticationMiddleware
        request.state.actor_type: Set by AuthenticationMiddleware

    Sets:
        request.state.request_id: The generated request ID (UUIDv7)
        X-Request-ID response header: For client correlation
    """

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Process request within a RequestContext."""
        # Generate request ID
        request_id = uuid7()
        request.state.request_id = request_id

        # Skip context setup for paths that don't need it
        if self._should_skip_context(request.url.path):
            response = await call_next(request)
            response.headers["X-Request-ID"] = str(request_id)
            return response

        # Get tenant and actor from request state (set by upstream middleware)
        tenant_id = self._get_tenant_id(request)
        actor_id = self._get_actor_id(request)
        actor_type = self._get_actor_type(request)

        # Extract additional context from headers
        locale = request.headers.get("X-Locale", "US")
        cache_scope = self._parse_cache_scope(
            request.headers.get("X-Cache-Scope", "tenant_isolated")
        )

        # Create the request context
        ctx = create_context(
            tenant_id=tenant_id,
            actor_id=actor_id,
            actor_type=actor_type,
            locale=locale,
            cache_scope=cache_scope,
        )

        # Override request_id with our generated one
        # (create_context generates its own, but we want consistency)
        ctx = ctx.model_copy(update={"request_id": request_id})

        # Execute request within context
        with request_context(ctx):
            response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = str(request_id)
        response.headers["X-Correlation-ID"] = str(ctx.correlation_id)

        return response

    def _should_skip_context(self, path: str) -> bool:
        """Check if path should skip context setup."""
        return path in SKIP_CONTEXT_PATHS or path.startswith(("/docs", "/redoc"))

    def _get_tenant_id(self, request: Request) -> UUID:
        """Extract tenant ID from request state."""
        if hasattr(request.state, "tenant_id"):
            return request.state.tenant_id

        # Fallback to default tenant for paths that bypassed validation
        from elile.config.settings import get_settings
        return UUID(get_settings().DEFAULT_TENANT_ID)

    def _get_actor_id(self, request: Request) -> UUID:
        """Extract actor ID from request state."""
        if hasattr(request.state, "actor_id"):
            return request.state.actor_id
        return uuid7()  # Generate anonymous actor ID

    def _get_actor_type(self, request: Request) -> ActorType:
        """Extract actor type from request state."""
        if hasattr(request.state, "actor_type"):
            return request.state.actor_type
        return ActorType.SYSTEM

    def _parse_cache_scope(self, value: str) -> CacheScope:
        """Parse cache scope from header value."""
        value = value.lower().strip()
        if value == "shared":
            return CacheScope.SHARED
        return CacheScope.TENANT_ISOLATED
