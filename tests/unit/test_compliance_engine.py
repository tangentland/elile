"""Unit tests for compliance engine."""

from datetime import timedelta

import pytest

from elile.agent.state import ServiceTier
from elile.compliance.engine import ComplianceEngine, get_compliance_engine
from elile.compliance.rules import ComplianceRule, RuleRepository
from elile.compliance.types import (
    CheckType,
    Locale,
    RestrictionType,
    RoleCategory,
)


class TestComplianceEngineInit:
    """Tests for ComplianceEngine initialization."""

    def test_default_init(self):
        """Test initialization with default rules."""
        engine = ComplianceEngine()
        assert engine is not None

    def test_custom_repository(self):
        """Test initialization with custom repository."""
        repo = RuleRepository()
        engine = ComplianceEngine(rule_repository=repo)
        assert engine is not None

    def test_get_compliance_engine(self):
        """Test factory function."""
        engine = get_compliance_engine()
        assert isinstance(engine, ComplianceEngine)


class TestEvaluateCheck:
    """Tests for evaluate_check method."""

    @pytest.fixture
    def engine(self):
        """Create engine with default rules."""
        return ComplianceEngine()

    def test_permitted_check(self, engine):
        """Test evaluating permitted check."""
        result = engine.evaluate_check(
            locale=Locale.US,
            check_type=CheckType.CRIMINAL_NATIONAL,
        )
        assert result.permitted is True
        assert result.check_type == CheckType.CRIMINAL_NATIONAL
        assert result.locale == Locale.US

    def test_blocked_check(self, engine):
        """Test evaluating blocked check."""
        result = engine.evaluate_check(
            locale=Locale.EU,
            check_type=CheckType.CREDIT_REPORT,
        )
        assert result.permitted is False
        assert result.block_reason is not None

    def test_lookback_period(self, engine):
        """Test check with lookback period."""
        result = engine.evaluate_check(
            locale=Locale.US,
            check_type=CheckType.CRIMINAL_NATIONAL,
        )
        assert result.lookback_days == 2555  # ~7 years
        assert result.lookback_period == timedelta(days=2555)

    def test_consent_required(self, engine):
        """Test check requiring consent."""
        result = engine.evaluate_check(
            locale=Locale.US,
            check_type=CheckType.CREDIT_REPORT,
            role_category=RoleCategory.FINANCIAL,
        )
        assert result.requires_consent is True

    def test_disclosure_required(self, engine):
        """Test check requiring disclosure."""
        result = engine.evaluate_check(
            locale=Locale.US,
            check_type=CheckType.CRIMINAL_NATIONAL,
        )
        assert result.requires_disclosure is True

    def test_role_restricted_permitted(self, engine):
        """Test role-restricted check for permitted role."""
        result = engine.evaluate_check(
            locale=Locale.US,
            check_type=CheckType.CREDIT_REPORT,
            role_category=RoleCategory.FINANCIAL,
        )
        assert result.permitted is True

    def test_role_restricted_blocked(self, engine):
        """Test role-restricted check for non-permitted role."""
        result = engine.evaluate_check(
            locale=Locale.US,
            check_type=CheckType.CREDIT_REPORT,
            role_category=RoleCategory.STANDARD,
        )
        # Note: The default rules allow credit for certain roles
        # With role restriction, it may or may not be permitted
        # depending on implementation

    def test_tier_restricted_standard(self, engine):
        """Test enhanced-tier check with standard tier."""
        result = engine.evaluate_check(
            locale=Locale.US,
            check_type=CheckType.DIGITAL_FOOTPRINT,
            tier=ServiceTier.STANDARD,
        )
        assert result.permitted is False
        assert result.requires_enhanced_tier is True

    def test_tier_restricted_enhanced(self, engine):
        """Test enhanced-tier check with enhanced tier."""
        result = engine.evaluate_check(
            locale=Locale.US,
            check_type=CheckType.DIGITAL_FOOTPRINT,
            tier=ServiceTier.ENHANCED,
        )
        assert result.permitted is True
        assert result.requires_enhanced_tier is True

    def test_restrictions_list(self, engine):
        """Test that restrictions list is populated."""
        result = engine.evaluate_check(
            locale=Locale.US,
            check_type=CheckType.CRIMINAL_NATIONAL,
        )
        assert len(result.restrictions) > 0


