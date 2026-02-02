"""Unit tests for GDPR Erasure Service."""

from datetime import datetime, timedelta
from uuid import uuid7

import pytest

from elile.compliance.erasure.anonymizer import DataAnonymizer
from elile.compliance.erasure.service import (
    DATA_TYPE_EXEMPTIONS,
    DEFAULT_DEADLINE_DAYS,
    GDPR_DEADLINE_DAYS,
    ErasureService,
    ErasureServiceConfig,
    get_erasure_service,
    initialize_erasure_service,
)
from elile.compliance.erasure.types import (
    ErasureBlockedException,
    ErasureExemption,
    ErasureStatus,
    ErasureType,
    ErasureVerificationError,
    LegalHoldException,
)
from elile.compliance.retention.manager import RetentionManager
from elile.compliance.retention.types import DataType, RetentionStatus
from elile.compliance.types import Locale


@pytest.fixture
def retention_manager():
    """Create a fresh retention manager for testing."""
    return RetentionManager()


@pytest.fixture
def anonymizer():
    """Create an anonymizer for testing."""
    return DataAnonymizer()


@pytest.fixture
def erasure_service(retention_manager, anonymizer):
    """Create an erasure service for testing."""
    return ErasureService(
        config=ErasureServiceConfig(
            require_identity_verification=True,
            auto_process_after_verification=False,
        ),
        retention_manager=retention_manager,
        anonymizer=anonymizer,
    )


