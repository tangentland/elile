"""Tests for Configurable Risk Thresholds.

Tests cover:
- Threshold set operations
- Threshold configuration
- Breach detection
- Role and locale overrides
- History tracking
- Templates
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid7

import pytest

from elile.compliance.types import Locale, RoleCategory
from elile.risk.risk_scorer import Recommendation, RiskLevel
from elile.risk.thresholds import (
    BreachSeverity,
    CONSERVATIVE_THRESHOLDS,
    create_threshold_manager,
    LENIENT_THRESHOLDS,
    ROLE_THRESHOLD_TEMPLATES,
    STANDARD_THRESHOLDS,
    ThresholdAction,
    ThresholdBreach,
    ThresholdConfig,
    ThresholdHistory,
    ThresholdManager,
    ThresholdManagerConfig,
    ThresholdScope,
    ThresholdSet,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def manager() -> ThresholdManager:
    """Create a default threshold manager."""
    return create_threshold_manager()


@pytest.fixture
def tenant_id():
    """Create a test tenant ID."""
    return uuid7()


@pytest.fixture
def entity_id():
    """Create a test entity ID."""
    return uuid7()


# =============================================================================
# ThresholdSet Tests
# =============================================================================


class TestThresholdSet:
    """Tests for ThresholdSet dataclass."""

    def test_default_thresholds(self) -> None:
        """Test default threshold values."""
        ts = ThresholdSet()
        assert ts.low_max == 39
        assert ts.moderate_max == 59
        assert ts.high_max == 79

    def test_get_level_for_score_low(self) -> None:
        """Test getting LOW level."""
        ts = ThresholdSet()
        assert ts.get_level_for_score(0) == RiskLevel.LOW
        assert ts.get_level_for_score(20) == RiskLevel.LOW
        assert ts.get_level_for_score(39) == RiskLevel.LOW

    def test_get_level_for_score_moderate(self) -> None:
        """Test getting MODERATE level."""
        ts = ThresholdSet()
        assert ts.get_level_for_score(40) == RiskLevel.MODERATE
        assert ts.get_level_for_score(50) == RiskLevel.MODERATE
        assert ts.get_level_for_score(59) == RiskLevel.MODERATE

    def test_get_level_for_score_high(self) -> None:
        """Test getting HIGH level."""
        ts = ThresholdSet()
        assert ts.get_level_for_score(60) == RiskLevel.HIGH
        assert ts.get_level_for_score(70) == RiskLevel.HIGH
        assert ts.get_level_for_score(79) == RiskLevel.HIGH

    def test_get_level_for_score_critical(self) -> None:
        """Test getting CRITICAL level."""
        ts = ThresholdSet()
        assert ts.get_level_for_score(80) == RiskLevel.CRITICAL
        assert ts.get_level_for_score(90) == RiskLevel.CRITICAL
        assert ts.get_level_for_score(100) == RiskLevel.CRITICAL

    def test_get_threshold_for_level(self) -> None:
        """Test getting threshold for level."""
        ts = ThresholdSet()
        assert ts.get_threshold_for_level(RiskLevel.LOW) == 0
        assert ts.get_threshold_for_level(RiskLevel.MODERATE) == 40
        assert ts.get_threshold_for_level(RiskLevel.HIGH) == 60
        assert ts.get_threshold_for_level(RiskLevel.CRITICAL) == 80

    def test_is_approaching_threshold(self) -> None:
        """Test approaching threshold detection."""
        ts = ThresholdSet(approach_buffer=5)

        # Approaching MODERATE
        approaching, level = ts.is_approaching_threshold(37)
        assert approaching is True
        assert level == RiskLevel.MODERATE

        # Not approaching (too far)
        approaching, level = ts.is_approaching_threshold(30)
        assert approaching is False

        # Already at level
        approaching, level = ts.is_approaching_threshold(45)
        assert approaching is False

    def test_to_dict(self) -> None:
        """Test serialization."""
        ts = ThresholdSet(low_max=30, moderate_max=55)
        d = ts.to_dict()

        assert d["low_max"] == 30
        assert d["moderate_max"] == 55
        assert "threshold_id" in d

    def test_from_dict(self) -> None:
        """Test deserialization."""
        ts = ThresholdSet(low_max=30)
        d = ts.to_dict()
        restored = ThresholdSet.from_dict(d)

        assert restored.low_max == 30
        assert restored.threshold_id == ts.threshold_id


# =============================================================================
# ThresholdConfig Tests
# =============================================================================


class TestThresholdConfig:
    """Tests for ThresholdConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration."""
        config = ThresholdConfig()
        assert config.scope == ThresholdScope.ORGANIZATION
        assert config.is_active is True
        assert config.base_thresholds is not None

    def test_get_thresholds_base(self) -> None:
        """Test getting base thresholds."""
        config = ThresholdConfig()
        ts = config.get_thresholds()

        assert ts == config.base_thresholds

    def test_get_thresholds_role_override(self) -> None:
        """Test role override priority."""
        config = ThresholdConfig()
        role_ts = ThresholdSet(low_max=29)
        config.role_overrides[RoleCategory.FINANCIAL] = role_ts

        ts = config.get_thresholds(role=RoleCategory.FINANCIAL)
        assert ts.low_max == 29

        # Different role should get base
        ts = config.get_thresholds(role=RoleCategory.STANDARD)
        assert ts == config.base_thresholds

    def test_get_thresholds_locale_override(self) -> None:
        """Test locale override priority."""
        config = ThresholdConfig()
        locale_ts = ThresholdSet(low_max=34)
        config.locale_overrides[Locale.EU] = locale_ts

        ts = config.get_thresholds(locale=Locale.EU)
        assert ts.low_max == 34

    def test_get_thresholds_locale_over_role(self) -> None:
        """Test locale takes priority over role."""
        config = ThresholdConfig()
        config.role_overrides[RoleCategory.FINANCIAL] = ThresholdSet(low_max=29)
        config.locale_overrides[Locale.EU] = ThresholdSet(low_max=34)

        # Locale should win
        ts = config.get_thresholds(role=RoleCategory.FINANCIAL, locale=Locale.EU)
        assert ts.low_max == 34

    def test_breach_actions(self) -> None:
        """Test breach actions configuration."""
        config = ThresholdConfig()

        assert config.breach_actions[BreachSeverity.INFO] == ThresholdAction.LOG_ONLY
        assert config.breach_actions[BreachSeverity.CRITICAL] == ThresholdAction.BLOCK

    def test_to_dict(self) -> None:
        """Test serialization."""
        config = ThresholdConfig(name="Test Config")
        d = config.to_dict()

        assert d["name"] == "Test Config"
        assert "base_thresholds" in d
        assert "breach_actions" in d


# =============================================================================
# ThresholdManager Tests
# =============================================================================


class TestThresholdManager:
    """Tests for ThresholdManager."""

    def test_create_config(self, manager: ThresholdManager, tenant_id) -> None:
        """Test creating a configuration."""
        config = manager.create_config(
            tenant_id=tenant_id,
            name="Org Config",
        )

        assert config.tenant_id == tenant_id
        assert config.name == "Org Config"
        assert config.is_active is True

    def test_get_config(self, manager: ThresholdManager, tenant_id) -> None:
        """Test getting a configuration."""
        created = manager.create_config(tenant_id=tenant_id)
        retrieved = manager.get_config(created.config_id)

        assert retrieved == created

    def test_get_config_for_tenant(self, manager: ThresholdManager, tenant_id) -> None:
        """Test getting config by tenant."""
        created = manager.create_config(tenant_id=tenant_id)
        retrieved = manager.get_config_for_tenant(tenant_id)

        assert retrieved == created

    def test_get_effective_config_fallback(self, manager: ThresholdManager) -> None:
        """Test fallback to global config."""
        config = manager.get_effective_config(tenant_id=uuid7())

        assert config.scope == ThresholdScope.GLOBAL
        assert config.name == "Global Defaults"

    def test_update_base_thresholds(self, manager: ThresholdManager, tenant_id) -> None:
        """Test updating base thresholds."""
        config = manager.create_config(tenant_id=tenant_id)
        new_ts = ThresholdSet(low_max=35, moderate_max=55, high_max=75)

        result = manager.update_base_thresholds(
            config_id=config.config_id,
            thresholds=new_ts,
            changed_by="admin",
            change_reason="Testing",
        )

        assert result is True
        updated = manager.get_config(config.config_id)
        assert updated.base_thresholds.low_max == 35

    def test_set_role_thresholds(self, manager: ThresholdManager, tenant_id) -> None:
        """Test setting role thresholds."""
        config = manager.create_config(tenant_id=tenant_id)
        role_ts = ThresholdSet(low_max=29)

        result = manager.set_role_thresholds(
            config_id=config.config_id,
            role=RoleCategory.SECURITY,
            thresholds=role_ts,
        )

        assert result is True
        updated = manager.get_config(config.config_id)
        assert RoleCategory.SECURITY in updated.role_overrides

    def test_set_locale_thresholds(self, manager: ThresholdManager, tenant_id) -> None:
        """Test setting locale thresholds."""
        config = manager.create_config(tenant_id=tenant_id)
        locale_ts = ThresholdSet(low_max=44)

        result = manager.set_locale_thresholds(
            config_id=config.config_id,
            locale=Locale.EU,
            thresholds=locale_ts,
        )

        assert result is True
        updated = manager.get_config(config.config_id)
        assert Locale.EU in updated.locale_overrides


# =============================================================================
# Breach Detection Tests
# =============================================================================


class TestBreachDetection:
    """Tests for breach detection."""

    def test_detect_level_increase(self, manager: ThresholdManager, entity_id) -> None:
        """Test detecting level increase."""
        breaches = manager.detect_breaches(
            score=65,  # HIGH
            previous_score=45,  # MODERATE
            entity_id=entity_id,
        )

        assert len(breaches) >= 1
        level_change = next((b for b in breaches if b.breach_type == "level_change"), None)
        assert level_change is not None
        assert level_change.previous_level == RiskLevel.MODERATE
        assert level_change.current_level == RiskLevel.HIGH

    def test_detect_level_decrease(self, manager: ThresholdManager, entity_id) -> None:
        """Test detecting level decrease."""
        breaches = manager.detect_breaches(
            score=35,  # LOW
            previous_score=55,  # MODERATE
            entity_id=entity_id,
        )

        assert len(breaches) >= 1
        level_change = next((b for b in breaches if b.breach_type == "level_change"), None)
        assert level_change is not None
        assert level_change.severity == BreachSeverity.INFO

    def test_detect_approaching_threshold(self, manager: ThresholdManager) -> None:
        """Test detecting approaching threshold."""
        breaches = manager.detect_breaches(
            score=57,  # Approaching 60 (HIGH)
            previous_score=50,
        )

        approaching = [b for b in breaches if b.breach_type == "approaching"]
        assert len(approaching) >= 1

    def test_detect_critical_breach(self, manager: ThresholdManager, entity_id) -> None:
        """Test detecting critical level breach."""
        breaches = manager.detect_breaches(
            score=85,  # CRITICAL
            previous_score=70,  # HIGH
            entity_id=entity_id,
        )

        assert len(breaches) >= 1
        critical = next((b for b in breaches if b.current_level == RiskLevel.CRITICAL), None)
        assert critical is not None
        assert critical.severity == BreachSeverity.CRITICAL

    def test_detect_critical_overage(self, manager: ThresholdManager) -> None:
        """Test detecting significant critical overage."""
        breaches = manager.detect_breaches(
            score=95,  # 15 points over critical threshold
            previous_score=85,  # Already critical
        )

        overage = [b for b in breaches if b.breach_type == "critical_overage"]
        assert len(overage) >= 1

    def test_no_breach_same_level(self, manager: ThresholdManager) -> None:
        """Test no breach when staying in same level."""
        breaches = manager.detect_breaches(
            score=50,  # MODERATE
            previous_score=45,  # MODERATE
        )

        level_changes = [b for b in breaches if b.breach_type == "level_change"]
        assert len(level_changes) == 0

    def test_breach_with_role_override(self, manager: ThresholdManager, tenant_id) -> None:
        """Test breach detection with role override."""
        config = manager.create_config(tenant_id=tenant_id)
        manager.set_role_thresholds(
            config_id=config.config_id,
            role=RoleCategory.SECURITY,
            thresholds=ThresholdSet(low_max=25, moderate_max=45, high_max=65),
        )

        # With security role, 50 is HIGH
        breaches = manager.detect_breaches(
            score=50,
            previous_score=30,  # Was LOW with security thresholds
            config=config,
            role=RoleCategory.SECURITY,
        )

        assert len(breaches) >= 1
        breach = breaches[0]
        assert breach.current_level == RiskLevel.HIGH


# =============================================================================
# Recommendation Tests
# =============================================================================


class TestRecommendation:
    """Tests for recommendation generation."""

    def test_recommend_proceed(self, manager: ThresholdManager) -> None:
        """Test PROCEED recommendation."""
        rec = manager.get_recommendation(score=25)
        assert rec == Recommendation.PROCEED

    def test_recommend_proceed_with_caution(self, manager: ThresholdManager) -> None:
        """Test PROCEED_WITH_CAUTION recommendation."""
        rec = manager.get_recommendation(score=50)
        assert rec == Recommendation.PROCEED_WITH_CAUTION

    def test_recommend_review_required(self, manager: ThresholdManager) -> None:
        """Test REVIEW_REQUIRED recommendation."""
        rec = manager.get_recommendation(score=70)
        assert rec == Recommendation.REVIEW_REQUIRED

    def test_recommend_do_not_proceed(self, manager: ThresholdManager) -> None:
        """Test DO_NOT_PROCEED recommendation."""
        rec = manager.get_recommendation(score=85)
        assert rec == Recommendation.DO_NOT_PROCEED

    def test_recommendation_with_role(self, manager: ThresholdManager, tenant_id) -> None:
        """Test recommendation with role override."""
        config = manager.create_config(tenant_id=tenant_id)
        # Security role: stricter thresholds
        manager.set_role_thresholds(
            config_id=config.config_id,
            role=RoleCategory.SECURITY,
            thresholds=ThresholdSet(low_max=25, moderate_max=45, high_max=65),
        )

        # 50 is MODERATE normally, but HIGH for security
        rec = manager.get_recommendation(
            score=50,
            config=config,
            role=RoleCategory.SECURITY,
        )
        assert rec == Recommendation.REVIEW_REQUIRED


# =============================================================================
# History Tests
# =============================================================================


class TestHistory:
    """Tests for threshold history tracking."""

    def test_creation_recorded(self, manager: ThresholdManager, tenant_id) -> None:
        """Test that creation is recorded."""
        config = manager.create_config(tenant_id=tenant_id)
        history = manager.get_history(config_id=config.config_id)

        assert len(history) >= 1
        assert history[0].change_type == "created"

    def test_update_recorded(self, manager: ThresholdManager, tenant_id) -> None:
        """Test that updates are recorded."""
        config = manager.create_config(tenant_id=tenant_id)
        manager.update_base_thresholds(
            config_id=config.config_id,
            thresholds=ThresholdSet(low_max=35),
            changed_by="admin",
            change_reason="Adjusted",
        )

        history = manager.get_history(config_id=config.config_id)
        assert len(history) >= 2

        update = next((h for h in history if h.change_type == "updated"), None)
        assert update is not None
        assert update.changed_by == "admin"

    def test_history_tracks_previous(self, manager: ThresholdManager, tenant_id) -> None:
        """Test that history tracks previous values."""
        config = manager.create_config(tenant_id=tenant_id)
        original_max = config.base_thresholds.low_max

        manager.update_base_thresholds(
            config_id=config.config_id,
            thresholds=ThresholdSet(low_max=30),
        )

        history = manager.get_history(config_id=config.config_id)
        update = next((h for h in history if h.change_type == "updated"), None)

        assert update.previous_thresholds.low_max == original_max
        assert update.new_thresholds.low_max == 30


# =============================================================================
# Breach Management Tests
# =============================================================================


class TestBreachManagement:
    """Tests for breach management."""

    def test_acknowledge_breach(self, manager: ThresholdManager) -> None:
        """Test acknowledging a breach."""
        breaches = manager.detect_breaches(score=65, previous_score=45)
        breach_id = breaches[0].breach_id

        result = manager.acknowledge_breach(
            breach_id=breach_id,
            acknowledged_by="admin",
        )

        assert result is True
        retrieved = manager.get_breaches()
        acknowledged = next((b for b in retrieved if b.breach_id == breach_id), None)
        assert acknowledged.acknowledged is True

    def test_get_breaches_filtered(self, manager: ThresholdManager, tenant_id) -> None:
        """Test getting breaches with filters."""
        entity1 = uuid7()
        entity2 = uuid7()

        manager.detect_breaches(score=65, previous_score=45, entity_id=entity1, tenant_id=tenant_id)
        manager.detect_breaches(score=85, previous_score=70, entity_id=entity2, tenant_id=tenant_id)

        # Filter by entity
        breaches = manager.get_breaches(entity_id=entity1)
        assert all(b.entity_id == entity1 for b in breaches)

    def test_get_unacknowledged_breaches(self, manager: ThresholdManager) -> None:
        """Test getting unacknowledged breaches."""
        manager.detect_breaches(score=65, previous_score=45)
        manager.detect_breaches(score=85, previous_score=70)

        # Acknowledge first
        breaches = manager.get_breaches()
        manager.acknowledge_breach(breaches[0].breach_id, "admin")

        # Get unacknowledged
        unacked = manager.get_breaches(acknowledged=False)
        assert all(not b.acknowledged for b in unacked)


# =============================================================================
# Template Tests
# =============================================================================


class TestTemplates:
    """Tests for threshold templates."""

    def test_standard_template(self) -> None:
        """Test standard template values."""
        assert STANDARD_THRESHOLDS.low_max == 39
        assert STANDARD_THRESHOLDS.moderate_max == 59
        assert STANDARD_THRESHOLDS.high_max == 79

    def test_conservative_template(self) -> None:
        """Test conservative template is stricter."""
        assert CONSERVATIVE_THRESHOLDS.low_max < STANDARD_THRESHOLDS.low_max
        assert CONSERVATIVE_THRESHOLDS.moderate_max < STANDARD_THRESHOLDS.moderate_max

    def test_lenient_template(self) -> None:
        """Test lenient template is more tolerant."""
        assert LENIENT_THRESHOLDS.low_max > STANDARD_THRESHOLDS.low_max
        assert LENIENT_THRESHOLDS.moderate_max > STANDARD_THRESHOLDS.moderate_max

    def test_apply_template(self, manager: ThresholdManager, tenant_id) -> None:
        """Test applying a template."""
        config = manager.create_config(tenant_id=tenant_id)

        result = manager.apply_template(
            config_id=config.config_id,
            template="conservative",
            changed_by="admin",
        )

        assert result is True
        updated = manager.get_config(config.config_id)
        assert updated.base_thresholds.low_max == CONSERVATIVE_THRESHOLDS.low_max

    def test_apply_role_template(self, manager: ThresholdManager, tenant_id) -> None:
        """Test applying role template."""
        config = manager.create_config(tenant_id=tenant_id)

        result = manager.apply_role_template(
            config_id=config.config_id,
            role=RoleCategory.GOVERNMENT,
        )

        assert result is True
        updated = manager.get_config(config.config_id)
        assert RoleCategory.GOVERNMENT in updated.role_overrides

    def test_role_templates_exist(self) -> None:
        """Test that role templates are defined."""
        expected_roles = [
            RoleCategory.GOVERNMENT,
            RoleCategory.SECURITY,
            RoleCategory.FINANCIAL,
        ]
        for role in expected_roles:
            assert role in ROLE_THRESHOLD_TEMPLATES


# =============================================================================
# Configuration Tests
# =============================================================================


class TestThresholdManagerConfig:
    """Tests for manager configuration."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = ThresholdManagerConfig()
        assert config.default_low_max == 39
        assert config.default_moderate_max == 59
        assert config.default_approach_buffer == 5

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = ThresholdManagerConfig(
            default_low_max=35,
            default_approach_buffer=10,
        )
        assert config.default_low_max == 35
        assert config.default_approach_buffer == 10

    def test_config_affects_manager(self) -> None:
        """Test that config affects manager behavior."""
        config = ThresholdManagerConfig(default_low_max=35)
        manager = ThresholdManager(config=config)

        global_config = manager.get_effective_config()
        assert global_config.base_thresholds.low_max == 35


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for factory function."""

    def test_create_with_defaults(self) -> None:
        """Test creating manager with defaults."""
        manager = create_threshold_manager()
        assert isinstance(manager, ThresholdManager)

    def test_create_with_config(self) -> None:
        """Test creating manager with config."""
        config = ThresholdManagerConfig(default_low_max=30)
        manager = create_threshold_manager(config=config)
        assert manager.config.default_low_max == 30


# =============================================================================
# Serialization Tests
# =============================================================================


class TestSerialization:
    """Tests for serialization."""

    def test_breach_to_dict(self) -> None:
        """Test breach serialization."""
        breach = ThresholdBreach(
            score=75,
            current_level=RiskLevel.HIGH,
            severity=BreachSeverity.ALERT,
        )
        d = breach.to_dict()

        assert d["score"] == 75
        assert d["current_level"] == "high"
        assert d["severity"] == "alert"

    def test_history_to_dict(self) -> None:
        """Test history serialization."""
        history = ThresholdHistory(
            change_type="updated",
            changed_by="admin",
        )
        d = history.to_dict()

        assert d["change_type"] == "updated"
        assert d["changed_by"] == "admin"
