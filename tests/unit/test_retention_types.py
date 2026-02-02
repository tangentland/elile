"""Tests for data retention types."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from elile.compliance.retention.types import (
    DataType,
    DeletionMethod,
    ErasureRequest,
    RetentionAction,
    RetentionPolicy,
    RetentionRecord,
    RetentionReport,
    RetentionStatus,
)
from elile.compliance.types import Locale


class TestDataType:
    """Tests for DataType enum."""

    def test_all_data_types_exist(self) -> None:
        """Verify all expected data types are defined."""
        expected = [
            "SCREENING_RESULT",
            "SCREENING_FINDING",
            "SCREENING_RAW_DATA",
            "ENTITY_PROFILE",
            "ENTITY_RELATION",
            "AUDIT_LOG",
            "CONSENT_RECORD",
            "DISCLOSURE_RECORD",
            "ADVERSE_ACTION",
            "REPORT",
            "PROVIDER_RESPONSE",
            "CACHE_ENTRY",
            "MONITORING_ALERT",
            "MONITORING_CHECK",
        ]
        for name in expected:
            assert hasattr(DataType, name)

    def test_data_type_values(self) -> None:
        """Verify data type values are strings."""
        assert DataType.SCREENING_RESULT.value == "screening_result"
        assert DataType.AUDIT_LOG.value == "audit_log"


class TestDeletionMethod:
    """Tests for DeletionMethod enum."""

    def test_all_methods_exist(self) -> None:
        """Verify all deletion methods are defined."""
        assert DeletionMethod.SOFT_DELETE.value == "soft_delete"
        assert DeletionMethod.HARD_DELETE.value == "hard_delete"
        assert DeletionMethod.ANONYMIZE.value == "anonymize"
        assert DeletionMethod.ARCHIVE.value == "archive"
        assert DeletionMethod.CRYPTO_SHRED.value == "crypto_shred"


class TestRetentionPolicy:
    """Tests for RetentionPolicy model."""

    def test_create_policy(self) -> None:
        """Test creating a retention policy."""
        policy = RetentionPolicy(
            name="test_policy",
            description="Test policy",
            data_type=DataType.SCREENING_RESULT,
            retention_days=365,
            deletion_method=DeletionMethod.SOFT_DELETE,
        )

        assert policy.name == "test_policy"
        assert policy.data_type == DataType.SCREENING_RESULT
        assert policy.retention_days == 365
        assert policy.policy_id is not None

    def test_retention_period_property(self) -> None:
        """Test retention_period property."""
        policy = RetentionPolicy(
            name="test",
            data_type=DataType.SCREENING_RESULT,
            retention_days=365,
        )

        assert policy.retention_period == timedelta(days=365)

    def test_archive_period_property(self) -> None:
        """Test archive_period property."""
        # With archive
        policy = RetentionPolicy(
            name="test",
            data_type=DataType.SCREENING_RESULT,
            retention_days=365,
            archive_after_days=90,
        )
        assert policy.archive_period == timedelta(days=90)

        # Without archive
        policy_no_archive = RetentionPolicy(
            name="test",
            data_type=DataType.SCREENING_RESULT,
            retention_days=365,
        )
        assert policy_no_archive.archive_period is None

    def test_calculate_expiry(self) -> None:
        """Test expiry date calculation."""
        policy = RetentionPolicy(
            name="test",
            data_type=DataType.SCREENING_RESULT,
            retention_days=30,
        )

        created = datetime(2024, 1, 1)
        expiry = policy.calculate_expiry(created)

        assert expiry == datetime(2024, 1, 31)

    def test_calculate_archive_date(self) -> None:
        """Test archive date calculation."""
        policy = RetentionPolicy(
            name="test",
            data_type=DataType.SCREENING_RESULT,
            retention_days=365,
            archive_after_days=30,
        )

        created = datetime(2024, 1, 1)
        archive_date = policy.calculate_archive_date(created)

        assert archive_date == datetime(2024, 1, 31)

    def test_calculate_warning_date(self) -> None:
        """Test warning date calculation."""
        policy = RetentionPolicy(
            name="test",
            data_type=DataType.SCREENING_RESULT,
            retention_days=60,
            warning_days=30,
        )

        created = datetime(2024, 1, 1)
        warning_date = policy.calculate_warning_date(created)

        # Expiry is Jan 1 + 60 days = Mar 1
        # Warning is Mar 1 - 30 days = Jan 31
        assert warning_date == datetime(2024, 1, 31)

    def test_locale_specific_policy(self) -> None:
        """Test policy with locale."""
        policy = RetentionPolicy(
            name="eu_policy",
            data_type=DataType.ENTITY_PROFILE,
            locale=Locale.EU,
            retention_days=365 * 5,
            subject_request_override=True,
            regulatory_basis="GDPR Article 17",
        )

        assert policy.locale == Locale.EU
        assert policy.subject_request_override is True
        assert "GDPR" in policy.regulatory_basis


class TestRetentionRecord:
    """Tests for RetentionRecord dataclass."""

    def test_create_record(self) -> None:
        """Test creating a retention record."""
        record = RetentionRecord(
            data_type=DataType.SCREENING_RESULT,
            data_id=uuid4(),
            tenant_id=uuid4(),
            policy_id=uuid4(),
        )

        assert record.record_id is not None
        assert record.status == RetentionStatus.ACTIVE
        assert not record.legal_hold

    def test_add_event(self) -> None:
        """Test adding events to record."""
        record = RetentionRecord()
        record.add_event(RetentionAction.CREATED, {"key": "value"})

        assert len(record.events) == 1
        assert record.events[0]["action"] == "created"
        assert record.events[0]["details"]["key"] == "value"

    def test_place_legal_hold(self) -> None:
        """Test placing legal hold."""
        record = RetentionRecord()
        record.place_legal_hold("Litigation pending")

        assert record.legal_hold is True
        assert record.legal_hold_reason == "Litigation pending"
        assert record.status == RetentionStatus.LEGAL_HOLD
        assert record.legal_hold_placed_at is not None
        assert len(record.events) == 1

    def test_release_legal_hold(self) -> None:
        """Test releasing legal hold."""
        record = RetentionRecord()
        record.place_legal_hold("Test")
        record.release_legal_hold()

        assert record.legal_hold is False
        assert record.legal_hold_reason is None
        assert record.status == RetentionStatus.ACTIVE
        assert len(record.events) == 2

    def test_is_expired(self) -> None:
        """Test expiration check."""
        # Not expired
        record = RetentionRecord(
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        assert not record.is_expired

        # Expired
        record_expired = RetentionRecord(
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        assert record_expired.is_expired

        # Legal hold prevents expiration
        record_hold = RetentionRecord(
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        record_hold.place_legal_hold("Test")
        assert not record_hold.is_expired

    def test_is_warning_period(self) -> None:
        """Test warning period check."""
        # In warning period (within 30 days of expiry)
        record = RetentionRecord(
            expires_at=datetime.utcnow() + timedelta(days=15),
        )
        assert record.is_warning_period

        # Not in warning period
        record_far = RetentionRecord(
            expires_at=datetime.utcnow() + timedelta(days=60),
        )
        assert not record_far.is_warning_period

    def test_days_until_expiry(self) -> None:
        """Test days until expiry calculation."""
        record = RetentionRecord(
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        # Allow 1 day tolerance for test timing
        assert 29 <= record.days_until_expiry <= 31

        # Legal hold returns -1
        record.place_legal_hold("Test")
        assert record.days_until_expiry == -1


class TestRetentionReport:
    """Tests for RetentionReport dataclass."""

    def test_create_report(self) -> None:
        """Test creating a report."""
        report = RetentionReport(
            active_count=100,
            archived_count=50,
            expiry_warning_count=10,
            deletion_pending_count=5,
            legal_hold_count=2,
        )

        assert report.report_id is not None
        assert report.generated_at is not None

    def test_total_count(self) -> None:
        """Test total count property."""
        report = RetentionReport(
            active_count=100,
            archived_count=50,
            expiry_warning_count=10,
            deletion_pending_count=5,
            legal_hold_count=2,
        )

        assert report.total_count == 167

    def test_compliance_rate(self) -> None:
        """Test compliance rate calculation."""
        report = RetentionReport(
            compliant_count=90,
            non_compliant_count=10,
        )

        assert report.compliance_rate == 90.0

        # Empty case
        empty_report = RetentionReport()
        assert empty_report.compliance_rate == 100.0


class TestErasureRequest:
    """Tests for ErasureRequest model."""

    def test_create_request(self) -> None:
        """Test creating an erasure request."""
        request = ErasureRequest(
            subject_id=uuid4(),
            tenant_id=uuid4(),
            locale=Locale.EU,
            reason="GDPR request",
        )

        assert request.request_id is not None
        assert request.status == "pending"
        assert not request.verified

    def test_request_with_data_types(self) -> None:
        """Test request with specific data types."""
        request = ErasureRequest(
            subject_id=uuid4(),
            tenant_id=uuid4(),
            locale=Locale.EU,
            requested_data_types=[
                DataType.ENTITY_PROFILE,
                DataType.SCREENING_RAW_DATA,
            ],
        )

        assert len(request.requested_data_types) == 2
        assert DataType.ENTITY_PROFILE in request.requested_data_types