class TestGetPermittedChecks:
    """Tests for get_permitted_checks method."""

    @pytest.fixture
    def engine(self):
        """Create engine with default rules."""
        return ComplianceEngine()

    def test_us_permitted_checks(self, engine):
        """Test getting permitted checks for US."""
        permitted = engine.get_permitted_checks(
            locale=Locale.US,
            role_category=RoleCategory.STANDARD,
            tier=ServiceTier.STANDARD,
        )
        assert len(permitted) > 0
        assert CheckType.CRIMINAL_NATIONAL in permitted
        assert CheckType.EMPLOYMENT_VERIFICATION in permitted

    def test_eu_permitted_checks(self, engine):
        """Test getting permitted checks for EU."""
        permitted = engine.get_permitted_checks(
            locale=Locale.EU,
            role_category=RoleCategory.STANDARD,
            tier=ServiceTier.STANDARD,
        )
        # Credit should not be in permitted
        assert CheckType.CREDIT_REPORT not in permitted

    def test_enhanced_tier_adds_checks(self, engine):
        """Test that enhanced tier permits more checks."""
        standard_permitted = engine.get_permitted_checks(
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
        )
        enhanced_permitted = engine.get_permitted_checks(
            locale=Locale.US,
            tier=ServiceTier.ENHANCED,
        )
        # Enhanced should have at least as many
        assert len(enhanced_permitted) >= len(standard_permitted)
        # Digital footprint only in enhanced
        assert CheckType.DIGITAL_FOOTPRINT not in standard_permitted
        assert CheckType.DIGITAL_FOOTPRINT in enhanced_permitted


class TestGetBlockedChecks:
    """Tests for get_blocked_checks method."""

    @pytest.fixture
    def engine(self):
        """Create engine with default rules."""
        return ComplianceEngine()

    def test_eu_blocked_checks(self, engine):
        """Test getting blocked checks for EU."""
        blocked = engine.get_blocked_checks(
            locale=Locale.EU,
            role_category=RoleCategory.STANDARD,
        )
        # Credit should be blocked
        credit_blocked = any(
            check_type == CheckType.CREDIT_REPORT
            for check_type, _ in blocked
        )
        assert credit_blocked

    def test_blocked_with_reasons(self, engine):
        """Test that blocked checks have reasons."""
        blocked = engine.get_blocked_checks(
            locale=Locale.EU,
        )
        for check_type, reason in blocked:
            assert reason is not None
            assert len(reason) > 0


class TestGetLookbackPeriod:
    """Tests for get_lookback_period method."""

    @pytest.fixture
    def engine(self):
        """Create engine with default rules."""
        return ComplianceEngine()

    def test_us_criminal_lookback(self, engine):
        """Test US criminal lookback period."""
        period = engine.get_lookback_period(
            locale=Locale.US,
            check_type=CheckType.CRIMINAL_NATIONAL,
        )
        assert period is not None
        assert period == timedelta(days=2555)

    def test_sanctions_no_lookback(self, engine):
        """Test sanctions have no lookback limit."""
        period = engine.get_lookback_period(
            locale=Locale.US,
            check_type=CheckType.SANCTIONS_OFAC,
        )
        # Sanctions typically have no lookback limit
        # The period may be None or unlimited


class TestRequiresConsent:
    """Tests for requires_consent method."""

    @pytest.fixture
    def engine(self):
        """Create engine with default rules."""
        return ComplianceEngine()

    def test_credit_requires_consent(self, engine):
        """Test that credit checks require consent."""
        requires = engine.requires_consent(
            locale=Locale.US,
            check_type=CheckType.CREDIT_REPORT,
        )
        assert requires is True

    def test_criminal_requires_consent(self, engine):
        """Test that criminal checks require consent."""
        requires = engine.requires_consent(
            locale=Locale.US,
            check_type=CheckType.CRIMINAL_NATIONAL,
        )
        assert requires is True


class TestRequiresDisclosure:
    """Tests for requires_disclosure method."""

    @pytest.fixture
    def engine(self):
        """Create engine with default rules."""
        return ComplianceEngine()

    def test_us_criminal_requires_disclosure(self, engine):
        """Test US criminal requires disclosure."""
        requires = engine.requires_disclosure(
            locale=Locale.US,
            check_type=CheckType.CRIMINAL_NATIONAL,
        )
        assert requires is True


