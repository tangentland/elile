"""Integration tests for screening API endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from httpx import AsyncClient
from pydantic import SecretStr

from elile.agent.state import SearchDegree, ServiceTier, VigilanceLevel
from elile.api.app import create_app
from elile.compliance.types import Locale, RoleCategory
from elile.config.settings import ModelProvider, Settings
from elile.screening import (
    ScreeningResult,
    ScreeningStatus,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def screening_test_settings() -> Settings:
    """Create settings for screening API testing."""
    return Settings(
        anthropic_api_key=SecretStr("test-anthropic-key"),
        openai_api_key=SecretStr("test-openai-key"),
        google_api_key=SecretStr("test-google-key"),
        default_model_provider=ModelProvider.ANTHROPIC,
        API_SECRET_KEY=SecretStr("test-api-secret"),
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        ENVIRONMENT="test",
        DEBUG=True,
        log_level="DEBUG",
    )


@pytest.fixture
def screening_test_app(screening_test_settings: Settings):
    """Create a FastAPI test application for screening tests."""
    return create_app(settings=screening_test_settings)


@pytest.fixture
def mock_tenant_validation():
    """Mock the tenant validation to skip database checks."""
    with patch(
        "elile.api.middleware.tenant.TenantValidationMiddleware._validate_tenant",
        new_callable=AsyncMock,
    ) as mock:
        # Mock returns None (validation passes)
        mock.return_value = None
        yield mock


@pytest.fixture(autouse=True)
def reset_screening_storage():
    """Reset the screening storage between tests."""
    # Clear the module-level state before each test
    from elile.api.routers.v1 import screening

    screening._stored_results.clear()
    screening._state_manager = None
    yield
    # Clear again after test
    screening._stored_results.clear()
    screening._state_manager = None


@pytest.fixture
async def screening_client(
    screening_test_app, screening_test_settings: Settings, mock_tenant_validation
):
    """Create an authenticated async HTTP client for screening tests."""
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=screening_test_app),
        base_url="http://test",
        headers={
            "Authorization": f"Bearer {screening_test_settings.API_SECRET_KEY.get_secret_value()}",
            "X-Tenant-ID": "01234567-89ab-cdef-0123-456789abcdef",
        },
    ) as client:
        yield client


def create_mock_screening_result(
    screening_id: UUID | None = None,
    status: ScreeningStatus = ScreeningStatus.COMPLETE,
    risk_score: int = 35,
) -> ScreeningResult:
    """Create a mock screening result for testing."""
    from uuid import uuid4

    # Convert to standard UUID if it's a uuid_utils.UUID
    if screening_id is None:
        screening_id = uuid4()
    else:
        # Ensure it's a standard uuid.UUID for Pydantic serialization
        screening_id = UUID(str(screening_id))

    return ScreeningResult(
        screening_id=screening_id,
        tenant_id=UUID("01234567-89ab-cdef-0123-456789abcdef"),
        status=status,
        risk_score=risk_score,
        risk_level="moderate" if status == ScreeningStatus.COMPLETE else "low",
        recommendation="proceed_with_caution" if status == ScreeningStatus.COMPLETE else "proceed",
        findings_count=3 if status == ScreeningStatus.COMPLETE else 0,
        critical_findings=0,
        high_findings=1 if status == ScreeningStatus.COMPLETE else 0,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC) if status != ScreeningStatus.IN_PROGRESS else None,
    )


@pytest.fixture
def mock_orchestrator():
    """Create a mock screening orchestrator that returns a successful result."""
    orchestrator = MagicMock()

    async def mock_execute(request, ctx=None):
        return create_mock_screening_result(
            screening_id=request.screening_id,
            status=ScreeningStatus.COMPLETE,
        )

    orchestrator.execute_screening = AsyncMock(side_effect=mock_execute)
    return orchestrator


@pytest.fixture
def mock_in_progress_orchestrator():
    """Create a mock orchestrator that returns in-progress status."""
    orchestrator = MagicMock()

    async def mock_execute(request, ctx=None):
        return create_mock_screening_result(
            screening_id=request.screening_id,
            status=ScreeningStatus.IN_PROGRESS,
        )

    orchestrator.execute_screening = AsyncMock(side_effect=mock_execute)
    return orchestrator


# =============================================================================
# POST /v1/screenings Tests
# =============================================================================


@pytest.mark.asyncio
class TestInitiateScreening:
    """Tests for POST /v1/screenings endpoint."""

    async def test_initiate_screening_returns_202(
        self, screening_client: AsyncClient, mock_orchestrator
    ):
        """Test initiating screening returns 202 Accepted."""
        with patch(
            "elile.api.routers.v1.screening.get_orchestrator",
            return_value=mock_orchestrator,
        ):
            response = await screening_client.post(
                "/v1/screenings/",
                json={
                    "subject": {
                        "full_name": "John Smith",
                        "date_of_birth": "1985-03-15",
                    },
                    "consent_token": "consent-abc123",
                },
            )

            assert response.status_code == 202

    async def test_initiate_screening_returns_screening_id(
        self, screening_client: AsyncClient, mock_orchestrator
    ):
        """Test response includes screening_id."""
        with patch(
            "elile.api.routers.v1.screening.get_orchestrator",
            return_value=mock_orchestrator,
        ):
            response = await screening_client.post(
                "/v1/screenings/",
                json={
                    "subject": {"full_name": "John Smith"},
                    "consent_token": "consent-abc123",
                },
            )

            data = response.json()
            assert "screening_id" in data
            # Validate it's a valid UUID
            UUID(data["screening_id"])

    async def test_initiate_screening_returns_status(
        self, screening_client: AsyncClient, mock_orchestrator
    ):
        """Test response includes status."""
        with patch(
            "elile.api.routers.v1.screening.get_orchestrator",
            return_value=mock_orchestrator,
        ):
            response = await screening_client.post(
                "/v1/screenings/",
                json={
                    "subject": {"full_name": "John Smith"},
                    "consent_token": "consent-abc123",
                },
            )

            data = response.json()
            assert "status" in data
            assert data["status"] in ["pending", "validating", "in_progress", "complete", "failed"]

    async def test_initiate_screening_with_all_fields(
        self, screening_client: AsyncClient, mock_orchestrator
    ):
        """Test initiating screening with all optional fields."""
        with patch(
            "elile.api.routers.v1.screening.get_orchestrator",
            return_value=mock_orchestrator,
        ):
            response = await screening_client.post(
                "/v1/screenings/",
                json={
                    "subject": {
                        "full_name": "John Michael Smith",
                        "first_name": "John",
                        "last_name": "Smith",
                        "middle_name": "Michael",
                        "date_of_birth": "1985-03-15",
                        "ssn": "6789",
                        "email": "john.smith@example.com",
                        "phone": "+1-555-123-4567",
                        "current_address": {
                            "street_address": "123 Main St",
                            "city": "Springfield",
                            "state": "IL",
                            "postal_code": "62701",
                            "country": "US",
                        },
                    },
                    "locale": "US",
                    "service_tier": "standard",
                    "search_degree": "d1",
                    "vigilance_level": "v0",
                    "role_category": "standard",
                    "consent_token": "consent-abc123",
                    "report_types": ["summary"],
                    "priority": "normal",
                    "metadata": {"reference_id": "HR-2026-001"},
                },
            )

            assert response.status_code == 202
            data = response.json()
            assert "screening_id" in data

    async def test_initiate_screening_missing_name_returns_422(self, screening_client: AsyncClient):
        """Test missing subject name returns 422."""
        response = await screening_client.post(
            "/v1/screenings/",
            json={
                "subject": {},  # Missing full_name
                "consent_token": "consent-abc123",
            },
        )

        assert response.status_code == 422

    async def test_initiate_screening_missing_consent_returns_422(
        self, screening_client: AsyncClient
    ):
        """Test missing consent token returns 422."""
        response = await screening_client.post(
            "/v1/screenings/",
            json={
                "subject": {"full_name": "John Smith"},
                # Missing consent_token
            },
        )

        assert response.status_code == 422

    async def test_initiate_screening_invalid_dob_returns_422(self, screening_client: AsyncClient):
        """Test invalid date_of_birth format returns 422."""
        response = await screening_client.post(
            "/v1/screenings/",
            json={
                "subject": {
                    "full_name": "John Smith",
                    "date_of_birth": "03/15/1985",  # Wrong format
                },
                "consent_token": "consent-abc123",
            },
        )

        assert response.status_code == 422

    async def test_initiate_screening_d3_requires_enhanced(self, screening_client: AsyncClient):
        """Test D3 search degree requires Enhanced tier."""
        response = await screening_client.post(
            "/v1/screenings/",
            json={
                "subject": {"full_name": "John Smith"},
                "consent_token": "consent-abc123",
                "service_tier": "standard",
                "search_degree": "d3",  # Requires enhanced tier
            },
        )

        assert response.status_code == 422

    async def test_initiate_screening_d3_with_enhanced_succeeds(
        self, screening_client: AsyncClient, mock_orchestrator
    ):
        """Test D3 search degree with Enhanced tier succeeds."""
        with patch(
            "elile.api.routers.v1.screening.get_orchestrator",
            return_value=mock_orchestrator,
        ):
            response = await screening_client.post(
                "/v1/screenings/",
                json={
                    "subject": {"full_name": "John Smith"},
                    "consent_token": "consent-abc123",
                    "service_tier": "enhanced",
                    "search_degree": "d3",
                },
            )

            assert response.status_code == 202

    async def test_initiate_screening_requires_auth(self, screening_test_app):
        """Test screening endpoint requires authentication."""
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=screening_test_app),
            base_url="http://test",
            headers={
                # No Authorization header
                "X-Tenant-ID": "01234567-89ab-cdef-0123-456789abcdef",
            },
        ) as client:
            response = await client.post(
                "/v1/screenings/",
                json={
                    "subject": {"full_name": "John Smith"},
                    "consent_token": "consent-abc123",
                },
            )

            assert response.status_code == 401

    async def test_initiate_screening_requires_tenant(
        self, screening_test_app, screening_test_settings: Settings
    ):
        """Test screening endpoint requires tenant header."""
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=screening_test_app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {screening_test_settings.API_SECRET_KEY.get_secret_value()}",
                # No X-Tenant-ID header
            },
        ) as client:
            response = await client.post(
                "/v1/screenings/",
                json={
                    "subject": {"full_name": "John Smith"},
                    "consent_token": "consent-abc123",
                },
            )

            # Should fail tenant validation
            assert response.status_code in [400, 401, 403, 422]


# =============================================================================
# GET /v1/screenings/{screening_id} Tests
# =============================================================================


@pytest.mark.asyncio
class TestGetScreening:
    """Tests for GET /v1/screenings/{screening_id} endpoint."""

    async def test_get_screening_not_found_returns_404(self, screening_client: AsyncClient):
        """Test getting non-existent screening returns 404."""
        response = await screening_client.get("/v1/screenings/01234567-89ab-cdef-0123-000000000000")

        assert response.status_code == 404

    async def test_get_screening_invalid_uuid_returns_422(self, screening_client: AsyncClient):
        """Test getting screening with invalid UUID returns 422."""
        response = await screening_client.get("/v1/screenings/not-a-uuid")

        assert response.status_code == 422

    async def test_get_screening_after_create(
        self, screening_client: AsyncClient, mock_orchestrator
    ):
        """Test getting screening after creation."""
        with patch(
            "elile.api.routers.v1.screening.get_orchestrator",
            return_value=mock_orchestrator,
        ):
            # Create a screening
            create_response = await screening_client.post(
                "/v1/screenings/",
                json={
                    "subject": {"full_name": "John Smith"},
                    "consent_token": "consent-abc123",
                },
            )
            screening_id = create_response.json()["screening_id"]

        # Get the screening (outside mock, but result was stored)
        response = await screening_client.get(f"/v1/screenings/{screening_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["screening_id"] == screening_id

    async def test_get_screening_returns_risk_score(
        self, screening_client: AsyncClient, mock_orchestrator
    ):
        """Test completed screening includes risk score."""
        with patch(
            "elile.api.routers.v1.screening.get_orchestrator",
            return_value=mock_orchestrator,
        ):
            # Create a screening
            create_response = await screening_client.post(
                "/v1/screenings/",
                json={
                    "subject": {"full_name": "John Smith"},
                    "consent_token": "consent-abc123",
                },
            )
            screening_id = create_response.json()["screening_id"]

        # Get the screening
        response = await screening_client.get(f"/v1/screenings/{screening_id}")

        data = response.json()
        if data["status"] == "complete":
            assert "risk_score" in data
            assert isinstance(data["risk_score"], int)

    async def test_get_screening_requires_auth(self, screening_test_app):
        """Test get screening requires authentication."""
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=screening_test_app),
            base_url="http://test",
            headers={"X-Tenant-ID": "01234567-89ab-cdef-0123-456789abcdef"},
        ) as client:
            response = await client.get("/v1/screenings/01234567-89ab-cdef-0123-456789abcdef")

            assert response.status_code == 401


# =============================================================================
# DELETE /v1/screenings/{screening_id} Tests
# =============================================================================


@pytest.mark.asyncio
class TestCancelScreening:
    """Tests for DELETE /v1/screenings/{screening_id} endpoint."""

    async def test_cancel_screening_not_found_returns_404(self, screening_client: AsyncClient):
        """Test cancelling non-existent screening returns 404."""
        response = await screening_client.delete(
            "/v1/screenings/01234567-89ab-cdef-0123-000000000000"
        )

        assert response.status_code == 404

    @pytest.mark.skip(
        reason="Requires async background tasks - screenings complete synchronously for now"
    )
    async def test_cancel_in_progress_screening(self, screening_client: AsyncClient):
        """Test cancelling a screening that is in progress.

        NOTE: This test is skipped because the current implementation
        processes screenings synchronously. In production with background
        tasks, this test would verify that in-progress screenings can be
        cancelled.
        """
        pass

    async def test_cancel_completed_screening_returns_409(
        self, screening_client: AsyncClient, mock_orchestrator
    ):
        """Test cancelling completed screening returns 409."""
        with patch(
            "elile.api.routers.v1.screening.get_orchestrator",
            return_value=mock_orchestrator,
        ):
            # Create a completed screening
            create_response = await screening_client.post(
                "/v1/screenings/",
                json={
                    "subject": {"full_name": "John Smith"},
                    "consent_token": "consent-abc123",
                },
            )
            screening_id = create_response.json()["screening_id"]

        # Try to cancel - should fail because it's complete
        response = await screening_client.delete(f"/v1/screenings/{screening_id}")

        assert response.status_code == 409

    async def test_cancel_screening_requires_auth(self, screening_test_app):
        """Test cancel screening requires authentication."""
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=screening_test_app),
            base_url="http://test",
            headers={"X-Tenant-ID": "01234567-89ab-cdef-0123-456789abcdef"},
        ) as client:
            response = await client.delete("/v1/screenings/01234567-89ab-cdef-0123-456789abcdef")

            assert response.status_code == 401


# =============================================================================
# GET /v1/screenings/ Tests
# =============================================================================


@pytest.mark.asyncio
class TestListScreenings:
    """Tests for GET /v1/screenings/ endpoint."""

    async def test_list_screenings_returns_200(self, screening_client: AsyncClient):
        """Test listing screenings returns 200."""
        response = await screening_client.get("/v1/screenings/")

        assert response.status_code == 200

    async def test_list_screenings_returns_pagination(self, screening_client: AsyncClient):
        """Test listing screenings returns pagination info."""
        response = await screening_client.get("/v1/screenings/")

        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "has_more" in data

    async def test_list_screenings_structure(self, screening_client: AsyncClient):
        """Test listing screenings returns proper structure."""
        response = await screening_client.get("/v1/screenings/")

        data = response.json()
        # Check structure, not counts (counts depend on test isolation)
        assert isinstance(data["total"], int)
        assert data["total"] >= 0
        assert isinstance(data["items"], list)
        assert isinstance(data["page"], int)
        assert isinstance(data["page_size"], int)
        assert isinstance(data["has_more"], bool)

    async def test_list_screenings_includes_created(
        self, screening_client: AsyncClient, mock_orchestrator
    ):
        """Test listing screenings includes created screenings."""
        with patch(
            "elile.api.routers.v1.screening.get_orchestrator",
            return_value=mock_orchestrator,
        ):
            # Create a screening
            await screening_client.post(
                "/v1/screenings/",
                json={
                    "subject": {"full_name": "John Smith"},
                    "consent_token": "consent-abc123",
                },
            )

            # List screenings
            response = await screening_client.get("/v1/screenings/")

            data = response.json()
            assert data["total"] >= 1

    async def test_list_screenings_with_status_filter(
        self, screening_client: AsyncClient, mock_orchestrator
    ):
        """Test listing screenings with status filter."""
        with patch(
            "elile.api.routers.v1.screening.get_orchestrator",
            return_value=mock_orchestrator,
        ):
            # Create a screening
            await screening_client.post(
                "/v1/screenings/",
                json={
                    "subject": {"full_name": "John Smith"},
                    "consent_token": "consent-abc123",
                },
            )

            # List with status filter
            response = await screening_client.get("/v1/screenings/?status=complete")

            assert response.status_code == 200
            data = response.json()
            for item in data["items"]:
                assert item["status"] == "complete"

    async def test_list_screenings_pagination(self, screening_client: AsyncClient):
        """Test listing screenings with pagination parameters."""
        response = await screening_client.get("/v1/screenings/?page=1&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    async def test_list_screenings_requires_auth(self, screening_test_app):
        """Test listing screenings requires authentication."""
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=screening_test_app),
            base_url="http://test",
            headers={"X-Tenant-ID": "01234567-89ab-cdef-0123-456789abcdef"},
        ) as client:
            response = await client.get("/v1/screenings/")

            assert response.status_code == 401


# =============================================================================
# Response Format Tests
# =============================================================================


@pytest.mark.asyncio
class TestScreeningResponseFormat:
    """Tests for screening response format."""

    async def test_response_includes_timestamps(
        self, screening_client: AsyncClient, mock_orchestrator
    ):
        """Test response includes timestamp fields."""
        with patch(
            "elile.api.routers.v1.screening.get_orchestrator",
            return_value=mock_orchestrator,
        ):
            response = await screening_client.post(
                "/v1/screenings/",
                json={
                    "subject": {"full_name": "John Smith"},
                    "consent_token": "consent-abc123",
                },
            )

            data = response.json()
            assert "created_at" in data
            assert "updated_at" in data

    async def test_response_includes_progress(
        self, screening_client: AsyncClient, mock_orchestrator
    ):
        """Test response includes progress info."""
        with patch(
            "elile.api.routers.v1.screening.get_orchestrator",
            return_value=mock_orchestrator,
        ):
            response = await screening_client.post(
                "/v1/screenings/",
                json={
                    "subject": {"full_name": "John Smith"},
                    "consent_token": "consent-abc123",
                },
            )

            data = response.json()
            assert "progress_percent" in data
            assert 0 <= data["progress_percent"] <= 100

    async def test_response_includes_findings_count(
        self, screening_client: AsyncClient, mock_orchestrator
    ):
        """Test response includes findings counts."""
        with patch(
            "elile.api.routers.v1.screening.get_orchestrator",
            return_value=mock_orchestrator,
        ):
            response = await screening_client.post(
                "/v1/screenings/",
                json={
                    "subject": {"full_name": "John Smith"},
                    "consent_token": "consent-abc123",
                },
            )

            data = response.json()
            assert "findings_count" in data
            assert "critical_findings" in data
            assert "high_findings" in data


# =============================================================================
# Error Response Tests
# =============================================================================


@pytest.mark.asyncio
class TestScreeningErrorResponses:
    """Tests for screening error responses."""

    async def test_404_includes_error_code(self, screening_client: AsyncClient):
        """Test 404 response includes error_code."""
        response = await screening_client.get("/v1/screenings/01234567-89ab-cdef-0123-000000000000")

        assert response.status_code == 404
        data = response.json()
        assert "error_code" in data["detail"]
        assert data["detail"]["error_code"] == "not_found"

    async def test_404_includes_request_id(self, screening_client: AsyncClient):
        """Test 404 response includes request_id."""
        response = await screening_client.get("/v1/screenings/01234567-89ab-cdef-0123-000000000000")

        assert response.status_code == 404
        data = response.json()
        assert "request_id" in data["detail"]

    async def test_validation_error_format(self, screening_client: AsyncClient):
        """Test validation error response format."""
        response = await screening_client.post(
            "/v1/screenings/",
            json={
                "subject": {},  # Invalid - missing full_name
                "consent_token": "consent-abc123",
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
