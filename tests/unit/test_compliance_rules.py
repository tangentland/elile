"""Unit tests for compliance rules repository."""

import pytest

from elile.agent.state import ServiceTier
from elile.compliance.default_rules import get_default_rules
from elile.compliance.rules import ComplianceRule, RuleRepository
from elile.compliance.types import (
    CheckType,
    Locale,
    RestrictionType,
    RoleCategory,
)


class TestComplianceRule:
    """Tests for ComplianceRule model."""

    def test_basic_rule(self):
        """Test creating a basic rule."""
        rule = ComplianceRule(
            locale=Locale.US,
            check_type=CheckType.CRIMINAL_NATIONAL,
            permitted=True,
        )
        assert rule.locale == Locale.US
        assert rule.check_type == CheckType.CRIMINAL_NATIONAL
        assert rule.permitted is True
        assert rule.role_category is None

    def test_rule_with_lookback(self):
        """Test rule with lookback period."""
        rule = ComplianceRule(
            locale=Locale.US,
            check_type=CheckType.CRIMINAL_NATIONAL,
            permitted=True,
            restriction_type=RestrictionType.LOOKBACK_LIMITED,
            lookback_days=2555,
        )
        assert rule.lookback_days == 2555

    def test_rule_with_role(self):
        """Test rule with role category."""
        rule = ComplianceRule(
            locale=Locale.US,
            check_type=CheckType.CREDIT_REPORT,
            role_category=RoleCategory.FINANCIAL,
            permitted=True,
        )
        assert rule.role_category == RoleCategory.FINANCIAL

    def test_rule_with_permitted_roles(self):
        """Test rule with permitted roles list."""
        rule = ComplianceRule(
            locale=Locale.US,
            check_type=CheckType.CREDIT_REPORT,
            permitted=True,
            permitted_roles=[RoleCategory.FINANCIAL, RoleCategory.EXECUTIVE],
        )
        assert RoleCategory.FINANCIAL in rule.permitted_roles
        assert RoleCategory.EXECUTIVE in rule.permitted_roles

    def test_rule_blocked(self):
        """Test blocked rule."""
        rule = ComplianceRule(
            locale=Locale.EU,
            check_type=CheckType.CREDIT_REPORT,
            permitted=False,
            restriction_type=RestrictionType.BLOCKED,
            notes="GDPR prohibits credit checks",
        )
        assert rule.permitted is False
        assert rule.restriction_type == RestrictionType.BLOCKED

    def test_to_restriction(self):
        """Test converting rule to restriction."""
        rule = ComplianceRule(
            locale=Locale.US,
            check_type=CheckType.CRIMINAL_NATIONAL,
            permitted=True,
            restriction_type=RestrictionType.LOOKBACK_LIMITED,
            lookback_days=2555,
            requires_consent=True,
            requires_disclosure=True,
        )
        restriction = rule.to_restriction()

        assert restriction.check_type == CheckType.CRIMINAL_NATIONAL
        assert restriction.permitted is True
        assert restriction.lookback_days == 2555
        assert restriction.requires_consent is True
        assert restriction.requires_disclosure is True


