"""Unit tests for the VigilanceManager.

Tests vigilance level determination, risk-based escalation, position changes,
and lifecycle event creation.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid7

import pytest

from elile.agent.state import VigilanceLevel
from elile.compliance.types import RoleCategory
from elile.monitoring.types import (
    LifecycleEventType,
    MonitoringConfig,
    MonitoringConfigError,
)
from elile.monitoring.vigilance_manager import (
    RISK_THRESHOLD_V2,
    RISK_THRESHOLD_V3,
    ROLE_DEFAULT_VIGILANCE,
    EscalationAction,
    ManagerConfig,
    RoleVigilanceMapping,
    VigilanceChangeReason,
    VigilanceDecision,
    VigilanceManager,
    VigilanceUpdate,
    create_vigilance_manager,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def manager() -> VigilanceManager:
    """Create a VigilanceManager for testing."""
    return create_vigilance_manager()


@pytest.fixture
def config_factory():
    """Factory for creating MonitoringConfig instances."""

    def _create(
        vigilance_level: VigilanceLevel = VigilanceLevel.V1,
        role_category: RoleCategory = RoleCategory.STANDARD,
        tenant_id=None,
        subject_id=None,
    ):
        return MonitoringConfig(
            subject_id=subject_id or uuid7(),
            tenant_id=tenant_id or uuid7(),
            vigilance_level=vigilance_level,
            role_category=role_category,
            baseline_profile_id=uuid7(),
        )

    return _create


@pytest.fixture
def tenant_id():
    """Create a tenant ID for testing."""
    return uuid7()


@pytest.fixture
def subject_id():
    """Create a subject ID for testing."""
    return uuid7()


# =============================================================================
# Role Default Mapping Tests
# =============================================================================


class TestRoleDefaultMappings:
    """Tests for role-based default vigilance levels."""

    def test_role_defaults_defined(self):
        """Test that all role categories have defaults."""
        for role in RoleCategory:
            assert role in ROLE_DEFAULT_VIGILANCE

    def test_government_role_is_v3(self):
        """Test that government roles default to V3."""
        assert ROLE_DEFAULT_VIGILANCE[RoleCategory.GOVERNMENT] == VigilanceLevel.V3

    def test_security_role_is_v3(self):
        """Test that security roles default to V3."""
        assert ROLE_DEFAULT_VIGILANCE[RoleCategory.SECURITY] == VigilanceLevel.V3

    def test_executive_role_is_v2(self):
        """Test that executive roles default to V2."""
        assert ROLE_DEFAULT_VIGILANCE[RoleCategory.EXECUTIVE] == VigilanceLevel.V2

    def test_financial_role_is_v2(self):
        """Test that financial roles default to V2."""
        assert ROLE_DEFAULT_VIGILANCE[RoleCategory.FINANCIAL] == VigilanceLevel.V2

    def test_healthcare_role_is_v2(self):
        """Test that healthcare roles default to V2."""
        assert ROLE_DEFAULT_VIGILANCE[RoleCategory.HEALTHCARE] == VigilanceLevel.V2

    def test_education_role_is_v2(self):
        """Test that education roles default to V2."""
        assert ROLE_DEFAULT_VIGILANCE[RoleCategory.EDUCATION] == VigilanceLevel.V2

    def test_transportation_role_is_v2(self):
        """Test that transportation roles default to V2."""
        assert ROLE_DEFAULT_VIGILANCE[RoleCategory.TRANSPORTATION] == VigilanceLevel.V2

    def test_standard_role_is_v1(self):
        """Test that standard roles default to V1."""
        assert ROLE_DEFAULT_VIGILANCE[RoleCategory.STANDARD] == VigilanceLevel.V1

    def test_contractor_role_is_v1(self):
        """Test that contractor roles default to V1."""
        assert ROLE_DEFAULT_VIGILANCE[RoleCategory.CONTRACTOR] == VigilanceLevel.V1


class TestGetRoleDefault:
    """Tests for get_role_default method."""

    def test_get_standard_role_default(self, manager):
        """Test getting default for standard role."""
        level = manager.get_role_default(RoleCategory.STANDARD)
        assert level == VigilanceLevel.V1

    def test_get_government_role_default(self, manager):
        """Test getting default for government role."""
        level = manager.get_role_default(RoleCategory.GOVERNMENT)
        assert level == VigilanceLevel.V3

    def test_get_executive_role_default(self, manager):
        """Test getting default for executive role."""
        level = manager.get_role_default(RoleCategory.EXECUTIVE)
        assert level == VigilanceLevel.V2

    def test_tenant_specific_mapping_overrides_default(self, manager, tenant_id):
        """Test that tenant-specific mapping overrides system default."""
        # Set custom mapping
        manager.set_tenant_mapping(
            tenant_id=tenant_id,
            role_category=RoleCategory.STANDARD,
            vigilance_level=VigilanceLevel.V2,
        )

        # Without tenant, use system default
        level_default = manager.get_role_default(RoleCategory.STANDARD)
        assert level_default == VigilanceLevel.V1

        # With tenant, use custom mapping
        level_custom = manager.get_role_default(RoleCategory.STANDARD, tenant_id)
        assert level_custom == VigilanceLevel.V2


# =============================================================================
# Tenant Mapping Tests
# =============================================================================


class TestTenantMappings:
    """Tests for tenant-specific role mappings."""

    def test_set_tenant_mapping(self, manager, tenant_id):
        """Test setting a tenant mapping."""
        mapping = manager.set_tenant_mapping(
            tenant_id=tenant_id,
            role_category=RoleCategory.CONTRACTOR,
            vigilance_level=VigilanceLevel.V2,
            notes="Elevated contractor monitoring",
        )

        assert isinstance(mapping, RoleVigilanceMapping)
        assert mapping.tenant_id == tenant_id
        assert mapping.role_category == RoleCategory.CONTRACTOR
        assert mapping.vigilance_level == VigilanceLevel.V2
        assert mapping.notes == "Elevated contractor monitoring"

    def test_set_mapping_with_risk_threshold_override(self, manager, tenant_id):
        """Test setting mapping with risk threshold override."""
        mapping = manager.set_tenant_mapping(
            tenant_id=tenant_id,
            role_category=RoleCategory.FINANCIAL,
            vigilance_level=VigilanceLevel.V3,
            risk_threshold_override=40,
        )

        assert mapping.risk_threshold_override == 40

    def test_clear_tenant_mappings(self, manager, tenant_id):
        """Test clearing tenant mappings."""
        manager.set_tenant_mapping(
            tenant_id=tenant_id,
            role_category=RoleCategory.STANDARD,
            vigilance_level=VigilanceLevel.V2,
        )

        # Verify mapping exists
        level = manager.get_role_default(RoleCategory.STANDARD, tenant_id)
        assert level == VigilanceLevel.V2

        # Clear mappings
        manager.clear_tenant_mappings(tenant_id)

        # Verify back to default
        level = manager.get_role_default(RoleCategory.STANDARD, tenant_id)
        assert level == VigilanceLevel.V1


# =============================================================================
# Vigilance Level Determination Tests
# =============================================================================


class TestDetermineVigilanceLevel:
    """Tests for determine_vigilance_level method."""

    def test_initial_assignment_standard_role(self, manager):
        """Test initial assignment for standard role."""
        decision = manager.determine_vigilance_level(
            role_category=RoleCategory.STANDARD,
        )

        assert decision.recommended_level == VigilanceLevel.V1
        assert decision.reason == VigilanceChangeReason.INITIAL_ASSIGNMENT
        assert decision.level_changed is True
        assert decision.action == EscalationAction.UPGRADE

    def test_initial_assignment_government_role(self, manager):
        """Test initial assignment for government role."""
        decision = manager.determine_vigilance_level(
            role_category=RoleCategory.GOVERNMENT,
        )

        assert decision.recommended_level == VigilanceLevel.V3
        assert decision.role_default_level == VigilanceLevel.V3

    def test_initial_assignment_financial_role(self, manager):
        """Test initial assignment for financial role."""
        decision = manager.determine_vigilance_level(
            role_category=RoleCategory.FINANCIAL,
        )

        assert decision.recommended_level == VigilanceLevel.V2

    def test_role_change_detection(self, manager):
        """Test that role change is detected."""
        decision = manager.determine_vigilance_level(
            role_category=RoleCategory.EXECUTIVE,
            current_level=VigilanceLevel.V1,
        )

        assert decision.recommended_level == VigilanceLevel.V2
        assert decision.level_changed is True
        assert decision.action == EscalationAction.UPGRADE

    def test_no_change_when_same_level(self, manager):
        """Test no change when level matches."""
        decision = manager.determine_vigilance_level(
            role_category=RoleCategory.STANDARD,
            current_level=VigilanceLevel.V1,
        )

        assert decision.recommended_level == VigilanceLevel.V1
        assert decision.level_changed is False
        assert decision.action == EscalationAction.MAINTAIN


class TestRiskBasedEscalation:
    """Tests for risk-based escalation."""

    def test_high_risk_escalates_to_v3(self, manager):
        """Test that high risk score escalates to V3."""
        decision = manager.determine_vigilance_level(
            role_category=RoleCategory.STANDARD,
            risk_score=80,  # Above V3 threshold (75)
        )

        assert decision.recommended_level == VigilanceLevel.V3
        assert decision.risk_escalated is True
        assert decision.risk_escalation_reason is not None
        assert "V3" in decision.risk_escalation_reason
        assert decision.reason == VigilanceChangeReason.RISK_ESCALATION

    def test_medium_risk_escalates_to_v2(self, manager):
        """Test that medium risk score escalates to V2."""
        decision = manager.determine_vigilance_level(
            role_category=RoleCategory.STANDARD,
            risk_score=55,  # Above V2 threshold (50)
        )

        assert decision.recommended_level == VigilanceLevel.V2
        assert decision.risk_escalated is True

    def test_low_risk_no_escalation(self, manager):
        """Test that low risk score doesn't escalate."""
        decision = manager.determine_vigilance_level(
            role_category=RoleCategory.STANDARD,
            risk_score=30,
        )

        assert decision.recommended_level == VigilanceLevel.V1
        assert decision.risk_escalated is False

    def test_risk_doesnt_override_higher_role_default(self, manager):
        """Test that risk doesn't downgrade from role default."""
        # Government already defaults to V3
        decision = manager.determine_vigilance_level(
            role_category=RoleCategory.GOVERNMENT,
            risk_score=30,  # Low risk
        )

        # Should still be V3 (role default)
        assert decision.recommended_level == VigilanceLevel.V3

    def test_risk_escalates_above_role_default(self, manager):
        """Test that risk can escalate above role default."""
        decision = manager.determine_vigilance_level(
            role_category=RoleCategory.CONTRACTOR,  # Default V1
            risk_score=80,  # Critical risk
        )

        # Should escalate to V3
        assert decision.recommended_level == VigilanceLevel.V3
        assert decision.role_default_level == VigilanceLevel.V1

    def test_risk_at_v3_threshold_boundary(self, manager):
        """Test risk score exactly at V3 threshold."""
        decision = manager.determine_vigilance_level(
            role_category=RoleCategory.STANDARD,
            risk_score=RISK_THRESHOLD_V3,  # Exactly 75
        )

        assert decision.recommended_level == VigilanceLevel.V3

    def test_risk_at_v2_threshold_boundary(self, manager):
        """Test risk score exactly at V2 threshold."""
        decision = manager.determine_vigilance_level(
            role_category=RoleCategory.STANDARD,
            risk_score=RISK_THRESHOLD_V2,  # Exactly 50
        )

        assert decision.recommended_level == VigilanceLevel.V2

    def test_auto_escalation_can_be_disabled(self):
        """Test that auto escalation can be disabled."""
        config = ManagerConfig(auto_escalate_on_risk=False)
        manager = create_vigilance_manager(config=config)

        decision = manager.determine_vigilance_level(
            role_category=RoleCategory.STANDARD,
            risk_score=90,  # Very high risk
        )

        # Should not escalate
        assert decision.recommended_level == VigilanceLevel.V1
        assert decision.risk_escalated is False

    def test_tenant_risk_threshold_override(self, manager, tenant_id):
        """Test tenant-specific risk threshold override."""
        # Set lower threshold for tenant
        manager.set_tenant_mapping(
            tenant_id=tenant_id,
            role_category=RoleCategory.STANDARD,
            vigilance_level=VigilanceLevel.V1,
            risk_threshold_override=30,  # Lower V2 threshold
        )

        decision = manager.determine_vigilance_level(
            role_category=RoleCategory.STANDARD,
            risk_score=35,  # Above custom threshold
            tenant_id=tenant_id,
        )

        # Should escalate to V2 with lower threshold
        assert decision.recommended_level == VigilanceLevel.V2


