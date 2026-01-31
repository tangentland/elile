"""Unit tests for API schemas."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from elile.api.schemas.errors import APIError, ErrorCode
from elile.api.schemas.health import (
    ComponentHealth,
    HealthDetailResponse,
    HealthResponse,
    HealthStatus,
)


class TestErrorCode:
    """Tests for ErrorCode enum."""

    def test_error_codes_exist(self):
        """Verify all expected error codes are defined."""
        expected = [
            "unauthorized",
            "forbidden",
            "not_found",
            "invalid_request",
            "internal_error",
            "tenant_not_found",
            "tenant_inactive",
            "compliance_blocked",
            "budget_exceeded",
            "consent_expired",
            "consent_scope_error",
        ]
        actual = [e.value for e in ErrorCode]
        for code in expected:
            assert code in actual, f"Missing error code: {code}"


class TestAPIError:
    """Tests for APIError schema."""

    def test_api_error_creation(self):
        """Test creating a valid APIError."""
        error = APIError(
            error_code="unauthorized",
            message="Missing authentication",
            details=None,
            request_id="01234567-89ab-cdef-0123-456789abcdef",
            timestamp=datetime.now(UTC),
        )
        assert error.error_code == "unauthorized"
        assert error.message == "Missing authentication"
        assert error.details is None
        assert error.request_id == "01234567-89ab-cdef-0123-456789abcdef"

    def test_api_error_with_details(self):
        """Test APIError with additional details."""
        error = APIError(
            error_code="invalid_request",
            message="Validation failed",
            details={"field": "email", "error": "invalid format"},
            request_id="test-request-id",
            timestamp=datetime.now(UTC),
        )
        assert error.details == {"field": "email", "error": "invalid format"}

    def test_api_error_json_serialization(self):
        """Test APIError can be serialized to JSON."""
        timestamp = datetime.now(UTC)
        error = APIError(
            error_code="not_found",
            message="Resource not found",
            details=None,
            request_id="test-id",
            timestamp=timestamp,
        )
        json_data = error.model_dump(mode="json")
        assert json_data["error_code"] == "not_found"
        assert json_data["message"] == "Resource not found"
        assert "timestamp" in json_data

    def test_api_error_requires_message(self):
        """Test that message is required."""
        with pytest.raises(ValidationError):
            APIError(
                error_code="internal_error",
                details=None,
                request_id="test-id",
                timestamp=datetime.now(UTC),
            )


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_health_status_values(self):
        """Verify health status values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"


class TestHealthResponse:
    """Tests for HealthResponse schema."""

    def test_health_response_creation(self):
        """Test creating a valid HealthResponse."""
        response = HealthResponse(
            status=HealthStatus.HEALTHY,
            version="1.0.0",
            timestamp=datetime.now(UTC),
        )
        assert response.status == HealthStatus.HEALTHY
        assert response.version == "1.0.0"

    def test_health_response_json_serialization(self):
        """Test HealthResponse JSON serialization."""
        response = HealthResponse(
            status=HealthStatus.HEALTHY,
            version="1.0.0",
            timestamp=datetime.now(UTC),
        )
        json_data = response.model_dump(mode="json")
        assert json_data["status"] == "healthy"
        assert json_data["version"] == "1.0.0"


class TestComponentHealth:
    """Tests for ComponentHealth schema."""

    def test_component_health_creation(self):
        """Test creating ComponentHealth."""
        health = ComponentHealth(
            status=HealthStatus.HEALTHY,
            message="Connection successful",
            latency_ms=5.2,
        )
        assert health.status == HealthStatus.HEALTHY
        assert health.message == "Connection successful"
        assert health.latency_ms == 5.2

    def test_component_health_without_latency(self):
        """Test ComponentHealth with optional latency."""
        health = ComponentHealth(
            status=HealthStatus.HEALTHY,
            message="Check skipped",
            latency_ms=None,
        )
        assert health.latency_ms is None

    def test_unhealthy_component(self):
        """Test unhealthy component status."""
        health = ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            message="Connection timeout",
            latency_ms=30000.0,
        )
        assert health.status == HealthStatus.UNHEALTHY


class TestHealthDetailResponse:
    """Tests for HealthDetailResponse schema."""

    def test_health_detail_response_creation(self):
        """Test creating HealthDetailResponse."""
        db_health = ComponentHealth(
            status=HealthStatus.HEALTHY,
            message="Database OK",
            latency_ms=2.5,
        )
        response = HealthDetailResponse(
            status=HealthStatus.HEALTHY,
            version="1.0.0",
            timestamp=datetime.now(UTC),
            database=db_health,
            redis=None,
            details=None,
        )
        assert response.database == db_health
        assert response.redis is None

    def test_health_detail_with_all_components(self):
        """Test HealthDetailResponse with all components."""
        db_health = ComponentHealth(
            status=HealthStatus.HEALTHY,
            message="Database OK",
            latency_ms=2.5,
        )
        redis_health = ComponentHealth(
            status=HealthStatus.HEALTHY,
            message="Redis OK",
            latency_ms=1.0,
        )
        response = HealthDetailResponse(
            status=HealthStatus.HEALTHY,
            version="1.0.0",
            timestamp=datetime.now(UTC),
            database=db_health,
            redis=redis_health,
            details={"checks_performed": ["database", "redis"]},
        )
        assert response.database is not None
        assert response.redis is not None
        assert response.details == {"checks_performed": ["database", "redis"]}

    def test_degraded_status_response(self):
        """Test HealthDetailResponse with degraded status."""
        db_health = ComponentHealth(
            status=HealthStatus.HEALTHY,
            message="Database OK",
            latency_ms=2.5,
        )
        redis_health = ComponentHealth(
            status=HealthStatus.DEGRADED,
            message="Redis slow",
            latency_ms=500.0,
        )
        response = HealthDetailResponse(
            status=HealthStatus.DEGRADED,
            version="1.0.0",
            timestamp=datetime.now(UTC),
            database=db_health,
            redis=redis_health,
            details=None,
        )
        assert response.status == HealthStatus.DEGRADED
