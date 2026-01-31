"""Unit tests for Entity Validation.

Tests the EntityValidator class and validation functions.
"""

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from elile.db.models.entity import Entity
from elile.entity import (
    EntityValidator,
    IdentifierType,
    SubjectIdentifiers,
    ValidationError,
    ValidationResult,
    ValidationSeverity,
    ValidationWarning,
    validate_identifier,
    validate_or_raise,
    validate_subject,
)


# =============================================================================
# ValidationResult Tests
# =============================================================================


class TestValidationResult:
    """Tests for ValidationResult model."""

    def test_valid_result(self):
        """Test creating a valid result."""
        result = ValidationResult()
        assert result.valid is True
        assert result.has_errors is False
        assert result.has_warnings is False

    def test_result_with_errors(self):
        """Test result with errors."""
        result = ValidationResult(
            valid=False,
            errors=[
                ValidationError(field="ssn", message="Invalid SSN"),
            ],
        )
        assert result.valid is False
        assert result.has_errors is True
        assert len(result.errors) == 1

    def test_result_with_warnings(self):
        """Test result with warnings."""
        result = ValidationResult(
            valid=True,
            warnings=[
                ValidationWarning(field="phone", message="Consider E.164 format"),
            ],
        )
        assert result.valid is True
        assert result.has_warnings is True
        assert len(result.warnings) == 1

    def test_merge_results(self):
        """Test merging two validation results."""
        result1 = ValidationResult(
            valid=True,
            warnings=[ValidationWarning(field="a", message="Warning A")],
        )
        result2 = ValidationResult(
            valid=False,
            errors=[ValidationError(field="b", message="Error B")],
        )

        merged = result1.merge(result2)

        assert merged.valid is False
        assert len(merged.warnings) == 1
        assert len(merged.errors) == 1


# =============================================================================
# SSN Validation Tests
# =============================================================================


class TestSSNValidation:
    """Tests for SSN validation."""

    @pytest.fixture
    def validator(self):
        """Create EntityValidator instance."""
        return EntityValidator()

    def test_valid_ssn_formatted(self, validator):
        """Test valid SSN with dashes."""
        result = validator.validate_identifier(IdentifierType.SSN, "123-45-6789")
        assert result.valid is True

    def test_valid_ssn_unformatted(self, validator):
        """Test valid SSN without formatting."""
        result = validator.validate_identifier(IdentifierType.SSN, "123456789")
        assert result.valid is True

    def test_ssn_too_short(self, validator):
        """Test SSN with too few digits."""
        result = validator.validate_identifier(IdentifierType.SSN, "12345678")
        assert result.valid is False
        assert any(e.code == "ssn_invalid_length" for e in result.errors)

    def test_ssn_too_long(self, validator):
        """Test SSN with too many digits."""
        result = validator.validate_identifier(IdentifierType.SSN, "1234567890")
        assert result.valid is False

    def test_ssn_invalid_area_000(self, validator):
        """Test SSN with area 000."""
        result = validator.validate_identifier(IdentifierType.SSN, "000-12-3456")
        assert result.valid is False
        assert any(e.code == "ssn_invalid_area" for e in result.errors)

    def test_ssn_invalid_area_666(self, validator):
        """Test SSN with area 666."""
        result = validator.validate_identifier(IdentifierType.SSN, "666-12-3456")
        assert result.valid is False
        assert any(e.code == "ssn_invalid_area" for e in result.errors)

    def test_ssn_invalid_area_900s(self, validator):
        """Test SSN with area in 900s."""
        result = validator.validate_identifier(IdentifierType.SSN, "900-12-3456")
        assert result.valid is False
        result = validator.validate_identifier(IdentifierType.SSN, "999-12-3456")
        assert result.valid is False

    def test_ssn_invalid_group_00(self, validator):
        """Test SSN with group 00."""
        result = validator.validate_identifier(IdentifierType.SSN, "123-00-6789")
        assert result.valid is False
        assert any(e.code == "ssn_invalid_group" for e in result.errors)

    def test_ssn_invalid_serial_0000(self, validator):
        """Test SSN with serial 0000."""
        result = validator.validate_identifier(IdentifierType.SSN, "123-45-0000")
        assert result.valid is False
        assert any(e.code == "ssn_invalid_serial" for e in result.errors)