# =============================================================================
# Position Change Tests
# =============================================================================


class TestPositionChange:
    """Tests for position change evaluation."""

    def test_evaluate_position_change_upgrade(self, manager, config_factory):
        """Test position change that upgrades vigilance."""
        config = config_factory(
            vigilance_level=VigilanceLevel.V1,
            role_category=RoleCategory.STANDARD,
        )

        decision = manager.evaluate_position_change(
            monitoring_config=config,
            new_role_category=RoleCategory.EXECUTIVE,
        )

        assert decision.recommended_level == VigilanceLevel.V2
        assert decision.reason == VigilanceChangeReason.ROLE_CHANGE
        assert decision.level_changed is True

    def test_evaluate_position_change_downgrade(self, manager, config_factory):
        """Test position change that downgrades vigilance."""
        config = config_factory(
            vigilance_level=VigilanceLevel.V3,
            role_category=RoleCategory.GOVERNMENT,
        )

        decision = manager.evaluate_position_change(
            monitoring_config=config,
            new_role_category=RoleCategory.STANDARD,
        )

        assert decision.recommended_level == VigilanceLevel.V1
        assert decision.level_changed is True
        assert decision.action == EscalationAction.DOWNGRADE

    def test_evaluate_position_change_no_change(self, manager, config_factory):
        """Test position change with same vigilance level."""
        config = config_factory(
            vigilance_level=VigilanceLevel.V2,
            role_category=RoleCategory.FINANCIAL,
        )

        decision = manager.evaluate_position_change(
            monitoring_config=config,
            new_role_category=RoleCategory.HEALTHCARE,  # Also V2 default
        )

        assert decision.recommended_level == VigilanceLevel.V2
        assert decision.level_changed is False

    def test_position_change_with_risk_score(self, manager, config_factory):
        """Test position change considers risk score."""
        config = config_factory(
            vigilance_level=VigilanceLevel.V1,
            role_category=RoleCategory.STANDARD,
        )

        decision = manager.evaluate_position_change(
            monitoring_config=config,
            new_role_category=RoleCategory.CONTRACTOR,  # Still V1 default
            risk_score=80,  # But high risk
        )

        # Risk should escalate to V3
        assert decision.recommended_level == VigilanceLevel.V3


