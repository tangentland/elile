"""Unit tests for GDPR erasure type definitions."""

from datetime import datetime, timedelta
from uuid import uuid7

import pytest

from elile.compliance.erasure.types import (
    AnonymizationMethod,
    AnonymizationRule,
    ErasedItem,
    ErasureBlockedException,
    ErasureConfirmationReport,
    ErasureExemption,
    ErasureOperation,
    ErasureStatus,
    ErasureType,
    ErasureVerificationError,
    LegalHoldException,
    RetainedItem,
)
from elile.compliance.retention.types import DataType
from elile.compliance.types import Locale


class TestErasureType:
    """Tests for ErasureType enum."""

    def test_erasure_type_values(self):
        """Test erasure type enum values."""
        assert ErasureType.FULL_ERASURE.value == "full_erasure"
        assert ErasureType.ANONYMIZE.value == "anonymize"
        assert ErasureType.EXPORT.value == "export"
        assert ErasureType.SELECTIVE.value == "selective"

    def test_erasure_type_is_string_enum(self):
        """Test that ErasureType is a string enum."""
        assert isinstance(ErasureType.FULL_ERASURE, str)
        assert ErasureType.FULL_ERASURE == "full_erasure"


class TestErasureStatus:
    """Tests for ErasureStatus enum."""

    def test_status_values(self):
        """Test all status values exist."""
        assert ErasureStatus.PENDING.value == "pending"
        assert ErasureStatus.VERIFIED.value == "verified"
        assert ErasureStatus.PROCESSING.value == "processing"
        assert ErasureStatus.COMPLETED.value == "completed"
        assert ErasureStatus.PARTIALLY_COMPLETED.value == "partially_completed"
        assert ErasureStatus.REJECTED.value == "rejected"
        assert ErasureStatus.BLOCKED.value == "blocked"


class TestErasureExemption:
    """Tests for ErasureExemption enum."""

    def test_exemption_values(self):
        """Test all exemption values exist."""
        assert ErasureExemption.LEGAL_HOLD.value == "legal_hold"
        assert ErasureExemption.REGULATORY_REQUIREMENT.value == "regulatory_requirement"
        assert ErasureExemption.CONTRACT_OBLIGATION.value == "contract_obligation"
        assert ErasureExemption.LEGITIMATE_INTEREST.value == "legitimate_interest"
        assert ErasureExemption.PUBLIC_INTEREST.value == "public_interest"
        assert ErasureExemption.LEGAL_CLAIMS.value == "legal_claims"
        assert ErasureExemption.FREEDOM_OF_EXPRESSION.value == "freedom_of_expression"


class TestAnonymizationMethod:
    """Tests for AnonymizationMethod enum."""

    def test_method_values(self):
        """Test all anonymization methods exist."""
        assert AnonymizationMethod.PSEUDONYMIZATION.value == "pseudonymization"
        assert AnonymizationMethod.MASKING.value == "masking"
        assert AnonymizationMethod.GENERALIZATION.value == "generalization"
        assert AnonymizationMethod.TOKENIZATION.value == "tokenization"
        assert AnonymizationMethod.REDACTION.value == "redaction"
        assert AnonymizationMethod.HASHING.value == "hashing"


class TestAnonymizationRule:
    """Tests for AnonymizationRule dataclass."""

    def test_create_basic_rule(self):
        """Test creating a basic anonymization rule."""
        rule = AnonymizationRule(
            field_name="ssn",
            method=AnonymizationMethod.MASKING,
        )
        assert rule.field_name == "ssn"
        assert rule.method == AnonymizationMethod.MASKING
        assert rule.preserve_format is False
        assert rule.preserve_length is False
        assert rule.custom_value is None

    def test_create_rule_with_options(self):
        """Test creating a rule with all options."""
        rule = AnonymizationRule(
            field_name="name",
            method=AnonymizationMethod.REDACTION,
            preserve_format=True,
            preserve_length=True,
            custom_value="[REMOVED]",
        )
        assert rule.preserve_format is True
        assert rule.preserve_length is True
        assert rule.custom_value == "[REMOVED]"


