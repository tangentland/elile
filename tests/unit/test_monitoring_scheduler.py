"""Unit tests for the monitoring scheduler.

Tests scheduling, check execution, lifecycle events, and alert generation.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid7

import pytest

from elile.agent.state import SearchDegree, ServiceTier, VigilanceLevel
from elile.compliance.types import Locale, RoleCategory
from elile.monitoring.scheduler import (
    AUTO_ALERT_THRESHOLDS,
    HUMAN_REVIEW_THRESHOLDS,
    InMemoryMonitoringStore,
    MonitoringScheduler,
    SchedulerConfig,
    create_monitoring_scheduler,
)
from elile.monitoring.types import (
    AlertSeverity,
    CheckStatus,
    CheckType,
    DeltaSeverity,
    LifecycleEvent,
    LifecycleEventType,
    MonitoringCheck,
    MonitoringConfig,
    MonitoringConfigError,
    MonitoringStatus,
    ProfileDelta,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def store() -> InMemoryMonitoringStore:
    """Create an in-memory store for testing."""
    return InMemoryMonitoringStore()


@pytest.fixture
def scheduler(store: InMemoryMonitoringStore) -> MonitoringScheduler:
    """Create a monitoring scheduler with in-memory store."""
    return MonitoringScheduler(store=store)


@pytest.fixture
def tenant_id() -> UUID:
    """Generate a tenant ID for testing."""
    return uuid7()


@pytest.fixture
def subject_id() -> UUID:
    """Generate a subject ID for testing."""
    return uuid7()


@pytest.fixture
def baseline_profile_id() -> UUID:
    """Generate a baseline profile ID for testing."""
    return uuid7()


# =============================================================================
# Vigilance Interval Tests
# =============================================================================


class TestVigilanceIntervals:
    """Test vigilance level interval calculations."""

    def test_v1_interval_is_annual(self, scheduler: MonitoringScheduler) -> None:
        """V1 vigilance should have 365 day interval."""
        interval = scheduler.get_interval(VigilanceLevel.V1)
        assert interval == timedelta(days=365)

    def test_v2_interval_is_monthly(self, scheduler: MonitoringScheduler) -> None:
        """V2 vigilance should have 30 day interval."""
        interval = scheduler.get_interval(VigilanceLevel.V2)
        assert interval == timedelta(days=30)

    def test_v3_interval_is_bimonthly(self, scheduler: MonitoringScheduler) -> None:
        """V3 vigilance should have 15 day interval."""
        interval = scheduler.get_interval(VigilanceLevel.V3)
        assert interval == timedelta(days=15)

    def test_v0_raises_error(self, scheduler: MonitoringScheduler) -> None:
        """V0 vigilance should raise error (no ongoing monitoring)."""
        with pytest.raises(MonitoringConfigError, match="V0 vigilance"):
            scheduler.get_interval(VigilanceLevel.V0)

    def test_custom_intervals_from_config(self, store: InMemoryMonitoringStore) -> None:
        """Custom intervals should be applied from config."""
        config = SchedulerConfig(
            v1_interval=timedelta(days=180),
            v2_interval=timedelta(days=14),
            v3_interval=timedelta(days=7),
        )
        scheduler = MonitoringScheduler(store=store, config=config)

        assert scheduler.get_interval(VigilanceLevel.V1) == timedelta(days=180)
        assert scheduler.get_interval(VigilanceLevel.V2) == timedelta(days=14)
        assert scheduler.get_interval(VigilanceLevel.V3) == timedelta(days=7)


# =============================================================================
# Schedule Monitoring Tests
# =============================================================================


class TestScheduleMonitoring:
    """Test scheduling new monitoring configurations."""

    @pytest.mark.anyio
    async def test_schedule_v1_monitoring(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Schedule V1 (annual) monitoring."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V1,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        assert result.success is True
        assert result.interval_days == 365
        assert result.next_check_date is not None
        assert "V1" in result.message or "v1" in result.message

    @pytest.mark.anyio
    async def test_schedule_v2_monitoring(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Schedule V2 (monthly) monitoring."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        assert result.success is True
        assert result.interval_days == 30
        assert result.next_check_date is not None

    @pytest.mark.anyio
    async def test_schedule_v3_monitoring(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Schedule V3 (bi-monthly) monitoring."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V3,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        assert result.success is True
        assert result.interval_days == 15
        assert result.next_check_date is not None

    @pytest.mark.anyio
    async def test_schedule_v0_returns_failure(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """V0 scheduling should return failure (no ongoing monitoring)."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V0,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        assert result.success is False
        assert "V0" in result.error

    @pytest.mark.anyio
    async def test_schedule_with_v3_realtime_features(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Schedule V3 with real-time features enabled."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V3,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
            sanctions_realtime=True,
            adverse_media_continuous=True,
        )

        assert result.success is True

        # Verify config was saved
        config = await scheduler.store.get_config(result.config_id)
        assert config is not None
        assert config.sanctions_realtime is True
        assert config.adverse_media_continuous is True

    @pytest.mark.anyio
    async def test_schedule_with_dark_web_monitoring_requires_enhanced(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Dark web monitoring should require Enhanced tier."""
        # Standard tier should fail
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V3,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
            service_tier=ServiceTier.STANDARD,
            dark_web_monitoring=True,
        )

        assert result.success is False
        assert "Enhanced" in result.error

    @pytest.mark.anyio
    async def test_schedule_with_dark_web_enhanced_tier(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Dark web monitoring should work with Enhanced tier."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V3,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
            service_tier=ServiceTier.ENHANCED,
            dark_web_monitoring=True,
        )

        assert result.success is True

        config = await scheduler.store.get_config(result.config_id)
        assert config is not None
        assert config.dark_web_monitoring is True

    @pytest.mark.anyio
    async def test_schedule_with_all_options(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Schedule with all configuration options."""
        entity_id = uuid7()
        alert_recipients = ["security@example.com", "hr@example.com"]
        escalation_path = ["ciso@example.com"]
        metadata = {"department": "Finance"}

        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V3,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
            entity_id=entity_id,
            service_tier=ServiceTier.ENHANCED,
            degrees=SearchDegree.D2,
            locale=Locale.EU,
            role_category=RoleCategory.FINANCIAL,
            alert_recipients=alert_recipients,
            escalation_path=escalation_path,
            sanctions_realtime=True,
            adverse_media_continuous=True,
            dark_web_monitoring=True,
            metadata=metadata,
        )

        assert result.success is True

        config = await scheduler.store.get_config(result.config_id)
        assert config is not None
        assert config.entity_id == entity_id
        assert config.service_tier == ServiceTier.ENHANCED
        assert config.degrees == SearchDegree.D2
        assert config.locale == Locale.EU
        assert config.role_category == RoleCategory.FINANCIAL
        assert config.alert_recipients == alert_recipients
        assert config.escalation_path == escalation_path
        assert config.metadata["department"] == "Finance"