# =============================================================================
# Escalation Evaluation Tests
# =============================================================================


class TestEscalationEvaluation:
    """Tests for escalation evaluation."""

    def test_evaluate_for_escalation(self, manager, config_factory):
        """Test evaluating if config should be escalated."""
        config = config_factory(
            vigilance_level=VigilanceLevel.V1,
            role_category=RoleCategory.STANDARD,
        )

        decision = manager.evaluate_for_escalation(
            monitoring_config=config,
            new_risk_score=80,
        )

        assert decision.recommended_level == VigilanceLevel.V3
        assert decision.risk_escalated is True

    def test_no_escalation_needed(self, manager, config_factory):
        """Test when no escalation is needed."""
        config = config_factory(
            vigilance_level=VigilanceLevel.V3,
            role_category=RoleCategory.GOVERNMENT,
        )

        decision = manager.evaluate_for_escalation(
            monitoring_config=config,
            new_risk_score=80,
        )

        # Already at V3
        assert decision.recommended_level == VigilanceLevel.V3
        assert decision.level_changed is False


class TestGetEscalationRecommendation:
    """Tests for escalation recommendation helper."""

    def test_recommendation_for_high_risk(self, manager):
        """Test recommendation for high risk score."""
        level, explanation = manager.get_escalation_recommendation(
            risk_score=80,
            current_level=VigilanceLevel.V1,
        )

        assert level == VigilanceLevel.V3
        assert "V3" in explanation
        assert "bi-monthly" in explanation

    def test_recommendation_for_medium_risk(self, manager):
        """Test recommendation for medium risk score."""
        level, explanation = manager.get_escalation_recommendation(
            risk_score=55,
            current_level=VigilanceLevel.V1,
        )

        assert level == VigilanceLevel.V2
        assert "V2" in explanation
        assert "monthly" in explanation

    def test_recommendation_maintain_level(self, manager):
        """Test recommendation to maintain level."""
        level, explanation = manager.get_escalation_recommendation(
            risk_score=30,
            current_level=VigilanceLevel.V1,
        )

        assert level == VigilanceLevel.V1
        assert "Maintain" in explanation


