"""Unit tests for compliance type definitions."""

from datetime import timedelta

import pytest

from elile.compliance.types import (
    CheckRestriction,
    CheckResult,
    CheckType,
    ENHANCED_TIER_CHECKS,
    EXPLICIT_CONSENT_CHECKS,
    HIRING_RESTRICTED_CHECKS,
    Locale,
    LocaleConfig,
    RestrictionType,
    RoleCategory,
)


class TestLocaleEnum:
    """Tests for Locale enum."""

    def test_us_locales(self):
        """Test US locale values."""
        assert Locale.US.value == "US"
        assert Locale.US_CA.value == "US_CA"
        assert Locale.US_NY.value == "US_NY"

    def test_eu_locales(self):
        """Test EU locale values."""
        assert Locale.EU.value == "EU"
        assert Locale.UK.value == "UK"
        assert Locale.DE.value == "DE"

    def test_canada_locales(self):
        """Test Canada locale values."""
        assert Locale.CA.value == "CA"
        assert Locale.CA_BC.value == "CA_BC"
        assert Locale.CA_QC.value == "CA_QC"

    def test_apac_locales(self):
        """Test APAC locale values."""
        assert Locale.AU.value == "AU"
        assert Locale.SG.value == "SG"
        assert Locale.JP.value == "JP"

    def test_latam_locales(self):
        """Test LATAM locale values."""
        assert Locale.BR.value == "BR"
        assert Locale.MX.value == "MX"
        assert Locale.AR.value == "AR"


class TestCheckTypeEnum:
    """Tests for CheckType enum."""

    def test_identity_checks(self):
        """Test identity check type values."""
        assert CheckType.IDENTITY_BASIC.value == "identity_basic"
        assert CheckType.IDENTITY_BIOMETRIC.value == "identity_biometric"
        assert CheckType.SSN_TRACE.value == "ssn_trace"

    def test_criminal_checks(self):
        """Test criminal check type values."""
        assert CheckType.CRIMINAL_NATIONAL.value == "criminal_national"
        assert CheckType.CRIMINAL_STATE.value == "criminal_state"
        assert CheckType.CRIMINAL_COUNTY.value == "criminal_county"
        assert CheckType.CRIMINAL_FEDERAL.value == "criminal_federal"

    def test_financial_checks(self):
        """Test financial check type values."""
        assert CheckType.CREDIT_REPORT.value == "credit_report"
        assert CheckType.BANKRUPTCY.value == "bankruptcy"
        assert CheckType.LIENS.value == "liens"

    def test_employment_checks(self):
        """Test employment check type values."""
        assert CheckType.EMPLOYMENT_VERIFICATION.value == "employment_verification"
        assert CheckType.EMPLOYMENT_REFERENCE.value == "employment_reference"

    def test_sanctions_checks(self):
        """Test sanctions check type values."""
        assert CheckType.SANCTIONS_OFAC.value == "sanctions_ofac"
        assert CheckType.SANCTIONS_PEP.value == "sanctions_pep"
        assert CheckType.WATCHLIST_INTERPOL.value == "watchlist_interpol"

    def test_enhanced_tier_checks(self):
        """Test enhanced tier only check types."""
        assert CheckType.DIGITAL_FOOTPRINT.value == "digital_footprint"
        assert CheckType.SOCIAL_MEDIA.value == "social_media"
        assert CheckType.NETWORK_D3.value == "network_d3"
        assert CheckType.DARK_WEB_MONITORING.value == "dark_web_monitoring"


class TestRoleCategoryEnum:
    """Tests for RoleCategory enum."""

    def test_role_categories(self):
        """Test role category values."""
        assert RoleCategory.STANDARD.value == "standard"
        assert RoleCategory.FINANCIAL.value == "financial"
        assert RoleCategory.GOVERNMENT.value == "government"
        assert RoleCategory.HEALTHCARE.value == "healthcare"
        assert RoleCategory.EDUCATION.value == "education"
        assert RoleCategory.EXECUTIVE.value == "executive"


class TestRestrictionTypeEnum:
    """Tests for RestrictionType enum."""

    def test_restriction_types(self):
        """Test restriction type values."""
        assert RestrictionType.BLOCKED.value == "blocked"
        assert RestrictionType.LOOKBACK_LIMITED.value == "lookback_limited"
        assert RestrictionType.CONSENT_REQUIRED.value == "consent_required"
        assert RestrictionType.TIER_RESTRICTED.value == "tier_restricted"