# =============================================================================
# Execute Scheduled Checks Tests
# =============================================================================


class TestExecuteScheduledChecks:
    """Test execution of scheduled monitoring checks."""

    @pytest.mark.anyio
    async def test_execute_due_checks(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Execute checks that are due."""
        # Schedule monitoring
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        # Manually set check to be due now
        config = await scheduler.store.get_config(result.config_id)
        assert config is not None
        config.next_check_date = datetime.now(UTC) - timedelta(hours=1)
        await scheduler.store.save_config(config)

        # Execute checks
        checks = await scheduler.execute_scheduled_checks()

        assert len(checks) == 1
        assert checks[0].status == CheckStatus.COMPLETED
        assert checks[0].monitoring_config_id == config.config_id

    @pytest.mark.anyio
    async def test_no_due_checks(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """No checks executed when none are due."""
        # Schedule monitoring (next check in future)
        await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V1,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        # Execute checks
        checks = await scheduler.execute_scheduled_checks()

        assert len(checks) == 0

    @pytest.mark.anyio
    async def test_check_updates_next_check_date(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Executing a check should update next_check_date."""
        # Schedule V2 monitoring
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        config = await scheduler.store.get_config(result.config_id)
        assert config is not None
        original_next_check = config.next_check_date

        # Make it due
        config.next_check_date = datetime.now(UTC) - timedelta(hours=1)
        await scheduler.store.save_config(config)

        # Execute
        await scheduler.execute_scheduled_checks()

        # Verify next check is updated
        updated_config = await scheduler.store.get_config(result.config_id)
        assert updated_config is not None
        assert updated_config.next_check_date != original_next_check
        # Should be approximately 30 days from now
        expected = datetime.now(UTC) + timedelta(days=30)
        assert abs((updated_config.next_check_date - expected).total_seconds()) < 60

    @pytest.mark.anyio
    async def test_check_increments_completed_count(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Executing a check should increment checks_completed."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        config = await scheduler.store.get_config(result.config_id)
        assert config is not None
        assert config.checks_completed == 0

        # Make it due and execute
        config.next_check_date = datetime.now(UTC) - timedelta(hours=1)
        await scheduler.store.save_config(config)
        await scheduler.execute_scheduled_checks()

        updated_config = await scheduler.store.get_config(result.config_id)
        assert updated_config is not None
        assert updated_config.checks_completed == 1

    @pytest.mark.anyio
    async def test_paused_configs_not_checked(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Paused configurations should not be checked."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        config = await scheduler.store.get_config(result.config_id)
        assert config is not None
        config.next_check_date = datetime.now(UTC) - timedelta(hours=1)
        config.status = MonitoringStatus.PAUSED
        await scheduler.store.save_config(config)

        checks = await scheduler.execute_scheduled_checks()
        assert len(checks) == 0


# =============================================================================
# Lifecycle Event Tests
# =============================================================================


class TestLifecycleEvents:
    """Test handling of employee lifecycle events."""

    @pytest.mark.anyio
    async def test_termination_stops_monitoring(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Termination event should stop monitoring."""
        # Schedule monitoring
        await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        # Handle termination event
        event = LifecycleEvent(
            subject_id=subject_id,
            tenant_id=tenant_id,
            event_type=LifecycleEventType.TERMINATION,
            description="Employment ended",
        )

        config = await scheduler.handle_lifecycle_event(event)

        assert config is not None
        assert config.status == MonitoringStatus.TERMINATED
        assert config.next_check_date is None
        assert event.processed is True

    @pytest.mark.anyio
    async def test_leave_of_absence_pauses_monitoring(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Leave of absence should pause monitoring."""
        await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        event = LifecycleEvent(
            subject_id=subject_id,
            tenant_id=tenant_id,
            event_type=LifecycleEventType.LEAVE_OF_ABSENCE,
            description="Medical leave",
        )

        config = await scheduler.handle_lifecycle_event(event)

        assert config is not None
        assert config.status == MonitoringStatus.PAUSED
        assert config.pause_reason == "Medical leave"

    @pytest.mark.anyio
    async def test_return_from_leave_resumes_monitoring(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Return from leave should resume monitoring."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        # First pause
        config = await scheduler.store.get_config(result.config_id)
        assert config is not None
        config.status = MonitoringStatus.PAUSED
        await scheduler.store.save_config(config)

        # Then return
        event = LifecycleEvent(
            subject_id=subject_id,
            tenant_id=tenant_id,
            event_type=LifecycleEventType.RETURN_FROM_LEAVE,
        )

        updated = await scheduler.handle_lifecycle_event(event)

        assert updated is not None
        assert updated.status == MonitoringStatus.ACTIVE
        assert updated.pause_reason is None

    @pytest.mark.anyio
    async def test_position_change_updates_role(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Position change should update role category."""
        await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
            role_category=RoleCategory.STANDARD,
        )

        event = LifecycleEvent(
            subject_id=subject_id,
            tenant_id=tenant_id,
            event_type=LifecycleEventType.PROMOTION,
            new_role_category=RoleCategory.EXECUTIVE,
            new_vigilance_level=VigilanceLevel.V3,
        )

        config = await scheduler.handle_lifecycle_event(event)

        assert config is not None
        assert config.role_category == RoleCategory.EXECUTIVE
        assert config.vigilance_level == VigilanceLevel.V3

    @pytest.mark.anyio
    async def test_transfer_updates_locale(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Transfer should update locale."""
        await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
            locale=Locale.US,
        )

        event = LifecycleEvent(
            subject_id=subject_id,
            tenant_id=tenant_id,
            event_type=LifecycleEventType.TRANSFER,
            new_locale=Locale.EU,
        )

        config = await scheduler.handle_lifecycle_event(event)

        assert config is not None
        assert config.locale == Locale.EU

    @pytest.mark.anyio
    async def test_vigilance_upgrade(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Vigilance upgrade should increase monitoring frequency."""
        await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V1,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        event = LifecycleEvent(
            subject_id=subject_id,
            tenant_id=tenant_id,
            event_type=LifecycleEventType.VIGILANCE_UPGRADE,
            new_vigilance_level=VigilanceLevel.V2,
        )

        config = await scheduler.handle_lifecycle_event(event)

        assert config is not None
        assert config.vigilance_level == VigilanceLevel.V2

    @pytest.mark.anyio
    async def test_vigilance_downgrade_disables_v3_features(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Downgrade from V3 should disable V3 features."""
        await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V3,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
            sanctions_realtime=True,
            adverse_media_continuous=True,
        )

        event = LifecycleEvent(
            subject_id=subject_id,
            tenant_id=tenant_id,
            event_type=LifecycleEventType.VIGILANCE_DOWNGRADE,
            new_vigilance_level=VigilanceLevel.V2,
        )

        config = await scheduler.handle_lifecycle_event(event)

        assert config is not None
        assert config.vigilance_level == VigilanceLevel.V2
        assert config.sanctions_realtime is False
        assert config.adverse_media_continuous is False

    @pytest.mark.anyio
    async def test_rehire_resumes_monitoring(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Rehire should resume monitoring."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        # Terminate first
        config = await scheduler.store.get_config(result.config_id)
        assert config is not None
        config.status = MonitoringStatus.TERMINATED
        await scheduler.store.save_config(config)

        # Then rehire
        event = LifecycleEvent(
            subject_id=subject_id,
            tenant_id=tenant_id,
            event_type=LifecycleEventType.REHIRE,
            new_vigilance_level=VigilanceLevel.V2,
        )

        updated = await scheduler.handle_lifecycle_event(event)

        assert updated is not None
        assert updated.status == MonitoringStatus.ACTIVE
        assert "rehire_date" in updated.metadata

    @pytest.mark.anyio
    async def test_event_for_nonexistent_config(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
    ) -> None:
        """Event for non-existent config should be marked processed."""
        event = LifecycleEvent(
            subject_id=subject_id,
            tenant_id=tenant_id,
            event_type=LifecycleEventType.POSITION_CHANGE,
        )

        result = await scheduler.handle_lifecycle_event(event)

        assert result is None
        assert event.processed is True
        assert "No monitoring" in (event.processing_result or "")


# =============================================================================
# Pause/Resume/Terminate Tests
# =============================================================================


class TestPauseResumeTerminate:
    """Test pause, resume, and terminate operations."""

    @pytest.mark.anyio
    async def test_pause_monitoring(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Pause monitoring manually."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        config = await scheduler.pause_monitoring(
            config_id=result.config_id,
            reason="Investigation in progress",
        )

        assert config.status == MonitoringStatus.PAUSED
        assert config.pause_reason == "Investigation in progress"

    @pytest.mark.anyio
    async def test_pause_with_until_date(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Pause monitoring with specific resume date."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        until = datetime.now(UTC) + timedelta(days=7)
        config = await scheduler.pause_monitoring(
            config_id=result.config_id,
            reason="Temporary pause",
            until=until,
        )

        assert config.pause_until == until

    @pytest.mark.anyio
    async def test_resume_monitoring(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Resume paused monitoring."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        await scheduler.pause_monitoring(result.config_id, "Test pause")
        config = await scheduler.resume_monitoring(result.config_id)

        assert config.status == MonitoringStatus.ACTIVE
        assert config.pause_reason is None

    @pytest.mark.anyio
    async def test_resume_with_immediate_check(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Resume with immediate check should schedule now."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        await scheduler.pause_monitoring(result.config_id, "Test pause")
        config = await scheduler.resume_monitoring(result.config_id, immediate_check=True)

        # Should be scheduled for now
        assert config.next_check_date is not None
        assert (config.next_check_date - datetime.now(UTC)).total_seconds() < 60

    @pytest.mark.anyio
    async def test_resume_non_paused_raises_error(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Resume on non-paused config should raise error."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        with pytest.raises(MonitoringConfigError, match="not paused"):
            await scheduler.resume_monitoring(result.config_id)

    @pytest.mark.anyio
    async def test_terminate_monitoring(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Terminate monitoring."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        config = await scheduler.terminate_monitoring(
            config_id=result.config_id,
            reason="Employee resigned",
        )

        assert config.status == MonitoringStatus.TERMINATED
        assert config.next_check_date is None
        assert config.metadata["termination_reason"] == "Employee resigned"

    @pytest.mark.anyio
    async def test_operations_on_nonexistent_config(
        self,
        scheduler: MonitoringScheduler,
    ) -> None:
        """Operations on non-existent config should raise error."""
        fake_id = uuid7()

        with pytest.raises(MonitoringConfigError, match="not found"):
            await scheduler.pause_monitoring(fake_id, "test")

        with pytest.raises(MonitoringConfigError, match="not found"):
            await scheduler.resume_monitoring(fake_id)

        with pytest.raises(MonitoringConfigError, match="not found"):
            await scheduler.terminate_monitoring(fake_id)


# =============================================================================
# Update Vigilance Level Tests
# =============================================================================


class TestUpdateVigilanceLevel:
    """Test vigilance level updates."""

    @pytest.mark.anyio
    async def test_upgrade_vigilance(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Upgrade vigilance level."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V1,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        config = await scheduler.update_vigilance_level(
            config_id=result.config_id,
            new_level=VigilanceLevel.V3,
        )

        assert config.vigilance_level == VigilanceLevel.V3
        # Next check should be in ~15 days
        expected = datetime.now(UTC) + timedelta(days=15)
        assert abs((config.next_check_date - expected).total_seconds()) < 60

    @pytest.mark.anyio
    async def test_downgrade_vigilance_disables_features(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Downgrade from V3 should disable V3 features."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V3,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
            sanctions_realtime=True,
            adverse_media_continuous=True,
        )

        config = await scheduler.update_vigilance_level(
            config_id=result.config_id,
            new_level=VigilanceLevel.V1,
        )

        assert config.sanctions_realtime is False
        assert config.adverse_media_continuous is False

    @pytest.mark.anyio
    async def test_change_to_v0_raises_error(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Changing to V0 should raise error."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        with pytest.raises(MonitoringConfigError, match="V0"):
            await scheduler.update_vigilance_level(result.config_id, VigilanceLevel.V0)


# =============================================================================
# Trigger Immediate Check Tests
# =============================================================================


class TestTriggerImmediateCheck:
    """Test immediate check triggering."""

    @pytest.mark.anyio
    async def test_trigger_immediate_check(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Trigger an immediate check."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        check = await scheduler.trigger_immediate_check(
            config_id=result.config_id,
            reason="Security concern",
        )

        assert check.check_type == CheckType.TRIGGERED
        assert check.status == CheckStatus.COMPLETED
        assert check.metadata.get("trigger_reason") == "Security concern"

    @pytest.mark.anyio
    async def test_trigger_check_on_paused_raises_error(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Triggering check on paused config should raise error."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        await scheduler.pause_monitoring(result.config_id, "Test")

        with pytest.raises(MonitoringConfigError, match="paused"):
            await scheduler.trigger_immediate_check(result.config_id)


# =============================================================================
# Get Monitoring Status Tests
# =============================================================================


class TestGetMonitoringStatus:
    """Test monitoring status retrieval."""

    @pytest.mark.anyio
    async def test_get_status(
        self,
        scheduler: MonitoringScheduler,
        tenant_id: UUID,
        subject_id: UUID,
        baseline_profile_id: UUID,
    ) -> None:
        """Get monitoring status."""
        result = await scheduler.schedule_monitoring(
            subject_id=subject_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=baseline_profile_id,
            tenant_id=tenant_id,
        )

        status = await scheduler.get_monitoring_status(result.config_id)

        assert status["config_id"] == str(result.config_id)
        assert status["status"] == "active"
        assert status["vigilance_level"] == "v2"
        assert status["checks_completed"] == 0

    @pytest.mark.anyio
    async def test_get_status_nonexistent_raises_error(
        self,
        scheduler: MonitoringScheduler,
    ) -> None:
        """Get status for non-existent config should raise error."""
        with pytest.raises(MonitoringConfigError, match="not found"):
            await scheduler.get_monitoring_status(uuid7())


# =============================================================================
# Alert Generation Tests
# =============================================================================


class TestAlertGeneration:
    """Test alert generation from deltas."""

    def test_delta_meets_threshold_critical(self, scheduler: MonitoringScheduler) -> None:
        """Critical deltas should meet all thresholds."""
        assert scheduler._delta_meets_threshold(DeltaSeverity.CRITICAL, DeltaSeverity.CRITICAL)
        assert scheduler._delta_meets_threshold(DeltaSeverity.CRITICAL, DeltaSeverity.HIGH)
        assert scheduler._delta_meets_threshold(DeltaSeverity.CRITICAL, DeltaSeverity.MEDIUM)
        assert scheduler._delta_meets_threshold(DeltaSeverity.CRITICAL, DeltaSeverity.LOW)

    def test_delta_meets_threshold_low(self, scheduler: MonitoringScheduler) -> None:
        """Low deltas should not meet high thresholds."""
        assert scheduler._delta_meets_threshold(DeltaSeverity.LOW, DeltaSeverity.LOW)
        assert not scheduler._delta_meets_threshold(DeltaSeverity.LOW, DeltaSeverity.MEDIUM)
        assert not scheduler._delta_meets_threshold(DeltaSeverity.LOW, DeltaSeverity.HIGH)
        assert not scheduler._delta_meets_threshold(DeltaSeverity.LOW, DeltaSeverity.CRITICAL)

    def test_map_delta_to_alert_severity(self, scheduler: MonitoringScheduler) -> None:
        """Delta severity should map to alert severity."""
        assert (
            scheduler._map_delta_to_alert_severity(DeltaSeverity.CRITICAL) == AlertSeverity.CRITICAL
        )
        assert scheduler._map_delta_to_alert_severity(DeltaSeverity.HIGH) == AlertSeverity.HIGH
        assert scheduler._map_delta_to_alert_severity(DeltaSeverity.MEDIUM) == AlertSeverity.MEDIUM
        assert scheduler._map_delta_to_alert_severity(DeltaSeverity.LOW) == AlertSeverity.LOW
        assert scheduler._map_delta_to_alert_severity(DeltaSeverity.POSITIVE) == AlertSeverity.LOW

    def test_build_alert_description(self, scheduler: MonitoringScheduler) -> None:
        """Alert description should include all deltas."""
        deltas = [
            ProfileDelta(
                delta_type="new_finding",
                severity=DeltaSeverity.HIGH,
                description="New criminal record found",
            ),
            ProfileDelta(
                delta_type="status_change",
                severity=DeltaSeverity.MEDIUM,
                description="License expired",
            ),
        ]

        description = scheduler._build_alert_description(deltas)

        assert "New criminal record found" in description
        assert "License expired" in description
        assert "high" in description
        assert "medium" in description


# =============================================================================
# Threshold Configuration Tests
# =============================================================================


class TestAlertThresholds:
    """Test alert threshold configurations."""

    def test_v1_auto_alert_threshold(self) -> None:
        """V1 should have critical auto-alert threshold."""
        assert AUTO_ALERT_THRESHOLDS[VigilanceLevel.V1] == DeltaSeverity.CRITICAL

    def test_v2_auto_alert_threshold(self) -> None:
        """V2 should have high auto-alert threshold."""
        assert AUTO_ALERT_THRESHOLDS[VigilanceLevel.V2] == DeltaSeverity.HIGH

    def test_v3_auto_alert_threshold(self) -> None:
        """V3 should have medium auto-alert threshold."""
        assert AUTO_ALERT_THRESHOLDS[VigilanceLevel.V3] == DeltaSeverity.MEDIUM

    def test_v1_review_threshold(self) -> None:
        """V1 should have high review threshold."""
        assert HUMAN_REVIEW_THRESHOLDS[VigilanceLevel.V1] == DeltaSeverity.HIGH

    def test_v2_review_threshold(self) -> None:
        """V2 should have medium review threshold."""
        assert HUMAN_REVIEW_THRESHOLDS[VigilanceLevel.V2] == DeltaSeverity.MEDIUM

    def test_v3_review_threshold(self) -> None:
        """V3 should have low review threshold (all deltas)."""
        assert HUMAN_REVIEW_THRESHOLDS[VigilanceLevel.V3] == DeltaSeverity.LOW


# =============================================================================
# MonitoringConfig Validation Tests
# =============================================================================


class TestMonitoringConfigValidation:
    """Test MonitoringConfig validation rules."""

    def test_v0_not_allowed(
        self, tenant_id: UUID, subject_id: UUID, baseline_profile_id: UUID
    ) -> None:
        """V0 vigilance should not be allowed."""
        with pytest.raises(ValueError, match="V0"):
            MonitoringConfig(
                subject_id=subject_id,
                tenant_id=tenant_id,
                vigilance_level=VigilanceLevel.V0,
                baseline_profile_id=baseline_profile_id,
            )

    def test_dark_web_requires_enhanced(
        self, tenant_id: UUID, subject_id: UUID, baseline_profile_id: UUID
    ) -> None:
        """Dark web monitoring requires Enhanced tier."""
        with pytest.raises(ValueError, match="Enhanced"):
            MonitoringConfig(
                subject_id=subject_id,
                tenant_id=tenant_id,
                vigilance_level=VigilanceLevel.V3,
                baseline_profile_id=baseline_profile_id,
                service_tier=ServiceTier.STANDARD,
                dark_web_monitoring=True,
            )

    def test_realtime_requires_v3(
        self, tenant_id: UUID, subject_id: UUID, baseline_profile_id: UUID
    ) -> None:
        """Real-time features require V3 vigilance."""
        with pytest.raises(ValueError, match="V3"):
            MonitoringConfig(
                subject_id=subject_id,
                tenant_id=tenant_id,
                vigilance_level=VigilanceLevel.V2,
                baseline_profile_id=baseline_profile_id,
                sanctions_realtime=True,
            )

        with pytest.raises(ValueError, match="V3"):
            MonitoringConfig(
                subject_id=subject_id,
                tenant_id=tenant_id,
                vigilance_level=VigilanceLevel.V1,
                baseline_profile_id=baseline_profile_id,
                adverse_media_continuous=True,
            )


# =============================================================================
# Types Tests
# =============================================================================


class TestMonitoringCheck:
    """Test MonitoringCheck functionality."""

    def test_check_start(self) -> None:
        """Check should track start time."""
        check = MonitoringCheck()
        assert check.started_at is None

        check.start()
        assert check.started_at is not None
        assert check.status == CheckStatus.IN_PROGRESS

    def test_check_complete(self) -> None:
        """Check should track completion."""
        check = MonitoringCheck()
        check.start()
        check.complete(CheckStatus.COMPLETED)

        assert check.completed_at is not None
        assert check.status == CheckStatus.COMPLETED
        assert check.duration_seconds is not None
        assert check.duration_seconds >= 0

    def test_check_complete_with_error(self) -> None:
        """Check should track error on failure."""
        check = MonitoringCheck()
        check.start()
        check.complete(CheckStatus.FAILED, error="Connection timeout")

        assert check.status == CheckStatus.FAILED
        assert check.error_message == "Connection timeout"

    def test_check_has_critical_deltas(self) -> None:
        """Check should detect critical deltas."""
        check = MonitoringCheck()
        assert check.has_critical_deltas is False

        check.deltas_detected = [
            ProfileDelta(severity=DeltaSeverity.LOW, description="Minor change"),
            ProfileDelta(severity=DeltaSeverity.CRITICAL, description="Major change"),
        ]
        assert check.has_critical_deltas is True

    def test_check_to_dict(self) -> None:
        """Check should convert to dictionary."""
        check = MonitoringCheck(check_type=CheckType.SCHEDULED)
        check.start()
        check.complete(CheckStatus.COMPLETED)

        data = check.to_dict()

        assert data["check_type"] == "scheduled"
        assert data["status"] == "completed"
        assert data["started_at"] is not None
        assert data["completed_at"] is not None


class TestProfileDelta:
    """Test ProfileDelta functionality."""

    def test_delta_to_dict(self) -> None:
        """Delta should convert to dictionary."""
        delta = ProfileDelta(
            delta_type="new_finding",
            category="criminal",
            severity=DeltaSeverity.HIGH,
            description="New arrest record",
            previous_value=None,
            current_value="Arrested 2024-01-15",
            source_provider="criminal_check_provider",
            requires_review=True,
        )

        data = delta.to_dict()

        assert data["delta_type"] == "new_finding"
        assert data["category"] == "criminal"
        assert data["severity"] == "high"
        assert data["description"] == "New arrest record"
        assert data["requires_review"] is True


class TestLifecycleEvent:
    """Test LifecycleEvent functionality."""

    def test_event_mark_processed(self) -> None:
        """Event should track processing."""
        event = LifecycleEvent(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            event_type=LifecycleEventType.TERMINATION,
        )

        assert event.processed is False
        event.mark_processed("Monitoring terminated")

        assert event.processed is True
        assert event.processed_at is not None
        assert event.processing_result == "Monitoring terminated"

    def test_event_to_dict(self) -> None:
        """Event should convert to dictionary."""
        event = LifecycleEvent(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            event_type=LifecycleEventType.PROMOTION,
            new_role_category=RoleCategory.EXECUTIVE,
            new_vigilance_level=VigilanceLevel.V3,
        )

        data = event.to_dict()

        assert data["event_type"] == "promotion"
        assert data["new_role_category"] == "executive"
        assert data["new_vigilance_level"] == "v3"


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Test create_monitoring_scheduler factory."""

    def test_create_with_defaults(self) -> None:
        """Create scheduler with default configuration."""
        scheduler = create_monitoring_scheduler()

        assert scheduler is not None
        assert isinstance(scheduler.store, InMemoryMonitoringStore)
        assert scheduler.config is not None

    def test_create_with_custom_config(self) -> None:
        """Create scheduler with custom configuration."""
        config = SchedulerConfig(
            v1_interval=timedelta(days=180),
            enable_alerts=False,
        )
        scheduler = create_monitoring_scheduler(config=config)

        assert scheduler.config.v1_interval == timedelta(days=180)
        assert scheduler.config.enable_alerts is False

    def test_create_with_custom_store(self, store: InMemoryMonitoringStore) -> None:
        """Create scheduler with custom store."""
        scheduler = create_monitoring_scheduler(store=store)

        assert scheduler.store is store


# =============================================================================
# InMemoryMonitoringStore Tests
# =============================================================================


class TestInMemoryStore:
    """Test InMemoryMonitoringStore implementation."""

    @pytest.mark.anyio
    async def test_save_and_get_config(self, store: InMemoryMonitoringStore) -> None:
        """Save and retrieve configuration."""
        config = MonitoringConfig(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=uuid7(),
        )

        await store.save_config(config)
        retrieved = await store.get_config(config.config_id)

        assert retrieved is not None
        assert retrieved.config_id == config.config_id

    @pytest.mark.anyio
    async def test_get_config_by_subject(self, store: InMemoryMonitoringStore) -> None:
        """Retrieve configuration by subject ID."""
        subject_id = uuid7()
        tenant_id = uuid7()
        config = MonitoringConfig(
            subject_id=subject_id,
            tenant_id=tenant_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=uuid7(),
        )

        await store.save_config(config)
        retrieved = await store.get_config_by_subject(subject_id, tenant_id)

        assert retrieved is not None
        assert retrieved.subject_id == subject_id

    @pytest.mark.anyio
    async def test_get_due_checks(self, store: InMemoryMonitoringStore) -> None:
        """Get configurations with due checks."""
        now = datetime.now(UTC)

        # Due config
        due_config = MonitoringConfig(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=uuid7(),
            status=MonitoringStatus.ACTIVE,
            next_check_date=now - timedelta(hours=1),
        )

        # Not due config
        not_due_config = MonitoringConfig(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=uuid7(),
            status=MonitoringStatus.ACTIVE,
            next_check_date=now + timedelta(days=10),
        )

        await store.save_config(due_config)
        await store.save_config(not_due_config)

        due = await store.get_due_checks(now)

        assert len(due) == 1
        assert due[0].config_id == due_config.config_id

    @pytest.mark.anyio
    async def test_get_active_configs(self, store: InMemoryMonitoringStore) -> None:
        """Get active configurations for tenant."""
        tenant_id = uuid7()

        active_config = MonitoringConfig(
            subject_id=uuid7(),
            tenant_id=tenant_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=uuid7(),
            status=MonitoringStatus.ACTIVE,
        )

        paused_config = MonitoringConfig(
            subject_id=uuid7(),
            tenant_id=tenant_id,
            vigilance_level=VigilanceLevel.V2,
            baseline_profile_id=uuid7(),
            status=MonitoringStatus.PAUSED,
        )

        await store.save_config(active_config)
        await store.save_config(paused_config)

        active = await store.get_active_configs(tenant_id)

        assert len(active) == 1
        assert active[0].config_id == active_config.config_id

    @pytest.mark.anyio
    async def test_save_and_get_checks(self, store: InMemoryMonitoringStore) -> None:
        """Save and retrieve checks."""
        config_id = uuid7()

        check1 = MonitoringCheck(monitoring_config_id=config_id, check_type=CheckType.SCHEDULED)
        check2 = MonitoringCheck(monitoring_config_id=config_id, check_type=CheckType.TRIGGERED)

        await store.save_check(check1)
        await store.save_check(check2)

        checks = await store.get_checks(config_id)

        assert len(checks) == 2