# =============================================================================
# Downgrade Validation Tests
# =============================================================================


class TestDowngradeValidation:
    """Tests for downgrade validation."""

    def test_downgrade_permitted_when_valid(self, manager):
        """Test that valid downgrade is permitted."""
        is_valid, explanation = manager.validate_downgrade(
            current_level=VigilanceLevel.V3,
            proposed_level=VigilanceLevel.V2,
            risk_score=40,
            role_category=RoleCategory.EXECUTIVE,  # Default V2
        )

        assert is_valid is True

    def test_downgrade_blocked_below_role_default(self, manager):
        """Test that downgrade below role default is blocked."""
        is_valid, explanation = manager.validate_downgrade(
            current_level=VigilanceLevel.V2,
            proposed_level=VigilanceLevel.V1,
            risk_score=None,
            role_category=RoleCategory.EXECUTIVE,  # Default V2
        )

        assert is_valid is False
        assert "below role default" in explanation

    def test_downgrade_blocked_by_risk_v3(self, manager):
        """Test that downgrade from V3 blocked when risk requires it."""
        is_valid, explanation = manager.validate_downgrade(
            current_level=VigilanceLevel.V3,
            proposed_level=VigilanceLevel.V2,
            risk_score=80,  # Requires V3
            role_category=RoleCategory.STANDARD,
        )

        assert is_valid is False
        assert "Risk score" in explanation
        assert "requires V3" in explanation

    def test_downgrade_blocked_by_risk_v2(self, manager):
        """Test that downgrade from V2 blocked when risk requires it."""
        is_valid, explanation = manager.validate_downgrade(
            current_level=VigilanceLevel.V2,
            proposed_level=VigilanceLevel.V1,
            risk_score=55,  # Requires V2
            role_category=RoleCategory.STANDARD,
        )

        assert is_valid is False
        assert "requires at least V2" in explanation

    def test_downgrade_disabled_by_config(self):
        """Test that downgrade can be disabled by config."""
        config = ManagerConfig(allow_manual_downgrade=False)
        manager = create_vigilance_manager(config=config)

        is_valid, explanation = manager.validate_downgrade(
            current_level=VigilanceLevel.V3,
            proposed_level=VigilanceLevel.V1,
            risk_score=None,
            role_category=RoleCategory.STANDARD,
        )

        assert is_valid is False
        assert "not permitted" in explanation

    def test_not_a_downgrade_passes(self, manager):
        """Test that upgrade/maintain passes validation."""
        is_valid, explanation = manager.validate_downgrade(
            current_level=VigilanceLevel.V1,
            proposed_level=VigilanceLevel.V2,
            risk_score=None,
            role_category=RoleCategory.STANDARD,
        )

        assert is_valid is True
        assert "Not a downgrade" in explanation


