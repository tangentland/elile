"""Tests for data retention manager."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from elile.compliance.retention.manager import (
    RetentionManager,
    RetentionManagerConfig,
    get_retention_manager,
    initialize_retention_manager,
)
from elile.compliance.retention.types import (
    DataType,
    DeletionMethod,
    RetentionPolicy,
    RetentionStatus,
)
from elile.compliance.types import Locale


class TestRetentionManagerConfig:
    """Tests for RetentionManagerConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = RetentionManagerConfig()

        assert config.check_interval_seconds == 3600
        assert config.batch_size == 100
        assert config.warning_days == 30
        assert config.auto_delete is False
        assert config.auto_archive is True
        assert config.require_confirmation is True
        assert config.erasure_verification_required is True
        assert config.erasure_response_days == 30

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = RetentionManagerConfig(
            check_interval_seconds=1800,
            auto_delete=True,
            warning_days=14,
        )

        assert config.check_interval_seconds == 1800
        assert config.auto_delete is True
        assert config.warning_days == 14


class TestRetentionManagerPolicies:
    """Tests for policy management."""

    def test_default_policies_loaded(self) -> None:
        """Test that default policies are loaded."""
        manager = RetentionManager()

        # Should have policies registered
        assert len(manager._policies) > 0

    def test_register_custom_policy(self) -> None:
        """Test registering a custom policy."""
        manager = RetentionManager()
        policy = RetentionPolicy(
            name="custom_test",
            data_type=DataType.SCREENING_RESULT,
            retention_days=90,
        )

        manager.register_policy(policy)

        retrieved = manager.get_policy(policy.policy_id)
        assert retrieved is not None
        assert retrieved.name == "custom_test"

    def test_get_applicable_policy(self) -> None:
        """Test getting applicable policy."""
        manager = RetentionManager()

        policy = manager.get_applicable_policy(DataType.SCREENING_RESULT)
        assert policy is not None
        assert policy.data_type == DataType.SCREENING_RESULT

    def test_get_applicable_policy_locale(self) -> None:
        """Test getting locale-specific policy."""
        manager = RetentionManager()

        policy = manager.get_applicable_policy(DataType.SCREENING_RAW_DATA, Locale.EU)
        assert policy is not None
        assert policy.locale == Locale.EU


class TestRetentionManagerRecords:
    """Tests for record management."""

    def test_track_data(self) -> None:
        """Test tracking data retention."""
        manager = RetentionManager()
        data_id = uuid4()
        tenant_id = uuid4()

        record = manager.track_data(
            data_id=data_id,
            data_type=DataType.SCREENING_RESULT,
            tenant_id=tenant_id,
        )

        assert record is not None
        assert record.data_id == data_id
        assert record.tenant_id == tenant_id
        assert record.status == RetentionStatus.ACTIVE
        assert len(record.events) == 1  # CREATED event

    def test_track_data_with_locale(self) -> None:
        """Test tracking with locale-specific policy."""
        manager = RetentionManager()

        record = manager.track_data(
            data_id=uuid4(),
            data_type=DataType.SCREENING_RAW_DATA,
            tenant_id=uuid4(),
            locale=Locale.EU,
        )

        # EU has 14-day retention for raw data
        expected_expiry = datetime.utcnow() + timedelta(days=14)
        # Allow 1 second tolerance
        assert abs((record.expires_at - expected_expiry).total_seconds()) < 2

    def test_track_data_with_custom_created_at(self) -> None:
        """Test tracking with custom creation date."""
        manager = RetentionManager()
        created = datetime(2024, 1, 1)

        record = manager.track_data(
            data_id=uuid4(),
            data_type=DataType.SCREENING_RESULT,
            tenant_id=uuid4(),
            created_at=created,
        )

        assert record.created_at == created

    def test_get_record(self) -> None:
        """Test getting record by ID."""
        manager = RetentionManager()

        record = manager.track_data(
            data_id=uuid4(),
            data_type=DataType.SCREENING_RESULT,
            tenant_id=uuid4(),
        )

        retrieved = manager.get_record(record.record_id)
        assert retrieved is record

    def test_get_record_by_data_id(self) -> None:
        """Test getting record by data ID."""
        manager = RetentionManager()
        data_id = uuid4()

        manager.track_data(
            data_id=data_id,
            data_type=DataType.SCREENING_RESULT,
            tenant_id=uuid4(),
        )

        retrieved = manager.get_record_by_data_id(data_id)
        assert retrieved is not None
        assert retrieved.data_id == data_id

    def test_get_records_by_status(self) -> None:
        """Test getting records by status."""
        manager = RetentionManager()
        tenant = uuid4()

        # Create some records
        for _ in range(3):
            manager.track_data(
                data_id=uuid4(),
                data_type=DataType.SCREENING_RESULT,
                tenant_id=tenant,
            )

        active = manager.get_records_by_status(RetentionStatus.ACTIVE)
        assert len(active) == 3

    def test_get_records_by_tenant(self) -> None:
        """Test getting records by tenant."""
        manager = RetentionManager()
        tenant1 = uuid4()
        tenant2 = uuid4()

        # Create records for two tenants
        for _ in range(2):
            manager.track_data(uuid4(), DataType.SCREENING_RESULT, tenant1)
        for _ in range(3):
            manager.track_data(uuid4(), DataType.SCREENING_RESULT, tenant2)

        tenant1_records = manager.get_records_by_tenant(tenant1)
        tenant2_records = manager.get_records_by_tenant(tenant2)

        assert len(tenant1_records) == 2
        assert len(tenant2_records) == 3


