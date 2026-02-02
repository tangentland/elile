"""Integration tests for Compliance Portal API endpoints.

Tests the Compliance Portal API endpoints:
- GET /v1/compliance/audit-log
- GET /v1/compliance/consent-tracking
- POST /v1/compliance/data-erasure
- GET /v1/compliance/reports
- GET /v1/compliance/metrics
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid7

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from elile.api.app import create_app
from elile.api.schemas.compliance import ComplianceStatus, ErasureStatus
from elile.compliance.consent import (
    Consent,
    ConsentScope,
    ConsentVerificationMethod,
    create_consent,
)
from elile.compliance.types import Locale
from elile.config.settings import ModelProvider, Settings
from elile.db.models.audit import AuditEvent, AuditEventType, AuditSeverity

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def compliance_test_settings() -> Settings:
    """Create settings for compliance API testing."""
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
def compliance_test_app(compliance_test_settings: Settings):
    """Create a FastAPI test application for compliance tests."""
    return create_app(settings=compliance_test_settings)


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
    from elile.api.routers.v1 import compliance

    compliance._reset_storage()
    yield
    compliance._reset_storage()


@pytest.fixture
def test_tenant_id() -> UUID:
    """Fixed tenant ID for tests."""
    return UUID("01234567-89ab-cdef-0123-456789abcdef")


@pytest.fixture
async def compliance_client(
    compliance_test_app,
    compliance_test_settings: Settings,
    mock_tenant_validation,  # noqa: ARG001 - fixture needed to patch tenant validation
    test_tenant_id,
):
    """Create an authenticated async HTTP client for compliance tests."""
    async with AsyncClient(
        transport=ASGITransport(app=compliance_test_app),
        base_url="http://test",
        headers={
            "Authorization": f"Bearer {compliance_test_settings.API_SECRET_KEY.get_secret_value()}",
            "X-Tenant-ID": str(test_tenant_id),
        },
    ) as client:
        yield client


def create_test_audit_event(
    tenant_id: UUID,
    event_type: AuditEventType = AuditEventType.SCREENING_INITIATED,
    severity: AuditSeverity = AuditSeverity.INFO,
    user_id: UUID | None = None,
    entity_id: UUID | None = None,
    created_at: datetime | None = None,
) -> AuditEvent:
    """Create a test audit event."""
    return AuditEvent(
        audit_id=uuid7(),
        event_type=event_type.value,
        severity=severity.value,
        tenant_id=tenant_id,
        user_id=user_id or uuid7(),
        correlation_id=uuid7(),
        entity_id=entity_id,
        event_data={"test": "data"},
        created_at=created_at or datetime.now(UTC),
    )


def add_test_audit_event(event: AuditEvent) -> None:
    """Add an audit event to the test storage."""
    from elile.api.routers.v1 import compliance

    compliance._audit_events.append(event)


def add_test_consent(consent: Consent) -> None:
    """Add a consent to the consent manager."""
    from elile.api.routers.v1 import compliance

    manager = compliance._get_consent_manager()
    manager.register_consent(consent)


def add_test_compliance_report(report) -> None:
    """Add a compliance report to the test storage."""
    from elile.api.routers.v1 import compliance

    compliance._compliance_reports[str(report.report_id)] = report


# =============================================================================
# Audit Log Endpoint Tests
# =============================================================================


class TestAuditLogEndpoint:
    """Tests for GET /v1/compliance/audit-log."""

    @pytest.mark.asyncio
    async def test_audit_log_empty(self, compliance_client: AsyncClient) -> None:
        """Test audit log with no events."""
        response = await compliance_client.get("/v1/compliance/audit-log")

        assert response.status_code == 200
        data = response.json()

        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_audit_log_with_events(
        self, compliance_client: AsyncClient, test_tenant_id: UUID
    ) -> None:
        """Test audit log with events."""
        for _ in range(5):
            add_test_audit_event(create_test_audit_event(test_tenant_id))

        response = await compliance_client.get("/v1/compliance/audit-log")

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 5
        assert data["total"] == 5

    @pytest.mark.asyncio
    async def test_audit_log_filter_by_event_type(
        self, compliance_client: AsyncClient, test_tenant_id: UUID
    ) -> None:
        """Test filtering audit log by event type."""
        add_test_audit_event(
            create_test_audit_event(test_tenant_id, AuditEventType.SCREENING_INITIATED)
        )
        add_test_audit_event(create_test_audit_event(test_tenant_id, AuditEventType.DATA_ACCESSED))
        add_test_audit_event(
            create_test_audit_event(test_tenant_id, AuditEventType.SCREENING_INITIATED)
        )

        response = await compliance_client.get(
            "/v1/compliance/audit-log",
            params={"event_type": "screening.initiated"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 2
        assert data["filters_applied"]["event_type"] == "screening.initiated"

    @pytest.mark.asyncio
    async def test_audit_log_filter_by_severity(
        self, compliance_client: AsyncClient, test_tenant_id: UUID
    ) -> None:
        """Test filtering audit log by severity."""
        add_test_audit_event(create_test_audit_event(test_tenant_id, severity=AuditSeverity.INFO))
        add_test_audit_event(create_test_audit_event(test_tenant_id, severity=AuditSeverity.ERROR))
        add_test_audit_event(create_test_audit_event(test_tenant_id, severity=AuditSeverity.ERROR))

        response = await compliance_client.get(
            "/v1/compliance/audit-log",
            params={"severity": "error"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 2
        assert data["filters_applied"]["severity"] == "error"

    @pytest.mark.asyncio
    async def test_audit_log_filter_by_date_range(
        self, compliance_client: AsyncClient, test_tenant_id: UUID
    ) -> None:
        """Test filtering audit log by date range."""
        now = datetime.now(UTC)
        yesterday = now - timedelta(days=1)
        last_week = now - timedelta(days=7)

        add_test_audit_event(create_test_audit_event(test_tenant_id, created_at=now))
        add_test_audit_event(create_test_audit_event(test_tenant_id, created_at=yesterday))
        add_test_audit_event(create_test_audit_event(test_tenant_id, created_at=last_week))

        response = await compliance_client.get(
            "/v1/compliance/audit-log",
            params={"start_date": yesterday.isoformat()},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_audit_log_pagination(
        self, compliance_client: AsyncClient, test_tenant_id: UUID
    ) -> None:
        """Test pagination of audit log."""
        for _ in range(15):
            add_test_audit_event(create_test_audit_event(test_tenant_id))

        # First page
        response = await compliance_client.get(
            "/v1/compliance/audit-log",
            params={"page": 1, "page_size": 10},
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 10
        assert data["total"] == 15
        assert data["has_more"] is True

        # Second page
        response = await compliance_client.get(
            "/v1/compliance/audit-log",
            params={"page": 2, "page_size": 10},
        )

        data = response.json()

        assert len(data["items"]) == 5
        assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_audit_log_unauthorized(self, compliance_test_app) -> None:
        """Test audit log without auth fails."""
        async with AsyncClient(
            transport=ASGITransport(app=compliance_test_app),
            base_url="http://test",
        ) as client:
            response = await client.get("/v1/compliance/audit-log")
            assert response.status_code == 401


# =============================================================================
# Consent Tracking Endpoint Tests
# =============================================================================


class TestConsentTrackingEndpoint:
    """Tests for GET /v1/compliance/consent-tracking."""

    @pytest.mark.asyncio
    async def test_consent_tracking_empty(self, compliance_client: AsyncClient) -> None:
        """Test consent tracking with no consents."""
        response = await compliance_client.get("/v1/compliance/consent-tracking")

        assert response.status_code == 200
        data = response.json()

        assert data["metrics"]["total_consents"] == 0
        assert data["metrics"]["active_consents"] == 0
        assert data["recent_consents"] == []
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_consent_tracking_with_consents(self, compliance_client: AsyncClient) -> None:
        """Test consent tracking with consents."""
        subject_id = uuid7()

        # Active consent
        consent1 = create_consent(
            subject_id=subject_id,
            scopes=[ConsentScope.BACKGROUND_CHECK, ConsentScope.CRIMINAL_RECORDS],
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
            locale=Locale.US,
        )
        add_test_consent(consent1)

        # Another active consent
        consent2 = create_consent(
            subject_id=uuid7(),
            scopes=[ConsentScope.CREDIT_CHECK],
            verification_method=ConsentVerificationMethod.HRIS_API,
            locale=Locale.EU,
        )
        add_test_consent(consent2)

        response = await compliance_client.get("/v1/compliance/consent-tracking")

        assert response.status_code == 200
        data = response.json()

        assert data["metrics"]["total_consents"] == 2
        assert data["metrics"]["active_consents"] == 2
        assert len(data["recent_consents"]) == 2

    @pytest.mark.asyncio
    async def test_consent_tracking_metrics_breakdown(self, compliance_client: AsyncClient) -> None:
        """Test consent tracking metrics breakdown."""
        # Add consents with different scopes and methods
        for _ in range(3):
            consent = create_consent(
                subject_id=uuid7(),
                scopes=[ConsentScope.BACKGROUND_CHECK],
                verification_method=ConsentVerificationMethod.E_SIGNATURE,
            )
            add_test_consent(consent)

        for _ in range(2):
            consent = create_consent(
                subject_id=uuid7(),
                scopes=[ConsentScope.CREDIT_CHECK],
                verification_method=ConsentVerificationMethod.HRIS_API,
            )
            add_test_consent(consent)

        response = await compliance_client.get("/v1/compliance/consent-tracking")

        assert response.status_code == 200
        data = response.json()

        metrics = data["metrics"]
        assert metrics["total_consents"] == 5
        assert "background_check" in metrics["by_scope"]
        assert "credit_check" in metrics["by_scope"]
        assert "e_signature" in metrics["by_verification_method"]
        assert "hris_api" in metrics["by_verification_method"]

    @pytest.mark.asyncio
    async def test_consent_tracking_expiring_soon(self, compliance_client: AsyncClient) -> None:
        """Test consent tracking expiring soon detection."""
        subject_id = uuid7()

        # Consent expiring in 15 days
        consent = create_consent(
            subject_id=subject_id,
            scopes=[ConsentScope.BACKGROUND_CHECK],
            expires_in_days=15,
        )
        add_test_consent(consent)

        response = await compliance_client.get("/v1/compliance/consent-tracking")

        assert response.status_code == 200
        data = response.json()

        assert data["metrics"]["pending_renewals"] == 1
        assert len(data["expiring_soon"]) == 1


# =============================================================================
# Data Erasure Endpoint Tests
# =============================================================================


class TestDataErasureEndpoint:
    """Tests for POST /v1/compliance/data-erasure."""

    @pytest.mark.asyncio
    async def test_data_erasure_request(self, compliance_client: AsyncClient) -> None:
        """Test creating a data erasure request."""
        subject_id = uuid7()

        response = await compliance_client.post(
            "/v1/compliance/data-erasure",
            json={
                "subject_id": str(subject_id),
                "reason": "Subject requested data deletion under GDPR Article 17",
                "requester_email": "subject@example.com",
                "include_audit_records": False,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["subject_id"] == str(subject_id)
        assert data["status"] == ErasureStatus.PENDING.value
        assert "erasure_id" in data
        assert "requested_at" in data
        assert "estimated_completion" in data
        assert len(data["data_categories_affected"]) > 0
        assert "audit_logs" in data["retention_exceptions"]
        assert data["confirmation_token"].startswith("ERS-")

    @pytest.mark.asyncio
    async def test_data_erasure_with_audit_records(self, compliance_client: AsyncClient) -> None:
        """Test erasure request including audit records."""
        subject_id = uuid7()

        response = await compliance_client.post(
            "/v1/compliance/data-erasure",
            json={
                "subject_id": str(subject_id),
                "reason": "Full data deletion requested by subject",
                "include_audit_records": True,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Audit trails should not be in exceptions when include_audit_records=True
        assert "audit_trails" not in data["retention_exceptions"]

    @pytest.mark.asyncio
    async def test_data_erasure_logs_audit_event(
        self,
        compliance_client: AsyncClient,
        test_tenant_id: UUID,  # noqa: ARG002 - fixture needed for consistency
    ) -> None:
        """Test that erasure request creates an audit event."""
        from elile.api.routers.v1 import compliance

        subject_id = uuid7()

        await compliance_client.post(
            "/v1/compliance/data-erasure",
            json={
                "subject_id": str(subject_id),
                "reason": "GDPR erasure request for compliance testing",
            },
        )

        # Check audit event was created
        events = compliance._get_audit_events()
        erasure_events = [e for e in events if e.event_type == AuditEventType.DATA_ERASED.value]

        assert len(erasure_events) == 1
        assert erasure_events[0].entity_id == subject_id

    @pytest.mark.asyncio
    async def test_data_erasure_invalid_reason(self, compliance_client: AsyncClient) -> None:
        """Test erasure request with too short reason."""
        subject_id = uuid7()

        response = await compliance_client.post(
            "/v1/compliance/data-erasure",
            json={
                "subject_id": str(subject_id),
                "reason": "short",  # Too short (min 10 chars)
            },
        )

        assert response.status_code == 422  # Validation error


# =============================================================================
# Compliance Reports Endpoint Tests
# =============================================================================


class TestComplianceReportsEndpoint:
    """Tests for GET /v1/compliance/reports."""

    @pytest.mark.asyncio
    async def test_reports_list_empty(self, compliance_client: AsyncClient) -> None:
        """Test listing compliance reports with no data."""
        response = await compliance_client.get("/v1/compliance/reports")

        assert response.status_code == 200
        data = response.json()

        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_reports_list_with_data(self, compliance_client: AsyncClient) -> None:
        """Test listing compliance reports with data."""
        from elile.api.schemas.compliance import ComplianceReportSummary

        for _ in range(3):
            report = ComplianceReportSummary(
                report_id=uuid7(),
                report_type="screening_audit",
                screening_id=uuid7(),
                locale=Locale.US,
                generated_at=datetime.now(UTC),
                compliance_status=ComplianceStatus.COMPLIANT,
                rules_evaluated=10,
                violations_found=0,
            )
            add_test_compliance_report(report)

        response = await compliance_client.get("/v1/compliance/reports")

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 3
        assert data["total"] == 3

    @pytest.mark.asyncio
    async def test_reports_filter_by_status(self, compliance_client: AsyncClient) -> None:
        """Test filtering reports by compliance status."""
        from elile.api.schemas.compliance import ComplianceReportSummary

        # Add compliant
        report1 = ComplianceReportSummary(
            report_id=uuid7(),
            report_type="screening_audit",
            locale=Locale.US,
            generated_at=datetime.now(UTC),
            compliance_status=ComplianceStatus.COMPLIANT,
        )
        add_test_compliance_report(report1)

        # Add non-compliant
        report2 = ComplianceReportSummary(
            report_id=uuid7(),
            report_type="screening_audit",
            locale=Locale.US,
            generated_at=datetime.now(UTC),
            compliance_status=ComplianceStatus.NON_COMPLIANT,
            violations_found=2,
        )
        add_test_compliance_report(report2)

        response = await compliance_client.get(
            "/v1/compliance/reports",
            params={"compliance_status": "non_compliant"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert data["items"][0]["compliance_status"] == "non_compliant"

    @pytest.mark.asyncio
    async def test_reports_filter_by_locale(self, compliance_client: AsyncClient) -> None:
        """Test filtering reports by locale."""
        from elile.api.schemas.compliance import ComplianceReportSummary

        # Add US report
        report1 = ComplianceReportSummary(
            report_id=uuid7(),
            report_type="screening_audit",
            locale=Locale.US,
            generated_at=datetime.now(UTC),
            compliance_status=ComplianceStatus.COMPLIANT,
        )
        add_test_compliance_report(report1)

        # Add EU report
        report2 = ComplianceReportSummary(
            report_id=uuid7(),
            report_type="screening_audit",
            locale=Locale.EU,
            generated_at=datetime.now(UTC),
            compliance_status=ComplianceStatus.COMPLIANT,
        )
        add_test_compliance_report(report2)

        response = await compliance_client.get(
            "/v1/compliance/reports",
            params={"locale": "EU"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert data["items"][0]["locale"] == "EU"

    @pytest.mark.asyncio
    async def test_reports_pagination(self, compliance_client: AsyncClient) -> None:
        """Test pagination of compliance reports."""
        from elile.api.schemas.compliance import ComplianceReportSummary

        for _ in range(25):
            report = ComplianceReportSummary(
                report_id=uuid7(),
                report_type="screening_audit",
                locale=Locale.US,
                generated_at=datetime.now(UTC),
                compliance_status=ComplianceStatus.COMPLIANT,
            )
            add_test_compliance_report(report)

        response = await compliance_client.get(
            "/v1/compliance/reports",
            params={"page": 1, "page_size": 10},
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 10
        assert data["total"] == 25
        assert data["has_more"] is True


# =============================================================================
# Compliance Metrics Endpoint Tests
# =============================================================================


class TestComplianceMetricsEndpoint:
    """Tests for GET /v1/compliance/metrics."""

    @pytest.mark.asyncio
    async def test_metrics_empty(self, compliance_client: AsyncClient) -> None:
        """Test compliance metrics with no data."""
        response = await compliance_client.get("/v1/compliance/metrics")

        assert response.status_code == 200
        data = response.json()

        metrics = data["metrics"]
        assert metrics["total_screenings"] == 0
        assert metrics["compliance_rate"] == 100.0
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_metrics_with_reports(self, compliance_client: AsyncClient) -> None:
        """Test compliance metrics with reports."""
        from elile.api.schemas.compliance import ComplianceReportSummary

        # Add compliant reports
        for _ in range(8):
            report = ComplianceReportSummary(
                report_id=uuid7(),
                report_type="screening_audit",
                locale=Locale.US,
                generated_at=datetime.now(UTC),
                compliance_status=ComplianceStatus.COMPLIANT,
            )
            add_test_compliance_report(report)

        # Add non-compliant reports
        for _ in range(2):
            report = ComplianceReportSummary(
                report_id=uuid7(),
                report_type="screening_audit",
                locale=Locale.US,
                generated_at=datetime.now(UTC),
                compliance_status=ComplianceStatus.NON_COMPLIANT,
                violations_found=1,
            )
            add_test_compliance_report(report)

        response = await compliance_client.get("/v1/compliance/metrics")

        assert response.status_code == 200
        data = response.json()

        metrics = data["metrics"]
        assert metrics["total_screenings"] == 10
        assert metrics["compliant_screenings"] == 8
        assert metrics["non_compliant_screenings"] == 2
        assert metrics["compliance_rate"] == 80.0

    @pytest.mark.asyncio
    async def test_metrics_with_consents(self, compliance_client: AsyncClient) -> None:
        """Test metrics includes active consent count."""
        for _ in range(5):
            consent = create_consent(
                subject_id=uuid7(),
                scopes=[ConsentScope.BACKGROUND_CHECK],
            )
            add_test_consent(consent)

        response = await compliance_client.get("/v1/compliance/metrics")

        assert response.status_code == 200
        data = response.json()

        assert data["metrics"]["active_consents"] == 5

    @pytest.mark.asyncio
    async def test_metrics_locale_breakdown(self, compliance_client: AsyncClient) -> None:
        """Test metrics locale breakdown."""
        from elile.api.schemas.compliance import ComplianceReportSummary

        # US reports
        for _ in range(5):
            report = ComplianceReportSummary(
                report_id=uuid7(),
                report_type="screening_audit",
                locale=Locale.US,
                generated_at=datetime.now(UTC),
                compliance_status=ComplianceStatus.COMPLIANT,
            )
            add_test_compliance_report(report)

        # EU reports
        for _ in range(3):
            report = ComplianceReportSummary(
                report_id=uuid7(),
                report_type="screening_audit",
                locale=Locale.EU,
                generated_at=datetime.now(UTC),
                compliance_status=ComplianceStatus.COMPLIANT,
            )
            add_test_compliance_report(report)

        response = await compliance_client.get("/v1/compliance/metrics")

        assert response.status_code == 200
        data = response.json()

        by_locale = data["metrics"]["by_locale"]
        assert by_locale["US"] == 5
        assert by_locale["EU"] == 3


# =============================================================================
# Tenant Isolation Tests
# =============================================================================


class TestTenantIsolation:
    """Tests for tenant data isolation."""

    @pytest.mark.asyncio
    async def test_audit_log_tenant_isolation(
        self,
        compliance_test_app,
        compliance_test_settings,
        mock_tenant_validation,  # noqa: ARG002 - fixture needed to patch tenant validation
    ) -> None:
        """Test that audit log only shows tenant's own events."""
        from uuid import uuid4

        tenant1_id = uuid4()
        tenant2_id = uuid4()

        # Add events for both tenants
        add_test_audit_event(create_test_audit_event(tenant1_id))
        add_test_audit_event(create_test_audit_event(tenant1_id))
        add_test_audit_event(create_test_audit_event(tenant2_id))

        # Request as tenant 1
        async with AsyncClient(
            transport=ASGITransport(app=compliance_test_app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {compliance_test_settings.API_SECRET_KEY.get_secret_value()}",
                "X-Tenant-ID": str(tenant1_id),
            },
        ) as client:
            response = await client.get("/v1/compliance/audit-log")

        assert response.status_code == 200
        assert response.json()["total"] == 2

    @pytest.mark.asyncio
    async def test_erasure_tenant_isolation(
        self,
        compliance_test_app,
        compliance_test_settings,
        mock_tenant_validation,  # noqa: ARG002 - fixture needed to patch tenant validation
    ) -> None:
        """Test that erasure requests are logged with correct tenant."""
        from uuid import uuid4

        from elile.api.routers.v1 import compliance

        tenant1_id = uuid4()
        subject_id = uuid4()

        async with AsyncClient(
            transport=ASGITransport(app=compliance_test_app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {compliance_test_settings.API_SECRET_KEY.get_secret_value()}",
                "X-Tenant-ID": str(tenant1_id),
            },
        ) as client:
            await client.post(
                "/v1/compliance/data-erasure",
                json={
                    "subject_id": str(subject_id),
                    "reason": "Test erasure for tenant isolation verification",
                },
            )

        # Verify audit event has correct tenant
        events = compliance._get_audit_events()
        assert len(events) == 1
        assert events[0].tenant_id == tenant1_id