# =============================================================================
# Lifecycle Event Creation Tests
# =============================================================================


class TestLifecycleEventCreation:
    """Tests for lifecycle event creation helpers."""

    def test_create_position_change_event(self, manager, tenant_id, subject_id):
        """Test creating position change event."""
        event = manager.create_position_change_event(
            subject_id=subject_id,
            tenant_id=tenant_id,
            new_role_category=RoleCategory.EXECUTIVE,
            description="Promoted to VP",
        )

        assert event.event_type == LifecycleEventType.POSITION_CHANGE
        assert event.subject_id == subject_id
        assert event.tenant_id == tenant_id
        assert event.new_role_category == RoleCategory.EXECUTIVE
        assert event.new_vigilance_level == VigilanceLevel.V2  # Executive default
        assert "Promoted to VP" in event.description

    def test_create_position_change_event_auto_vigilance(self, manager, tenant_id, subject_id):
        """Test position change event auto-calculates vigilance."""
        event = manager.create_position_change_event(
            subject_id=subject_id,
            tenant_id=tenant_id,
            new_role_category=RoleCategory.GOVERNMENT,
        )

        assert event.new_vigilance_level == VigilanceLevel.V3

    def test_create_position_change_event_explicit_vigilance(self, manager, tenant_id, subject_id):
        """Test position change with explicit vigilance level."""
        event = manager.create_position_change_event(
            subject_id=subject_id,
            tenant_id=tenant_id,
            new_role_category=RoleCategory.STANDARD,
            new_vigilance_level=VigilanceLevel.V3,  # Override
        )

        assert event.new_vigilance_level == VigilanceLevel.V3

    def test_create_promotion_event(self, manager, tenant_id, subject_id):
        """Test creating promotion event."""
        event = manager.create_promotion_event(
            subject_id=subject_id,
            tenant_id=tenant_id,
            new_role_category=RoleCategory.SECURITY,
            description="Security team lead",
        )

        assert event.event_type == LifecycleEventType.PROMOTION
        assert event.new_role_category == RoleCategory.SECURITY
        assert event.new_vigilance_level == VigilanceLevel.V3

    def test_create_vigilance_upgrade_event(self, manager, tenant_id, subject_id):
        """Test creating vigilance upgrade event."""
        event = manager.create_vigilance_upgrade_event(
            subject_id=subject_id,
            tenant_id=tenant_id,
            new_vigilance_level=VigilanceLevel.V3,
            reason="High risk screening result",
        )

        assert event.event_type == LifecycleEventType.VIGILANCE_UPGRADE
        assert event.new_vigilance_level == VigilanceLevel.V3
        assert "High risk" in event.description

    def test_create_vigilance_downgrade_event(self, manager, tenant_id, subject_id):
        """Test creating vigilance downgrade event."""
        event = manager.create_vigilance_downgrade_event(
            subject_id=subject_id,
            tenant_id=tenant_id,
            new_vigilance_level=VigilanceLevel.V1,
            reason="Risk reduced after review",
        )

        assert event.event_type == LifecycleEventType.VIGILANCE_DOWNGRADE
        assert event.new_vigilance_level == VigilanceLevel.V1