class TestErasedItem:
    """Tests for ErasedItem dataclass."""

    def test_create_erased_item(self):
        """Test creating an erased item record."""
        data_id = uuid7()
        item = ErasedItem(
            data_id=data_id,
            data_type=DataType.ENTITY_PROFILE,
            action_taken="deleted",
        )
        assert item.data_id == data_id
        assert item.data_type == DataType.ENTITY_PROFILE
        assert item.action_taken == "deleted"
        assert isinstance(item.timestamp, datetime)
        assert item.original_hash is None

    def test_erased_item_with_hash(self):
        """Test erased item with original hash."""
        item = ErasedItem(
            data_id=uuid7(),
            data_type=DataType.SCREENING_RAW_DATA,
            action_taken="anonymized",
            original_hash="sha256:abc123",
        )
        assert item.original_hash == "sha256:abc123"


class TestRetainedItem:
    """Tests for RetainedItem dataclass."""

    def test_create_retained_item(self):
        """Test creating a retained item record."""
        data_id = uuid7()
        item = RetainedItem(
            data_id=data_id,
            data_type=DataType.AUDIT_LOG,
            exemption=ErasureExemption.REGULATORY_REQUIREMENT,
            exemption_details="FCRA 7-year retention",
        )
        assert item.data_id == data_id
        assert item.data_type == DataType.AUDIT_LOG
        assert item.exemption == ErasureExemption.REGULATORY_REQUIREMENT
        assert item.exemption_details == "FCRA 7-year retention"

    def test_retained_item_with_retention_date(self):
        """Test retained item with retention until date."""
        retention_until = datetime.utcnow() + timedelta(days=365 * 7)
        item = RetainedItem(
            data_id=uuid7(),
            data_type=DataType.CONSENT_RECORD,
            exemption=ErasureExemption.REGULATORY_REQUIREMENT,
            legal_basis="GDPR Art. 7",
            retention_until=retention_until,
        )
        assert item.legal_basis == "GDPR Art. 7"
        assert item.retention_until == retention_until


class TestErasureOperation:
    """Tests for ErasureOperation model."""

    def test_create_operation(self):
        """Test creating an erasure operation."""
        subject_id = uuid7()
        tenant_id = uuid7()
        operation = ErasureOperation(
            subject_id=subject_id,
            tenant_id=tenant_id,
            locale=Locale.EU,
            erasure_type=ErasureType.FULL_ERASURE,
        )
        assert operation.subject_id == subject_id
        assert operation.tenant_id == tenant_id
        assert operation.locale == Locale.EU
        assert operation.erasure_type == ErasureType.FULL_ERASURE
        assert operation.status == ErasureStatus.PENDING
        assert isinstance(operation.operation_id, type(uuid7()))

    def test_operation_with_data_types(self):
        """Test operation with specific data types."""
        operation = ErasureOperation(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.UK,
            erasure_type=ErasureType.SELECTIVE,
            requested_data_types=[DataType.ENTITY_PROFILE, DataType.SCREENING_RAW_DATA],
        )
        assert len(operation.requested_data_types) == 2
        assert DataType.ENTITY_PROFILE in operation.requested_data_types

    def test_add_audit_entry(self):
        """Test adding audit entries."""
        operation = ErasureOperation(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.EU,
            erasure_type=ErasureType.FULL_ERASURE,
        )
        operation.add_audit_entry("request_submitted", {"source": "api"})
        assert len(operation.audit_log) == 1
        assert operation.audit_log[0]["action"] == "request_submitted"
        assert operation.audit_log[0]["details"]["source"] == "api"
        assert "timestamp" in operation.audit_log[0]

    def test_operation_counts(self):
        """Test erased and retained count properties."""
        operation = ErasureOperation(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.EU,
            erasure_type=ErasureType.FULL_ERASURE,
        )
        operation.erased_items.append({"data_id": str(uuid7())})
        operation.erased_items.append({"data_id": str(uuid7())})
        operation.retained_items.append({"data_id": str(uuid7())})
        assert operation.items_erased_count == 2
        assert operation.items_retained_count == 1

    def test_is_complete_property(self):
        """Test is_complete property for different statuses."""
        operation = ErasureOperation(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.EU,
            erasure_type=ErasureType.FULL_ERASURE,
        )
        assert operation.is_complete is False

        operation.status = ErasureStatus.COMPLETED
        assert operation.is_complete is True

        operation.status = ErasureStatus.PARTIALLY_COMPLETED
        assert operation.is_complete is True

        operation.status = ErasureStatus.BLOCKED
        assert operation.is_complete is True

        operation.status = ErasureStatus.PROCESSING
        assert operation.is_complete is False


