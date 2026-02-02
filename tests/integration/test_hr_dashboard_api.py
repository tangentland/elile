"""Integration tests for HR Dashboard API endpoints.

Tests the HR Dashboard API endpoints:
- GET /v1/dashboard/hr/portfolio
- GET /v1/dashboard/hr/screenings
- GET /v1/dashboard/hr/alerts
- GET /v1/dashboard/hr/risk-distribution
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from elile.api.app import create_app
from elile.config.settings import ModelProvider, Settings
from elile.monitoring.alert_generator import GeneratedAlert
from elile.monitoring.types import AlertSeverity, MonitoringAlert
from elile.screening.types import ScreeningResult, ScreeningStatus

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def dashboard_test_settings() -> Settings:
    """Create settings for dashboard API testing."""
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
def dashboard_test_app(dashboard_test_settings: Settings):
    """Create a FastAPI test application for dashboard tests."""
    return create_app(settings=dashboard_test_settings)


@pytest.fixture
def mock_tenant_validation():
    """Mock the tenant validation to skip database checks."""
    with patch(
        "elile.api.middleware.tenant.TenantValidationMiddleware._validate_tenant",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = None
        yield mock


@pytest.fixture(autouse=True)
def reset_storage():
    """Reset storage between tests."""
    from elile.api.routers.v1 import dashboard, screening

    # Clear screening storage
    screening._stored_results.clear()
    screening._state_manager = None

    # Clear dashboard storage
    dashboard._state_manager = None
    dashboard._alert_generator = None

    yield

    # Clear again after test
    screening._stored_results.clear()
    screening._state_manager = None
    dashboard._state_manager = None
    dashboard._alert_generator = None


@pytest.fixture
def test_tenant_id() -> UUID:
    """Fixed tenant ID for tests."""
    return UUID("01234567-89ab-cdef-0123-456789abcdef")


@pytest.fixture
async def dashboard_client(
    dashboard_test_app,
    dashboard_test_settings: Settings,
    mock_tenant_validation,  # noqa: ARG001 - fixture needed to patch tenant validation
    test_tenant_id,
):
    """Create an authenticated async HTTP client for dashboard tests."""
    async with AsyncClient(
        transport=ASGITransport(app=dashboard_test_app),
        base_url="http://test",
        headers={
            "Authorization": f"Bearer {dashboard_test_settings.API_SECRET_KEY.get_secret_value()}",
            "X-Tenant-ID": str(test_tenant_id),
        },
    ) as client:
        yield client


def create_test_screening(
    tenant_id: UUID,
    status: ScreeningStatus = ScreeningStatus.COMPLETE,
    risk_score: int = 25,
    risk_level: str = "low",
    recommendation: str = "proceed",
    findings_count: int = 0,
    critical_findings: int = 0,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> ScreeningResult:
    """Create a test screening result."""
    from uuid import uuid4

    now = datetime.now(UTC)
    return ScreeningResult(
        screening_id=uuid4(),
        tenant_id=tenant_id,
        status=status,
        risk_score=risk_score,
        risk_level=risk_level,
        recommendation=recommendation,
        findings_count=findings_count,
        critical_findings=critical_findings,
        started_at=started_at or now,
        completed_at=completed_at or (now if status == ScreeningStatus.COMPLETE else None),
    )


def add_test_screening(screening: ScreeningResult) -> None:
    """Add a screening to the test storage."""
    from elile.api.routers.v1 import screening as screening_module

    key = str(screening.screening_id)
    screening_module._stored_results[key] = screening


def get_alert_generator():
    """Get or create the test alert generator."""
    from elile.api.routers.v1 import dashboard

    return dashboard._get_global_alert_generator()


# =============================================================================
# Portfolio Endpoint Tests
# =============================================================================


class TestPortfolioEndpoint:
    """Tests for GET /v1/dashboard/hr/portfolio."""

    @pytest.mark.asyncio
    async def test_portfolio_empty(self, dashboard_client: AsyncClient) -> None:
        """Test portfolio with no screenings."""
        response = await dashboard_client.get("/v1/dashboard/hr/portfolio")

        assert response.status_code == 200
        data = response.json()

        assert "metrics" in data
        assert "recent_alerts" in data
        assert "updated_at" in data

        metrics = data["metrics"]
        assert metrics["total_screenings"] == 0
        assert metrics["active_screenings"] == 0
        assert metrics["completed_screenings"] == 0
        assert metrics["pending_reviews"] == 0
        assert metrics["average_risk_score"] == 0.0

    @pytest.mark.asyncio
    async def test_portfolio_with_screenings(
        self, dashboard_client: AsyncClient, test_tenant_id: UUID
    ) -> None:
        """Test portfolio with multiple screenings."""
        add_test_screening(create_test_screening(test_tenant_id, risk_score=20, risk_level="low"))
        add_test_screening(
            create_test_screening(test_tenant_id, risk_score=40, risk_level="moderate")
        )
        add_test_screening(create_test_screening(test_tenant_id, risk_score=60, risk_level="high"))
        add_test_screening(
            create_test_screening(
                test_tenant_id, status=ScreeningStatus.IN_PROGRESS, risk_score=0
            )
        )

        response = await dashboard_client.get("/v1/dashboard/hr/portfolio")

        assert response.status_code == 200
        data = response.json()

        metrics = data["metrics"]
        assert metrics["total_screenings"] == 4
        assert metrics["active_screenings"] == 1
        assert metrics["completed_screenings"] == 3

        distribution = metrics["risk_distribution"]
        assert distribution["low"] == 1
        assert distribution["moderate"] == 1
        assert distribution["high"] == 1
        assert distribution["total"] == 3

    @pytest.mark.asyncio
    async def test_portfolio_average_risk_score(
        self, dashboard_client: AsyncClient, test_tenant_id: UUID
    ) -> None:
        """Test average risk score calculation."""
        add_test_screening(create_test_screening(test_tenant_id, risk_score=20))
        add_test_screening(create_test_screening(test_tenant_id, risk_score=40))
        add_test_screening(create_test_screening(test_tenant_id, risk_score=60))

        response = await dashboard_client.get("/v1/dashboard/hr/portfolio")

        assert response.status_code == 200
        metrics = response.json()["metrics"]
        assert metrics["average_risk_score"] == 40.0

    @pytest.mark.asyncio
    async def test_portfolio_pending_reviews(
        self, dashboard_client: AsyncClient, test_tenant_id: UUID
    ) -> None:
        """Test pending reviews count."""
        add_test_screening(create_test_screening(test_tenant_id, recommendation="proceed"))
        add_test_screening(create_test_screening(test_tenant_id, recommendation="review_required"))
        add_test_screening(create_test_screening(test_tenant_id, recommendation="do_not_proceed"))

        response = await dashboard_client.get("/v1/dashboard/hr/portfolio")

        assert response.status_code == 200
        metrics = response.json()["metrics"]
        assert metrics["pending_reviews"] == 2

    @pytest.mark.asyncio
    async def test_portfolio_unauthorized(self, dashboard_test_app) -> None:
        """Test portfolio without auth fails."""
        async with AsyncClient(
            transport=ASGITransport(app=dashboard_test_app),
            base_url="http://test",
        ) as client:
            response = await client.get("/v1/dashboard/hr/portfolio")
            assert response.status_code == 401


# =============================================================================
# Screenings List Endpoint Tests
# =============================================================================


class TestScreeningsListEndpoint:
    """Tests for GET /v1/dashboard/hr/screenings."""

    @pytest.mark.asyncio
    async def test_list_screenings_empty(self, dashboard_client: AsyncClient) -> None:
        """Test listing screenings with no data."""
        response = await dashboard_client.get("/v1/dashboard/hr/screenings")

        assert response.status_code == 200
        data = response.json()

        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_list_screenings_with_data(
        self, dashboard_client: AsyncClient, test_tenant_id: UUID
    ) -> None:
        """Test listing screenings with data."""
        for i in range(5):
            add_test_screening(create_test_screening(test_tenant_id, risk_score=20 + i * 10))

        response = await dashboard_client.get("/v1/dashboard/hr/screenings")

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 5
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_list_screenings_filter_by_status(
        self, dashboard_client: AsyncClient, test_tenant_id: UUID
    ) -> None:
        """Test filtering screenings by status."""
        add_test_screening(create_test_screening(test_tenant_id, status=ScreeningStatus.COMPLETE))
        add_test_screening(
            create_test_screening(test_tenant_id, status=ScreeningStatus.IN_PROGRESS)
        )
        add_test_screening(create_test_screening(test_tenant_id, status=ScreeningStatus.COMPLETE))

        response = await dashboard_client.get(
            "/v1/dashboard/hr/screenings",
            params={"status": "complete"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 2
        assert data["filters_applied"]["status"] == "complete"

    @pytest.mark.asyncio
    async def test_list_screenings_filter_by_risk_level(
        self, dashboard_client: AsyncClient, test_tenant_id: UUID
    ) -> None:
        """Test filtering screenings by risk level."""
        add_test_screening(create_test_screening(test_tenant_id, risk_level="low"))
        add_test_screening(create_test_screening(test_tenant_id, risk_level="high"))
        add_test_screening(create_test_screening(test_tenant_id, risk_level="high"))

        response = await dashboard_client.get(
            "/v1/dashboard/hr/screenings",
            params={"risk_level": "high"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 2
        assert data["filters_applied"]["risk_level"] == "high"

    @pytest.mark.asyncio
    async def test_list_screenings_filter_by_critical_findings(
        self, dashboard_client: AsyncClient, test_tenant_id: UUID
    ) -> None:
        """Test filtering screenings by critical findings."""
        add_test_screening(create_test_screening(test_tenant_id, critical_findings=0))
        add_test_screening(create_test_screening(test_tenant_id, critical_findings=2))
        add_test_screening(create_test_screening(test_tenant_id, critical_findings=0))

        response = await dashboard_client.get(
            "/v1/dashboard/hr/screenings",
            params={"has_critical_findings": "true"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert data["filters_applied"]["has_critical_findings"] is True

    @pytest.mark.asyncio
    async def test_list_screenings_pagination(
        self, dashboard_client: AsyncClient, test_tenant_id: UUID
    ) -> None:
        """Test pagination of screenings."""
        for i in range(15):
            add_test_screening(create_test_screening(test_tenant_id, risk_score=20 + i))

        # First page
        response = await dashboard_client.get(
            "/v1/dashboard/hr/screenings",
            params={"page": 1, "page_size": 10},
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 10
        assert data["total"] == 15
        assert data["page"] == 1
        assert data["has_more"] is True

        # Second page
        response = await dashboard_client.get(
            "/v1/dashboard/hr/screenings",
            params={"page": 2, "page_size": 10},
        )

        data = response.json()

        assert len(data["items"]) == 5
        assert data["page"] == 2
        assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_list_screenings_date_filter(
        self, dashboard_client: AsyncClient, test_tenant_id: UUID
    ) -> None:
        """Test filtering screenings by date range."""
        now = datetime.now(UTC)
        yesterday = now - timedelta(days=1)
        last_week = now - timedelta(days=7)

        add_test_screening(create_test_screening(test_tenant_id, started_at=now))
        add_test_screening(create_test_screening(test_tenant_id, started_at=yesterday))
        add_test_screening(create_test_screening(test_tenant_id, started_at=last_week))

        response = await dashboard_client.get(
            "/v1/dashboard/hr/screenings",
            params={"date_from": yesterday.isoformat()},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 2


# =============================================================================
# Alerts List Endpoint Tests
# =============================================================================


class TestAlertsListEndpoint:
    """Tests for GET /v1/dashboard/hr/alerts."""

    @pytest.mark.asyncio
    async def test_list_alerts_empty(self, dashboard_client: AsyncClient) -> None:
        """Test listing alerts with no data."""
        response = await dashboard_client.get("/v1/dashboard/hr/alerts")

        assert response.status_code == 200
        data = response.json()

        assert data["items"] == []
        assert data["total"] == 0
        assert data["unacknowledged_count"] == 0

    @pytest.mark.asyncio
    async def test_list_alerts_pagination(self, dashboard_client: AsyncClient) -> None:
        """Test pagination of alerts."""
        generator = get_alert_generator()

        for i in range(25):
            alert = MonitoringAlert(
                severity=AlertSeverity.MEDIUM,
                title=f"Alert {i}",
                description=f"Alert description {i}",
            )
            generated = GeneratedAlert(alert=alert)
            generator._alert_history.append(generated)

        response = await dashboard_client.get(
            "/v1/dashboard/hr/alerts",
            params={"page": 1, "page_size": 10},
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 10
        assert data["total"] == 25
        assert data["has_more"] is True

    @pytest.mark.asyncio
    async def test_list_alerts_filter_by_severity(self, dashboard_client: AsyncClient) -> None:
        """Test filtering alerts by severity."""
        generator = get_alert_generator()

        for severity in [AlertSeverity.LOW, AlertSeverity.MEDIUM, AlertSeverity.HIGH]:
            alert = MonitoringAlert(
                severity=severity,
                title=f"{severity.value} Alert",
                description="Test",
            )
            generator._alert_history.append(GeneratedAlert(alert=alert))

        response = await dashboard_client.get(
            "/v1/dashboard/hr/alerts",
            params={"severity": "high"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert data["items"][0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_list_alerts_filter_by_acknowledged(self, dashboard_client: AsyncClient) -> None:
        """Test filtering alerts by acknowledgment status."""
        generator = get_alert_generator()

        # Add unacknowledged
        alert1 = MonitoringAlert(
            severity=AlertSeverity.MEDIUM,
            title="Unacknowledged Alert",
            description="Test",
            acknowledged=False,
        )
        generator._alert_history.append(GeneratedAlert(alert=alert1))

        # Add acknowledged
        alert2 = MonitoringAlert(
            severity=AlertSeverity.MEDIUM,
            title="Acknowledged Alert",
            description="Test",
            acknowledged=True,
        )
        generator._alert_history.append(GeneratedAlert(alert=alert2))

        response = await dashboard_client.get(
            "/v1/dashboard/hr/alerts",
            params={"acknowledged": "false"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert data["unacknowledged_count"] == 1

    @pytest.mark.asyncio
    async def test_list_alerts_unacknowledged_count(self, dashboard_client: AsyncClient) -> None:
        """Test unacknowledged alerts count."""
        generator = get_alert_generator()

        # Add 3 unacknowledged
        for i in range(3):
            alert = MonitoringAlert(
                severity=AlertSeverity.MEDIUM,
                title=f"Alert {i}",
                description="Test",
                acknowledged=False,
            )
            generator._alert_history.append(GeneratedAlert(alert=alert))

        # Add 2 acknowledged
        for i in range(2):
            alert = MonitoringAlert(
                severity=AlertSeverity.LOW,
                title=f"Ack Alert {i}",
                description="Test",
                acknowledged=True,
            )
            generator._alert_history.append(GeneratedAlert(alert=alert))

        response = await dashboard_client.get("/v1/dashboard/hr/alerts")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 5
        assert data["unacknowledged_count"] == 3


# =============================================================================
# Risk Distribution Endpoint Tests
# =============================================================================


class TestRiskDistributionEndpoint:
    """Tests for GET /v1/dashboard/hr/risk-distribution."""

    @pytest.mark.asyncio
    async def test_risk_distribution_empty(self, dashboard_client: AsyncClient) -> None:
        """Test risk distribution with no data."""
        response = await dashboard_client.get("/v1/dashboard/hr/risk-distribution")

        assert response.status_code == 200
        data = response.json()

        assert data["distribution"]["total"] == 0
        assert data["period"] == "all_time"
        assert "items" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_risk_distribution_with_data(
        self, dashboard_client: AsyncClient, test_tenant_id: UUID
    ) -> None:
        """Test risk distribution calculation."""
        add_test_screening(create_test_screening(test_tenant_id, risk_level="low"))
        add_test_screening(create_test_screening(test_tenant_id, risk_level="low"))
        add_test_screening(create_test_screening(test_tenant_id, risk_level="moderate"))
        add_test_screening(create_test_screening(test_tenant_id, risk_level="high"))
        # Add incomplete - shouldn't be in distribution
        add_test_screening(
            create_test_screening(
                test_tenant_id, status=ScreeningStatus.IN_PROGRESS, risk_level="low"
            )
        )

        response = await dashboard_client.get("/v1/dashboard/hr/risk-distribution")

        assert response.status_code == 200
        data = response.json()

        distribution = data["distribution"]
        assert distribution["low"] == 2
        assert distribution["moderate"] == 1
        assert distribution["high"] == 1
        assert distribution["critical"] == 0
        assert distribution["total"] == 4

    @pytest.mark.asyncio
    async def test_risk_distribution_items_percentage(
        self, dashboard_client: AsyncClient, test_tenant_id: UUID
    ) -> None:
        """Test risk distribution items have correct percentages."""
        add_test_screening(create_test_screening(test_tenant_id, risk_level="low"))
        add_test_screening(create_test_screening(test_tenant_id, risk_level="low"))
        add_test_screening(create_test_screening(test_tenant_id, risk_level="moderate"))
        add_test_screening(create_test_screening(test_tenant_id, risk_level="high"))

        response = await dashboard_client.get("/v1/dashboard/hr/risk-distribution")

        assert response.status_code == 200
        items = response.json()["items"]

        # Find low item
        low_item = next(i for i in items if i["level"] == "low")
        assert low_item["count"] == 2
        assert low_item["percentage"] == 50.0

    @pytest.mark.asyncio
    async def test_risk_distribution_period_filter(
        self, dashboard_client: AsyncClient, test_tenant_id: UUID
    ) -> None:
        """Test risk distribution period filtering."""
        now = datetime.now(UTC)

        # This month
        add_test_screening(
            create_test_screening(test_tenant_id, risk_level="high", completed_at=now)
        )

        # We can't easily test last month filtering without proper date manipulation
        # Just test that the endpoint accepts the period parameter

        response = await dashboard_client.get(
            "/v1/dashboard/hr/risk-distribution",
            params={"period": "this_month"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["period"] == "this_month"


# =============================================================================
# Tenant Isolation Tests
# =============================================================================


class TestTenantIsolation:
    """Tests for tenant data isolation."""

    @pytest.mark.asyncio
    async def test_portfolio_tenant_isolation(
        self,
        dashboard_test_app,
        dashboard_test_settings,
        mock_tenant_validation,  # noqa: ARG002 - fixture needed to patch tenant validation
    ) -> None:
        """Test that portfolio only shows tenant's own data."""
        from uuid import uuid4

        tenant1_id = uuid4()
        tenant2_id = uuid4()

        # Add screenings for both tenants
        add_test_screening(create_test_screening(tenant1_id, risk_score=30))
        add_test_screening(create_test_screening(tenant1_id, risk_score=40))
        add_test_screening(create_test_screening(tenant2_id, risk_score=50))

        # Request as tenant 1
        async with AsyncClient(
            transport=ASGITransport(app=dashboard_test_app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {dashboard_test_settings.API_SECRET_KEY.get_secret_value()}",
                "X-Tenant-ID": str(tenant1_id),
            },
        ) as client:
            response = await client.get("/v1/dashboard/hr/portfolio")

        assert response.status_code == 200
        metrics = response.json()["metrics"]
        assert metrics["total_screenings"] == 2
        assert metrics["average_risk_score"] == 35.0

    @pytest.mark.asyncio
    async def test_screenings_list_tenant_isolation(
        self,
        dashboard_test_app,
        dashboard_test_settings,
        mock_tenant_validation,  # noqa: ARG002 - fixture needed to patch tenant validation
    ) -> None:
        """Test that screenings list only shows tenant's own data."""
        from uuid import uuid4

        tenant1_id = uuid4()
        tenant2_id = uuid4()

        add_test_screening(create_test_screening(tenant1_id))
        add_test_screening(create_test_screening(tenant2_id))
        add_test_screening(create_test_screening(tenant2_id))

        async with AsyncClient(
            transport=ASGITransport(app=dashboard_test_app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {dashboard_test_settings.API_SECRET_KEY.get_secret_value()}",
                "X-Tenant-ID": str(tenant1_id),
            },
        ) as client:
            response = await client.get("/v1/dashboard/hr/screenings")

        assert response.status_code == 200
        assert response.json()["total"] == 1

    @pytest.mark.asyncio
    async def test_risk_distribution_tenant_isolation(
        self,
        dashboard_test_app,
        dashboard_test_settings,
        mock_tenant_validation,  # noqa: ARG002 - fixture needed to patch tenant validation
    ) -> None:
        """Test that risk distribution only includes tenant's own data."""
        from uuid import uuid4

        tenant1_id = uuid4()
        tenant2_id = uuid4()

        add_test_screening(create_test_screening(tenant1_id, risk_level="low"))
        add_test_screening(create_test_screening(tenant2_id, risk_level="critical"))

        async with AsyncClient(
            transport=ASGITransport(app=dashboard_test_app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {dashboard_test_settings.API_SECRET_KEY.get_secret_value()}",
                "X-Tenant-ID": str(tenant1_id),
            },
        ) as client:
            response = await client.get("/v1/dashboard/hr/risk-distribution")

        assert response.status_code == 200
        distribution = response.json()["distribution"]
        assert distribution["low"] == 1
        assert distribution["critical"] == 0
        assert distribution["total"] == 1