class TestRuleRepository:
    """Tests for RuleRepository."""

    @pytest.fixture
    def sample_rules(self):
        """Create sample rules for testing."""
        return [
            ComplianceRule(
                locale=Locale.US,
                check_type=CheckType.CRIMINAL_NATIONAL,
                permitted=True,
                lookback_days=2555,
            ),
            ComplianceRule(
                locale=Locale.US,
                check_type=CheckType.CREDIT_REPORT,
                permitted=True,
                permitted_roles=[RoleCategory.FINANCIAL],
            ),
            ComplianceRule(
                locale=Locale.US,
                check_type=CheckType.CREDIT_REPORT,
                role_category=RoleCategory.STANDARD,
                permitted=False,
                restriction_type=RestrictionType.ROLE_RESTRICTED,
            ),
            ComplianceRule(
                locale=Locale.EU,
                check_type=CheckType.CREDIT_REPORT,
                permitted=False,
                restriction_type=RestrictionType.BLOCKED,
            ),
            ComplianceRule(
                locale=Locale.US_CA,
                check_type=CheckType.CRIMINAL_COUNTY,
                permitted=True,
                lookback_days=2555,
                notes="California ICRAA",
            ),
        ]

    def test_empty_repository(self):
        """Test creating empty repository."""
        repo = RuleRepository()
        assert repo.count() == 0

    def test_load_rules(self, sample_rules):
        """Test loading rules."""
        repo = RuleRepository(rules=sample_rules)
        assert repo.count() == 5

    def test_get_rules_for_locale(self, sample_rules):
        """Test getting rules by locale."""
        repo = RuleRepository(rules=sample_rules)

        us_rules = repo.get_rules_for_locale(Locale.US)
        assert len(us_rules) == 3

        eu_rules = repo.get_rules_for_locale(Locale.EU)
        assert len(eu_rules) == 1

    def test_get_rules_for_check(self, sample_rules):
        """Test getting rules by check type."""
        repo = RuleRepository(rules=sample_rules)

        credit_rules = repo.get_rules_for_check(CheckType.CREDIT_REPORT)
        assert len(credit_rules) == 3  # US general, US standard role, EU

        criminal_rules = repo.get_rules_for_check(CheckType.CRIMINAL_NATIONAL)
        assert len(criminal_rules) == 1

    def test_get_rule_exact_match(self, sample_rules):
        """Test getting rule with exact match."""
        repo = RuleRepository(rules=sample_rules)

        rule = repo.get_rule(Locale.US, CheckType.CRIMINAL_NATIONAL)
        assert rule is not None
        assert rule.locale == Locale.US
        assert rule.check_type == CheckType.CRIMINAL_NATIONAL

    def test_get_rule_with_role(self, sample_rules):
        """Test getting rule with specific role."""
        repo = RuleRepository(rules=sample_rules)

        # Should get role-specific rule
        rule = repo.get_rule(Locale.US, CheckType.CREDIT_REPORT, RoleCategory.STANDARD)
        assert rule is not None
        assert rule.role_category == RoleCategory.STANDARD
        assert rule.permitted is False

    def test_get_rule_no_match(self, sample_rules):
        """Test getting rule with no match."""
        repo = RuleRepository(rules=sample_rules)

        rule = repo.get_rule(Locale.JP, CheckType.CRIMINAL_NATIONAL)
        assert rule is None

    def test_get_rule_parent_locale(self, sample_rules):
        """Test rule inheritance from parent locale."""
        repo = RuleRepository(rules=sample_rules)

        # US_CA should inherit from US for criminal national
        rule = repo.get_rule(Locale.US_CA, CheckType.CRIMINAL_NATIONAL)
        assert rule is not None
        assert rule.locale == Locale.US  # Inherited from parent

    def test_get_rule_child_override(self, sample_rules):
        """Test child locale overrides parent."""
        repo = RuleRepository(rules=sample_rules)

        # US_CA has specific rule for criminal county
        rule = repo.get_rule(Locale.US_CA, CheckType.CRIMINAL_COUNTY)
        assert rule is not None
        assert rule.locale == Locale.US_CA

    def test_get_effective_rule_permitted(self, sample_rules):
        """Test getting effective restriction for permitted check."""
        repo = RuleRepository(rules=sample_rules)

        restriction = repo.get_effective_rule(
            Locale.US,
            CheckType.CRIMINAL_NATIONAL,
        )
        assert restriction.permitted is True
        assert restriction.lookback_days == 2555

    def test_get_effective_rule_blocked(self, sample_rules):
        """Test getting effective restriction for blocked check."""
        repo = RuleRepository(rules=sample_rules)

        restriction = repo.get_effective_rule(
            Locale.EU,
            CheckType.CREDIT_REPORT,
        )
        assert restriction.permitted is False
        assert restriction.restriction_type == RestrictionType.BLOCKED

    def test_get_effective_rule_enhanced_tier(self):
        """Test enhanced tier check with standard tier."""
        repo = RuleRepository()

        # Digital footprint requires enhanced tier
        restriction = repo.get_effective_rule(
            Locale.US,
            CheckType.DIGITAL_FOOTPRINT,
            tier=ServiceTier.STANDARD,
        )
        assert restriction.permitted is False
        assert restriction.restriction_type == RestrictionType.TIER_RESTRICTED

    def test_get_effective_rule_enhanced_tier_allowed(self):
        """Test enhanced tier check with enhanced tier."""
        repo = RuleRepository()

        restriction = repo.get_effective_rule(
            Locale.US,
            CheckType.DIGITAL_FOOTPRINT,
            tier=ServiceTier.ENHANCED,
        )
        assert restriction.permitted is True
        assert restriction.requires_enhanced_tier is True

    def test_get_effective_rule_consent_required(self):
        """Test explicit consent requirement."""
        repo = RuleRepository()

        restriction = repo.get_effective_rule(
            Locale.US,
            CheckType.CREDIT_REPORT,
        )
        assert restriction.requires_consent is True

    def test_get_effective_rule_role_restricted(self, sample_rules):
        """Test role restriction enforcement."""
        repo = RuleRepository(rules=sample_rules)

        # Credit report for standard role should be blocked
        restriction = repo.get_effective_rule(
            Locale.US,
            CheckType.CREDIT_REPORT,
            role_category=RoleCategory.STANDARD,
        )
        assert restriction.permitted is False
        assert restriction.restriction_type == RestrictionType.ROLE_RESTRICTED

    def test_all_rules(self, sample_rules):
        """Test getting all rules."""
        repo = RuleRepository(rules=sample_rules)

        all_rules = repo.all_rules()
        assert len(all_rules) == 5

    def test_with_default_rules(self):
        """Test creating repository with default rules."""
        repo = RuleRepository.with_default_rules()

        assert repo.count() > 0

        # Check that US rules exist
        us_rules = repo.get_rules_for_locale(Locale.US)
        assert len(us_rules) > 0

        # Check that EU rules exist
        eu_rules = repo.get_rules_for_locale(Locale.EU)
        assert len(eu_rules) > 0


