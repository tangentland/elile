"""Configurable Risk Thresholds for organization-specific risk tolerance.

This module provides:
- Threshold configuration per organization, role, and locale
- Threshold breach detection and alerting
- Historical threshold tracking
- Default threshold templates
- Threshold inheritance (org -> role -> locale)
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import structlog
from pydantic import BaseModel, Field
from uuid_utils import UUID, uuid7

from elile.compliance.types import Locale, RoleCategory
from elile.risk.risk_scorer import Recommendation, RiskLevel

logger = structlog.get_logger()


# =============================================================================
# Enums
# =============================================================================


class ThresholdScope(str, Enum):
    """Scope at which thresholds apply."""

    GLOBAL = "global"  # System-wide defaults
    ORGANIZATION = "organization"  # Org-specific
    ROLE = "role"  # Role-specific within org
    LOCALE = "locale"  # Locale-specific within org


class BreachSeverity(str, Enum):
    """Severity of a threshold breach."""

    INFO = "info"  # Approaching threshold
    WARNING = "warning"  # At threshold
    ALERT = "alert"  # Exceeded threshold
    CRITICAL = "critical"  # Far exceeded threshold


class ThresholdAction(str, Enum):
    """Action to take on threshold breach."""

    LOG_ONLY = "log_only"
    NOTIFY = "notify"
    ESCALATE = "escalate"
    BLOCK = "block"


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class ThresholdSet:
    """A set of risk level thresholds.

    Defines the score boundaries for each risk level.
    """

    threshold_id: UUID = field(default_factory=uuid7)

    # Score thresholds (score >= threshold means that level)
    low_max: int = 39  # 0-39 = LOW
    moderate_max: int = 59  # 40-59 = MODERATE
    high_max: int = 79  # 60-79 = HIGH
    # 80+ = CRITICAL

    # Alert thresholds (approaching)
    approach_buffer: int = 5  # Alert when within 5 points

    # Version tracking
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def get_level_for_score(self, score: int) -> RiskLevel:
        """Get risk level for a given score."""
        if score <= self.low_max:
            return RiskLevel.LOW
        elif score <= self.moderate_max:
            return RiskLevel.MODERATE
        elif score <= self.high_max:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

    def get_threshold_for_level(self, level: RiskLevel) -> int:
        """Get the minimum score for a risk level."""
        if level == RiskLevel.LOW:
            return 0
        elif level == RiskLevel.MODERATE:
            return self.low_max + 1
        elif level == RiskLevel.HIGH:
            return self.moderate_max + 1
        else:  # CRITICAL
            return self.high_max + 1

    def is_approaching_threshold(self, score: int) -> tuple[bool, RiskLevel | None]:
        """Check if score is approaching a threshold."""
        thresholds = [
            (self.low_max + 1, RiskLevel.MODERATE),
            (self.moderate_max + 1, RiskLevel.HIGH),
            (self.high_max + 1, RiskLevel.CRITICAL),
        ]
        for threshold, level in thresholds:
            if threshold - self.approach_buffer <= score < threshold:
                return True, level
        return False, None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "threshold_id": str(self.threshold_id),
            "low_max": self.low_max,
            "moderate_max": self.moderate_max,
            "high_max": self.high_max,
            "approach_buffer": self.approach_buffer,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ThresholdSet":
        """Create from dictionary."""
        return cls(
            threshold_id=UUID(d["threshold_id"]) if "threshold_id" in d else uuid7(),
            low_max=d.get("low_max", 39),
            moderate_max=d.get("moderate_max", 59),
            high_max=d.get("high_max", 79),
            approach_buffer=d.get("approach_buffer", 5),
            version=d.get("version", 1),
        )


@dataclass
class ThresholdConfig:
    """Complete threshold configuration for an organization.

    Supports hierarchical configuration:
    - Base thresholds (org-wide)
    - Role-specific overrides
    - Locale-specific overrides
    """

    config_id: UUID = field(default_factory=uuid7)
    tenant_id: UUID | None = None

    # Scope
    scope: ThresholdScope = ThresholdScope.ORGANIZATION

    # Base thresholds
    base_thresholds: ThresholdSet = field(default_factory=ThresholdSet)

    # Role-specific overrides (role_category -> thresholds)
    role_overrides: dict[RoleCategory, ThresholdSet] = field(default_factory=dict)

    # Locale-specific overrides (locale -> thresholds)
    locale_overrides: dict[Locale, ThresholdSet] = field(default_factory=dict)

    # Actions for each breach severity
    breach_actions: dict[BreachSeverity, ThresholdAction] = field(
        default_factory=lambda: {
            BreachSeverity.INFO: ThresholdAction.LOG_ONLY,
            BreachSeverity.WARNING: ThresholdAction.NOTIFY,
            BreachSeverity.ALERT: ThresholdAction.ESCALATE,
            BreachSeverity.CRITICAL: ThresholdAction.BLOCK,
        }
    )

    # Notification settings
    notify_on_approach: bool = True
    notify_on_breach: bool = True
    notify_on_level_change: bool = True

    # Metadata
    name: str = "Default Configuration"
    description: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def get_thresholds(
        self,
        role: RoleCategory | None = None,
        locale: Locale | None = None,
    ) -> ThresholdSet:
        """Get applicable thresholds with inheritance.

        Priority: locale > role > base
        """
        # Start with base
        thresholds = self.base_thresholds

        # Apply role override if exists
        if role and role in self.role_overrides:
            thresholds = self.role_overrides[role]

        # Apply locale override if exists (highest priority)
        if locale and locale in self.locale_overrides:
            thresholds = self.locale_overrides[locale]

        return thresholds

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "config_id": str(self.config_id),
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "scope": self.scope.value,
            "base_thresholds": self.base_thresholds.to_dict(),
            "role_overrides": {
                role.value: ts.to_dict() for role, ts in self.role_overrides.items()
            },
            "locale_overrides": {
                locale.value: ts.to_dict() for locale, ts in self.locale_overrides.items()
            },
            "breach_actions": {
                sev.value: action.value for sev, action in self.breach_actions.items()
            },
            "notify_on_approach": self.notify_on_approach,
            "notify_on_breach": self.notify_on_breach,
            "notify_on_level_change": self.notify_on_level_change,
            "name": self.name,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class ThresholdBreach:
    """Record of a threshold breach event."""

    breach_id: UUID = field(default_factory=uuid7)
    entity_id: UUID | None = None
    screening_id: UUID | None = None
    tenant_id: UUID | None = None

    # Breach details
    score: int = 0
    previous_score: int | None = None
    previous_level: RiskLevel | None = None
    current_level: RiskLevel = RiskLevel.LOW
    threshold_crossed: int = 0

    # Severity and action
    severity: BreachSeverity = BreachSeverity.WARNING
    recommended_action: ThresholdAction = ThresholdAction.NOTIFY

    # Context
    breach_type: str = "threshold_crossed"  # threshold_crossed, level_change, approaching
    description: str = ""
    role: RoleCategory | None = None
    locale: Locale | None = None

    # Status
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None

    # Timing
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "breach_id": str(self.breach_id),
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "screening_id": str(self.screening_id) if self.screening_id else None,
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "score": self.score,
            "previous_score": self.previous_score,
            "previous_level": self.previous_level.value if self.previous_level else None,
            "current_level": self.current_level.value,
            "threshold_crossed": self.threshold_crossed,
            "severity": self.severity.value,
            "recommended_action": self.recommended_action.value,
            "breach_type": self.breach_type,
            "description": self.description,
            "role": self.role.value if self.role else None,
            "locale": self.locale.value if self.locale else None,
            "acknowledged": self.acknowledged,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class ThresholdHistory:
    """Historical record of threshold configuration changes."""

    history_id: UUID = field(default_factory=uuid7)
    config_id: UUID | None = None
    tenant_id: UUID | None = None

    # Change details
    change_type: str = "created"  # created, updated, activated, deactivated
    previous_thresholds: ThresholdSet | None = None
    new_thresholds: ThresholdSet | None = None

    # Change context
    changed_by: str = ""
    change_reason: str = ""

    # Timing
    changed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    effective_from: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "history_id": str(self.history_id),
            "config_id": str(self.config_id) if self.config_id else None,
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "change_type": self.change_type,
            "previous_thresholds": self.previous_thresholds.to_dict() if self.previous_thresholds else None,
            "new_thresholds": self.new_thresholds.to_dict() if self.new_thresholds else None,
            "changed_by": self.changed_by,
            "change_reason": self.change_reason,
            "changed_at": self.changed_at.isoformat(),
            "effective_from": self.effective_from.isoformat(),
        }


# =============================================================================
# Default Threshold Templates
# =============================================================================


# Standard thresholds (default)
STANDARD_THRESHOLDS = ThresholdSet(
    low_max=39,
    moderate_max=59,
    high_max=79,
)

# Conservative thresholds (stricter)
CONSERVATIVE_THRESHOLDS = ThresholdSet(
    low_max=29,
    moderate_max=49,
    high_max=69,
)

# Lenient thresholds (more tolerant)
LENIENT_THRESHOLDS = ThresholdSet(
    low_max=49,
    moderate_max=69,
    high_max=89,
)

# Role-specific templates
ROLE_THRESHOLD_TEMPLATES: dict[RoleCategory, ThresholdSet] = {
    # Government and security roles: conservative
    RoleCategory.GOVERNMENT: ThresholdSet(low_max=29, moderate_max=49, high_max=69),
    RoleCategory.SECURITY: ThresholdSet(low_max=29, moderate_max=49, high_max=69),
    # Financial roles: moderately conservative
    RoleCategory.FINANCIAL: ThresholdSet(low_max=34, moderate_max=54, high_max=74),
    # Healthcare: moderately conservative
    RoleCategory.HEALTHCARE: ThresholdSet(low_max=34, moderate_max=54, high_max=74),
    # Executive: standard
    RoleCategory.EXECUTIVE: ThresholdSet(low_max=39, moderate_max=59, high_max=79),
    # Standard roles: standard thresholds
    RoleCategory.STANDARD: ThresholdSet(low_max=39, moderate_max=59, high_max=79),
}


# =============================================================================
# Configuration
# =============================================================================


class ThresholdManagerConfig(BaseModel):
    """Configuration for threshold manager."""

    # Default thresholds
    default_low_max: int = Field(default=39, ge=10, le=50)
    default_moderate_max: int = Field(default=59, ge=30, le=70)
    default_high_max: int = Field(default=79, ge=50, le=95)

    # Approach buffer
    default_approach_buffer: int = Field(default=5, ge=1, le=15)

    # Breach detection
    detect_approaches: bool = Field(default=True)
    detect_level_changes: bool = Field(default=True)

    # Severity escalation thresholds
    critical_overage: int = Field(default=10, ge=5, le=30)  # Points over threshold for critical


# =============================================================================
# Threshold Manager
# =============================================================================


class ThresholdManager:
    """Manages risk thresholds and breach detection.

    The manager:
    1. Stores and retrieves threshold configurations
    2. Detects threshold breaches
    3. Tracks threshold history
    4. Provides templates for common configurations

    Example:
        manager = ThresholdManager()

        # Create org-specific config
        config = manager.create_config(
            tenant_id=org_id,
            name="Org Thresholds",
        )

        # Set role-specific thresholds
        manager.set_role_thresholds(
            config_id=config.config_id,
            role=RoleCategory.FINANCIAL,
            thresholds=CONSERVATIVE_THRESHOLDS,
        )

        # Check for breaches
        breaches = manager.detect_breaches(
            score=75,
            previous_score=55,
            config=config,
            role=RoleCategory.FINANCIAL,
        )
    """

    def __init__(self, config: ThresholdManagerConfig | None = None) -> None:
        """Initialize manager.

        Args:
            config: Optional manager configuration.
        """
        self.config = config or ThresholdManagerConfig()

        # In-memory storage (would be database in production)
        self._configs: dict[UUID, ThresholdConfig] = {}
        self._breaches: list[ThresholdBreach] = []
        self._history: list[ThresholdHistory] = []

        # Global default config
        self._global_config = ThresholdConfig(
            scope=ThresholdScope.GLOBAL,
            name="Global Defaults",
            base_thresholds=ThresholdSet(
                low_max=self.config.default_low_max,
                moderate_max=self.config.default_moderate_max,
                high_max=self.config.default_high_max,
                approach_buffer=self.config.default_approach_buffer,
            ),
        )

    def create_config(
        self,
        tenant_id: UUID,
        name: str = "Custom Configuration",
        description: str = "",
        base_thresholds: ThresholdSet | None = None,
    ) -> ThresholdConfig:
        """Create a new threshold configuration.

        Args:
            tenant_id: Organization tenant ID.
            name: Configuration name.
            description: Configuration description.
            base_thresholds: Base thresholds (defaults to global).

        Returns:
            Created ThresholdConfig.
        """
        config = ThresholdConfig(
            tenant_id=tenant_id,
            scope=ThresholdScope.ORGANIZATION,
            name=name,
            description=description,
            base_thresholds=base_thresholds or ThresholdSet(
                low_max=self.config.default_low_max,
                moderate_max=self.config.default_moderate_max,
                high_max=self.config.default_high_max,
            ),
        )

        self._configs[config.config_id] = config

        # Record history
        self._history.append(
            ThresholdHistory(
                config_id=config.config_id,
                tenant_id=tenant_id,
                change_type="created",
                new_thresholds=config.base_thresholds,
                change_reason="Initial configuration created",
            )
        )

        logger.info(
            "Created threshold config",
            config_id=str(config.config_id),
            tenant_id=str(tenant_id),
            name=name,
        )

        return config

    def get_config(self, config_id: UUID) -> ThresholdConfig | None:
        """Get a threshold configuration by ID."""
        return self._configs.get(config_id)

    def get_config_for_tenant(self, tenant_id: UUID) -> ThresholdConfig | None:
        """Get threshold configuration for a tenant."""
        for config in self._configs.values():
            if config.tenant_id == tenant_id and config.is_active:
                return config
        return None

    def get_effective_config(self, tenant_id: UUID | None = None) -> ThresholdConfig:
        """Get effective configuration, falling back to global."""
        if tenant_id:
            config = self.get_config_for_tenant(tenant_id)
            if config:
                return config
        return self._global_config

    def update_base_thresholds(
        self,
        config_id: UUID,
        thresholds: ThresholdSet,
        changed_by: str = "",
        change_reason: str = "",
    ) -> bool:
        """Update base thresholds for a configuration.

        Args:
            config_id: Configuration to update.
            thresholds: New thresholds.
            changed_by: User making the change.
            change_reason: Reason for change.

        Returns:
            True if updated successfully.
        """
        config = self._configs.get(config_id)
        if not config:
            return False

        # Record history
        self._history.append(
            ThresholdHistory(
                config_id=config_id,
                tenant_id=config.tenant_id,
                change_type="updated",
                previous_thresholds=config.base_thresholds,
                new_thresholds=thresholds,
                changed_by=changed_by,
                change_reason=change_reason,
            )
        )

        # Update
        config.base_thresholds = thresholds
        config.base_thresholds.version += 1
        config.base_thresholds.updated_at = datetime.now(UTC)
        config.updated_at = datetime.now(UTC)

        logger.info(
            "Updated base thresholds",
            config_id=str(config_id),
            changed_by=changed_by,
        )

        return True

    def set_role_thresholds(
        self,
        config_id: UUID,
        role: RoleCategory,
        thresholds: ThresholdSet,
        changed_by: str = "",
        change_reason: str = "",
    ) -> bool:
        """Set role-specific thresholds.

        Args:
            config_id: Configuration to update.
            role: Role category.
            thresholds: Thresholds for this role.
            changed_by: User making the change.
            change_reason: Reason for change.

        Returns:
            True if updated successfully.
        """
        config = self._configs.get(config_id)
        if not config:
            return False

        previous = config.role_overrides.get(role)

        # Record history
        self._history.append(
            ThresholdHistory(
                config_id=config_id,
                tenant_id=config.tenant_id,
                change_type="updated",
                previous_thresholds=previous,
                new_thresholds=thresholds,
                changed_by=changed_by,
                change_reason=f"Role override for {role.value}: {change_reason}",
            )
        )

        config.role_overrides[role] = thresholds
        config.updated_at = datetime.now(UTC)

        logger.info(
            "Set role thresholds",
            config_id=str(config_id),
            role=role.value,
        )

        return True

    def set_locale_thresholds(
        self,
        config_id: UUID,
        locale: Locale,
        thresholds: ThresholdSet,
        changed_by: str = "",
        change_reason: str = "",
    ) -> bool:
        """Set locale-specific thresholds.

        Args:
            config_id: Configuration to update.
            locale: Locale.
            thresholds: Thresholds for this locale.
            changed_by: User making the change.
            change_reason: Reason for change.

        Returns:
            True if updated successfully.
        """
        config = self._configs.get(config_id)
        if not config:
            return False

        previous = config.locale_overrides.get(locale)

        self._history.append(
            ThresholdHistory(
                config_id=config_id,
                tenant_id=config.tenant_id,
                change_type="updated",
                previous_thresholds=previous,
                new_thresholds=thresholds,
                changed_by=changed_by,
                change_reason=f"Locale override for {locale.value}: {change_reason}",
            )
        )

        config.locale_overrides[locale] = thresholds
        config.updated_at = datetime.now(UTC)

        logger.info(
            "Set locale thresholds",
            config_id=str(config_id),
            locale=locale.value,
        )

        return True

    def detect_breaches(
        self,
        score: int,
        previous_score: int | None = None,
        config: ThresholdConfig | None = None,
        tenant_id: UUID | None = None,
        entity_id: UUID | None = None,
        screening_id: UUID | None = None,
        role: RoleCategory | None = None,
        locale: Locale | None = None,
    ) -> list[ThresholdBreach]:
        """Detect threshold breaches for a risk score.

        Args:
            score: Current risk score.
            previous_score: Previous score (for change detection).
            config: Threshold configuration to use.
            tenant_id: Tenant ID (to find config if not provided).
            entity_id: Entity being assessed.
            screening_id: Screening ID.
            role: Role category.
            locale: Locale.

        Returns:
            List of detected breaches.
        """
        # Get effective config
        if config is None:
            config = self.get_effective_config(tenant_id)

        # Get applicable thresholds
        thresholds = config.get_thresholds(role=role, locale=locale)

        breaches: list[ThresholdBreach] = []

        # Get current and previous levels
        current_level = thresholds.get_level_for_score(score)
        previous_level = (
            thresholds.get_level_for_score(previous_score)
            if previous_score is not None
            else None
        )

        # Check for level change (threshold crossed)
        if previous_level and previous_level != current_level:
            if self.config.detect_level_changes:
                # Determine severity based on direction
                level_order = [RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.CRITICAL]
                prev_idx = level_order.index(previous_level)
                curr_idx = level_order.index(current_level)

                if curr_idx > prev_idx:
                    # Risk increased
                    severity = BreachSeverity.ALERT if curr_idx >= 2 else BreachSeverity.WARNING
                    if current_level == RiskLevel.CRITICAL:
                        severity = BreachSeverity.CRITICAL
                else:
                    # Risk decreased - info only
                    severity = BreachSeverity.INFO

                threshold_crossed = thresholds.get_threshold_for_level(current_level)

                breach = ThresholdBreach(
                    entity_id=entity_id,
                    screening_id=screening_id,
                    tenant_id=tenant_id,
                    score=score,
                    previous_score=previous_score,
                    previous_level=previous_level,
                    current_level=current_level,
                    threshold_crossed=threshold_crossed,
                    severity=severity,
                    recommended_action=config.breach_actions.get(
                        severity, ThresholdAction.NOTIFY
                    ),
                    breach_type="level_change",
                    description=f"Risk level changed from {previous_level.value} to {current_level.value}",
                    role=role,
                    locale=locale,
                )
                breaches.append(breach)
                self._breaches.append(breach)

        # Check for approaching threshold
        if self.config.detect_approaches:
            approaching, next_level = thresholds.is_approaching_threshold(score)
            if approaching and next_level:
                # Only alert if not already at or above that level
                if next_level != current_level:
                    breach = ThresholdBreach(
                        entity_id=entity_id,
                        screening_id=screening_id,
                        tenant_id=tenant_id,
                        score=score,
                        previous_score=previous_score,
                        previous_level=previous_level,
                        current_level=current_level,
                        threshold_crossed=thresholds.get_threshold_for_level(next_level),
                        severity=BreachSeverity.INFO,
                        recommended_action=ThresholdAction.LOG_ONLY,
                        breach_type="approaching",
                        description=f"Score {score} approaching {next_level.value} threshold",
                        role=role,
                        locale=locale,
                    )
                    breaches.append(breach)
                    self._breaches.append(breach)

        # Check for critical overage
        if current_level == RiskLevel.CRITICAL:
            critical_threshold = thresholds.get_threshold_for_level(RiskLevel.CRITICAL)
            overage = score - critical_threshold
            if overage >= self.config.critical_overage:
                # Already at critical, but significantly over
                breach = ThresholdBreach(
                    entity_id=entity_id,
                    screening_id=screening_id,
                    tenant_id=tenant_id,
                    score=score,
                    previous_score=previous_score,
                    previous_level=previous_level,
                    current_level=current_level,
                    threshold_crossed=critical_threshold,
                    severity=BreachSeverity.CRITICAL,
                    recommended_action=ThresholdAction.BLOCK,
                    breach_type="critical_overage",
                    description=f"Score {score} significantly exceeds critical threshold by {overage} points",
                    role=role,
                    locale=locale,
                )
                # Avoid duplicate if already have a level change breach
                if not any(b.breach_type == "level_change" and b.severity == BreachSeverity.CRITICAL for b in breaches):
                    breaches.append(breach)
                    self._breaches.append(breach)

        if breaches:
            logger.info(
                "Detected threshold breaches",
                entity_id=str(entity_id) if entity_id else None,
                score=score,
                breach_count=len(breaches),
            )

        return breaches

    def get_recommendation(
        self,
        score: int,
        config: ThresholdConfig | None = None,
        tenant_id: UUID | None = None,
        role: RoleCategory | None = None,
        locale: Locale | None = None,
    ) -> Recommendation:
        """Get hiring recommendation based on score and thresholds.

        Args:
            score: Risk score.
            config: Optional threshold config.
            tenant_id: Tenant ID.
            role: Role category.
            locale: Locale.

        Returns:
            Hiring recommendation.
        """
        if config is None:
            config = self.get_effective_config(tenant_id)

        thresholds = config.get_thresholds(role=role, locale=locale)
        level = thresholds.get_level_for_score(score)

        if level == RiskLevel.LOW:
            return Recommendation.PROCEED
        elif level == RiskLevel.MODERATE:
            return Recommendation.PROCEED_WITH_CAUTION
        elif level == RiskLevel.HIGH:
            return Recommendation.REVIEW_REQUIRED
        else:  # CRITICAL
            return Recommendation.DO_NOT_PROCEED

    def acknowledge_breach(
        self,
        breach_id: UUID,
        acknowledged_by: str,
    ) -> bool:
        """Acknowledge a threshold breach.

        Args:
            breach_id: Breach to acknowledge.
            acknowledged_by: User acknowledging.

        Returns:
            True if acknowledged successfully.
        """
        for breach in self._breaches:
            if breach.breach_id == breach_id:
                breach.acknowledged = True
                breach.acknowledged_by = acknowledged_by
                breach.acknowledged_at = datetime.now(UTC)
                logger.info(
                    "Acknowledged breach",
                    breach_id=str(breach_id),
                    acknowledged_by=acknowledged_by,
                )
                return True
        return False

    def get_breaches(
        self,
        tenant_id: UUID | None = None,
        entity_id: UUID | None = None,
        acknowledged: bool | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[ThresholdBreach]:
        """Get threshold breaches with optional filters.

        Args:
            tenant_id: Filter by tenant.
            entity_id: Filter by entity.
            acknowledged: Filter by acknowledgment status.
            since: Filter by time.
            limit: Maximum results.

        Returns:
            List of matching breaches.
        """
        results = []
        for breach in reversed(self._breaches):  # Most recent first
            if tenant_id and breach.tenant_id != tenant_id:
                continue
            if entity_id and breach.entity_id != entity_id:
                continue
            if acknowledged is not None and breach.acknowledged != acknowledged:
                continue
            if since and breach.detected_at < since:
                continue
            results.append(breach)
            if len(results) >= limit:
                break
        return results

    def get_history(
        self,
        config_id: UUID | None = None,
        tenant_id: UUID | None = None,
        limit: int = 50,
    ) -> list[ThresholdHistory]:
        """Get threshold configuration history.

        Args:
            config_id: Filter by config.
            tenant_id: Filter by tenant.
            limit: Maximum results.

        Returns:
            List of history entries.
        """
        results = []
        for entry in reversed(self._history):
            if config_id and entry.config_id != config_id:
                continue
            if tenant_id and entry.tenant_id != tenant_id:
                continue
            results.append(entry)
            if len(results) >= limit:
                break
        return results

    def apply_template(
        self,
        config_id: UUID,
        template: str,
        changed_by: str = "",
    ) -> bool:
        """Apply a threshold template to a configuration.

        Args:
            config_id: Configuration to update.
            template: Template name ('standard', 'conservative', 'lenient').
            changed_by: User making the change.

        Returns:
            True if applied successfully.
        """
        templates = {
            "standard": STANDARD_THRESHOLDS,
            "conservative": CONSERVATIVE_THRESHOLDS,
            "lenient": LENIENT_THRESHOLDS,
        }

        if template not in templates:
            return False

        return self.update_base_thresholds(
            config_id=config_id,
            thresholds=templates[template],
            changed_by=changed_by,
            change_reason=f"Applied {template} template",
        )

    def apply_role_template(
        self,
        config_id: UUID,
        role: RoleCategory,
        changed_by: str = "",
    ) -> bool:
        """Apply recommended role template.

        Args:
            config_id: Configuration to update.
            role: Role category.
            changed_by: User making the change.

        Returns:
            True if applied successfully.
        """
        if role not in ROLE_THRESHOLD_TEMPLATES:
            return False

        return self.set_role_thresholds(
            config_id=config_id,
            role=role,
            thresholds=ROLE_THRESHOLD_TEMPLATES[role],
            changed_by=changed_by,
            change_reason=f"Applied recommended template for {role.value} role",
        )


# =============================================================================
# Factory Function
# =============================================================================


def create_threshold_manager(
    config: ThresholdManagerConfig | None = None,
) -> ThresholdManager:
    """Create a threshold manager with optional config.

    Args:
        config: Optional manager configuration.

    Returns:
        Configured ThresholdManager instance.
    """
    return ThresholdManager(config=config)
