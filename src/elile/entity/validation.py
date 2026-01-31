"""Entity validation and verification.

This module provides validation rules for entity identifiers
and cross-field validation to ensure data quality and compliance.
"""

import re
from datetime import date, timedelta
from enum import Enum

from pydantic import BaseModel, Field

from elile.core.logging import get_logger
from elile.db.models.entity import Entity

from .types import IdentifierType, SubjectIdentifiers

logger = get_logger(__name__)


class ValidationSeverity(str, Enum):
    """Severity level of validation issues."""

    ERROR = "error"  # Invalid data, cannot proceed
    WARNING = "warning"  # Suspicious data, may proceed with caution


class ValidationError(BaseModel):
    """Represents a validation error."""

    field: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    code: str | None = None


class ValidationWarning(BaseModel):
    """Represents a validation warning."""

    field: str
    message: str
    code: str | None = None


class ValidationResult(BaseModel):
    """Result of a validation operation."""

    valid: bool = True
    errors: list[ValidationError] = Field(default_factory=list)
    warnings: list[ValidationWarning] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        """Merge another validation result into this one."""
        return ValidationResult(
            valid=self.valid and other.valid,
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
        )


class EntityValidator:
    """Entity validation engine.

    Provides format validation for identifiers and
    cross-field consistency validation.
    """

    # SSN area numbers that are invalid
    INVALID_SSN_AREAS = {0, 666, *range(900, 1000)}

    # EIN prefixes that are valid (simplified - would use full list in production)
    VALID_EIN_PREFIXES = set(range(10, 100)) - {7, 8, 9}

    def validate_identifier(
        self,
        identifier_type: IdentifierType,
        value: str,
        **kwargs,
    ) -> ValidationResult:
        """Validate a single identifier.

        Args:
            identifier_type: Type of identifier to validate
            value: Value to validate
            **kwargs: Additional context (country, state, etc.)

        Returns:
            ValidationResult
        """
        validators = {
            IdentifierType.SSN: self._validate_ssn,
            IdentifierType.EIN: self._validate_ein,
            IdentifierType.PASSPORT: self._validate_passport,
            IdentifierType.DRIVERS_LICENSE: self._validate_drivers_license,
            IdentifierType.EMAIL: self._validate_email,
            IdentifierType.PHONE: self._validate_phone,
        }

        validator = validators.get(identifier_type)
        if validator:
            return validator(value, **kwargs)

        # No specific validator, just ensure non-empty
        if not value or not value.strip():
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        field=identifier_type.value,
                        message="Value cannot be empty",
                        code="empty_value",
                    )
                ],
            )

        return ValidationResult(valid=True)

    def validate_subject(
        self,
        identifiers: SubjectIdentifiers,
    ) -> ValidationResult:
        """Validate all identifiers in a subject.

        Args:
            identifiers: Subject identifiers to validate

        Returns:
            Combined ValidationResult
        """
        result = ValidationResult()

        # Validate canonical identifiers
        if identifiers.ssn:
            result = result.merge(
                self.validate_identifier(IdentifierType.SSN, identifiers.ssn)
            )

        if identifiers.ein:
            result = result.merge(
                self.validate_identifier(IdentifierType.EIN, identifiers.ein)
            )

        if identifiers.passport:
            result = result.merge(
                self.validate_identifier(
                    IdentifierType.PASSPORT,
                    identifiers.passport,
                    country=identifiers.passport_country,
                )
            )

        if identifiers.drivers_license:
            result = result.merge(
                self.validate_identifier(
                    IdentifierType.DRIVERS_LICENSE,
                    identifiers.drivers_license,
                    state=identifiers.drivers_license_state,
                )
            )

        if identifiers.email:
            result = result.merge(
                self.validate_identifier(IdentifierType.EMAIL, identifiers.email)
            )

        if identifiers.phone:
            result = result.merge(
                self.validate_identifier(IdentifierType.PHONE, identifiers.phone)
            )

        # Cross-field validation
        result = result.merge(self._validate_cross_fields(identifiers))

        return result

    def validate_entity(self, entity: Entity) -> ValidationResult:
        """Validate an entity's canonical identifiers.

        Args:
            entity: Entity to validate

        Returns:
            ValidationResult
        """
        # Convert entity identifiers to SubjectIdentifiers
        ids = entity.canonical_identifiers
        identifiers = SubjectIdentifiers()

        # Extract identifiers from entity
        if "ssn" in ids:
            ssn = ids["ssn"]
            identifiers.ssn = ssn.get("value") if isinstance(ssn, dict) else str(ssn)

        if "ein" in ids:
            ein = ids["ein"]
            identifiers.ein = ein.get("value") if isinstance(ein, dict) else str(ein)

        if "email" in ids:
            email = ids["email"]
            identifiers.email = email.get("value") if isinstance(email, dict) else str(email)

        if "phone" in ids:
            phone = ids["phone"]
            identifiers.phone = phone.get("value") if isinstance(phone, dict) else str(phone)

        if "date_of_birth" in ids:
            dob = ids["date_of_birth"]
            dob_str = dob.get("value") if isinstance(dob, dict) else str(dob)
            try:
                identifiers.date_of_birth = date.fromisoformat(dob_str)
            except (ValueError, TypeError):
                pass

        return self.validate_subject(identifiers)

    # -------------------------------------------------------------------------
    # Specific Identifier Validators
    # -------------------------------------------------------------------------

    def _validate_ssn(self, value: str, **kwargs) -> ValidationResult:
        """Validate US Social Security Number.

        Valid SSN format: XXX-XX-XXXX or XXXXXXXXX
        - Area number (first 3): not 000, 666, or 900-999
        - Group number (middle 2): not 00
        - Serial number (last 4): not 0000

        Args:
            value: SSN value

        Returns:
            ValidationResult
        """
        errors = []

        # Remove formatting
        digits = re.sub(r"\D", "", value)

        if len(digits) != 9:
            errors.append(
                ValidationError(
                    field="ssn",
                    message="SSN must be exactly 9 digits",
                    code="ssn_invalid_length",
                )
            )
            return ValidationResult(valid=False, errors=errors)

        # Area number validation (first 3 digits)
        area = int(digits[:3])
        if area in self.INVALID_SSN_AREAS:
            errors.append(
                ValidationError(
                    field="ssn",
                    message=f"Invalid SSN area number: {area:03d}",
                    code="ssn_invalid_area",
                )
            )

        # Group number validation (middle 2 digits)
        group = int(digits[3:5])
        if group == 0:
            errors.append(
                ValidationError(
                    field="ssn",
                    message="Invalid SSN group number: 00",
                    code="ssn_invalid_group",
                )
            )

        # Serial number validation (last 4 digits)
        serial = int(digits[5:])
        if serial == 0:
            errors.append(
                ValidationError(
                    field="ssn",
                    message="Invalid SSN serial number: 0000",
                    code="ssn_invalid_serial",
                )
            )

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def _validate_ein(self, value: str, **kwargs) -> ValidationResult:
        """Validate US Employer Identification Number.

        Valid EIN format: XX-XXXXXXX or XXXXXXXXX
        - First two digits must be a valid prefix

        Args:
            value: EIN value

        Returns:
            ValidationResult
        """
        errors = []

        # Remove formatting
        digits = re.sub(r"\D", "", value)

        if len(digits) != 9:
            errors.append(
                ValidationError(
                    field="ein",
                    message="EIN must be exactly 9 digits",
                    code="ein_invalid_length",
                )
            )
            return ValidationResult(valid=False, errors=errors)

        # Prefix validation (first 2 digits)
        prefix = int(digits[:2])
        if prefix not in self.VALID_EIN_PREFIXES:
            errors.append(
                ValidationError(
                    field="ein",
                    message=f"Invalid EIN prefix: {prefix:02d}",
                    code="ein_invalid_prefix",
                )
            )

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def _validate_passport(
        self, value: str, country: str | None = None, **kwargs
    ) -> ValidationResult:
        """Validate passport number.

        Basic validation - country-specific rules could be added.

        Args:
            value: Passport number
            country: Issuing country code

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        if not value or len(value.strip()) < 5:
            errors.append(
                ValidationError(
                    field="passport",
                    message="Passport number too short",
                    code="passport_too_short",
                )
            )
            return ValidationResult(valid=False, errors=errors)

        # US passport validation (if country specified)
        if country and country.upper() == "US":
            # US passports: alphanumeric, typically 9 characters
            cleaned = re.sub(r"[^A-Z0-9]", "", value.upper())
            if len(cleaned) != 9:
                warnings.append(
                    ValidationWarning(
                        field="passport",
                        message="US passport numbers are typically 9 characters",
                        code="passport_length_warning",
                    )
                )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def _validate_drivers_license(
        self, value: str, state: str | None = None, **kwargs
    ) -> ValidationResult:
        """Validate driver's license number.

        Basic validation - state-specific rules could be added.

        Args:
            value: License number
            state: Issuing state code

        Returns:
            ValidationResult
        """
        errors = []

        if not value or len(value.strip()) < 4:
            errors.append(
                ValidationError(
                    field="drivers_license",
                    message="Driver's license number too short",
                    code="dl_too_short",
                )
            )
            return ValidationResult(valid=False, errors=errors)

        # Basic alphanumeric check
        if not re.match(r"^[A-Za-z0-9\-*]+$", value):
            errors.append(
                ValidationError(
                    field="drivers_license",
                    message="Driver's license contains invalid characters",
                    code="dl_invalid_chars",
                )
            )

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def _validate_email(self, value: str, **kwargs) -> ValidationResult:
        """Validate email address.

        Uses RFC 5322 simplified pattern.

        Args:
            value: Email address

        Returns:
            ValidationResult
        """
        errors = []

        # Simplified RFC 5322 pattern
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

        if not re.match(pattern, value.strip()):
            errors.append(
                ValidationError(
                    field="email",
                    message="Invalid email address format",
                    code="email_invalid_format",
                )
            )

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def _validate_phone(self, value: str, **kwargs) -> ValidationResult:
        """Validate phone number.

        Accepts E.164 format and common US formats.

        Args:
            value: Phone number

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        # Remove common formatting
        digits = re.sub(r"[\s\-\.\(\)]+", "", value)

        # Handle + prefix for E.164
        if digits.startswith("+"):
            digits = digits[1:]

        # After removing formatting, should be mostly digits
        if not digits.isdigit():
            errors.append(
                ValidationError(
                    field="phone",
                    message="Phone number contains invalid characters",
                    code="phone_invalid_chars",
                )
            )
            return ValidationResult(valid=False, errors=errors)

        # Check length (10 or 11 for US, up to 15 for international E.164)
        if len(digits) < 10:
            errors.append(
                ValidationError(
                    field="phone",
                    message="Phone number too short (minimum 10 digits)",
                    code="phone_too_short",
                )
            )
        elif len(digits) > 15:
            errors.append(
                ValidationError(
                    field="phone",
                    message="Phone number too long (maximum 15 digits)",
                    code="phone_too_long",
                )
            )

        # Warn about non-E.164 format
        if len(digits) == 10:
            warnings.append(
                ValidationWarning(
                    field="phone",
                    message="Consider using E.164 format (+1XXXXXXXXXX)",
                    code="phone_format_suggestion",
                )
            )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    # -------------------------------------------------------------------------
    # Cross-Field Validation
    # -------------------------------------------------------------------------

    def _validate_cross_fields(
        self, identifiers: SubjectIdentifiers
    ) -> ValidationResult:
        """Validate logical consistency across fields.

        Args:
            identifiers: Subject identifiers

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        # Date of birth validation
        if identifiers.date_of_birth:
            today = date.today()

            # Future date check
            if identifiers.date_of_birth > today:
                errors.append(
                    ValidationError(
                        field="date_of_birth",
                        message="Date of birth cannot be in the future",
                        code="dob_future",
                    )
                )

            # Reasonable age check (not > 120 years old)
            max_age = today - timedelta(days=365 * 120)
            if identifiers.date_of_birth < max_age:
                errors.append(
                    ValidationError(
                        field="date_of_birth",
                        message="Date of birth indicates age over 120 years",
                        code="dob_too_old",
                    )
                )

            # Warning for very young (< 14)
            min_working_age = today - timedelta(days=365 * 14)
            if identifiers.date_of_birth > min_working_age:
                warnings.append(
                    ValidationWarning(
                        field="date_of_birth",
                        message="Subject appears to be under 14 years old",
                        code="dob_very_young",
                    )
                )

        # Name validation
        if identifiers.full_name:
            # Check for suspicious patterns
            if len(identifiers.full_name) < 2:
                errors.append(
                    ValidationError(
                        field="full_name",
                        message="Name is too short",
                        code="name_too_short",
                    )
                )

            # Check for all digits or special characters
            if re.match(r"^[\d\W]+$", identifiers.full_name):
                errors.append(
                    ValidationError(
                        field="full_name",
                        message="Name contains only digits or special characters",
                        code="name_invalid_chars",
                    )
                )

        # Both SSN and EIN check (unusual for an individual to have both)
        if identifiers.ssn and identifiers.ein:
            warnings.append(
                ValidationWarning(
                    field="ssn,ein",
                    message="Both SSN and EIN provided - verify entity type",
                    code="ssn_and_ein",
                )
            )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)


# Module-level convenience functions


def validate_identifier(
    identifier_type: IdentifierType,
    value: str,
    **kwargs,
) -> ValidationResult:
    """Validate a single identifier.

    Args:
        identifier_type: Type of identifier
        value: Value to validate
        **kwargs: Additional context

    Returns:
        ValidationResult
    """
    validator = EntityValidator()
    return validator.validate_identifier(identifier_type, value, **kwargs)


def validate_subject(identifiers: SubjectIdentifiers) -> ValidationResult:
    """Validate a subject's identifiers.

    Args:
        identifiers: Subject identifiers

    Returns:
        ValidationResult
    """
    validator = EntityValidator()
    return validator.validate_subject(identifiers)


def validate_or_raise(
    identifiers: SubjectIdentifiers,
    error_message: str = "Validation failed",
) -> None:
    """Validate identifiers and raise if invalid.

    Args:
        identifiers: Subject identifiers
        error_message: Error message prefix

    Raises:
        ValueError: If validation fails
    """
    result = validate_subject(identifiers)
    if not result.valid:
        error_details = "; ".join(e.message for e in result.errors)
        raise ValueError(f"{error_message}: {error_details}")