class TestLegalHold:
    """Tests for legal hold management."""

    def test_place_legal_hold(self) -> None:
        """Test placing legal hold."""
        manager = RetentionManager()
        data_id = uuid4()

        manager.track_data(data_id, DataType.SCREENING_RESULT, uuid4())

        result = manager.place_legal_hold(data_id, "Litigation pending")

        assert result is True
        record = manager.get_record_by_data_id(data_id)
        assert record.legal_hold is True
        assert record.status == RetentionStatus.LEGAL_HOLD

    def test_place_legal_hold_not_found(self) -> None:
        """Test placing hold on non-existent data."""
        manager = RetentionManager()

        result = manager.place_legal_hold(uuid4(), "Test")

        assert result is False

    def test_release_legal_hold(self) -> None:
        """Test releasing legal hold."""
        manager = RetentionManager()
        data_id = uuid4()

        manager.track_data(data_id, DataType.SCREENING_RESULT, uuid4())
        manager.place_legal_hold(data_id, "Test")

        result = manager.release_legal_hold(data_id)

        assert result is True
        record = manager.get_record_by_data_id(data_id)
        assert record.legal_hold is False
        assert record.status == RetentionStatus.ACTIVE

    def test_release_legal_hold_not_held(self) -> None:
        """Test releasing hold on data not under hold."""
        manager = RetentionManager()
        data_id = uuid4()

        manager.track_data(data_id, DataType.SCREENING_RESULT, uuid4())

        result = manager.release_legal_hold(data_id)

        assert result is False


