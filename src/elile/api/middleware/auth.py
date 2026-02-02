"""Authentication middleware for API key validation."""

import re
from typing import Callable
from uuid import uuid7

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from elile.core.context import ActorType


# Paths that don't require authentication
SKIP_AUTH_PATHS = {
    "/health",
    "/health/db",
    "/health/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
}

# Paths that start with these prefixes don't require auth
SKIP_AUTH_PREFIXES = (
    "/docs",
    "/redoc",
    "/v1/hris/webhooks",  # HRIS webhooks use signature validation, not API auth
)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware that validates Bearer token authentication.

    Extracts and validates the Authorization header, setting actor information
    on the request state for downstream middleware.

    Sets:
        request.state.actor_id: UUID of the authenticated actor
        request.state.actor_type: Type of actor (HUMAN, SERVICE, SYSTEM)
    """

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Process request and validate authentication."""
        # Skip auth for allowed paths
        if self._should_skip_auth(request.url.path):
            # Set system actor for unauthenticated requests
            request.state.actor_id = uuid7()
            request.state.actor_type = ActorType.SYSTEM
            return await call_next(request)

        # Extract and validate auth header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return self._unauthorized_response("Missing Authorization header")

        # Validate Bearer token format
        match = re.match(r"^Bearer\s+(.+)$", auth_header, re.IGNORECASE)
        if not match:
            return self._unauthorized_response("Invalid Authorization header format")

        token = match.group(1)

        # Validate token against configured API key
        if not self._validate_token(token, request):
            return self._unauthorized_response("Invalid API key")

        # Set actor information on request state
        # In production, token would be looked up to get actual actor ID
        request.state.actor_id = self._get_actor_id_from_token(token)
        request.state.actor_type = ActorType.SERVICE

        return await call_next(request)

    def _should_skip_auth(self, path: str) -> bool:
        """Check if path should skip authentication."""
        if path in SKIP_AUTH_PATHS:
            return True
        if path.startswith(SKIP_AUTH_PREFIXES):
            return True
        return False

    def _validate_token(self, token: str, request: Request) -> bool:
        """Validate API token against configured secret.

        Args:
            token: The Bearer token value
            request: The FastAPI request (for accessing app settings)

        Returns:
            True if token is valid, False otherwise
        """
        try:
            # Get settings from app state if available, otherwise fall back to global
            if hasattr(request.app.state, "settings"):
                settings = request.app.state.settings
            else:
                from elile.config.settings import get_settings
                settings = get_settings()

            # Check if API_SECRET_KEY is configured
            if settings.API_SECRET_KEY is None:
                # In development without key configured, accept any non-empty token
                return bool(token) and settings.DEBUG

            # Compare with configured secret
            return token == settings.API_SECRET_KEY.get_secret_value()
        except Exception:
            return False

    def _get_actor_id_from_token(self, token: str) -> "UUID":
        """Derive actor ID from token.

        In production, this would look up the API key to find the associated
        service account or user. For now, generate a deterministic UUID
        based on the token.

        Args:
            token: The validated API token

        Returns:
            UUID for the actor
        """
        # For now, use a consistent UUID for the same token
        # In production, this would be a database lookup
        import hashlib
        from uuid import UUID

        # Create a deterministic UUID from the token
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        # Use first 32 chars as UUID (format as proper UUID)
        uuid_str = f"{token_hash[:8]}-{token_hash[8:12]}-{token_hash[12:16]}-{token_hash[16:20]}-{token_hash[20:32]}"
        return UUID(uuid_str)

    def _unauthorized_response(self, message: str) -> JSONResponse:
        """Create a 401 unauthorized response."""
        from datetime import UTC, datetime
        from elile.api.schemas.errors import APIError, ErrorCode

        error = APIError(
            error_code=ErrorCode.UNAUTHORIZED.value,
            message=message,
            details=None,
            request_id="unknown",  # Request ID not yet assigned
            timestamp=datetime.now(UTC),
        )

        return JSONResponse(
            status_code=401,
            content=error.model_dump(mode="json"),
            headers={"WWW-Authenticate": "Bearer"},
        )


# Type hint import
from uuid import UUID