# =============================================================================
# Decision History Tests
# =============================================================================


class TestDecisionHistory:
    """Tests for decision history tracking."""

    def test_decisions_stored_in_history(self, manager, subject_id, tenant_id):
        """Test that decisions are stored in history."""
        # Make a decision
        manager.determine_vigilance_level(
            role_category=RoleCategory.STANDARD,
            subject_id=subject_id,
            tenant_id=tenant_id,
        )

        history = manager.get_decision_history()
        assert len(history) == 1
        assert history[0].subject_id == subject_id

    def test_history_filter_by_subject(self, manager):
        """Test filtering history by subject."""
        subject1 = uuid7()
        subject2 = uuid7()

        manager.determine_vigilance_level(
            role_category=RoleCategory.STANDARD,
            subject_id=subject1,
        )
        manager.determine_vigilance_level(
            role_category=RoleCategory.EXECUTIVE,
            subject_id=subject2,
        )

        history = manager.get_decision_history(subject_id=subject1)
        assert len(history) == 1
        assert history[0].subject_id == subject1

    def test_history_filter_by_tenant(self, manager):
        """Test filtering history by tenant."""
        tenant1 = uuid7()
        tenant2 = uuid7()

        manager.determine_vigilance_level(
            role_category=RoleCategory.STANDARD,
            tenant_id=tenant1,
        )
        manager.determine_vigilance_level(
            role_category=RoleCategory.EXECUTIVE,
            tenant_id=tenant2,
        )

        history = manager.get_decision_history(tenant_id=tenant1)
        assert len(history) == 1
        assert history[0].tenant_id == tenant1

    def test_history_limit(self, manager):
        """Test history limit."""
        for _ in range(10):
            manager.determine_vigilance_level(role_category=RoleCategory.STANDARD)

        history = manager.get_decision_history(limit=5)
        assert len(history) == 5

    def test_history_ordered_most_recent_first(self, manager):
        """Test history is ordered most recent first."""
        manager.determine_vigilance_level(role_category=RoleCategory.STANDARD)
        manager.determine_vigilance_level(role_category=RoleCategory.EXECUTIVE)

        history = manager.get_decision_history()
        assert history[0].role_category == RoleCategory.EXECUTIVE
        assert history[1].role_category == RoleCategory.STANDARD