class TestErasureServiceConfig:
    """Tests for ErasureServiceConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ErasureServiceConfig()
        assert config.require_identity_verification is True
        assert config.verification_timeout_hours == 72
        assert config.auto_process_after_verification is False
        assert config.max_processing_attempts == 3
        assert config.block_on_any_legal_hold is True
        assert config.anonymize_before_delete is True
        assert config.generate_confirmation_report is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = ErasureServiceConfig(
            require_identity_verification=False,
            verification_timeout_hours=24,
            auto_process_after_verification=True,
        )
        assert config.require_identity_verification is False
        assert config.verification_timeout_hours == 24
        assert config.auto_process_after_verification is True


class TestSubmitErasureRequest:
    """Tests for submitting erasure requests."""

    @pytest.mark.asyncio
    async def test_submit_basic_request(self, erasure_service):
        """Test submitting a basic erasure request."""
        subject_id = uuid7()
        tenant_id = uuid7()
        operation = await erasure_service.submit_erasure_request(
            subject_id=subject_id,
            tenant_id=tenant_id,
            locale=Locale.EU,
        )
        assert operation.subject_id == subject_id
        assert operation.tenant_id == tenant_id
        assert operation.locale == Locale.EU
        assert operation.erasure_type == ErasureType.FULL_ERASURE
        assert operation.status == ErasureStatus.PENDING

    @pytest.mark.asyncio
    async def test_submit_request_with_data_types(self, erasure_service):
        """Test submitting request with specific data types."""
        operation = await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.EU,
            data_types=[DataType.ENTITY_PROFILE, DataType.SCREENING_RAW_DATA],
        )
        assert len(operation.requested_data_types) == 2
        assert DataType.ENTITY_PROFILE in operation.requested_data_types

    @pytest.mark.asyncio
    async def test_submit_request_with_reason(self, erasure_service):
        """Test submitting request with reason."""
        operation = await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.EU,
            reason="GDPR Article 17 request",
        )
        assert operation.reason == "GDPR Article 17 request"

    @pytest.mark.asyncio
    async def test_submit_request_deadline_eu(self, erasure_service):
        """Test EU request has 30-day deadline."""
        operation = await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.EU,
        )
        expected_deadline = operation.requested_at + timedelta(days=30)
        assert operation.deadline is not None
        assert abs((operation.deadline - expected_deadline).total_seconds()) < 60

    @pytest.mark.asyncio
    async def test_submit_request_deadline_brazil(self, erasure_service):
        """Test Brazil request has 15-day deadline (LGPD)."""
        operation = await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.BR,
        )
        expected_deadline = operation.requested_at + timedelta(days=15)
        assert operation.deadline is not None
        assert abs((operation.deadline - expected_deadline).total_seconds()) < 60

    @pytest.mark.asyncio
    async def test_submit_request_creates_audit_entry(self, erasure_service):
        """Test that submitting creates an audit entry."""
        operation = await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.EU,
        )
        assert len(operation.audit_log) >= 1
        assert operation.audit_log[0]["action"] == "request_submitted"

    @pytest.mark.asyncio
    async def test_submit_anonymize_request(self, erasure_service):
        """Test submitting an anonymize request."""
        operation = await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.EU,
            erasure_type=ErasureType.ANONYMIZE,
        )
        assert operation.erasure_type == ErasureType.ANONYMIZE


class TestVerifyIdentity:
    """Tests for identity verification."""

    @pytest.mark.asyncio
    async def test_verify_identity_success(self, erasure_service):
        """Test successful identity verification."""
        operation = await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.EU,
        )
        verified = await erasure_service.verify_identity(
            operation.operation_id,
            verification_method="email_confirmation",
        )
        assert verified.status == ErasureStatus.VERIFIED
        assert verified.verification_method == "email_confirmation"
        assert verified.verified_at is not None

    @pytest.mark.asyncio
    async def test_verify_identity_creates_audit_entry(self, erasure_service):
        """Test that verification creates an audit entry."""
        operation = await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.EU,
        )
        verified = await erasure_service.verify_identity(
            operation.operation_id,
            verification_method="id_document",
            verified_by="admin@example.com",
        )
        identity_entry = next(
            (e for e in verified.audit_log if e["action"] == "identity_verified"),
            None,
        )
        assert identity_entry is not None
        assert identity_entry["details"]["method"] == "id_document"
        assert identity_entry["details"]["verified_by"] == "admin@example.com"

    @pytest.mark.asyncio
    async def test_verify_non_pending_request_fails(self, erasure_service):
        """Test that verifying a non-pending request fails."""
        operation = await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.EU,
        )
        # Verify once
        await erasure_service.verify_identity(
            operation.operation_id,
            verification_method="email",
        )
        # Try to verify again
        with pytest.raises(ErasureVerificationError) as exc_info:
            await erasure_service.verify_identity(
                operation.operation_id,
                verification_method="email",
            )
        assert "not pending" in str(exc_info.value).lower()


class TestProcessErasureRequest:
    """Tests for processing erasure requests."""

    @pytest.mark.asyncio
    async def test_process_verified_request(self, erasure_service, retention_manager):
        """Test processing a verified request."""
        tenant_id = uuid7()
        # Track some data
        data_id = uuid7()
        retention_manager.track_data(
            data_id=data_id,
            data_type=DataType.ENTITY_PROFILE,
            tenant_id=tenant_id,
            locale=Locale.EU,
        )
        # Submit and verify
        operation = await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=tenant_id,
            locale=Locale.EU,
        )
        await erasure_service.verify_identity(
            operation.operation_id,
            verification_method="email",
        )
        # Process
        result = await erasure_service.process_erasure_request(operation.operation_id)
        assert result.status in (ErasureStatus.COMPLETED, ErasureStatus.PARTIALLY_COMPLETED)
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_process_unverified_request_fails(self, erasure_service):
        """Test that processing unverified request fails."""
        operation = await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.EU,
        )
        with pytest.raises(ErasureVerificationError):
            await erasure_service.process_erasure_request(operation.operation_id)

    @pytest.mark.asyncio
    async def test_process_with_force_skips_verification(self, erasure_service):
        """Test force processing skips verification check."""
        tenant_id = uuid7()
        operation = await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=tenant_id,
            locale=Locale.EU,
        )
        # Process with force=True
        result = await erasure_service.process_erasure_request(
            operation.operation_id,
            force=True,
        )
        assert result.status in (ErasureStatus.COMPLETED, ErasureStatus.PARTIALLY_COMPLETED)

    @pytest.mark.asyncio
    async def test_process_blocked_by_legal_hold(self, erasure_service, retention_manager):
        """Test processing blocked by legal hold."""
        tenant_id = uuid7()
        data_id = uuid7()
        # Track data with legal hold
        record = retention_manager.track_data(
            data_id=data_id,
            data_type=DataType.ENTITY_PROFILE,
            tenant_id=tenant_id,
        )
        retention_manager.place_legal_hold(data_id, "Litigation hold")
        # Submit and verify
        operation = await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=tenant_id,
            locale=Locale.EU,
        )
        await erasure_service.verify_identity(
            operation.operation_id,
            verification_method="email",
        )
        # Process should raise exception
        with pytest.raises(LegalHoldException) as exc_info:
            await erasure_service.process_erasure_request(operation.operation_id)
        assert "Litigation hold" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_audit_logs_are_exempt(self, erasure_service, retention_manager):
        """Test that audit logs are exempt from erasure."""
        tenant_id = uuid7()
        data_id = uuid7()
        retention_manager.track_data(
            data_id=data_id,
            data_type=DataType.AUDIT_LOG,
            tenant_id=tenant_id,
        )
        operation = await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=tenant_id,
            locale=Locale.EU,
        )
        await erasure_service.verify_identity(
            operation.operation_id,
            verification_method="email",
        )
        result = await erasure_service.process_erasure_request(operation.operation_id)
        assert result.items_retained_count >= 1
        # Check retained items include audit log
        retained_types = [item["data_type"] for item in result.retained_items]
        assert DataType.AUDIT_LOG.value in retained_types

    @pytest.mark.asyncio
    async def test_consent_records_are_exempt(self, erasure_service, retention_manager):
        """Test that consent records are exempt from erasure."""
        tenant_id = uuid7()
        data_id = uuid7()
        retention_manager.track_data(
            data_id=data_id,
            data_type=DataType.CONSENT_RECORD,
            tenant_id=tenant_id,
        )
        operation = await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=tenant_id,
            locale=Locale.EU,
        )
        await erasure_service.verify_identity(
            operation.operation_id,
            verification_method="email",
        )
        result = await erasure_service.process_erasure_request(operation.operation_id)
        retained_types = [item["data_type"] for item in result.retained_items]
        assert DataType.CONSENT_RECORD.value in retained_types

    @pytest.mark.asyncio
    async def test_processing_creates_audit_entries(self, erasure_service, retention_manager):
        """Test that processing creates audit entries."""
        tenant_id = uuid7()
        operation = await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=tenant_id,
            locale=Locale.EU,
        )
        await erasure_service.verify_identity(
            operation.operation_id,
            verification_method="email",
        )
        result = await erasure_service.process_erasure_request(operation.operation_id)
        actions = [e["action"] for e in result.audit_log]
        assert "processing_started" in actions
        assert "processing_completed" in actions


class TestConfirmationReport:
    """Tests for confirmation report generation."""

    @pytest.mark.asyncio
    async def test_generate_report_for_completed(self, erasure_service, retention_manager):
        """Test generating report for completed operation."""
        tenant_id = uuid7()
        data_id = uuid7()
        retention_manager.track_data(
            data_id=data_id,
            data_type=DataType.ENTITY_PROFILE,
            tenant_id=tenant_id,
        )
        operation = await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=tenant_id,
            locale=Locale.EU,
        )
        await erasure_service.verify_identity(
            operation.operation_id,
            verification_method="email",
        )
        await erasure_service.process_erasure_request(operation.operation_id)
        report = await erasure_service.generate_confirmation_report(operation.operation_id)
        assert report.operation_id == operation.operation_id
        assert report.status in (ErasureStatus.COMPLETED, ErasureStatus.PARTIALLY_COMPLETED)
        assert report.gdpr_compliance_statement != ""

    @pytest.mark.asyncio
    async def test_report_has_verification_hash(self, erasure_service, retention_manager):
        """Test that report has verification hash."""
        tenant_id = uuid7()
        operation = await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=tenant_id,
            locale=Locale.EU,
        )
        await erasure_service.verify_identity(
            operation.operation_id,
            verification_method="email",
        )
        await erasure_service.process_erasure_request(operation.operation_id)
        report = await erasure_service.generate_confirmation_report(operation.operation_id)
        assert report.verification_hash is not None
        assert len(report.verification_hash) == 64  # SHA-256

    @pytest.mark.asyncio
    async def test_report_for_incomplete_fails(self, erasure_service):
        """Test that generating report for incomplete operation fails."""
        operation = await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.EU,
        )
        with pytest.raises(ValueError) as exc_info:
            await erasure_service.generate_confirmation_report(operation.operation_id)
        assert "not complete" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_report_includes_retained_explanation(self, erasure_service, retention_manager):
        """Test that report includes explanation for retained data."""
        tenant_id = uuid7()
        data_id = uuid7()
        retention_manager.track_data(
            data_id=data_id,
            data_type=DataType.AUDIT_LOG,
            tenant_id=tenant_id,
        )
        operation = await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=tenant_id,
            locale=Locale.EU,
        )
        await erasure_service.verify_identity(
            operation.operation_id,
            verification_method="email",
        )
        await erasure_service.process_erasure_request(operation.operation_id)
        report = await erasure_service.generate_confirmation_report(operation.operation_id)
        assert len(report.retained_data_explanation) >= 1
        assert report.legal_basis_for_retention


class TestOperationRetrieval:
    """Tests for operation retrieval methods."""

    @pytest.mark.asyncio
    async def test_get_operation(self, erasure_service):
        """Test getting an operation by ID."""
        operation = await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.EU,
        )
        retrieved = erasure_service.get_operation(operation.operation_id)
        assert retrieved is not None
        assert retrieved.operation_id == operation.operation_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_operation(self, erasure_service):
        """Test getting a nonexistent operation."""
        retrieved = erasure_service.get_operation(uuid7())
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_operations_by_subject(self, erasure_service):
        """Test getting operations for a subject."""
        subject_id = uuid7()
        tenant_id = uuid7()
        await erasure_service.submit_erasure_request(
            subject_id=subject_id,
            tenant_id=tenant_id,
            locale=Locale.EU,
        )
        await erasure_service.submit_erasure_request(
            subject_id=subject_id,
            tenant_id=tenant_id,
            locale=Locale.EU,
        )
        operations = erasure_service.get_operations_by_subject(subject_id)
        assert len(operations) == 2

    @pytest.mark.asyncio
    async def test_get_operations_by_tenant(self, erasure_service):
        """Test getting operations for a tenant."""
        tenant_id = uuid7()
        await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=tenant_id,
            locale=Locale.EU,
        )
        operations = erasure_service.get_operations_by_tenant(tenant_id)
        assert len(operations) == 1

    @pytest.mark.asyncio
    async def test_get_pending_operations(self, erasure_service):
        """Test getting pending operations."""
        await erasure_service.submit_erasure_request(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.EU,
        )
        pending = erasure_service.get_pending_operations()
        assert len(pending) >= 1


class TestModuleFunctions:
    """Tests for module-level functions."""

    def test_get_erasure_service_singleton(self):
        """Test that get_erasure_service returns singleton."""
        # Reset global
        import elile.compliance.erasure.service as service_module
        service_module._service = None

        service1 = get_erasure_service()
        service2 = get_erasure_service()
        assert service1 is service2

    def test_initialize_erasure_service(self):
        """Test initializing the global service."""
        config = ErasureServiceConfig(require_identity_verification=False)
        service = initialize_erasure_service(config=config)
        assert service.config.require_identity_verification is False


class TestConstants:
    """Tests for module constants."""

    def test_gdpr_deadline_days(self):
        """Test GDPR deadline days mapping."""
        assert GDPR_DEADLINE_DAYS[Locale.EU] == 30
        assert GDPR_DEADLINE_DAYS[Locale.UK] == 30
        assert GDPR_DEADLINE_DAYS[Locale.BR] == 15

    def test_default_deadline_days(self):
        """Test default deadline days."""
        assert DEFAULT_DEADLINE_DAYS == 30

    def test_data_type_exemptions(self):
        """Test data type exemptions mapping."""
        assert DataType.AUDIT_LOG in DATA_TYPE_EXEMPTIONS
        assert DataType.CONSENT_RECORD in DATA_TYPE_EXEMPTIONS
        assert DataType.ADVERSE_ACTION in DATA_TYPE_EXEMPTIONS
        assert DataType.SCREENING_RESULT in DATA_TYPE_EXEMPTIONS
