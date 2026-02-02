"""Vigilance level manager for determining and updating monitoring levels.

Manages vigilance level assignments based on role category and risk score,
handles position changes, and coordinates with the scheduler for rescheduling.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol
from uuid import UUID, uuid7

from elile.agent.state import VigilanceLevel
from elile.compliance.types import RoleCategory
from elile.monitoring.types import (
    LifecycleEvent,
    LifecycleEventType,
    MonitoringConfig,
    MonitoringConfigError,
)

# =============================================================================
# Role-Based Default Vigilance Levels
# =============================================================================

# Default vigilance levels by role category
# Higher-risk roles get more frequent monitoring
ROLE_DEFAULT_VIGILANCE: dict[RoleCategory, VigilanceLevel] = {
    # Critical roles - V3 (bi-monthly, 15 days)
    RoleCategory.GOVERNMENT: VigilanceLevel.V3,
    RoleCategory.SECURITY: VigilanceLevel.V3,
    # High-sensitivity roles - V2 (monthly, 30 days)
    RoleCategory.EXECUTIVE: VigilanceLevel.V2,
    RoleCategory.FINANCIAL: VigilanceLevel.V2,
    RoleCategory.HEALTHCARE: VigilanceLevel.V2,
    # Medium-sensitivity roles - V2 (monthly)
    RoleCategory.EDUCATION: VigilanceLevel.V2,
    RoleCategory.TRANSPORTATION: VigilanceLevel.V2,
    # Standard roles - V1 (annual, 365 days)
    RoleCategory.STANDARD: VigilanceLevel.V1,
    RoleCategory.CONTRACTOR: VigilanceLevel.V1,
}


# =============================================================================
# Risk Score Thresholds
# =============================================================================

# Risk score thresholds for vigilance escalation
# Risk scores are 0-100 from the risk analysis module
RISK_THRESHOLD_V3 = 75  # Critical risk - escalate to V3
RISK_THRESHOLD_V2 = 50  # High risk - at least V2


# =============================================================================
# Enums and Types
# =============================================================================


class VigilanceChangeReason(str, Enum):
    """Reasons for vigilance level changes."""

    INITIAL_ASSIGNMENT = "initial_assignment"  # First-time assignment
    ROLE_CHANGE = "role_change"  # Job role changed
    RISK_ESCALATION = "risk_escalation"  # Risk score increased
    RISK_DE_ESCALATION = "risk_de_escalation"  # Risk score decreased
    MANUAL_OVERRIDE = "manual_override"  # Administrator override
    POLICY_UPDATE = "policy_update"  # Organizational policy change
    PERIODIC_REVIEW = "periodic_review"  # Scheduled review resulted in change


class EscalationAction(str, Enum):
    """Actions for escalation handling."""

    UPGRADE = "upgrade"  # Increase vigilance level
    DOWNGRADE = "downgrade"  # Decrease vigilance level
    MAINTAIN = "maintain"  # Keep current level
    IMMEDIATE_CHECK = "immediate_check"  # Trigger immediate check


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class VigilanceDecision:
    """Result of a vigilance level determination.

    Captures the decision, factors, and audit trail for vigilance assignments.
    """

    decision_id: UUID = field(default_factory=uuid7)
    subject_id: UUID = field(default_factory=uuid7)
    tenant_id: UUID = field(default_factory=uuid7)

    # Decision
    recommended_level: VigilanceLevel = VigilanceLevel.V1
    previous_level: VigilanceLevel | None = None
    reason: VigilanceChangeReason = VigilanceChangeReason.INITIAL_ASSIGNMENT

    # Factors
    role_category: RoleCategory = RoleCategory.STANDARD
    role_default_level: VigilanceLevel = VigilanceLevel.V1
    risk_score: int | None = None
    risk_escalated: bool = False
    risk_escalation_reason: str | None = None

    # Result
    level_changed: bool = False
    action: EscalationAction = EscalationAction.MAINTAIN

    # Metadata
    decided_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    decided_by: str = "system"  # "system" or user ID
    notes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "decision_id": str(self.decision_id),
            "subject_id": str(self.subject_id),
            "tenant_id": str(self.tenant_id),
            "recommended_level": self.recommended_level.value,
            "previous_level": self.previous_level.value if self.previous_level else None,
            "reason": self.reason.value,
            "role_category": self.role_category.value,
            "role_default_level": self.role_default_level.value,
            "risk_score": self.risk_score,
            "risk_escalated": self.risk_escalated,
            "risk_escalation_reason": self.risk_escalation_reason,
            "level_changed": self.level_changed,
            "action": self.action.value,
            "decided_at": self.decided_at.isoformat(),
            "decided_by": self.decided_by,
            "notes": self.notes,
            "metadata": self.metadata,
        }


@dataclass
class VigilanceUpdate:
    """Result of a vigilance level update operation.

    Captures the outcome when applying a vigilance change to a monitoring config.
    """

    update_id: UUID = field(default_factory=uuid7)
    config_id: UUID = field(default_factory=uuid7)
    subject_id: UUID = field(default_factory=uuid7)

    # Update details
    success: bool = True
    previous_level: VigilanceLevel | None = None
    new_level: VigilanceLevel = VigilanceLevel.V1
    reason: VigilanceChangeReason = VigilanceChangeReason.MANUAL_OVERRIDE

    # Rescheduling
    rescheduled: bool = False
    next_check_date: datetime | None = None
    immediate_check_triggered: bool = False

    # Error handling
    error: str | None = None

    # Metadata
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_by: str = "system"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "update_id": str(self.update_id),
            "config_id": str(self.config_id),
            "subject_id": str(self.subject_id),
            "success": self.success,
            "previous_level": self.previous_level.value if self.previous_level else None,
            "new_level": self.new_level.value,
            "reason": self.reason.value,
            "rescheduled": self.rescheduled,
            "next_check_date": self.next_check_date.isoformat() if self.next_check_date else None,
            "immediate_check_triggered": self.immediate_check_triggered,
            "error": self.error,
            "updated_at": self.updated_at.isoformat(),
            "updated_by": self.updated_by,
        }


@dataclass
class RoleVigilanceMapping:
    """Mapping between role category and vigilance level for an organization.

    Allows organizations to customize role-based vigilance assignments.
    """

    tenant_id: UUID = field(default_factory=uuid7)
    role_category: RoleCategory = RoleCategory.STANDARD
    vigilance_level: VigilanceLevel = VigilanceLevel.V1
    risk_threshold_override: int | None = None  # Override risk escalation threshold
    notes: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ManagerConfig:
    """Configuration for the VigilanceManager.

    Attributes:
        risk_threshold_v3: Risk score threshold for V3 escalation.
        risk_threshold_v2: Risk score threshold for V2 escalation.
        allow_manual_downgrade: Allow manual downgrade below risk level.
        auto_escalate_on_risk: Automatically escalate when risk exceeds threshold.
        trigger_check_on_upgrade: Trigger immediate check when upgrading.
        trigger_check_on_downgrade: Trigger check when downgrading.
        preserve_v3_features: Keep V3 features when downgrading from V3.
    """

    risk_threshold_v3: int = RISK_THRESHOLD_V3
    risk_threshold_v2: int = RISK_THRESHOLD_V2
    allow_manual_downgrade: bool = True
    auto_escalate_on_risk: bool = True
    trigger_check_on_upgrade: bool = True
    trigger_check_on_downgrade: bool = False
    preserve_v3_features: bool = False


# =============================================================================
# Scheduler Protocol
# =============================================================================


class SchedulerProtocol(Protocol):
    """Protocol for the monitoring scheduler interface.

    Allows VigilanceManager to work with the MonitoringScheduler
    without direct dependency.
    """

    async def update_vigilance_level(
        self,
        config_id: UUID,
        new_level: VigilanceLevel,
    ) -> MonitoringConfig:
        """Update vigilance level for a monitoring configuration."""
        ...

    async def trigger_immediate_check(
        self,
        config_id: UUID,
        reason: str | None = None,
    ) -> Any:
        """Trigger an immediate monitoring check."""
        ...


# =============================================================================
# Vigilance Manager
# =============================================================================


class VigilanceManager:
    """Manages vigilance level assignments and transitions.

    Determines appropriate vigilance levels based on role category and risk
    score, handles position changes, and coordinates with the scheduler
    for rescheduling checks.

    Attributes:
        config: Manager configuration.
        scheduler: Optional scheduler for applying updates.
        tenant_mappings: Custom role-to-vigilance mappings by tenant.
    """

    def __init__(
        self,
        scheduler: SchedulerProtocol | None = None,
        config: ManagerConfig | None = None,
    ) -> None:
        """Initialize the vigilance manager.

        Args:
            scheduler: Optional scheduler for applying updates.
            config: Manager configuration.
        """
        self.config = config or ManagerConfig()
        self.scheduler = scheduler
        self._tenant_mappings: dict[UUID, dict[RoleCategory, RoleVigilanceMapping]] = {}
        self._decision_history: list[VigilanceDecision] = []

    def get_role_default(
        self,
        role_category: RoleCategory,
        tenant_id: UUID | None = None,
    ) -> VigilanceLevel:
        """Get the default vigilance level for a role category.

        Checks tenant-specific mappings first, then falls back to
        system defaults.

        Args:
            role_category: The job role category.
            tenant_id: Optional tenant ID for custom mappings.

        Returns:
            The default vigilance level for the role.
        """
        # Check tenant-specific mapping
        if tenant_id and tenant_id in self._tenant_mappings:
            tenant_map = self._tenant_mappings[tenant_id]
            if role_category in tenant_map:
                return tenant_map[role_category].vigilance_level

        # Fall back to system defaults
        return ROLE_DEFAULT_VIGILANCE.get(role_category, VigilanceLevel.V1)

    def set_tenant_mapping(
        self,
        tenant_id: UUID,
        role_category: RoleCategory,
        vigilance_level: VigilanceLevel,
        risk_threshold_override: int | None = None,
        notes: str | None = None,
    ) -> RoleVigilanceMapping:
        """Set a custom role-to-vigilance mapping for a tenant.

        Args:
            tenant_id: The tenant ID.
            role_category: The role category to map.
            vigilance_level: The vigilance level to assign.
            risk_threshold_override: Optional risk threshold override.
            notes: Optional notes about the mapping.

        Returns:
            The created mapping.
        """
        if tenant_id not in self._tenant_mappings:
            self._tenant_mappings[tenant_id] = {}

        mapping = RoleVigilanceMapping(
            tenant_id=tenant_id,
            role_category=role_category,
            vigilance_level=vigilance_level,
            risk_threshold_override=risk_threshold_override,
            notes=notes,
        )
        self._tenant_mappings[tenant_id][role_category] = mapping
        return mapping

    def clear_tenant_mappings(self, tenant_id: UUID) -> None:
        """Clear all custom mappings for a tenant.

        Args:
            tenant_id: The tenant ID.
        """
        if tenant_id in self._tenant_mappings:
            del self._tenant_mappings[tenant_id]

    def determine_vigilance_level(
        self,
        role_category: RoleCategory,
        risk_score: int | None = None,
        current_level: VigilanceLevel | None = None,
        tenant_id: UUID | None = None,
        subject_id: UUID | None = None,
    ) -> VigilanceDecision:
        """Determine appropriate vigilance level based on role and risk.

        The vigilance level is determined by:
        1. Start with the role-based default
        2. Escalate if risk score exceeds thresholds
        3. Never downgrade automatically based on risk (requires explicit action)

        Args:
            role_category: The subject's job role category.
            risk_score: Optional risk score (0-100) from risk analysis.
            current_level: The subject's current vigilance level, if any.
            tenant_id: Optional tenant ID for custom mappings.
            subject_id: Optional subject ID for audit trail.

        Returns:
            VigilanceDecision with the recommended level and reasoning.
        """
        decision = VigilanceDecision(
            subject_id=subject_id or uuid7(),
            tenant_id=tenant_id or uuid7(),
            role_category=role_category,
            risk_score=risk_score,
            previous_level=current_level,
        )

        # Get role-based default
        role_default = self.get_role_default(role_category, tenant_id)
        decision.role_default_level = role_default
        decision.recommended_level = role_default

        # Determine reason
        if current_level is None:
            decision.reason = VigilanceChangeReason.INITIAL_ASSIGNMENT
        else:
            decision.reason = VigilanceChangeReason.ROLE_CHANGE

        # Check for risk-based escalation
        if risk_score is not None and self.config.auto_escalate_on_risk:
            decision = self._apply_risk_escalation(decision, risk_score, tenant_id, role_category)

        # Determine if level changed
        if current_level is not None:
            decision.level_changed = decision.recommended_level != current_level
            decision.action = self._determine_action(current_level, decision.recommended_level)
        else:
            decision.level_changed = True
            decision.action = EscalationAction.UPGRADE

        # Store in history
        self._decision_history.append(decision)

        return decision

    def _apply_risk_escalation(
        self,
        decision: VigilanceDecision,
        risk_score: int,
        tenant_id: UUID | None,
        role_category: RoleCategory,
    ) -> VigilanceDecision:
        """Apply risk-based escalation to a decision.

        Args:
            decision: The current decision.
            risk_score: The risk score (0-100).
            tenant_id: Optional tenant ID for threshold overrides.
            role_category: The role category.

        Returns:
            Updated decision with risk escalation applied.
        """
        # Get thresholds (check for tenant override)
        threshold_v3 = self.config.risk_threshold_v3
        threshold_v2 = self.config.risk_threshold_v2

        if tenant_id and tenant_id in self._tenant_mappings:
            tenant_map = self._tenant_mappings[tenant_id]
            if role_category in tenant_map and tenant_map[role_category].risk_threshold_override:
                # Use the override as V2 threshold, V3 is V2 + 25
                threshold_v2 = tenant_map[role_category].risk_threshold_override or threshold_v2
                threshold_v3 = min(100, threshold_v2 + 25)

        # Check for V3 escalation
        if risk_score >= threshold_v3:
            if decision.recommended_level != VigilanceLevel.V3:
                decision.recommended_level = VigilanceLevel.V3
                decision.risk_escalated = True
                decision.risk_escalation_reason = (
                    f"Risk score {risk_score} exceeds V3 threshold ({threshold_v3})"
                )
                decision.reason = VigilanceChangeReason.RISK_ESCALATION
        # Check for V2 escalation
        elif (
            risk_score >= threshold_v2
            and self._compare_levels(decision.recommended_level, VigilanceLevel.V2) < 0
        ):
            decision.recommended_level = VigilanceLevel.V2
            decision.risk_escalated = True
            decision.risk_escalation_reason = (
                f"Risk score {risk_score} exceeds V2 threshold ({threshold_v2})"
            )
            decision.reason = VigilanceChangeReason.RISK_ESCALATION

        return decision

    def _compare_levels(
        self,
        level1: VigilanceLevel,
        level2: VigilanceLevel,
    ) -> int:
        """Compare two vigilance levels.

        Args:
            level1: First vigilance level.
            level2: Second vigilance level.

        Returns:
            -1 if level1 < level2, 0 if equal, 1 if level1 > level2.
            Higher vigilance = more frequent monitoring.
        """
        order = [VigilanceLevel.V0, VigilanceLevel.V1, VigilanceLevel.V2, VigilanceLevel.V3]
        idx1 = order.index(level1)
        idx2 = order.index(level2)
        return (idx1 > idx2) - (idx1 < idx2)

    def _determine_action(
        self,
        current: VigilanceLevel,
        recommended: VigilanceLevel,
    ) -> EscalationAction:
        """Determine the action based on level change.

        Args:
            current: Current vigilance level.
            recommended: Recommended vigilance level.

        Returns:
            The appropriate action.
        """
        comparison = self._compare_levels(recommended, current)
        if comparison > 0:
            return EscalationAction.UPGRADE
        elif comparison < 0:
            return EscalationAction.DOWNGRADE
        return EscalationAction.MAINTAIN

    def evaluate_for_escalation(
        self,
        monitoring_config: MonitoringConfig,
        new_risk_score: int,
    ) -> VigilanceDecision:
        """Evaluate if a monitoring config should be escalated based on new risk.

        This is called after a screening to check if vigilance should increase.

        Args:
            monitoring_config: The current monitoring configuration.
            new_risk_score: The new risk score from recent screening.

        Returns:
            VigilanceDecision with escalation recommendation.
        """
        return self.determine_vigilance_level(
            role_category=monitoring_config.role_category,
            risk_score=new_risk_score,
            current_level=monitoring_config.vigilance_level,
            tenant_id=monitoring_config.tenant_id,
            subject_id=monitoring_config.subject_id,
        )

    def evaluate_position_change(
        self,
        monitoring_config: MonitoringConfig,
        new_role_category: RoleCategory,
        risk_score: int | None = None,
    ) -> VigilanceDecision:
        """Evaluate vigilance level after a position change.

        Args:
            monitoring_config: The current monitoring configuration.
            new_role_category: The new role category.
            risk_score: Optional current risk score.

        Returns:
            VigilanceDecision with recommendation for the new role.
        """
        decision = self.determine_vigilance_level(
            role_category=new_role_category,
            risk_score=risk_score,
            current_level=monitoring_config.vigilance_level,
            tenant_id=monitoring_config.tenant_id,
            subject_id=monitoring_config.subject_id,
        )
        decision.reason = VigilanceChangeReason.ROLE_CHANGE
        return decision

    async def update_vigilance(
        self,
        config_id: UUID,
        new_level: VigilanceLevel,
        reason: VigilanceChangeReason,
        updated_by: str = "system",
        trigger_immediate_check: bool | None = None,
        previous_level: VigilanceLevel | None = None,
    ) -> VigilanceUpdate:
        """Update a subject's vigilance level.

        Applies the vigilance change through the scheduler and optionally
        triggers an immediate check.

        Args:
            config_id: The monitoring configuration ID.
            new_level: The new vigilance level.
            reason: Reason for the change.
            updated_by: Who is making the update.
            trigger_immediate_check: Override default immediate check behavior.
            previous_level: Previous vigilance level (for upgrade/downgrade detection).
                If not provided, cannot auto-detect upgrade/downgrade for check triggering.

        Returns:
            VigilanceUpdate with the result.

        Raises:
            MonitoringConfigError: If scheduler is not configured.
        """
        if self.scheduler is None:
            raise MonitoringConfigError(
                "Scheduler not configured. Cannot apply vigilance update.",
                details={"config_id": str(config_id)},
            )

        update = VigilanceUpdate(
            config_id=config_id,
            new_level=new_level,
            reason=reason,
            updated_by=updated_by,
            previous_level=previous_level,
        )

        try:
            # Apply the update through the scheduler
            config = await self.scheduler.update_vigilance_level(config_id, new_level)
            update.subject_id = config.subject_id
            update.rescheduled = True
            update.next_check_date = config.next_check_date

            # Determine if we should trigger immediate check
            # Note: previous_level must be passed in; scheduler returns config with NEW level
            should_check = False
            if trigger_immediate_check is not None:
                should_check = trigger_immediate_check
            elif previous_level is not None:
                if self._is_upgrade(previous_level, new_level):
                    should_check = self.config.trigger_check_on_upgrade
                elif self._is_downgrade(previous_level, new_level):
                    should_check = self.config.trigger_check_on_downgrade

            if should_check:
                await self.scheduler.trigger_immediate_check(
                    config_id, reason=f"Vigilance {reason.value}"
                )
                update.immediate_check_triggered = True

            update.success = True

        except Exception as e:
            update.success = False
            update.error = str(e)

        return update

    def _is_upgrade(
        self,
        old_level: VigilanceLevel | None,
        new_level: VigilanceLevel,
    ) -> bool:
        """Check if a level change is an upgrade.

        Args:
            old_level: Previous level.
            new_level: New level.

        Returns:
            True if this is an upgrade (more frequent monitoring).
        """
        if old_level is None:
            return True
        return self._compare_levels(new_level, old_level) > 0

    def _is_downgrade(
        self,
        old_level: VigilanceLevel | None,
        new_level: VigilanceLevel,
    ) -> bool:
        """Check if a level change is a downgrade.

        Args:
            old_level: Previous level.
            new_level: New level.

        Returns:
            True if this is a downgrade (less frequent monitoring).
        """
        if old_level is None:
            return False
        return self._compare_levels(new_level, old_level) < 0

    async def apply_decision(
        self,
        decision: VigilanceDecision,
        config_id: UUID,
        updated_by: str = "system",
    ) -> VigilanceUpdate:
        """Apply a vigilance decision to a monitoring configuration.

        Args:
            decision: The vigilance decision to apply.
            config_id: The monitoring configuration ID.
            updated_by: Who is applying the decision.

        Returns:
            VigilanceUpdate with the result.
        """
        if not decision.level_changed:
            return VigilanceUpdate(
                config_id=config_id,
                subject_id=decision.subject_id,
                success=True,
                previous_level=decision.previous_level,
                new_level=decision.recommended_level,
                reason=decision.reason,
                rescheduled=False,
                updated_by=updated_by,
            )

        return await self.update_vigilance(
            config_id=config_id,
            new_level=decision.recommended_level,
            reason=decision.reason,
            updated_by=updated_by,
        )

    def create_position_change_event(
        self,
        subject_id: UUID,
        tenant_id: UUID,
        new_role_category: RoleCategory,
        new_vigilance_level: VigilanceLevel | None = None,
        description: str | None = None,
    ) -> LifecycleEvent:
        """Create a lifecycle event for a position change.

        Convenience method for creating position change events that
        will trigger vigilance reassessment.

        Args:
            subject_id: The subject ID.
            tenant_id: The tenant ID.
            new_role_category: The new role category.
            new_vigilance_level: Optional explicit new vigilance level.
            description: Optional description of the change.

        Returns:
            LifecycleEvent for the position change.
        """
        # Determine vigilance level if not provided
        if new_vigilance_level is None:
            decision = self.determine_vigilance_level(
                role_category=new_role_category,
                tenant_id=tenant_id,
                subject_id=subject_id,
            )
            new_vigilance_level = decision.recommended_level

        return LifecycleEvent(
            subject_id=subject_id,
            tenant_id=tenant_id,
            event_type=LifecycleEventType.POSITION_CHANGE,
            description=description or f"Position changed to {new_role_category.value}",
            new_role_category=new_role_category,
            new_vigilance_level=new_vigilance_level,
        )

    def create_promotion_event(
        self,
        subject_id: UUID,
        tenant_id: UUID,
        new_role_category: RoleCategory,
        new_vigilance_level: VigilanceLevel | None = None,
        description: str | None = None,
    ) -> LifecycleEvent:
        """Create a lifecycle event for a promotion.

        Similar to position change but specifically for promotions,
        which typically involve increased responsibility and higher vigilance.

        Args:
            subject_id: The subject ID.
            tenant_id: The tenant ID.
            new_role_category: The new role category.
            new_vigilance_level: Optional explicit new vigilance level.
            description: Optional description of the promotion.

        Returns:
            LifecycleEvent for the promotion.
        """
        # Determine vigilance level if not provided
        if new_vigilance_level is None:
            decision = self.determine_vigilance_level(
                role_category=new_role_category,
                tenant_id=tenant_id,
                subject_id=subject_id,
            )
            new_vigilance_level = decision.recommended_level

        return LifecycleEvent(
            subject_id=subject_id,
            tenant_id=tenant_id,
            event_type=LifecycleEventType.PROMOTION,
            description=description or f"Promoted to {new_role_category.value} role",
            new_role_category=new_role_category,
            new_vigilance_level=new_vigilance_level,
        )

    def create_vigilance_upgrade_event(
        self,
        subject_id: UUID,
        tenant_id: UUID,
        new_vigilance_level: VigilanceLevel,
        reason: str,
    ) -> LifecycleEvent:
        """Create a lifecycle event for a vigilance upgrade.

        Args:
            subject_id: The subject ID.
            tenant_id: The tenant ID.
            new_vigilance_level: The new vigilance level.
            reason: Reason for the upgrade.

        Returns:
            LifecycleEvent for the vigilance upgrade.
        """
        return LifecycleEvent(
            subject_id=subject_id,
            tenant_id=tenant_id,
            event_type=LifecycleEventType.VIGILANCE_UPGRADE,
            description=reason,
            new_vigilance_level=new_vigilance_level,
        )

    def create_vigilance_downgrade_event(
        self,
        subject_id: UUID,
        tenant_id: UUID,
        new_vigilance_level: VigilanceLevel,
        reason: str,
    ) -> LifecycleEvent:
        """Create a lifecycle event for a vigilance downgrade.

        Args:
            subject_id: The subject ID.
            tenant_id: The tenant ID.
            new_vigilance_level: The new vigilance level.
            reason: Reason for the downgrade.

        Returns:
            LifecycleEvent for the vigilance downgrade.
        """
        return LifecycleEvent(
            subject_id=subject_id,
            tenant_id=tenant_id,
            event_type=LifecycleEventType.VIGILANCE_DOWNGRADE,
            description=reason,
            new_vigilance_level=new_vigilance_level,
        )

    def get_decision_history(
        self,
        subject_id: UUID | None = None,
        tenant_id: UUID | None = None,
        limit: int = 50,
    ) -> list[VigilanceDecision]:
        """Get vigilance decision history.

        Args:
            subject_id: Optional filter by subject.
            tenant_id: Optional filter by tenant.
            limit: Maximum number of decisions to return.

        Returns:
            List of past decisions, most recent first.
        """
        history = self._decision_history

        if subject_id:
            history = [d for d in history if d.subject_id == subject_id]

        if tenant_id:
            history = [d for d in history if d.tenant_id == tenant_id]

        # Sort by decision time, most recent first
        history = sorted(history, key=lambda d: d.decided_at, reverse=True)

        return history[:limit]

    def get_escalation_recommendation(
        self,
        risk_score: int,
        current_level: VigilanceLevel,
    ) -> tuple[VigilanceLevel, str]:
        """Get escalation recommendation based on risk score.

        Simple helper to determine if escalation is needed without
        full decision context.

        Args:
            risk_score: Current risk score (0-100).
            current_level: Current vigilance level.

        Returns:
            Tuple of (recommended level, explanation).
        """
        if risk_score >= self.config.risk_threshold_v3 and current_level != VigilanceLevel.V3:
            return (
                VigilanceLevel.V3,
                f"Risk score {risk_score} indicates critical risk. "
                f"Recommend escalation to V3 bi-monthly monitoring.",
            )
        if (
            risk_score >= self.config.risk_threshold_v2
            and self._compare_levels(current_level, VigilanceLevel.V2) < 0
        ):
            return (
                VigilanceLevel.V2,
                f"Risk score {risk_score} indicates elevated risk. "
                f"Recommend escalation to V2 monthly monitoring.",
            )

        return (
            current_level,
            f"Risk score {risk_score} does not require escalation. "
            f"Maintain {current_level.value} monitoring.",
        )

    def validate_downgrade(
        self,
        current_level: VigilanceLevel,
        proposed_level: VigilanceLevel,
        risk_score: int | None,
        role_category: RoleCategory,
        tenant_id: UUID | None = None,
    ) -> tuple[bool, str]:
        """Validate if a downgrade is permitted.

        Checks if downgrading would violate risk or role requirements.

        Args:
            current_level: Current vigilance level.
            proposed_level: Proposed new level.
            risk_score: Current risk score.
            role_category: Role category.
            tenant_id: Optional tenant ID.

        Returns:
            Tuple of (is_valid, explanation).
        """
        if not self._is_downgrade(current_level, proposed_level):
            return (True, "Not a downgrade")

        if not self.config.allow_manual_downgrade:
            return (False, "Manual downgrades are not permitted by configuration")

        # Check if downgrade would violate role default
        role_default = self.get_role_default(role_category, tenant_id)
        if self._compare_levels(proposed_level, role_default) < 0:
            return (
                False,
                f"Proposed level {proposed_level.value} is below role default "
                f"{role_default.value} for {role_category.value} roles",
            )

        # Check if downgrade would violate risk threshold
        if risk_score is not None:
            if risk_score >= self.config.risk_threshold_v3 and proposed_level != VigilanceLevel.V3:
                return (
                    False,
                    f"Risk score {risk_score} requires V3 monitoring. "
                    f"Cannot downgrade to {proposed_level.value}",
                )
            if (
                risk_score >= self.config.risk_threshold_v2
                and self._compare_levels(proposed_level, VigilanceLevel.V2) < 0
            ):
                return (
                    False,
                    f"Risk score {risk_score} requires at least V2 monitoring. "
                    f"Cannot downgrade to {proposed_level.value}",
                )

        return (True, "Downgrade permitted")


# =============================================================================
# Factory Function
# =============================================================================


def create_vigilance_manager(
    scheduler: SchedulerProtocol | None = None,
    config: ManagerConfig | None = None,
) -> VigilanceManager:
    """Create a vigilance manager with default or provided configuration.

    Args:
        scheduler: Optional scheduler for applying updates.
        config: Optional manager configuration.

    Returns:
        Configured VigilanceManager instance.
    """
    return VigilanceManager(
        scheduler=scheduler,
        config=config,
    )
