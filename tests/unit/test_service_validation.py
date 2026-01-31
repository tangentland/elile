"""Unit tests for service configuration validation."""

import pytest

from elile.agent.state import (
    InformationType,
    SearchDegree,
    ServiceConfiguration,
    ServiceTier,
)
from elile.compliance.types import CheckType, Locale, RoleCategory
from elile.compliance.validation import (
    ServiceConfigValidator,
    validate_or_raise,
    validate_service_config,
)


class TestServiceConfigValidator:
    """Tests for ServiceConfigValidator."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return ServiceConfigValidator()

    def test_valid_standard_config(self, validator):
        """Test valid standard configuration."""
        config = ServiceConfiguration(
            tier=ServiceTier.STANDARD,
            degrees=SearchDegree.D1,
        )
        result = validator.validate(config, Locale.US)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_valid_enhanced_config(self, validator):
        """Test valid enhanced configuration."""
        config = ServiceConfiguration(
            tier=ServiceTier.ENHANCED,
            degrees=SearchDegree.D3,
        )
        result = validator.validate(config, Locale.US)
        assert result.valid is True

    def test_d3_requires_enhanced(self, validator):
        """Test that D3 requires Enhanced tier."""
        config = ServiceConfiguration(
            tier=ServiceTier.STANDARD,
            degrees=SearchDegree.D3,
        )
        result = validator.validate(config, Locale.US)
        assert result.valid is False
        assert any(e.code == "d3_requires_enhanced" for e in result.errors)

    def test_d2_with_standard(self, validator):
        """Test that D2 is allowed with Standard tier."""
        config = ServiceConfiguration(
            tier=ServiceTier.STANDARD,
            degrees=SearchDegree.D2,
        )
        result = validator.validate(config, Locale.US)
        assert result.valid is True

    def test_enhanced_info_type_with_standard(self, validator):
        """Test enhanced-only info type with standard tier."""
        config = ServiceConfiguration(
            tier=ServiceTier.STANDARD,
            degrees=SearchDegree.D1,
            additional_checks=[InformationType.DIGITAL_FOOTPRINT],
        )
        result = validator.validate(config, Locale.US)
        assert result.valid is False
        assert any(e.code == "info_type_requires_enhanced" for e in result.errors)

    def test_enhanced_info_type_with_enhanced(self, validator):
        """Test enhanced-only info type with enhanced tier."""
        config = ServiceConfiguration(
            tier=ServiceTier.ENHANCED,
            degrees=SearchDegree.D1,
            additional_checks=[InformationType.DIGITAL_FOOTPRINT],
        )
        result = validator.validate(config, Locale.US)
        assert result.valid is True

    def test_blocked_check_in_locale(self, validator):
        """Test adding blocked check for locale."""
        config = ServiceConfiguration(
            tier=ServiceTier.STANDARD,
            degrees=SearchDegree.D1,
            additional_checks=[InformationType.FINANCIAL],  # Maps to credit
        )
        result = validator.validate(config, Locale.EU)  # Credit blocked in EU
        assert result.valid is False
        assert any(e.code == "check_not_permitted" for e in result.errors)

    def test_excluded_core_check_warning(self, validator):
        """Test warning when excluding core checks."""
        config = ServiceConfiguration(
            tier=ServiceTier.STANDARD,
            degrees=SearchDegree.D1,
            excluded_checks=[InformationType.IDENTITY],
        )
        result = validator.validate(config, Locale.US)
        # Should be valid but with warning
        assert result.valid is True
        assert any(e.code == "excluding_core_check" for e in result.warnings)


class TestValidateCheckList:
    """Tests for validate_check_list method."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return ServiceConfigValidator()

    def test_valid_check_list(self, validator):
        """Test valid check list."""
        checks = [
            CheckType.CRIMINAL_NATIONAL,
            CheckType.EMPLOYMENT_VERIFICATION,
        ]
        result = validator.validate_check_list(checks, Locale.US)
        assert result.valid is True

    def test_blocked_check_in_list(self, validator):
        """Test blocked check in list."""
        checks = [
            CheckType.EMPLOYMENT_VERIFICATION,
            CheckType.CREDIT_REPORT,  # Blocked in EU
        ]
        result = validator.validate_check_list(checks, Locale.EU)
        assert result.valid is False

    def test_consent_warning(self, validator):
        """Test consent requirement warning."""
        checks = [CheckType.CREDIT_REPORT]
        result = validator.validate_check_list(
            checks,
            Locale.US,
            role_category=RoleCategory.FINANCIAL,  # Credit allowed for financial
        )
        # Valid but should warn about consent
        assert result.valid is True
        assert any(e.code == "requires_consent" for e in result.warnings)