class TestCheckRestriction:
    """Tests for CheckRestriction model."""

    def test_basic_restriction(self):
        """Test creating a basic restriction."""
        restriction = CheckRestriction(
            check_type=CheckType.CRIMINAL_NATIONAL,
            permitted=True,
        )
        assert restriction.check_type == CheckType.CRIMINAL_NATIONAL
        assert restriction.permitted is True
        assert restriction.restriction_type is None
        assert restriction.lookback_days is None

    def test_restriction_with_lookback(self):
        """Test restriction with lookback period."""
        restriction = CheckRestriction(
            check_type=CheckType.CRIMINAL_NATIONAL,
            permitted=True,
            restriction_type=RestrictionType.LOOKBACK_LIMITED,
            lookback_days=2555,  # ~7 years
        )
        assert restriction.lookback_days == 2555
        assert restriction.lookback_period == timedelta(days=2555)

    def test_restriction_no_lookback(self):
        """Test lookback_period when unlimited."""
        restriction = CheckRestriction(
            check_type=CheckType.SANCTIONS_OFAC,
            permitted=True,
            lookback_days=None,
        )
        assert restriction.lookback_period is None

    def test_restriction_with_consent(self):
        """Test restriction requiring consent."""
        restriction = CheckRestriction(
            check_type=CheckType.CREDIT_REPORT,
            permitted=True,
            restriction_type=RestrictionType.CONSENT_REQUIRED,
            requires_consent=True,
        )
        assert restriction.requires_consent is True

    def test_restriction_with_roles(self):
        """Test restriction with role categories."""
        restriction = CheckRestriction(
            check_type=CheckType.CREDIT_REPORT,
            permitted=True,
            restriction_type=RestrictionType.ROLE_RESTRICTED,
            role_categories=[RoleCategory.FINANCIAL, RoleCategory.EXECUTIVE],
        )
        assert RoleCategory.FINANCIAL in restriction.role_categories
        assert RoleCategory.EXECUTIVE in restriction.role_categories

    def test_is_permitted_for_role_no_restriction(self):
        """Test role check with no role restriction."""
        restriction = CheckRestriction(
            check_type=CheckType.CRIMINAL_NATIONAL,
            permitted=True,
            role_categories=[],
        )
        assert restriction.is_permitted_for_role(RoleCategory.STANDARD) is True
        assert restriction.is_permitted_for_role(RoleCategory.FINANCIAL) is True

    def test_is_permitted_for_role_with_restriction(self):
        """Test role check with role restriction."""
        restriction = CheckRestriction(
            check_type=CheckType.CREDIT_REPORT,
            permitted=True,
            role_categories=[RoleCategory.FINANCIAL],
        )
        assert restriction.is_permitted_for_role(RoleCategory.FINANCIAL) is True
        assert restriction.is_permitted_for_role(RoleCategory.STANDARD) is False

    def test_is_permitted_for_role_blocked(self):
        """Test role check when check is blocked."""
        restriction = CheckRestriction(
            check_type=CheckType.CREDIT_REPORT,
            permitted=False,
            restriction_type=RestrictionType.BLOCKED,
        )
        assert restriction.is_permitted_for_role(RoleCategory.FINANCIAL) is False


class TestCheckResult:
    """Tests for CheckResult model."""

    def test_permitted_result(self):
        """Test permitted check result."""
        result = CheckResult(
            check_type=CheckType.CRIMINAL_NATIONAL,
            locale=Locale.US,
            permitted=True,
        )
        assert result.permitted is True
        assert result.block_reason is None

    def test_blocked_result(self):
        """Test blocked check result."""
        result = CheckResult(
            check_type=CheckType.CREDIT_REPORT,
            locale=Locale.EU,
            permitted=False,
            block_reason="Credit checks prohibited under GDPR for most roles",
        )
        assert result.permitted is False
        assert result.block_reason is not None

    def test_result_with_requirements(self):
        """Test result with consent and disclosure requirements."""
        result = CheckResult(
            check_type=CheckType.CRIMINAL_NATIONAL,
            locale=Locale.US,
            permitted=True,
            requires_consent=True,
            requires_disclosure=True,
            lookback_days=2555,
        )
        assert result.requires_consent is True
        assert result.requires_disclosure is True
        assert result.lookback_period == timedelta(days=2555)

    def test_result_with_restrictions(self):
        """Test result with multiple restrictions."""
        restrictions = [
            CheckRestriction(
                check_type=CheckType.CRIMINAL_NATIONAL,
                permitted=True,
                restriction_type=RestrictionType.LOOKBACK_LIMITED,
                lookback_days=2555,
            ),
            CheckRestriction(
                check_type=CheckType.CRIMINAL_NATIONAL,
                permitted=True,
                restriction_type=RestrictionType.DISCLOSURE_REQUIRED,
                requires_disclosure=True,
            ),
        ]
        result = CheckResult(
            check_type=CheckType.CRIMINAL_NATIONAL,
            locale=Locale.US,
            permitted=True,
            restrictions=restrictions,
        )
        assert len(result.restrictions) == 2


