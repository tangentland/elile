"""Integration tests for health check endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    async def test_health_returns_200(self, test_client: AsyncClient):
        """Test basic health check returns 200."""
        response = await test_client.get("/health")

        assert response.status_code == 200

    async def test_health_returns_healthy_status(self, test_client: AsyncClient):
        """Test health check returns healthy status."""
        response = await test_client.get("/health")

        data = response.json()
        assert data["status"] == "healthy"

    async def test_health_returns_version(self, test_client: AsyncClient):
        """Test health check includes version."""
        response = await test_client.get("/health")

        data = response.json()
        assert "version" in data
        assert data["version"] == "0.1.0"

    async def test_health_returns_timestamp(self, test_client: AsyncClient):
        """Test health check includes timestamp."""
        response = await test_client.get("/health")

        data = response.json()
        assert "timestamp" in data

    async def test_health_requires_no_auth(self, test_client: AsyncClient):
        """Test health check does not require authentication."""
        # No Authorization header
        response = await test_client.get("/health")

        assert response.status_code == 200

    async def test_health_requires_no_tenant(self, test_client: AsyncClient):
        """Test health check does not require tenant header."""
        # No X-Tenant-ID header
        response = await test_client.get("/health")

        assert response.status_code == 200


@pytest.mark.asyncio
class TestHealthDbEndpoint:
    """Tests for GET /health/db endpoint."""

    async def test_health_db_returns_200(self, test_client: AsyncClient):
        """Test database health check returns 200."""
        response = await test_client.get("/health/db")

        # May return 200 with healthy or unhealthy status
        assert response.status_code == 200

    async def test_health_db_includes_database_status(self, test_client: AsyncClient):
        """Test database health check includes database component."""
        response = await test_client.get("/health/db")

        data = response.json()
        assert "database" in data
        assert data["database"]["status"] in ["healthy", "unhealthy", "degraded"]

    async def test_health_db_includes_message(self, test_client: AsyncClient):
        """Test database health check includes message."""
        response = await test_client.get("/health/db")

        data = response.json()
        assert "message" in data["database"]

    async def test_health_db_requires_no_auth(self, test_client: AsyncClient):
        """Test database health check does not require authentication."""
        response = await test_client.get("/health/db")

        # Should not return 401
        assert response.status_code != 401


@pytest.mark.asyncio
class TestHealthReadyEndpoint:
    """Tests for GET /health/ready endpoint."""

    async def test_health_ready_returns_200(self, test_client: AsyncClient):
        """Test readiness check returns 200."""
        response = await test_client.get("/health/ready")

        assert response.status_code == 200

    async def test_health_ready_includes_all_components(self, test_client: AsyncClient):
        """Test readiness check includes all components."""
        response = await test_client.get("/health/ready")

        data = response.json()
        assert "database" in data
        assert "redis" in data

    async def test_health_ready_includes_details(self, test_client: AsyncClient):
        """Test readiness check includes details."""
        response = await test_client.get("/health/ready")

        data = response.json()
        assert "details" in data
        if data["details"]:
            assert "checks_performed" in data["details"]

    async def test_health_ready_requires_no_auth(self, test_client: AsyncClient):
        """Test readiness check does not require authentication."""
        response = await test_client.get("/health/ready")

        # Should not return 401
        assert response.status_code != 401


@pytest.mark.asyncio
class TestHealthEndpointHeaders:
    """Tests for health endpoint response headers."""

    async def test_health_returns_request_id(self, test_client: AsyncClient):
        """Test health check returns X-Request-ID header."""
        response = await test_client.get("/health")

        assert "X-Request-ID" in response.headers
        # Should be a valid UUID format
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) == 36  # UUID format with dashes

    async def test_multiple_requests_get_unique_ids(self, test_client: AsyncClient):
        """Test each request gets a unique request ID."""
        response1 = await test_client.get("/health")
        response2 = await test_client.get("/health")

        id1 = response1.headers["X-Request-ID"]
        id2 = response2.headers["X-Request-ID"]

        assert id1 != id2