class TestErasureConfirmationReport:
    """Tests for ErasureConfirmationReport model."""

    def test_create_report(self):
        """Test creating a confirmation report."""
        operation_id = uuid7()
        subject_id = uuid7()
        tenant_id = uuid7()
        report = ErasureConfirmationReport(
            operation_id=operation_id,
            subject_id=subject_id,
            tenant_id=tenant_id,
            locale=Locale.EU,
            request_date=datetime.utcnow(),
            completion_date=datetime.utcnow(),
            status=ErasureStatus.COMPLETED,
            is_fully_completed=True,
            items_erased=5,
            items_retained=0,
        )
        assert report.operation_id == operation_id
        assert report.is_fully_completed is True
        assert report.items_erased == 5
        assert report.total_items_processed == 0  # Need to set explicitly

    def test_report_with_categories(self):
        """Test report with data categories."""
        report = ErasureConfirmationReport(
            operation_id=uuid7(),
            subject_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.EU,
            request_date=datetime.utcnow(),
            completion_date=datetime.utcnow(),
            status=ErasureStatus.PARTIALLY_COMPLETED,
            data_categories_requested=["entity_profile", "screening_raw_data"],
            data_categories_erased=["entity_profile"],
            data_categories_retained=["screening_raw_data"],
        )
        assert len(report.data_categories_requested) == 2
        assert len(report.data_categories_erased) == 1
        assert len(report.data_categories_retained) == 1


class TestExceptions:
    """Tests for erasure exceptions."""

    def test_legal_hold_exception(self):
        """Test LegalHoldException creation."""
        subject_id = uuid7()
        hold_placed = datetime.utcnow()
        exc = LegalHoldException(
            subject_id=subject_id,
            hold_reason="Litigation hold - Case #12345",
            hold_placed_at=hold_placed,
        )
        assert exc.subject_id == subject_id
        assert exc.hold_reason == "Litigation hold - Case #12345"
        assert exc.hold_placed_at == hold_placed
        assert "legal hold" in str(exc).lower()

    def test_erasure_blocked_exception(self):
        """Test ErasureBlockedException creation."""
        subject_id = uuid7()
        exc = ErasureBlockedException(
            subject_id=subject_id,
            exemption=ErasureExemption.REGULATORY_REQUIREMENT,
            reason="FCRA requires 7-year retention",
        )
        assert exc.subject_id == subject_id
        assert exc.exemption == ErasureExemption.REGULATORY_REQUIREMENT
        assert exc.reason == "FCRA requires 7-year retention"
        assert "blocked" in str(exc).lower()

    def test_erasure_verification_error(self):
        """Test ErasureVerificationError creation."""
        subject_id = uuid7()
        exc = ErasureVerificationError(
            subject_id=subject_id,
            reason="Email verification failed",
        )
        assert exc.subject_id == subject_id
        assert exc.reason == "Email verification failed"
        assert "verification failed" in str(exc).lower()
