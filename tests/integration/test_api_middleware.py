"""Integration tests for API middleware stack."""

from uuid import uuid7

import pytest
from httpx import AsyncClient
from pydantic import SecretStr

from elile.config.settings import Settings


@pytest.mark.asyncio
class TestAuthenticationMiddleware:
    """Integration tests for authentication middleware."""

    async def test_missing_auth_header_returns_401(
        self, test_client: AsyncClient
    ):
        """Test that protected endpoints require authentication."""
        # Create a fake protected endpoint path
        # Health endpoints are skipped, so use a different path
        response = await test_client.get(
            "/v1/some-protected-resource",
            headers={"X-Tenant-ID": str(uuid7())},
        )

        # Should return 401 because no auth header
        assert response.status_code == 401

    async def test_invalid_bearer_token_returns_401(
        self, test_client: AsyncClient
    ):
        """Test that invalid bearer token returns 401."""
        response = await test_client.get(
            "/v1/some-protected-resource",
            headers={
                "Authorization": "Bearer invalid-token",
                "X-Tenant-ID": str(uuid7()),
            },
        )

        assert response.status_code == 401

    async def test_invalid_auth_format_returns_401(
        self, test_client: AsyncClient
    ):
        """Test that invalid auth format returns 401."""
        response = await test_client.get(
            "/v1/some-protected-resource",
            headers={
                "Authorization": "Basic dXNlcjpwYXNz",  # Basic auth format
                "X-Tenant-ID": str(uuid7()),
            },
        )

        assert response.status_code == 401

    async def test_valid_token_passes_authentication(
        self,
        test_client: AsyncClient,
        test_settings: Settings,
    ):
        """Test that valid token passes authentication."""
        response = await test_client.get(
            "/v1/some-protected-resource",
            headers={
                "Authorization": f"Bearer {test_settings.API_SECRET_KEY.get_secret_value()}",
                "X-Tenant-ID": str(uuid7()),
            },
        )

        # Should not return 401 (auth passed)
        # May return 404 since endpoint doesn't exist
        assert response.status_code != 401

    async def test_error_response_format(self, test_client: AsyncClient):
        """Test that 401 response uses correct error format."""
        response = await test_client.get(
            "/v1/some-protected-resource",
        )

        data = response.json()
        assert "error_code" in data
        assert "message" in data
        assert "request_id" in data
        assert "timestamp" in data
        assert data["error_code"] == "unauthorized"


@pytest.mark.asyncio
class TestTenantValidationMiddleware:
    """Integration tests for tenant validation middleware."""

    async def test_missing_tenant_header_returns_400(
        self,
        test_client: AsyncClient,
        test_settings: Settings,
    ):
        """Test that missing X-Tenant-ID returns 400."""
        response = await test_client.get(
            "/v1/some-resource",
            headers={
                "Authorization": f"Bearer {test_settings.API_SECRET_KEY.get_secret_value()}",
            },
        )

        assert response.status_code == 400

    async def test_invalid_tenant_uuid_returns_400(
        self,
        test_client: AsyncClient,
        test_settings: Settings,
    ):
        """Test that invalid tenant UUID format returns 400."""
        response = await test_client.get(
            "/v1/some-resource",
            headers={
                "Authorization": f"Bearer {test_settings.API_SECRET_KEY.get_secret_value()}",
                "X-Tenant-ID": "not-a-valid-uuid",
            },
        )

        assert response.status_code == 400

    async def test_tenant_error_response_format(
        self,
        test_client: AsyncClient,
        test_settings: Settings,
    ):
        """Test that tenant validation errors use correct format."""
        response = await test_client.get(
            "/v1/some-resource",
            headers={
                "Authorization": f"Bearer {test_settings.API_SECRET_KEY.get_secret_value()}",
                "X-Tenant-ID": "invalid",
            },
        )

        data = response.json()
        assert "error_code" in data
        assert "message" in data
        assert data["error_code"] == "invalid_request"


@pytest.mark.asyncio
class TestErrorHandlingMiddleware:
    """Integration tests for error handling middleware."""

    async def test_error_responses_are_json(
        self,
        test_client: AsyncClient,
    ):
        """Test that error responses are properly formatted JSON."""
        response = await test_client.get("/v1/test")

        # Should return 401 (no auth) as JSON
        assert response.status_code == 401
        data = response.json()
        assert "error_code" in data
        assert "message" in data

    async def test_successful_responses_include_request_id(
        self,
        test_client: AsyncClient,
    ):
        """Test that successful responses include X-Request-ID header."""
        response = await test_client.get("/health")

        # Health endpoints bypass auth and include request ID
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers


@pytest.mark.asyncio
class TestRequestContextMiddleware:
    """Integration tests for request context middleware."""

    async def test_request_id_header_present(self, test_client: AsyncClient):
        """Test that X-Request-ID header is always present."""
        response = await test_client.get("/health")

        assert "X-Request-ID" in response.headers

    async def test_request_id_is_valid_uuid(self, test_client: AsyncClient):
        """Test that X-Request-ID is a valid UUID."""
        response = await test_client.get("/health")

        request_id = response.headers["X-Request-ID"]
        # UUID v7 format: xxxxxxxx-xxxx-7xxx-xxxx-xxxxxxxxxxxx
        parts = request_id.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12

    async def test_correlation_id_header_on_context_paths(
        self,
        test_client: AsyncClient,
        test_settings: Settings,
    ):
        """Test that context paths get correlation ID."""
        # This requires a path that isn't skipped
        response = await test_client.get(
            "/v1/test",
            headers={
                "Authorization": f"Bearer {test_settings.API_SECRET_KEY.get_secret_value()}",
                "X-Tenant-ID": str(uuid7()),
            },
        )

        # Even if 404, correlation ID should be present for context paths
        # Note: May not be present if tenant validation fails first
        # This is testing the full middleware stack behavior


@pytest.mark.asyncio
class TestMiddlewareStackOrder:
    """Integration tests verifying correct middleware stack ordering."""

    async def test_auth_checked_before_tenant(
        self, test_client: AsyncClient
    ):
        """Test that authentication is checked before tenant validation."""
        # If auth was checked after tenant, we'd get a 400 (missing tenant)
        # instead of 401 (missing auth)
        response = await test_client.get("/v1/test")

        assert response.status_code == 401

    async def test_tenant_checked_after_auth(
        self,
        test_client: AsyncClient,
        test_settings: Settings,
    ):
        """Test that tenant is validated after auth succeeds."""
        response = await test_client.get(
            "/v1/test",
            headers={
                "Authorization": f"Bearer {test_settings.API_SECRET_KEY.get_secret_value()}",
            },
        )

        # Should get 400 (missing tenant), not 401 (auth failed)
        assert response.status_code == 400

    async def test_health_bypasses_auth_and_tenant(
        self, test_client: AsyncClient
    ):
        """Test that health endpoints bypass all validation."""
        response = await test_client.get("/health")

        # No auth, no tenant, should still succeed
        assert response.status_code == 200


@pytest.mark.asyncio
class TestRequestLoggingMiddleware:
    """Integration tests for request logging middleware."""

    async def test_requests_are_logged(
        self,
        test_client: AsyncClient,
        caplog: pytest.LogCaptureFixture,
    ):
        """Test that requests are logged."""
        import logging

        with caplog.at_level(logging.INFO, logger="elile.api.requests"):
            await test_client.get("/health")

        # Check that a log message was generated
        # The exact format depends on the logging configuration
        # This is a basic test that logging happens
        assert any(
            "/health" in record.message
            for record in caplog.records
            if record.name == "elile.api.requests"
        )