# =============================================================================
# EIN Validation Tests
# =============================================================================


class TestEINValidation:
    """Tests for EIN validation."""

    @pytest.fixture
    def validator(self):
        """Create EntityValidator instance."""
        return EntityValidator()

    def test_valid_ein_formatted(self, validator):
        """Test valid EIN with dash."""
        result = validator.validate_identifier(IdentifierType.EIN, "12-3456789")
        assert result.valid is True

    def test_valid_ein_unformatted(self, validator):
        """Test valid EIN without formatting."""
        result = validator.validate_identifier(IdentifierType.EIN, "123456789")
        assert result.valid is True

    def test_ein_too_short(self, validator):
        """Test EIN with too few digits."""
        result = validator.validate_identifier(IdentifierType.EIN, "12345678")
        assert result.valid is False
        assert any(e.code == "ein_invalid_length" for e in result.errors)

    def test_ein_invalid_prefix(self, validator):
        """Test EIN with invalid prefix."""
        result = validator.validate_identifier(IdentifierType.EIN, "07-1234567")
        assert result.valid is False
        assert any(e.code == "ein_invalid_prefix" for e in result.errors)


# =============================================================================
# Email Validation Tests
# =============================================================================


class TestEmailValidation:
    """Tests for email validation."""

    @pytest.fixture
    def validator(self):
        """Create EntityValidator instance."""
        return EntityValidator()

    def test_valid_email_simple(self, validator):
        """Test valid simple email."""
        result = validator.validate_identifier(IdentifierType.EMAIL, "user@example.com")
        assert result.valid is True

    def test_valid_email_with_dots(self, validator):
        """Test valid email with dots in local part."""
        result = validator.validate_identifier(
            IdentifierType.EMAIL, "first.last@example.com"
        )
        assert result.valid is True

    def test_valid_email_with_plus(self, validator):
        """Test valid email with plus sign."""
        result = validator.validate_identifier(
            IdentifierType.EMAIL, "user+tag@example.com"
        )
        assert result.valid is True

    def test_valid_email_subdomain(self, validator):
        """Test valid email with subdomain."""
        result = validator.validate_identifier(
            IdentifierType.EMAIL, "user@mail.example.com"
        )
        assert result.valid is True

    def test_invalid_email_no_at(self, validator):
        """Test invalid email without @ sign."""
        result = validator.validate_identifier(IdentifierType.EMAIL, "userexample.com")
        assert result.valid is False
        assert any(e.code == "email_invalid_format" for e in result.errors)

    def test_invalid_email_no_domain(self, validator):
        """Test invalid email without domain."""
        result = validator.validate_identifier(IdentifierType.EMAIL, "user@")
        assert result.valid is False

    def test_invalid_email_no_tld(self, validator):
        """Test invalid email without TLD."""
        result = validator.validate_identifier(IdentifierType.EMAIL, "user@example")
        assert result.valid is False


# =============================================================================
# Phone Validation Tests
# =============================================================================


class TestPhoneValidation:
    """Tests for phone validation."""

    @pytest.fixture
    def validator(self):
        """Create EntityValidator instance."""
        return EntityValidator()

    def test_valid_phone_e164(self, validator):
        """Test valid E.164 format phone."""
        result = validator.validate_identifier(IdentifierType.PHONE, "+14155551234")
        assert result.valid is True

    def test_valid_phone_us_formatted(self, validator):
        """Test valid US formatted phone."""
        result = validator.validate_identifier(IdentifierType.PHONE, "(415) 555-1234")
        assert result.valid is True

    def test_valid_phone_us_dashes(self, validator):
        """Test valid US phone with dashes."""
        result = validator.validate_identifier(IdentifierType.PHONE, "415-555-1234")
        assert result.valid is True

    def test_phone_warning_no_country_code(self, validator):
        """Test warning for phone without country code."""
        result = validator.validate_identifier(IdentifierType.PHONE, "4155551234")
        assert result.valid is True
        assert any(w.code == "phone_format_suggestion" for w in result.warnings)

    def test_invalid_phone_too_short(self, validator):
        """Test invalid phone too short."""
        result = validator.validate_identifier(IdentifierType.PHONE, "555-1234")
        assert result.valid is False
        assert any(e.code == "phone_too_short" for e in result.errors)

    def test_invalid_phone_too_long(self, validator):
        """Test invalid phone too long."""
        result = validator.validate_identifier(
            IdentifierType.PHONE, "12345678901234567890"
        )
        assert result.valid is False
        assert any(e.code == "phone_too_long" for e in result.errors)

    def test_invalid_phone_letters(self, validator):
        """Test invalid phone with letters."""
        result = validator.validate_identifier(IdentifierType.PHONE, "415-555-CALL")
        assert result.valid is False
        assert any(e.code == "phone_invalid_chars" for e in result.errors)