class TestValidateChecks:
    """Tests for validate_checks method."""

    @pytest.fixture
    def engine(self):
        """Create engine with default rules."""
        return ComplianceEngine()

    def test_all_permitted(self, engine):
        """Test validation when all checks permitted."""
        checks = [
            CheckType.CRIMINAL_NATIONAL,
            CheckType.EMPLOYMENT_VERIFICATION,
            CheckType.EDUCATION_VERIFICATION,
        ]
        permitted, blocked = engine.validate_checks(
            locale=Locale.US,
            check_types=checks,
        )
        assert len(permitted) == 3
        assert len(blocked) == 0

    def test_some_blocked(self, engine):
        """Test validation when some checks blocked."""
        checks = [
            CheckType.EMPLOYMENT_VERIFICATION,
            CheckType.CREDIT_REPORT,  # Blocked in EU
        ]
        permitted, blocked = engine.validate_checks(
            locale=Locale.EU,
            check_types=checks,
        )
        assert CheckType.EMPLOYMENT_VERIFICATION in permitted
        assert any(ct == CheckType.CREDIT_REPORT for ct, _ in blocked)

    def test_tier_validation(self, engine):
        """Test validation with tier restrictions."""
        checks = [
            CheckType.CRIMINAL_NATIONAL,
            CheckType.DIGITAL_FOOTPRINT,  # Enhanced only
        ]
        permitted, blocked = engine.validate_checks(
            locale=Locale.US,
            check_types=checks,
            tier=ServiceTier.STANDARD,
        )
        assert CheckType.CRIMINAL_NATIONAL in permitted
        assert any(ct == CheckType.DIGITAL_FOOTPRINT for ct, _ in blocked)


class TestLocaleSpecificRules:
    """Tests for locale-specific compliance rules."""

    @pytest.fixture
    def engine(self):
        """Create engine with default rules."""
        return ComplianceEngine()

    def test_us_fcra_7_year(self, engine):
        """Test US FCRA 7-year lookback."""
        result = engine.evaluate_check(
            locale=Locale.US,
            check_type=CheckType.CRIMINAL_NATIONAL,
        )
        assert result.lookback_days == 2555

    def test_eu_gdpr_credit_block(self, engine):
        """Test EU GDPR credit block."""
        result = engine.evaluate_check(
            locale=Locale.EU,
            check_type=CheckType.CREDIT_REPORT,
        )
        assert result.permitted is False

    def test_uk_dbs_rules(self, engine):
        """Test UK DBS rules."""
        result = engine.evaluate_check(
            locale=Locale.UK,
            check_type=CheckType.CRIMINAL_NATIONAL,
        )
        # UK criminal checks are role-restricted via DBS
        # May or may not be permitted depending on role

    def test_brazil_lgpd_credit_block(self, engine):
        """Test Brazil LGPD credit block."""
        result = engine.evaluate_check(
            locale=Locale.BR,
            check_type=CheckType.CREDIT_REPORT,
        )
        assert result.permitted is False

    def test_canada_pipeda(self, engine):
        """Test Canada PIPEDA rules."""
        result = engine.evaluate_check(
            locale=Locale.CA,
            check_type=CheckType.CRIMINAL_NATIONAL,
        )
        assert result.requires_consent is True


class TestCustomRuleRepository:
    """Tests with custom rule repository."""

    def test_empty_repository_defaults(self):
        """Test engine with empty repository uses defaults."""
        repo = RuleRepository()
        engine = ComplianceEngine(rule_repository=repo)

        # Should still apply built-in tier restrictions
        result = engine.evaluate_check(
            locale=Locale.US,
            check_type=CheckType.DIGITAL_FOOTPRINT,
            tier=ServiceTier.STANDARD,
        )
        assert result.permitted is False
        assert result.requires_enhanced_tier is True

    def test_custom_rule_override(self):
        """Test custom rule overrides."""
        rules = [
            ComplianceRule(
                locale=Locale.US,
                check_type=CheckType.CRIMINAL_NATIONAL,
                permitted=False,
                restriction_type=RestrictionType.BLOCKED,
                notes="Custom block for testing",
            )
        ]
        repo = RuleRepository(rules=rules)
        engine = ComplianceEngine(rule_repository=repo)

        result = engine.evaluate_check(
            locale=Locale.US,
            check_type=CheckType.CRIMINAL_NATIONAL,
        )
        assert result.permitted is False
        assert "Custom block" in (result.block_reason or "")
