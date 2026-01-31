"""Unit tests for API middleware components."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid7

import pytest
from fastapi import Request, Response

from elile.api.middleware.auth import AuthenticationMiddleware, SKIP_AUTH_PATHS
from elile.api.middleware.context import RequestContextMiddleware, SKIP_CONTEXT_PATHS
from elile.api.middleware.errors import ErrorHandlingMiddleware, EXCEPTION_MAP
from elile.api.middleware.tenant import TenantValidationMiddleware, SKIP_TENANT_PATHS
from elile.core.context import ActorType
from elile.core.exceptions import (
    AuthenticationError,
    BudgetExceededError,
    ComplianceError,
    ConsentExpiredError,
    ConsentScopeError,
    ContextNotSetError,
    TenantInactiveError,
    TenantNotFoundError,
)


class TestAuthenticationMiddleware:
    """Tests for AuthenticationMiddleware."""

    def test_skip_auth_paths_defined(self):
        """Verify health endpoints skip authentication."""
        expected_paths = {"/health", "/health/db", "/health/ready"}
        assert expected_paths.issubset(SKIP_AUTH_PATHS)

    def test_docs_paths_skipped(self):
        """Verify OpenAPI docs paths skip authentication."""
        assert "/docs" in SKIP_AUTH_PATHS
        assert "/redoc" in SKIP_AUTH_PATHS
        assert "/openapi.json" in SKIP_AUTH_PATHS

    @pytest.mark.asyncio
    async def test_missing_auth_header_returns_401(self):
        """Test that missing Authorization header returns 401."""
        middleware = AuthenticationMiddleware(app=MagicMock())

        # Create mock request without auth header
        request = MagicMock(spec=Request)
        request.url.path = "/v1/test"
        request.headers = {}
        request.state = MagicMock()

        # Call next should not be called
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 401
        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_auth_format_returns_401(self):
        """Test that invalid Authorization format returns 401."""
        middleware = AuthenticationMiddleware(app=MagicMock())

        request = MagicMock(spec=Request)
        request.url.path = "/v1/test"
        request.headers = {"Authorization": "InvalidFormat token123"}
        request.state = MagicMock()

        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 401
        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_skipped_path_sets_system_actor(self):
        """Test that skipped paths set SYSTEM actor type."""
        middleware = AuthenticationMiddleware(app=MagicMock())

        request = MagicMock(spec=Request)
        request.url.path = "/health"
        request.state = MagicMock()

        expected_response = Response(status_code=200)
        call_next = AsyncMock(return_value=expected_response)

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200
        assert request.state.actor_type == ActorType.SYSTEM
        call_next.assert_called_once()


class TestTenantValidationMiddleware:
    """Tests for TenantValidationMiddleware."""

    def test_skip_tenant_paths_defined(self):
        """Verify health endpoints skip tenant validation."""
        expected_paths = {"/health", "/health/db", "/health/ready"}
        assert expected_paths.issubset(SKIP_TENANT_PATHS)

    @pytest.mark.asyncio
    async def test_missing_tenant_header_returns_400(self):
        """Test that missing X-Tenant-ID header returns 400."""
        middleware = TenantValidationMiddleware(app=MagicMock())

        request = MagicMock(spec=Request)
        request.url.path = "/v1/test"
        request.headers = {}

        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 400
        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_tenant_uuid_returns_400(self):
        """Test that invalid tenant UUID returns 400."""
        middleware = TenantValidationMiddleware(app=MagicMock())

        request = MagicMock(spec=Request)
        request.url.path = "/v1/test"
        request.headers = {"X-Tenant-ID": "not-a-valid-uuid"}

        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 400
        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_skipped_path_bypasses_validation(self):
        """Test that skipped paths bypass tenant validation."""
        middleware = TenantValidationMiddleware(app=MagicMock())

        request = MagicMock(spec=Request)
        request.url.path = "/health"

        expected_response = Response(status_code=200)
        call_next = AsyncMock(return_value=expected_response)

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200
        call_next.assert_called_once()


class TestErrorHandlingMiddleware:
    """Tests for ErrorHandlingMiddleware."""

    def test_exception_map_contains_all_exceptions(self):
        """Verify all domain exceptions are mapped."""
        expected_exceptions = [
            AuthenticationError,
            TenantNotFoundError,
            TenantInactiveError,
            ComplianceError,
            BudgetExceededError,
            ConsentExpiredError,
            ConsentScopeError,
            ContextNotSetError,
        ]
        for exc_type in expected_exceptions:
            assert exc_type in EXCEPTION_MAP, f"Missing mapping for {exc_type.__name__}"

    def test_exception_map_status_codes(self):
        """Verify correct HTTP status codes for exceptions."""
        assert EXCEPTION_MAP[AuthenticationError][0] == 401
        assert EXCEPTION_MAP[TenantNotFoundError][0] == 404
        assert EXCEPTION_MAP[TenantInactiveError][0] == 403
        assert EXCEPTION_MAP[ComplianceError][0] == 403
        assert EXCEPTION_MAP[BudgetExceededError][0] == 402
        assert EXCEPTION_MAP[ConsentExpiredError][0] == 403
        assert EXCEPTION_MAP[ConsentScopeError][0] == 403
        assert EXCEPTION_MAP[ContextNotSetError][0] == 500

    @pytest.mark.asyncio
    async def test_unhandled_exception_returns_500(self):
        """Test that unhandled exceptions return 500."""
        middleware = ErrorHandlingMiddleware(app=MagicMock())

        request = MagicMock(spec=Request)
        request.url.path = "/v1/test"
        request.state = MagicMock()
        request.state.request_id = uuid7()

        call_next = AsyncMock(side_effect=RuntimeError("Unexpected error"))

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_success_response_passes_through(self):
        """Test that successful responses pass through unchanged."""
        middleware = ErrorHandlingMiddleware(app=MagicMock())

        request = MagicMock(spec=Request)
        request.url.path = "/v1/test"
        request.state = MagicMock()

        expected_response = Response(status_code=200, content=b"OK")
        call_next = AsyncMock(return_value=expected_response)

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200
        call_next.assert_called_once()


class TestRequestContextMiddleware:
    """Tests for RequestContextMiddleware."""

    def test_skip_context_paths_defined(self):
        """Verify context skip paths are defined."""
        assert "/health" in SKIP_CONTEXT_PATHS
        assert "/docs" in SKIP_CONTEXT_PATHS

    @pytest.mark.asyncio
    async def test_request_id_generated(self):
        """Test that request ID is generated."""
        middleware = RequestContextMiddleware(app=MagicMock())

        request = MagicMock(spec=Request)
        request.url.path = "/health"
        request.state = MagicMock()
        request.headers = {}

        expected_response = MagicMock(spec=Response)
        expected_response.headers = {}
        call_next = AsyncMock(return_value=expected_response)

        await middleware.dispatch(request, call_next)

        # Verify request ID was set on state
        assert hasattr(request.state, "request_id")

    @pytest.mark.asyncio
    async def test_request_id_in_response_header(self):
        """Test that X-Request-ID is added to response."""
        middleware = RequestContextMiddleware(app=MagicMock())

        request = MagicMock(spec=Request)
        request.url.path = "/health"
        request.state = MagicMock()
        request.headers = {}

        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        response = await middleware.dispatch(request, call_next)

        assert "X-Request-ID" in response.headers

    @pytest.mark.asyncio
    async def test_skipped_path_still_gets_request_id(self):
        """Test that even skipped paths get a request ID."""
        middleware = RequestContextMiddleware(app=MagicMock())

        request = MagicMock(spec=Request)
        request.url.path = "/health"
        request.state = MagicMock()
        request.headers = {}

        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        await middleware.dispatch(request, call_next)

        # Request ID should be set even for skipped paths
        assert request.state.request_id is not None