class TestLifecycleProcessing:
    """Tests for lifecycle processing."""

    @pytest.mark.asyncio
    async def test_check_expiring_data(self) -> None:
        """Test finding expiring data."""
        manager = RetentionManager()

        # Create record expiring soon
        record = manager.track_data(uuid4(), DataType.CACHE_ENTRY, uuid4())
        record.expires_at = datetime.utcnow() + timedelta(days=15)

        expiring = await manager.check_expiring_data()

        assert len(expiring) == 1
        assert expiring[0].status == RetentionStatus.EXPIRY_WARNING

    @pytest.mark.asyncio
    async def test_check_expiring_excludes_legal_hold(self) -> None:
        """Test that legal hold items are excluded."""
        manager = RetentionManager()
        data_id = uuid4()

        record = manager.track_data(data_id, DataType.CACHE_ENTRY, uuid4())
        record.expires_at = datetime.utcnow() + timedelta(days=15)
        manager.place_legal_hold(data_id, "Test")

        expiring = await manager.check_expiring_data()

        assert len(expiring) == 0

    @pytest.mark.asyncio
    async def test_check_expired_data(self) -> None:
        """Test finding expired data."""
        manager = RetentionManager()

        # Create expired record
        record = manager.track_data(uuid4(), DataType.CACHE_ENTRY, uuid4())
        record.expires_at = datetime.utcnow() - timedelta(days=1)

        expired = await manager.check_expired_data()

        assert len(expired) == 1
        assert expired[0].status == RetentionStatus.DELETION_PENDING

    @pytest.mark.asyncio
    async def test_check_archive_pending(self) -> None:
        """Test finding data ready for archival."""
        manager = RetentionManager()

        # Create record ready for archive
        record = manager.track_data(uuid4(), DataType.SCREENING_RESULT, uuid4())
        record.archive_at = datetime.utcnow() - timedelta(days=1)

        pending = await manager.check_archive_pending()

        assert len(pending) == 1
        assert pending[0].status == RetentionStatus.ARCHIVE_PENDING

    @pytest.mark.asyncio
    async def test_process_archival(self) -> None:
        """Test processing archival."""
        manager = RetentionManager()
        data_id = uuid4()

        record = manager.track_data(data_id, DataType.SCREENING_RESULT, uuid4())

        result = await manager.process_archival(record)

        assert result is True
        assert record.status == RetentionStatus.ARCHIVED
        assert any(e["action"] == "archived" for e in record.events)

    @pytest.mark.asyncio
    async def test_process_archival_legal_hold_blocked(self) -> None:
        """Test that legal hold blocks archival."""
        manager = RetentionManager()
        data_id = uuid4()

        record = manager.track_data(data_id, DataType.SCREENING_RESULT, uuid4())
        manager.place_legal_hold(data_id, "Test")

        result = await manager.process_archival(record)

        assert result is False
        assert record.status == RetentionStatus.LEGAL_HOLD

    @pytest.mark.asyncio
    async def test_process_deletion_soft(self) -> None:
        """Test soft deletion."""
        manager = RetentionManager()
        data_id = uuid4()

        record = manager.track_data(data_id, DataType.SCREENING_RESULT, uuid4())

        result = await manager.process_deletion(record)

        assert result is True
        assert record.status == RetentionStatus.DELETED
        assert record.deleted_at is not None

    @pytest.mark.asyncio
    async def test_process_deletion_legal_hold_blocked(self) -> None:
        """Test that legal hold blocks deletion."""
        manager = RetentionManager()
        data_id = uuid4()

        record = manager.track_data(data_id, DataType.SCREENING_RESULT, uuid4())
        manager.place_legal_hold(data_id, "Test")

        result = await manager.process_deletion(record)

        assert result is False


class TestErasureRequests:
    """Tests for GDPR erasure requests."""

    @pytest.mark.asyncio
    async def test_submit_erasure_request(self) -> None:
        """Test submitting erasure request."""
        manager = RetentionManager()

        request = await manager.submit_erasure_request(
            subject_id=uuid4(),
            tenant_id=uuid4(),
            locale=Locale.EU,
            reason="GDPR request",
        )

        assert request is not None
        assert request.status == "pending"
        assert not request.verified
        assert request.locale == Locale.EU

    @pytest.mark.asyncio
    async def test_verify_erasure_request(self) -> None:
        """Test verifying erasure request."""
        manager = RetentionManager()

        request = await manager.submit_erasure_request(
            subject_id=uuid4(),
            tenant_id=uuid4(),
            locale=Locale.EU,
        )

        result = await manager.verify_erasure_request(request.request_id, "email")

        assert result is True
        updated = manager._erasure_requests[request.request_id]
        assert updated.verified is True
        assert updated.verification_method == "email"

    @pytest.mark.asyncio
    async def test_process_erasure_request_unverified(self) -> None:
        """Test that unverified requests are rejected."""
        manager = RetentionManager()

        request = await manager.submit_erasure_request(
            subject_id=uuid4(),
            tenant_id=uuid4(),
            locale=Locale.EU,
        )

        with pytest.raises(ValueError, match="not verified"):
            await manager.process_erasure_request(request.request_id)

    @pytest.mark.asyncio
    async def test_process_erasure_request_success(self) -> None:
        """Test processing verified erasure request."""
        manager = RetentionManager(
            config=RetentionManagerConfig(erasure_verification_required=False),
        )
        tenant_id = uuid4()

        # Create some erasable data
        manager.track_data(uuid4(), DataType.ENTITY_PROFILE, tenant_id, Locale.EU)
        manager.track_data(uuid4(), DataType.CACHE_ENTRY, tenant_id, Locale.EU)

        request = await manager.submit_erasure_request(
            subject_id=uuid4(),
            tenant_id=tenant_id,
            locale=Locale.EU,
        )

        result = await manager.process_erasure_request(request.request_id)

        assert result.status == "completed"
        assert result.items_deleted > 0

    @pytest.mark.asyncio
    async def test_process_erasure_request_with_legal_hold(self) -> None:
        """Test erasure request with data under legal hold."""
        manager = RetentionManager(
            config=RetentionManagerConfig(erasure_verification_required=False),
        )
        tenant_id = uuid4()
        data_id = uuid4()

        # Create data and place legal hold
        manager.track_data(data_id, DataType.ENTITY_PROFILE, tenant_id, Locale.EU)
        manager.place_legal_hold(data_id, "Litigation")

        request = await manager.submit_erasure_request(
            subject_id=uuid4(),
            tenant_id=tenant_id,
            locale=Locale.EU,
        )

        result = await manager.process_erasure_request(request.request_id)

        assert result.items_retained > 0
        assert any("legal hold" in r.lower() for r in result.retention_reasons)