class TestDefaultRules:
    """Tests for default compliance rules."""

    def test_default_rules_loaded(self):
        """Test that default rules are loaded."""
        rules = get_default_rules()
        assert len(rules) > 0

    def test_us_fcra_lookback(self):
        """Test US FCRA 7-year lookback rule."""
        repo = RuleRepository.with_default_rules()

        rule = repo.get_rule(Locale.US, CheckType.CRIMINAL_NATIONAL)
        assert rule is not None
        assert rule.lookback_days == 2555  # ~7 years

    def test_us_credit_role_restriction(self):
        """Test US credit check role restriction."""
        repo = RuleRepository.with_default_rules()

        rule = repo.get_rule(Locale.US, CheckType.CREDIT_REPORT)
        assert rule is not None
        assert rule.restriction_type == RestrictionType.ROLE_RESTRICTED
        assert RoleCategory.FINANCIAL in rule.permitted_roles

    def test_eu_credit_blocked(self):
        """Test EU credit check blocked."""
        repo = RuleRepository.with_default_rules()

        rule = repo.get_rule(Locale.EU, CheckType.CREDIT_REPORT)
        assert rule is not None
        assert rule.permitted is False
        assert rule.restriction_type == RestrictionType.BLOCKED

    def test_eu_criminal_role_restricted(self):
        """Test EU criminal check role restriction."""
        repo = RuleRepository.with_default_rules()

        rule = repo.get_rule(Locale.EU, CheckType.CRIMINAL_NATIONAL)
        assert rule is not None
        assert rule.restriction_type == RestrictionType.ROLE_RESTRICTED

    def test_canada_pipeda(self):
        """Test Canada PIPEDA rules."""
        repo = RuleRepository.with_default_rules()

        rule = repo.get_rule(Locale.CA, CheckType.CRIMINAL_NATIONAL)
        assert rule is not None
        assert rule.requires_consent is True

    def test_brazil_lgpd_credit_blocked(self):
        """Test Brazil LGPD credit check blocked."""
        repo = RuleRepository.with_default_rules()

        rule = repo.get_rule(Locale.BR, CheckType.CREDIT_REPORT)
        assert rule is not None
        assert rule.permitted is False

    def test_uk_dbs_rules(self):
        """Test UK DBS rules."""
        repo = RuleRepository.with_default_rules()

        rule = repo.get_rule(Locale.UK, CheckType.CRIMINAL_NATIONAL)
        assert rule is not None
        assert rule.restriction_type == RestrictionType.ROLE_RESTRICTED

    def test_australia_rules(self):
        """Test Australia rules."""
        repo = RuleRepository.with_default_rules()

        rule = repo.get_rule(Locale.AU, CheckType.CRIMINAL_NATIONAL)
        assert rule is not None
        assert rule.requires_consent is True


class TestParentLocaleInheritance:
    """Tests for parent locale inheritance."""

    def test_us_state_inherits_us(self):
        """Test US state locales inherit from US."""
        repo = RuleRepository.with_default_rules()

        # US_CA should inherit sanctions rule from US
        restriction = repo.get_effective_rule(
            Locale.US_CA,
            CheckType.SANCTIONS_OFAC,
        )
        assert restriction.permitted is True

    def test_canada_province_inherits_canada(self):
        """Test Canada province locales inherit from Canada."""
        repo = RuleRepository.with_default_rules()

        # CA_BC should inherit employment verification from CA
        restriction = repo.get_effective_rule(
            Locale.CA_BC,
            CheckType.EMPLOYMENT_VERIFICATION,
        )
        assert restriction.permitted is True

    def test_eu_country_inherits_eu(self):
        """Test EU country locales inherit from EU."""
        repo = RuleRepository.with_default_rules()

        # DE should inherit credit block from EU
        restriction = repo.get_effective_rule(
            Locale.DE,
            CheckType.CREDIT_REPORT,
        )
        assert restriction.permitted is False