class TestLocaleConfig:
    """Tests for LocaleConfig model."""

    def test_us_locale_config(self):
        """Test US locale configuration."""
        config = LocaleConfig(
            locale=Locale.US,
            name="United States",
            framework="FCRA",
            default_lookback_days=2555,  # 7 years
            consent_always_required=True,
            adverse_action_required=True,
            adverse_action_waiting_days=5,
        )
        assert config.locale == Locale.US
        assert config.framework == "FCRA"
        assert config.adverse_action_required is True
        assert config.adverse_action_waiting_days == 5

    def test_eu_locale_config(self):
        """Test EU locale configuration."""
        config = LocaleConfig(
            locale=Locale.EU,
            name="European Union",
            framework="GDPR",
            consent_always_required=True,
            disclosure_always_required=True,
            max_retention_days=365,
            blocked_checks=[CheckType.CREDIT_REPORT, CheckType.CREDIT_SCORE],
        )
        assert config.framework == "GDPR"
        assert CheckType.CREDIT_REPORT in config.blocked_checks
        assert config.max_retention_days == 365

    def test_locale_inheritance(self):
        """Test locale with parent inheritance."""
        config = LocaleConfig(
            locale=Locale.US_CA,
            name="California",
            framework="ICRAA",
            parent_locale=Locale.US,
        )
        assert config.parent_locale == Locale.US

    def test_locale_with_enhanced_checks(self):
        """Test locale with enhanced tier only checks."""
        config = LocaleConfig(
            locale=Locale.US,
            name="United States",
            framework="FCRA",
            enhanced_only_checks=[
                CheckType.DIGITAL_FOOTPRINT,
                CheckType.SOCIAL_MEDIA,
            ],
        )
        assert CheckType.DIGITAL_FOOTPRINT in config.enhanced_only_checks


class TestConstants:
    """Tests for module-level constants."""

    def test_enhanced_tier_checks(self):
        """Test ENHANCED_TIER_CHECKS constant."""
        assert CheckType.IDENTITY_BIOMETRIC in ENHANCED_TIER_CHECKS
        assert CheckType.DIGITAL_FOOTPRINT in ENHANCED_TIER_CHECKS
        assert CheckType.NETWORK_D3 in ENHANCED_TIER_CHECKS
        assert CheckType.DARK_WEB_MONITORING in ENHANCED_TIER_CHECKS

        # Standard checks should not be in enhanced tier
        assert CheckType.CRIMINAL_NATIONAL not in ENHANCED_TIER_CHECKS
        assert CheckType.EMPLOYMENT_VERIFICATION not in ENHANCED_TIER_CHECKS

    def test_explicit_consent_checks(self):
        """Test EXPLICIT_CONSENT_CHECKS constant."""
        assert CheckType.CREDIT_REPORT in EXPLICIT_CONSENT_CHECKS
        assert CheckType.DRUG_TEST in EXPLICIT_CONSENT_CHECKS
        assert CheckType.LOCATION_HISTORY in EXPLICIT_CONSENT_CHECKS

        # Criminal checks don't require explicit consent beyond standard
        assert CheckType.CRIMINAL_NATIONAL not in EXPLICIT_CONSENT_CHECKS

    def test_hiring_restricted_checks(self):
        """Test HIRING_RESTRICTED_CHECKS constant."""
        assert CheckType.DARK_WEB_MONITORING in HIRING_RESTRICTED_CHECKS
        assert CheckType.BEHAVIORAL_DATA in HIRING_RESTRICTED_CHECKS

        # Standard checks are not hiring restricted
        assert CheckType.CRIMINAL_NATIONAL not in HIRING_RESTRICTED_CHECKS
        assert CheckType.EMPLOYMENT_VERIFICATION not in HIRING_RESTRICTED_CHECKS