# =============================================================================
# Passport Validation Tests
# =============================================================================


class TestPassportValidation:
    """Tests for passport validation."""

    @pytest.fixture
    def validator(self):
        """Create EntityValidator instance."""
        return EntityValidator()

    def test_valid_passport(self, validator):
        """Test valid passport number."""
        result = validator.validate_identifier(IdentifierType.PASSPORT, "N12345678")
        assert result.valid is True

    def test_valid_us_passport(self, validator):
        """Test valid US passport."""
        result = validator.validate_identifier(
            IdentifierType.PASSPORT, "123456789", country="US"
        )
        assert result.valid is True

    def test_us_passport_warning_length(self, validator):
        """Test US passport length warning."""
        result = validator.validate_identifier(
            IdentifierType.PASSPORT, "12345", country="US"
        )
        assert result.valid is True
        assert any(w.code == "passport_length_warning" for w in result.warnings)

    def test_invalid_passport_too_short(self, validator):
        """Test invalid passport too short."""
        result = validator.validate_identifier(IdentifierType.PASSPORT, "1234")
        assert result.valid is False
        assert any(e.code == "passport_too_short" for e in result.errors)


# =============================================================================
# Driver's License Validation Tests
# =============================================================================


class TestDriversLicenseValidation:
    """Tests for driver's license validation."""

    @pytest.fixture
    def validator(self):
        """Create EntityValidator instance."""
        return EntityValidator()

    def test_valid_drivers_license(self, validator):
        """Test valid driver's license."""
        result = validator.validate_identifier(
            IdentifierType.DRIVERS_LICENSE, "D1234567"
        )
        assert result.valid is True

    def test_valid_drivers_license_with_state(self, validator):
        """Test valid driver's license with state."""
        result = validator.validate_identifier(
            IdentifierType.DRIVERS_LICENSE, "D1234567", state="CA"
        )
        assert result.valid is True

    def test_invalid_drivers_license_too_short(self, validator):
        """Test invalid driver's license too short."""
        result = validator.validate_identifier(IdentifierType.DRIVERS_LICENSE, "D12")
        assert result.valid is False
        assert any(e.code == "dl_too_short" for e in result.errors)

    def test_invalid_drivers_license_special_chars(self, validator):
        """Test invalid driver's license with special characters."""
        result = validator.validate_identifier(IdentifierType.DRIVERS_LICENSE, "D@#$%")
        assert result.valid is False
        assert any(e.code == "dl_invalid_chars" for e in result.errors)


# =============================================================================
# Cross-Field Validation Tests
# =============================================================================


class TestCrossFieldValidation:
    """Tests for cross-field validation."""

    @pytest.fixture
    def validator(self):
        """Create EntityValidator instance."""
        return EntityValidator()

    def test_dob_future(self, validator):
        """Test DOB in the future is rejected."""
        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            date_of_birth=date.today() + timedelta(days=1),
        )
        result = validator.validate_subject(identifiers)
        assert result.valid is False
        assert any(e.code == "dob_future" for e in result.errors)

    def test_dob_too_old(self, validator):
        """Test DOB indicating age > 120 is rejected."""
        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            date_of_birth=date.today() - timedelta(days=365 * 121),
        )
        result = validator.validate_subject(identifiers)
        assert result.valid is False
        assert any(e.code == "dob_too_old" for e in result.errors)

    def test_dob_very_young_warning(self, validator):
        """Test DOB indicating age < 14 gives warning."""
        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            date_of_birth=date.today() - timedelta(days=365 * 10),  # 10 years old
        )
        result = validator.validate_subject(identifiers)
        assert result.valid is True  # Still valid, just warning
        assert any(w.code == "dob_very_young" for w in result.warnings)

    def test_name_too_short(self, validator):
        """Test name too short is rejected."""
        identifiers = SubjectIdentifiers(full_name="A")
        result = validator.validate_subject(identifiers)
        assert result.valid is False
        assert any(e.code == "name_too_short" for e in result.errors)

    def test_name_only_digits(self, validator):
        """Test name with only digits is rejected."""
        identifiers = SubjectIdentifiers(full_name="12345")
        result = validator.validate_subject(identifiers)
        assert result.valid is False
        assert any(e.code == "name_invalid_chars" for e in result.errors)

    def test_ssn_and_ein_warning(self, validator):
        """Test warning when both SSN and EIN provided."""
        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            ssn="123-45-6789",
            ein="12-3456789",
        )
        result = validator.validate_subject(identifiers)
        assert result.valid is True  # Still valid
        assert any(w.code == "ssn_and_ein" for w in result.warnings)


