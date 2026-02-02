"""Monitoring scheduler for ongoing employee vigilance checks.

Manages scheduling based on vigilance levels (V1/V2/V3), executes periodic
checks, and handles employee lifecycle events.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from elile.agent.state import SearchDegree, ServiceTier, VigilanceLevel
from elile.compliance.types import Locale, RoleCategory
from elile.monitoring.types import (
    AlertSeverity,
    CheckStatus,
    CheckType,
    DeltaSeverity,
    LifecycleEvent,
    LifecycleEventType,
    MonitoringAlert,
    MonitoringCheck,
    MonitoringConfig,
    MonitoringConfigError,
    MonitoringExecutionError,
    MonitoringLifecycleError,
    MonitoringStatus,
    ProfileDelta,
    ScheduleResult,
)

# =============================================================================
# Alert Thresholds by Vigilance Level
# =============================================================================

# Thresholds for auto-alert by vigilance level
AUTO_ALERT_THRESHOLDS: dict[VigilanceLevel, DeltaSeverity] = {
    VigilanceLevel.V1: DeltaSeverity.CRITICAL,  # V1: Only critical auto-alerts
    VigilanceLevel.V2: DeltaSeverity.HIGH,  # V2: High and above auto-alerts
    VigilanceLevel.V3: DeltaSeverity.MEDIUM,  # V3: Medium and above auto-alerts
}

# Thresholds for human review by vigilance level
HUMAN_REVIEW_THRESHOLDS: dict[VigilanceLevel, DeltaSeverity] = {
    VigilanceLevel.V1: DeltaSeverity.HIGH,  # V1: High and above for review
    VigilanceLevel.V2: DeltaSeverity.MEDIUM,  # V2: Medium and above for review
    VigilanceLevel.V3: DeltaSeverity.LOW,  # V3: All deltas for review
}


# =============================================================================
# Storage Protocol
# =============================================================================


class MonitoringStore(Protocol):
    """Protocol for monitoring configuration storage."""

    async def save_config(self, config: MonitoringConfig) -> None:
        """Save monitoring configuration."""
        ...

    async def get_config(self, config_id: UUID) -> MonitoringConfig | None:
        """Get monitoring configuration by ID."""
        ...

    async def get_config_by_subject(
        self, subject_id: UUID, tenant_id: UUID
    ) -> MonitoringConfig | None:
        """Get monitoring configuration by subject ID."""
        ...

    async def get_due_checks(self, as_of: datetime) -> list[MonitoringConfig]:
        """Get all configurations with due checks."""
        ...

    async def get_active_configs(self, tenant_id: UUID) -> list[MonitoringConfig]:
        """Get all active monitoring configurations for a tenant."""
        ...

    async def save_check(self, check: MonitoringCheck) -> None:
        """Save monitoring check record."""
        ...

    async def get_checks(self, config_id: UUID, limit: int = 10) -> list[MonitoringCheck]:
        """Get recent checks for a configuration."""
        ...

    async def save_lifecycle_event(self, event: LifecycleEvent) -> None:
        """Save lifecycle event."""
        ...


class InMemoryMonitoringStore:
    """In-memory implementation of MonitoringStore for testing."""

    def __init__(self) -> None:
        self._configs: dict[UUID, MonitoringConfig] = {}
        self._checks: dict[UUID, list[MonitoringCheck]] = {}
        self._events: list[LifecycleEvent] = []

    async def save_config(self, config: MonitoringConfig) -> None:
        """Save monitoring configuration."""
        self._configs[config.config_id] = config

    async def get_config(self, config_id: UUID) -> MonitoringConfig | None:
        """Get monitoring configuration by ID."""
        return self._configs.get(config_id)

    async def get_config_by_subject(
        self, subject_id: UUID, tenant_id: UUID
    ) -> MonitoringConfig | None:
        """Get monitoring configuration by subject ID."""
        for config in self._configs.values():
            if config.subject_id == subject_id and config.tenant_id == tenant_id:
                return config
        return None

    async def get_due_checks(self, as_of: datetime) -> list[MonitoringConfig]:
        """Get all configurations with due checks."""
        due = []
        for config in self._configs.values():
            if (
                config.status == MonitoringStatus.ACTIVE
                and config.next_check_date is not None
                and config.next_check_date <= as_of
            ):
                due.append(config)
        return due

    async def get_active_configs(self, tenant_id: UUID) -> list[MonitoringConfig]:
        """Get all active monitoring configurations for a tenant."""
        return [
            config
            for config in self._configs.values()
            if config.tenant_id == tenant_id and config.status == MonitoringStatus.ACTIVE
        ]

    async def save_check(self, check: MonitoringCheck) -> None:
        """Save monitoring check record."""
        config_id = check.monitoring_config_id
        if config_id not in self._checks:
            self._checks[config_id] = []
        self._checks[config_id].append(check)

    async def get_checks(self, config_id: UUID, limit: int = 10) -> list[MonitoringCheck]:
        """Get recent checks for a configuration."""
        checks = self._checks.get(config_id, [])
        # Sort by scheduled_at descending and return limited
        sorted_checks = sorted(checks, key=lambda c: c.scheduled_at, reverse=True)
        return sorted_checks[:limit]

    async def save_lifecycle_event(self, event: LifecycleEvent) -> None:
        """Save lifecycle event."""
        self._events.append(event)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class SchedulerConfig:
    """Configuration for the monitoring scheduler.

    Attributes:
        v1_interval: Interval for V1 (annual) checks.
        v2_interval: Interval for V2 (monthly) checks.
        v3_interval: Interval for V3 (bi-monthly) checks.
        auto_resume_paused: Auto-resume paused configs past pause_until.
        check_execution_timeout: Timeout for check execution.
        max_concurrent_checks: Maximum concurrent check executions.
        enable_alerts: Enable alert generation.
        enable_escalation: Enable alert escalation.
    """

    v1_interval: timedelta = field(default_factory=lambda: timedelta(days=365))
    v2_interval: timedelta = field(default_factory=lambda: timedelta(days=30))
    v3_interval: timedelta = field(default_factory=lambda: timedelta(days=15))
    auto_resume_paused: bool = True
    check_execution_timeout: timedelta = field(default_factory=lambda: timedelta(minutes=30))
    max_concurrent_checks: int = 10
    enable_alerts: bool = True
    enable_escalation: bool = True


# =============================================================================
# Monitoring Scheduler
# =============================================================================


class MonitoringScheduler:
    """Schedules and executes ongoing monitoring checks.

    Manages vigilance-level based scheduling (V1/V2/V3), executes periodic
    checks, detects profile deltas, and handles lifecycle events.

    Attributes:
        config: Scheduler configuration.
        store: Storage backend for monitoring data.
    """

    # Vigilance level to interval mapping
    VIGILANCE_INTERVALS: dict[VigilanceLevel, timedelta] = {
        VigilanceLevel.V1: timedelta(days=365),  # Annual
        VigilanceLevel.V2: timedelta(days=30),  # Monthly
        VigilanceLevel.V3: timedelta(days=15),  # Bi-monthly (twice per month)
    }

    def __init__(
        self,
        store: MonitoringStore,
        config: SchedulerConfig | None = None,
    ) -> None:
        """Initialize the monitoring scheduler.

        Args:
            store: Storage backend for monitoring configurations.
            config: Optional scheduler configuration.
        """
        self.config = config or SchedulerConfig()
        self.store = store

        # Update intervals from config if provided
        if self.config.v1_interval:
            self.VIGILANCE_INTERVALS[VigilanceLevel.V1] = self.config.v1_interval
        if self.config.v2_interval:
            self.VIGILANCE_INTERVALS[VigilanceLevel.V2] = self.config.v2_interval
        if self.config.v3_interval:
            self.VIGILANCE_INTERVALS[VigilanceLevel.V3] = self.config.v3_interval

    def get_interval(self, vigilance_level: VigilanceLevel) -> timedelta:
        """Get the check interval for a vigilance level.

        Args:
            vigilance_level: The vigilance level (V1/V2/V3).

        Returns:
            The timedelta interval between checks.

        Raises:
            MonitoringConfigError: If V0 is provided (no ongoing monitoring).
        """
        if vigilance_level == VigilanceLevel.V0:
            raise MonitoringConfigError("V0 vigilance level does not support ongoing monitoring")
        return self.VIGILANCE_INTERVALS.get(
            vigilance_level, self.VIGILANCE_INTERVALS[VigilanceLevel.V1]
        )

    async def schedule_monitoring(
        self,
        subject_id: UUID,
        vigilance_level: VigilanceLevel,
        baseline_profile_id: UUID,
        tenant_id: UUID,
        *,
        entity_id: UUID | None = None,
        service_tier: ServiceTier = ServiceTier.STANDARD,
        degrees: SearchDegree = SearchDegree.D1,
        locale: Locale = Locale.US,
        role_category: RoleCategory = RoleCategory.STANDARD,
        alert_recipients: list[str] | None = None,
        escalation_path: list[str] | None = None,
        sanctions_realtime: bool = False,
        adverse_media_continuous: bool = False,
        dark_web_monitoring: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> ScheduleResult:
        """Set up ongoing monitoring schedule for a subject.

        Creates a monitoring configuration with the specified vigilance level
        and schedules the first check.

        Args:
            subject_id: ID of the subject to monitor.
            vigilance_level: Monitoring frequency (V1/V2/V3).
            baseline_profile_id: Reference profile for delta detection.
            tenant_id: Tenant ID.
            entity_id: Optional associated entity ID.
            service_tier: Service tier (Standard/Enhanced).
            degrees: Search degree (D1/D2/D3).
            locale: Geographic jurisdiction.
            role_category: Job role category.
            alert_recipients: Email addresses for alerts.
            escalation_path: Escalation recipients.
            sanctions_realtime: Enable real-time sanctions (V3 only).
            adverse_media_continuous: Enable continuous adverse media (V3 only).
            dark_web_monitoring: Enable dark web monitoring (Enhanced V3 only).
            metadata: Additional configuration metadata.

        Returns:
            ScheduleResult with the configuration details.

        Raises:
            MonitoringConfigError: If configuration is invalid.
        """
        if vigilance_level == VigilanceLevel.V0:
            return ScheduleResult(
                success=False,
                error="V0 vigilance level does not support ongoing monitoring",
                message="No monitoring scheduled for V0",
            )

        try:
            interval = self.get_interval(vigilance_level)
            next_check = datetime.now(UTC) + interval

            config = MonitoringConfig(
                subject_id=subject_id,
                entity_id=entity_id,
                tenant_id=tenant_id,
                vigilance_level=vigilance_level,
                service_tier=service_tier,
                degrees=degrees,
                locale=locale,
                role_category=role_category,
                baseline_profile_id=baseline_profile_id,
                status=MonitoringStatus.ACTIVE,
                next_check_date=next_check,
                alert_recipients=alert_recipients or [],
                escalation_path=escalation_path or [],
                sanctions_realtime=sanctions_realtime,
                adverse_media_continuous=adverse_media_continuous,
                dark_web_monitoring=dark_web_monitoring,
                metadata=metadata or {},
            )

            await self.store.save_config(config)

            return ScheduleResult(
                config_id=config.config_id,
                success=True,
                next_check_date=next_check,
                interval_days=interval.days,
                message=f"Monitoring scheduled with {vigilance_level.value} vigilance",
            )

        except ValueError as e:
            return ScheduleResult(
                success=False,
                error=str(e),
                message="Failed to create monitoring configuration",
            )

    async def execute_scheduled_checks(
        self,
        as_of: datetime | None = None,
    ) -> list[MonitoringCheck]:
        """Execute all due monitoring checks.

        Finds all monitoring configurations with due checks and executes them.

        Args:
            as_of: Reference time for determining due checks. Defaults to now.

        Returns:
            List of executed MonitoringCheck records.
        """
        as_of = as_of or datetime.now(UTC)
        due_configs = await self.store.get_due_checks(as_of)

        checks = []
        for config in due_configs:
            check = await self._execute_monitoring_check(config)
            checks.append(check)

        return checks

    async def _execute_monitoring_check(
        self,
        config: MonitoringConfig,
    ) -> MonitoringCheck:
        """Execute a single monitoring check.

        Performs the monitoring check, detects deltas, generates alerts,
        and updates the schedule for the next check.

        Args:
            config: The monitoring configuration to check.

        Returns:
            The executed MonitoringCheck record.
        """
        check = MonitoringCheck(
            monitoring_config_id=config.config_id,
            check_type=CheckType.SCHEDULED,
        )
        check.start()

        try:
            # Run screening with delta detection
            # In production, this would call the screening orchestrator
            # For now, we simulate a check
            deltas = await self._perform_delta_detection(config, check)

            # Generate alerts for significant deltas
            if self.config.enable_alerts and deltas:
                alerts = self._generate_alerts(config, check, deltas)
                check.alerts_generated = alerts
                config.alerts_generated += len(alerts)

            check.deltas_detected = deltas
            check.complete(CheckStatus.COMPLETED)

            # Update configuration
            config.last_check_date = datetime.now(UTC)
            config.checks_completed += 1

            # Schedule next check
            interval = self.get_interval(config.vigilance_level)
            config.next_check_date = datetime.now(UTC) + interval
            config.updated_at = datetime.now(UTC)

            await self.store.save_config(config)
            await self.store.save_check(check)

        except Exception as e:
            check.complete(CheckStatus.FAILED, error=str(e))
            await self.store.save_check(check)
            raise MonitoringExecutionError(
                f"Failed to execute monitoring check: {e}",
                details={"config_id": str(config.config_id)},
            ) from e

        return check

    async def _perform_delta_detection(
        self,
        config: MonitoringConfig,  # noqa: ARG002
        check: MonitoringCheck,
    ) -> list[ProfileDelta]:
        """Perform delta detection against baseline.

        This is a placeholder that would integrate with the screening
        orchestrator in production.

        Args:
            config: The monitoring configuration (used in production implementation).
            check: The check record being executed.

        Returns:
            List of detected profile deltas.
        """
        # In production, this would:
        # 1. Execute a screening against current data using config.baseline_profile_id
        # 2. Compare results to baseline profile
        # 3. Return detected differences
        #
        # For now, return empty list (no deltas)
        _ = config  # Will be used in production implementation
        check.data_sources_checked = 0
        check.queries_executed = 0
        return []

    def _generate_alerts(
        self,
        config: MonitoringConfig,
        check: MonitoringCheck,
        deltas: list[ProfileDelta],
    ) -> list[MonitoringAlert]:
        """Generate alerts based on detected deltas and thresholds.

        Args:
            config: The monitoring configuration.
            check: The check record.
            deltas: Detected profile deltas.

        Returns:
            List of generated alerts.
        """
        alerts: list[MonitoringAlert] = []
        auto_threshold = AUTO_ALERT_THRESHOLDS.get(config.vigilance_level, DeltaSeverity.CRITICAL)

        # Group deltas that meet threshold
        alert_deltas = [
            d for d in deltas if self._delta_meets_threshold(d.severity, auto_threshold)
        ]

        if not alert_deltas:
            return alerts

        # Determine overall alert severity
        max_severity = max(d.severity for d in alert_deltas)
        alert_severity = self._map_delta_to_alert_severity(max_severity)

        alert = MonitoringAlert(
            monitoring_config_id=config.config_id,
            check_id=check.check_id,
            severity=alert_severity,
            title=f"Monitoring Alert: {len(alert_deltas)} change(s) detected",
            description=self._build_alert_description(alert_deltas),
            delta_ids=[d.delta_id for d in alert_deltas],
            recipients_notified=list(config.alert_recipients),
        )

        # Check if escalation needed
        if self.config.enable_escalation and alert_severity in (
            AlertSeverity.CRITICAL,
            AlertSeverity.HIGH,
        ):
            alert.escalated = True
            alert.escalated_to = list(config.escalation_path)

        alerts.append(alert)
        return alerts

    def _delta_meets_threshold(
        self,
        delta_severity: DeltaSeverity,
        threshold: DeltaSeverity,
    ) -> bool:
        """Check if a delta severity meets the alert threshold.

        Args:
            delta_severity: The delta's severity.
            threshold: The threshold to meet.

        Returns:
            True if delta meets or exceeds threshold.
        """
        severity_order = [
            DeltaSeverity.POSITIVE,
            DeltaSeverity.LOW,
            DeltaSeverity.MEDIUM,
            DeltaSeverity.HIGH,
            DeltaSeverity.CRITICAL,
        ]
        return severity_order.index(delta_severity) >= severity_order.index(threshold)

    def _map_delta_to_alert_severity(
        self,
        delta_severity: DeltaSeverity,
    ) -> AlertSeverity:
        """Map delta severity to alert severity.

        Args:
            delta_severity: The delta severity.

        Returns:
            Corresponding alert severity.
        """
        mapping = {
            DeltaSeverity.CRITICAL: AlertSeverity.CRITICAL,
            DeltaSeverity.HIGH: AlertSeverity.HIGH,
            DeltaSeverity.MEDIUM: AlertSeverity.MEDIUM,
            DeltaSeverity.LOW: AlertSeverity.LOW,
            DeltaSeverity.POSITIVE: AlertSeverity.LOW,
        }
        return mapping.get(delta_severity, AlertSeverity.LOW)

    def _build_alert_description(self, deltas: list[ProfileDelta]) -> str:
        """Build alert description from deltas.

        Args:
            deltas: The deltas to describe.

        Returns:
            Formatted alert description.
        """
        lines = []
        for delta in deltas:
            lines.append(f"- [{delta.severity.value}] {delta.description}")
        return "\n".join(lines)

    async def handle_lifecycle_event(
        self,
        event: LifecycleEvent,
    ) -> MonitoringConfig | None:
        """Handle an employee lifecycle event.

        Processes lifecycle events from HRIS and updates monitoring
        configuration accordingly.

        Args:
            event: The lifecycle event to process.

        Returns:
            Updated monitoring configuration, or None if no config exists.

        Raises:
            MonitoringLifecycleError: If event processing fails.
        """
        config = await self.store.get_config_by_subject(event.subject_id, event.tenant_id)

        if config is None:
            event.mark_processed("No monitoring configuration found")
            await self.store.save_lifecycle_event(event)
            return None

        try:
            match event.event_type:
                case LifecycleEventType.TERMINATION:
                    config = await self._handle_termination(config, event)

                case LifecycleEventType.LEAVE_OF_ABSENCE:
                    config = await self._handle_leave_of_absence(config, event)

                case LifecycleEventType.RETURN_FROM_LEAVE:
                    config = await self._handle_return_from_leave(config, event)

                case LifecycleEventType.POSITION_CHANGE | LifecycleEventType.PROMOTION:
                    config = await self._handle_position_change(config, event)

                case LifecycleEventType.TRANSFER:
                    config = await self._handle_transfer(config, event)

                case LifecycleEventType.VIGILANCE_UPGRADE:
                    config = await self._handle_vigilance_change(config, event, upgrade=True)

                case LifecycleEventType.VIGILANCE_DOWNGRADE:
                    config = await self._handle_vigilance_change(config, event, upgrade=False)

                case LifecycleEventType.REHIRE:
                    config = await self._handle_rehire(config, event)

                case _:
                    event.mark_processed(f"Unknown event type: {event.event_type}")

            await self.store.save_lifecycle_event(event)
            return config

        except Exception as e:
            raise MonitoringLifecycleError(
                f"Failed to process lifecycle event: {e}",
                details={
                    "event_id": str(event.event_id),
                    "event_type": event.event_type.value,
                },
            ) from e

    async def _handle_termination(
        self,
        config: MonitoringConfig,
        event: LifecycleEvent,
    ) -> MonitoringConfig:
        """Handle employee termination.

        Stops monitoring and triggers retention policy.
        """
        config.status = MonitoringStatus.TERMINATED
        config.next_check_date = None
        config.updated_at = datetime.now(UTC)
        config.metadata["termination_date"] = event.event_date.isoformat()

        await self.store.save_config(config)
        event.mark_processed("Monitoring terminated")
        return config

    async def _handle_leave_of_absence(
        self,
        config: MonitoringConfig,
        event: LifecycleEvent,
    ) -> MonitoringConfig:
        """Handle leave of absence.

        Pauses monitoring until return or specified date.
        """
        config.status = MonitoringStatus.PAUSED
        config.pause_reason = event.description or "Leave of absence"
        if event.effective_date:
            # Resume 30 days after leave ends if no specific date
            config.pause_until = datetime.combine(
                event.effective_date + timedelta(days=30),
                datetime.min.time(),
                tzinfo=UTC,
            )
        config.updated_at = datetime.now(UTC)

        await self.store.save_config(config)
        event.mark_processed("Monitoring paused for leave")
        return config

    async def _handle_return_from_leave(
        self,
        config: MonitoringConfig,
        event: LifecycleEvent,
    ) -> MonitoringConfig:
        """Handle return from leave.

        Resumes monitoring and schedules immediate check.
        """
        if config.status == MonitoringStatus.PAUSED:
            config.status = MonitoringStatus.ACTIVE
            config.pause_reason = None
            config.pause_until = None
            # Schedule check for soon (within 1 day)
            config.next_check_date = datetime.now(UTC) + timedelta(days=1)
            config.updated_at = datetime.now(UTC)

            await self.store.save_config(config)
            event.mark_processed("Monitoring resumed from leave")
        else:
            event.mark_processed("Not currently paused")

        return config

    async def _handle_position_change(
        self,
        config: MonitoringConfig,
        event: LifecycleEvent,
    ) -> MonitoringConfig:
        """Handle position change or promotion.

        May update role category and vigilance level.
        """
        updated = False

        if event.new_role_category:
            config.role_category = event.new_role_category
            updated = True

        if event.new_vigilance_level:
            config.vigilance_level = event.new_vigilance_level
            # Recalculate next check based on new vigilance
            interval = self.get_interval(event.new_vigilance_level)
            config.next_check_date = datetime.now(UTC) + interval
            updated = True

        if updated:
            config.updated_at = datetime.now(UTC)
            await self.store.save_config(config)
            event.mark_processed("Position change applied")
        else:
            event.mark_processed("No monitoring changes needed")

        return config

    async def _handle_transfer(
        self,
        config: MonitoringConfig,
        event: LifecycleEvent,
    ) -> MonitoringConfig:
        """Handle employee transfer.

        Updates locale and re-applies compliance rules.
        """
        if event.new_locale:
            config.locale = event.new_locale
            config.updated_at = datetime.now(UTC)
            await self.store.save_config(config)
            event.mark_processed(f"Locale updated to {event.new_locale.value}")
        else:
            event.mark_processed("No locale change")

        return config

    async def _handle_vigilance_change(
        self,
        config: MonitoringConfig,
        event: LifecycleEvent,
        *,
        upgrade: bool,
    ) -> MonitoringConfig:
        """Handle vigilance level change.

        Upgrades or downgrades monitoring frequency.
        """
        if event.new_vigilance_level:
            old_level = config.vigilance_level
            config.vigilance_level = event.new_vigilance_level

            # Recalculate next check based on new level
            interval = self.get_interval(event.new_vigilance_level)
            config.next_check_date = datetime.now(UTC) + interval
            config.updated_at = datetime.now(UTC)

            # Disable V3 features if downgrading from V3
            if old_level == VigilanceLevel.V3 and event.new_vigilance_level != VigilanceLevel.V3:
                config.sanctions_realtime = False
                config.adverse_media_continuous = False

            await self.store.save_config(config)
            event.mark_processed(
                f"Vigilance {'upgraded' if upgrade else 'downgraded'} "
                f"from {old_level.value} to {event.new_vigilance_level.value}"
            )
        else:
            event.mark_processed("No new vigilance level specified")

        return config

    async def _handle_rehire(
        self,
        config: MonitoringConfig,
        event: LifecycleEvent,
    ) -> MonitoringConfig:
        """Handle employee rehire.

        Resumes monitoring with new baseline.
        """
        config.status = MonitoringStatus.ACTIVE
        config.pause_reason = None
        config.pause_until = None

        # Apply any new configuration from event
        if event.new_locale:
            config.locale = event.new_locale
        if event.new_role_category:
            config.role_category = event.new_role_category
        if event.new_vigilance_level:
            config.vigilance_level = event.new_vigilance_level

        # Schedule immediate baseline check
        config.next_check_date = datetime.now(UTC) + timedelta(days=1)
        config.updated_at = datetime.now(UTC)
        config.metadata["rehire_date"] = event.event_date.isoformat()

        await self.store.save_config(config)
        event.mark_processed("Monitoring resumed for rehire")
        return config

    async def pause_monitoring(
        self,
        config_id: UUID,
        reason: str,
        until: datetime | None = None,
    ) -> MonitoringConfig:
        """Pause monitoring for a subject.

        Args:
            config_id: The monitoring configuration ID.
            reason: Reason for pausing.
            until: Optional datetime to auto-resume.

        Returns:
            Updated monitoring configuration.

        Raises:
            MonitoringConfigError: If configuration not found.
        """
        config = await self.store.get_config(config_id)
        if config is None:
            raise MonitoringConfigError(f"Monitoring configuration not found: {config_id}")

        config.status = MonitoringStatus.PAUSED
        config.pause_reason = reason
        config.pause_until = until
        config.updated_at = datetime.now(UTC)

        await self.store.save_config(config)
        return config

    async def resume_monitoring(
        self,
        config_id: UUID,
        immediate_check: bool = False,
    ) -> MonitoringConfig:
        """Resume paused monitoring.

        Args:
            config_id: The monitoring configuration ID.
            immediate_check: Schedule check immediately if True.

        Returns:
            Updated monitoring configuration.

        Raises:
            MonitoringConfigError: If configuration not found.
        """
        config = await self.store.get_config(config_id)
        if config is None:
            raise MonitoringConfigError(f"Monitoring configuration not found: {config_id}")

        if config.status != MonitoringStatus.PAUSED:
            raise MonitoringConfigError(f"Configuration is not paused: {config.status.value}")

        config.status = MonitoringStatus.ACTIVE
        config.pause_reason = None
        config.pause_until = None

        if immediate_check:
            config.next_check_date = datetime.now(UTC)
        else:
            interval = self.get_interval(config.vigilance_level)
            config.next_check_date = datetime.now(UTC) + interval

        config.updated_at = datetime.now(UTC)
        await self.store.save_config(config)
        return config

    async def terminate_monitoring(
        self,
        config_id: UUID,
        reason: str | None = None,
    ) -> MonitoringConfig:
        """Terminate monitoring for a subject.

        Args:
            config_id: The monitoring configuration ID.
            reason: Optional termination reason.

        Returns:
            Updated monitoring configuration.

        Raises:
            MonitoringConfigError: If configuration not found.
        """
        config = await self.store.get_config(config_id)
        if config is None:
            raise MonitoringConfigError(f"Monitoring configuration not found: {config_id}")

        config.status = MonitoringStatus.TERMINATED
        config.next_check_date = None
        config.updated_at = datetime.now(UTC)
        if reason:
            config.metadata["termination_reason"] = reason

        await self.store.save_config(config)
        return config

    async def update_vigilance_level(
        self,
        config_id: UUID,
        new_level: VigilanceLevel,
    ) -> MonitoringConfig:
        """Update the vigilance level for a monitoring configuration.

        Args:
            config_id: The monitoring configuration ID.
            new_level: The new vigilance level.

        Returns:
            Updated monitoring configuration.

        Raises:
            MonitoringConfigError: If configuration not found or V0 specified.
        """
        if new_level == VigilanceLevel.V0:
            raise MonitoringConfigError(
                "Cannot change to V0 vigilance level. Use terminate_monitoring instead."
            )

        config = await self.store.get_config(config_id)
        if config is None:
            raise MonitoringConfigError(f"Monitoring configuration not found: {config_id}")

        old_level = config.vigilance_level
        config.vigilance_level = new_level

        # Recalculate next check
        interval = self.get_interval(new_level)
        config.next_check_date = datetime.now(UTC) + interval

        # Disable V3 features if downgrading from V3
        if old_level == VigilanceLevel.V3 and new_level != VigilanceLevel.V3:
            config.sanctions_realtime = False
            config.adverse_media_continuous = False

        config.updated_at = datetime.now(UTC)
        await self.store.save_config(config)
        return config

    async def get_monitoring_status(
        self,
        config_id: UUID,
    ) -> dict[str, Any]:
        """Get the current monitoring status for a configuration.

        Args:
            config_id: The monitoring configuration ID.

        Returns:
            Dictionary with status information.

        Raises:
            MonitoringConfigError: If configuration not found.
        """
        config = await self.store.get_config(config_id)
        if config is None:
            raise MonitoringConfigError(f"Monitoring configuration not found: {config_id}")

        recent_checks = await self.store.get_checks(config_id, limit=5)

        return {
            "config_id": str(config.config_id),
            "subject_id": str(config.subject_id),
            "status": config.status.value,
            "vigilance_level": config.vigilance_level.value,
            "next_check_date": (
                config.next_check_date.isoformat() if config.next_check_date else None
            ),
            "last_check_date": (
                config.last_check_date.isoformat() if config.last_check_date else None
            ),
            "checks_completed": config.checks_completed,
            "alerts_generated": config.alerts_generated,
            "recent_checks": [c.to_dict() for c in recent_checks],
        }

    async def trigger_immediate_check(
        self,
        config_id: UUID,
        reason: str | None = None,
    ) -> MonitoringCheck:
        """Trigger an immediate monitoring check.

        Args:
            config_id: The monitoring configuration ID.
            reason: Optional reason for triggering.

        Returns:
            The executed MonitoringCheck record.

        Raises:
            MonitoringConfigError: If configuration not found or not active.
        """
        config = await self.store.get_config(config_id)
        if config is None:
            raise MonitoringConfigError(f"Monitoring configuration not found: {config_id}")

        if config.status != MonitoringStatus.ACTIVE:
            raise MonitoringConfigError(
                f"Cannot trigger check for {config.status.value} configuration"
            )

        check = MonitoringCheck(
            monitoring_config_id=config.config_id,
            check_type=CheckType.TRIGGERED,
            metadata={"trigger_reason": reason} if reason else {},
        )
        check.start()

        try:
            deltas = await self._perform_delta_detection(config, check)

            if self.config.enable_alerts and deltas:
                alerts = self._generate_alerts(config, check, deltas)
                check.alerts_generated = alerts
                config.alerts_generated += len(alerts)

            check.deltas_detected = deltas
            check.complete(CheckStatus.COMPLETED)

            config.last_check_date = datetime.now(UTC)
            config.checks_completed += 1
            config.updated_at = datetime.now(UTC)

            await self.store.save_config(config)
            await self.store.save_check(check)

        except Exception as e:
            check.complete(CheckStatus.FAILED, error=str(e))
            await self.store.save_check(check)
            raise MonitoringExecutionError(
                f"Failed to execute triggered check: {e}",
                details={"config_id": str(config.config_id)},
            ) from e

        return check


# =============================================================================
# Factory Function
# =============================================================================


def create_monitoring_scheduler(
    store: MonitoringStore | None = None,
    config: SchedulerConfig | None = None,
) -> MonitoringScheduler:
    """Create a monitoring scheduler with default or provided components.

    Args:
        store: Optional storage backend. Uses in-memory store if not provided.
        config: Optional scheduler configuration.

    Returns:
        Configured MonitoringScheduler instance.
    """
    return MonitoringScheduler(
        store=store or InMemoryMonitoringStore(),
        config=config,
    )