class TestReporting:
    """Tests for retention reporting."""

    def test_generate_report(self) -> None:
        """Test generating retention report."""
        manager = RetentionManager()
        tenant = uuid4()

        # Create various records
        for _ in range(5):
            manager.track_data(uuid4(), DataType.SCREENING_RESULT, tenant)
        for _ in range(3):
            manager.track_data(uuid4(), DataType.CACHE_ENTRY, tenant)

        report = manager.generate_report(tenant)

        assert report is not None
        assert report.tenant_id == tenant
        assert report.active_count == 8
        assert report.total_count == 8

    def test_generate_report_with_status(self) -> None:
        """Test report with different statuses."""
        manager = RetentionManager()
        tenant = uuid4()

        # Create records with different statuses
        active_record = manager.track_data(uuid4(), DataType.SCREENING_RESULT, tenant)

        archived_record = manager.track_data(uuid4(), DataType.SCREENING_RESULT, tenant)
        archived_record.status = RetentionStatus.ARCHIVED

        hold_data = uuid4()
        manager.track_data(hold_data, DataType.SCREENING_RESULT, tenant)
        manager.place_legal_hold(hold_data, "Test")

        report = manager.generate_report(tenant)

        assert report.active_count == 1
        assert report.archived_count == 1
        assert report.legal_hold_count == 1

    def test_generate_report_expiration_windows(self) -> None:
        """Test report expiration window counts."""
        manager = RetentionManager()
        tenant = uuid4()

        # Create records expiring at different times
        soon = manager.track_data(uuid4(), DataType.CACHE_ENTRY, tenant)
        soon.expires_at = datetime.utcnow() + timedelta(days=5)

        medium = manager.track_data(uuid4(), DataType.CACHE_ENTRY, tenant)
        medium.expires_at = datetime.utcnow() + timedelta(days=20)

        later = manager.track_data(uuid4(), DataType.CACHE_ENTRY, tenant)
        later.expires_at = datetime.utcnow() + timedelta(days=60)

        report = manager.generate_report(tenant)

        assert report.expiring_next_7_days == 1
        assert report.expiring_next_30_days == 2
        assert report.expiring_next_90_days == 3


class TestGlobalManager:
    """Tests for global manager instance."""

    def test_get_retention_manager(self) -> None:
        """Test getting global manager."""
        manager1 = get_retention_manager()
        manager2 = get_retention_manager()

        assert manager1 is manager2  # Same instance

    def test_initialize_retention_manager(self) -> None:
        """Test initializing with custom config."""
        config = RetentionManagerConfig(auto_delete=True)

        manager = initialize_retention_manager(config=config)

        assert manager.config.auto_delete is True