# =============================================================================
# Subject Validation Tests
# =============================================================================


class TestSubjectValidation:
    """Tests for complete subject validation."""

    @pytest.fixture
    def validator(self):
        """Create EntityValidator instance."""
        return EntityValidator()

    def test_valid_subject_all_fields(self, validator):
        """Test valid subject with all fields."""
        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            date_of_birth=date(1980, 1, 15),
            ssn="123-45-6789",
            email="john@example.com",
            phone="+14155551234",
        )
        result = validator.validate_subject(identifiers)
        assert result.valid is True

    def test_subject_with_invalid_ssn(self, validator):
        """Test subject with invalid SSN."""
        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            ssn="000-00-0000",
        )
        result = validator.validate_subject(identifiers)
        assert result.valid is False

    def test_subject_with_multiple_errors(self, validator):
        """Test subject with multiple validation errors."""
        identifiers = SubjectIdentifiers(
            full_name="A",  # Too short
            ssn="000-00-0000",  # Invalid
            email="not-an-email",  # Invalid
        )
        result = validator.validate_subject(identifiers)
        assert result.valid is False
        assert len(result.errors) >= 3


# =============================================================================
# Entity Validation Tests
# =============================================================================


class TestEntityValidation:
    """Tests for entity validation."""

    @pytest.fixture
    def validator(self):
        """Create EntityValidator instance."""
        return EntityValidator()

    def test_validate_entity(self, validator):
        """Test validating an entity."""
        entity = MagicMock(spec=Entity)
        entity.canonical_identifiers = {
            "ssn": {"value": "123-45-6789"},
            "email": {"value": "john@example.com"},
        }

        result = validator.validate_entity(entity)
        assert result.valid is True

    def test_validate_entity_with_invalid_ssn(self, validator):
        """Test validating entity with invalid SSN."""
        entity = MagicMock(spec=Entity)
        entity.canonical_identifiers = {
            "ssn": {"value": "000-00-0000"},
        }

        result = validator.validate_entity(entity)
        assert result.valid is False


# =============================================================================
# Module Function Tests
# =============================================================================


class TestModuleFunctions:
    """Tests for module-level validation functions."""

    def test_validate_identifier_function(self):
        """Test validate_identifier module function."""
        result = validate_identifier(IdentifierType.SSN, "123-45-6789")
        assert result.valid is True

    def test_validate_subject_function(self):
        """Test validate_subject module function."""
        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            ssn="123-45-6789",
        )
        result = validate_subject(identifiers)
        assert result.valid is True

    def test_validate_or_raise_valid(self):
        """Test validate_or_raise with valid data."""
        identifiers = SubjectIdentifiers(
            full_name="John Smith",
            ssn="123-45-6789",
        )
        # Should not raise
        validate_or_raise(identifiers)

    def test_validate_or_raise_invalid(self):
        """Test validate_or_raise with invalid data."""
        identifiers = SubjectIdentifiers(
            full_name="A",
            ssn="000-00-0000",
        )
        with pytest.raises(ValueError, match="Validation failed"):
            validate_or_raise(identifiers)

    def test_validate_or_raise_custom_message(self):
        """Test validate_or_raise with custom message."""
        identifiers = SubjectIdentifiers(ssn="000-00-0000")
        with pytest.raises(ValueError, match="Custom error"):
            validate_or_raise(identifiers, error_message="Custom error")