# =============================================================================
# Data Class Tests
# =============================================================================


class TestVigilanceDecision:
    """Tests for VigilanceDecision dataclass."""

    def test_decision_defaults(self):
        """Test decision default values."""
        decision = VigilanceDecision()

        assert decision.recommended_level == VigilanceLevel.V1
        assert decision.previous_level is None
        assert decision.reason == VigilanceChangeReason.INITIAL_ASSIGNMENT
        assert decision.risk_escalated is False
        assert decision.level_changed is False

    def test_decision_to_dict(self):
        """Test decision serialization."""
        decision = VigilanceDecision(
            subject_id=uuid7(),
            tenant_id=uuid7(),
            recommended_level=VigilanceLevel.V3,
            risk_score=80,
            risk_escalated=True,
        )

        data = decision.to_dict()

        assert data["recommended_level"] == "v3"  # Lowercase enum value
        assert data["risk_score"] == 80
        assert data["risk_escalated"] is True
        assert "decision_id" in data


class TestVigilanceUpdate:
    """Tests for VigilanceUpdate dataclass."""

    def test_update_defaults(self):
        """Test update default values."""
        update = VigilanceUpdate()

        assert update.success is True
        assert update.rescheduled is False
        assert update.immediate_check_triggered is False
        assert update.error is None

    def test_update_to_dict(self):
        """Test update serialization."""
        update = VigilanceUpdate(
            config_id=uuid7(),
            success=True,
            new_level=VigilanceLevel.V2,
            rescheduled=True,
        )

        data = update.to_dict()

        assert data["success"] is True
        assert data["new_level"] == "v2"  # Lowercase enum value
        assert data["rescheduled"] is True


# =============================================================================
# Manager Configuration Tests
# =============================================================================


class TestManagerConfig:
    """Tests for ManagerConfig."""

    def test_default_config_values(self):
        """Test default configuration values."""
        config = ManagerConfig()

        assert config.risk_threshold_v3 == 75
        assert config.risk_threshold_v2 == 50
        assert config.allow_manual_downgrade is True
        assert config.auto_escalate_on_risk is True
        assert config.trigger_check_on_upgrade is True
        assert config.trigger_check_on_downgrade is False

    def test_custom_risk_thresholds(self):
        """Test custom risk thresholds."""
        config = ManagerConfig(
            risk_threshold_v3=80,
            risk_threshold_v2=60,
        )
        manager = create_vigilance_manager(config=config)

        # Score 75 should not trigger V3 with higher threshold
        decision = manager.determine_vigilance_level(
            role_category=RoleCategory.STANDARD,
            risk_score=75,
        )

        # 75 >= 60 (custom V2 threshold) but < 80 (custom V3)
        assert decision.recommended_level == VigilanceLevel.V2


# =============================================================================
# Async Update Tests (Scheduler Integration)
# =============================================================================


class MockScheduler:
    """Mock scheduler for testing."""

    def __init__(self):
        self.updates = []
        self.checks_triggered = []
        self._configs = {}

    async def update_vigilance_level(
        self,
        config_id,
        new_level,
    ):
        """Mock update vigilance level."""
        self.updates.append((config_id, new_level))
        # Return a mock config
        config = MonitoringConfig(
            config_id=config_id,
            subject_id=uuid7(),
            tenant_id=uuid7(),
            vigilance_level=new_level,
            baseline_profile_id=uuid7(),
            next_check_date=datetime.now(UTC) + timedelta(days=30),
        )
        self._configs[config_id] = config
        return config

    async def trigger_immediate_check(
        self,
        config_id,
        reason=None,
    ):
        """Mock trigger immediate check."""
        self.checks_triggered.append((config_id, reason))
        return None


@pytest.fixture
def mock_scheduler():
    """Create mock scheduler."""
    return MockScheduler()