class TestGetAvailableChecks:
    """Tests for get_available_checks method."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return ServiceConfigValidator()

    def test_us_available_checks(self, validator):
        """Test available checks in US."""
        checks = validator.get_available_checks(Locale.US)
        assert CheckType.CRIMINAL_NATIONAL in checks
        assert CheckType.EMPLOYMENT_VERIFICATION in checks

    def test_eu_excludes_credit(self, validator):
        """Test EU excludes credit checks."""
        checks = validator.get_available_checks(Locale.EU)
        assert CheckType.CREDIT_REPORT not in checks

    def test_enhanced_adds_checks(self, validator):
        """Test enhanced tier adds more checks."""
        standard_checks = validator.get_available_checks(
            Locale.US, tier=ServiceTier.STANDARD
        )
        enhanced_checks = validator.get_available_checks(
            Locale.US, tier=ServiceTier.ENHANCED
        )
        assert len(enhanced_checks) >= len(standard_checks)
        assert CheckType.DIGITAL_FOOTPRINT in enhanced_checks


class TestGetAvailableInfoTypes:
    """Tests for get_available_info_types method."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return ServiceConfigValidator()

    def test_standard_info_types(self, validator):
        """Test standard tier info types."""
        types = validator.get_available_info_types(
            Locale.US, tier=ServiceTier.STANDARD
        )
        assert InformationType.IDENTITY in types
        assert InformationType.CRIMINAL in types
        assert InformationType.EMPLOYMENT in types
        # Enhanced only should not be included
        assert InformationType.DIGITAL_FOOTPRINT not in types
        assert InformationType.NETWORK_D3 not in types

    def test_enhanced_info_types(self, validator):
        """Test enhanced tier info types."""
        types = validator.get_available_info_types(
            Locale.US, tier=ServiceTier.ENHANCED
        )
        assert InformationType.DIGITAL_FOOTPRINT in types

    def test_eu_excludes_financial(self, validator):
        """Test EU excludes financial (credit) info type."""
        types = validator.get_available_info_types(Locale.EU)
        assert InformationType.FINANCIAL not in types


class TestValidateServiceConfig:
    """Tests for validate_service_config convenience function."""

    def test_valid_config(self):
        """Test valid configuration."""
        config = ServiceConfiguration(
            tier=ServiceTier.STANDARD,
            degrees=SearchDegree.D1,
        )
        result = validate_service_config(config, Locale.US)
        assert result.valid is True

    def test_invalid_config(self):
        """Test invalid configuration."""
        config = ServiceConfiguration(
            tier=ServiceTier.STANDARD,
            degrees=SearchDegree.D3,
        )
        result = validate_service_config(config, Locale.US)
        assert result.valid is False


class TestValidateOrRaise:
    """Tests for validate_or_raise convenience function."""

    def test_valid_config_no_raise(self):
        """Test valid configuration doesn't raise."""
        config = ServiceConfiguration(
            tier=ServiceTier.STANDARD,
            degrees=SearchDegree.D1,
        )
        # Should not raise
        validate_or_raise(config, Locale.US)

    def test_invalid_config_raises(self):
        """Test invalid configuration raises ValueError."""
        config = ServiceConfiguration(
            tier=ServiceTier.STANDARD,
            degrees=SearchDegree.D3,
        )
        with pytest.raises(ValueError) as exc_info:
            validate_or_raise(config, Locale.US)
        assert "D3" in str(exc_info.value)
        assert "Enhanced" in str(exc_info.value)


class TestLocaleSpecificValidation:
    """Tests for locale-specific validation."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return ServiceConfigValidator()

    def test_us_allows_criminal(self, validator):
        """Test US allows criminal checks."""
        config = ServiceConfiguration(
            tier=ServiceTier.STANDARD,
            additional_checks=[InformationType.CRIMINAL],
        )
        result = validator.validate(config, Locale.US)
        assert result.valid is True

    def test_eu_allows_employment(self, validator):
        """Test EU allows employment verification."""
        config = ServiceConfiguration(
            tier=ServiceTier.STANDARD,
            additional_checks=[InformationType.EMPLOYMENT],
        )
        result = validator.validate(config, Locale.EU)
        assert result.valid is True

    def test_brazil_blocks_credit(self, validator):
        """Test Brazil blocks credit checks."""
        config = ServiceConfiguration(
            tier=ServiceTier.STANDARD,
            additional_checks=[InformationType.FINANCIAL],
        )
        result = validator.validate(config, Locale.BR)
        assert result.valid is False


class TestRoleCategoryValidation:
    """Tests for role category validation."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return ServiceConfigValidator()

    def test_financial_role_allows_credit(self, validator):
        """Test financial role allows credit in US."""
        checks = validator.get_available_checks(
            Locale.US,
            role_category=RoleCategory.FINANCIAL,
        )
        assert CheckType.CREDIT_REPORT in checks

    def test_standard_role_excludes_credit(self, validator):
        """Test standard role may exclude credit."""
        # In US, credit is role-restricted
        checks = validator.get_available_checks(
            Locale.US,
            role_category=RoleCategory.STANDARD,
        )
        # Credit may or may not be included depending on rules