@pytest.fixture
def manager_with_scheduler(mock_scheduler):
    """Create manager with mock scheduler."""
    return create_vigilance_manager(scheduler=mock_scheduler)


class TestAsyncUpdates:
    """Tests for async vigilance updates."""

    @pytest.mark.asyncio
    async def test_update_vigilance_calls_scheduler(self, manager_with_scheduler, mock_scheduler):
        """Test that update_vigilance calls the scheduler."""
        config_id = uuid7()

        update = await manager_with_scheduler.update_vigilance(
            config_id=config_id,
            new_level=VigilanceLevel.V2,
            reason=VigilanceChangeReason.RISK_ESCALATION,
        )

        assert update.success is True
        assert update.rescheduled is True
        assert len(mock_scheduler.updates) == 1
        assert mock_scheduler.updates[0] == (config_id, VigilanceLevel.V2)

    @pytest.mark.asyncio
    async def test_update_triggers_immediate_check_on_upgrade(
        self, manager_with_scheduler, mock_scheduler
    ):
        """Test that upgrade triggers immediate check by default."""
        config_id = uuid7()

        update = await manager_with_scheduler.update_vigilance(
            config_id=config_id,
            new_level=VigilanceLevel.V2,
            reason=VigilanceChangeReason.RISK_ESCALATION,
            previous_level=VigilanceLevel.V1,  # Explicit previous level for upgrade detection
        )

        assert update.immediate_check_triggered is True
        assert len(mock_scheduler.checks_triggered) == 1

    @pytest.mark.asyncio
    async def test_update_no_check_on_downgrade_by_default(self, manager_with_scheduler):
        """Test that downgrade doesn't trigger check by default."""
        config_id = uuid7()

        update = await manager_with_scheduler.update_vigilance(
            config_id=config_id,
            new_level=VigilanceLevel.V2,
            reason=VigilanceChangeReason.MANUAL_OVERRIDE,
            previous_level=VigilanceLevel.V3,  # Explicit previous level for downgrade detection
        )

        assert update.immediate_check_triggered is False

    @pytest.mark.asyncio
    async def test_update_without_scheduler_raises_error(self, manager):
        """Test that update without scheduler raises error."""
        with pytest.raises(MonitoringConfigError) as exc_info:
            await manager.update_vigilance(
                config_id=uuid7(),
                new_level=VigilanceLevel.V2,
                reason=VigilanceChangeReason.MANUAL_OVERRIDE,
            )

        assert "Scheduler not configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_apply_decision_no_change(self, manager_with_scheduler):
        """Test applying decision when no change needed."""
        decision = VigilanceDecision(
            recommended_level=VigilanceLevel.V1,
            previous_level=VigilanceLevel.V1,
            level_changed=False,
        )

        update = await manager_with_scheduler.apply_decision(
            decision=decision,
            config_id=uuid7(),
        )

        assert update.success is True
        assert update.rescheduled is False

    @pytest.mark.asyncio
    async def test_apply_decision_with_change(self, manager_with_scheduler, mock_scheduler):
        """Test applying decision when change needed."""
        config_id = uuid7()
        decision = VigilanceDecision(
            recommended_level=VigilanceLevel.V3,
            previous_level=VigilanceLevel.V1,
            level_changed=True,
            reason=VigilanceChangeReason.RISK_ESCALATION,
        )

        update = await manager_with_scheduler.apply_decision(
            decision=decision,
            config_id=config_id,
        )

        assert update.success is True
        assert update.new_level == VigilanceLevel.V3
        assert len(mock_scheduler.updates) == 1


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for create_vigilance_manager factory."""

    def test_create_with_defaults(self):
        """Test creating manager with defaults."""
        manager = create_vigilance_manager()

        assert isinstance(manager, VigilanceManager)
        assert manager.scheduler is None
        assert manager.config is not None

    def test_create_with_scheduler(self, mock_scheduler):
        """Test creating manager with scheduler."""
        manager = create_vigilance_manager(scheduler=mock_scheduler)

        assert manager.scheduler is mock_scheduler

    def test_create_with_config(self):
        """Test creating manager with custom config."""
        config = ManagerConfig(risk_threshold_v3=90)
        manager = create_vigilance_manager(config=config)

        assert manager.config.risk_threshold_v3 == 90
