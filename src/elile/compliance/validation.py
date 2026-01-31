"""Service configuration validation for compliance.

This module provides validation of service configurations to ensure
they comply with locale-specific regulations and tier restrictions.
"""

from pydantic import BaseModel, Field

from elile.agent.state import (
    InformationType,
    SearchDegree,
    ServiceConfiguration,
    ServiceTier,
)
from elile.compliance.engine import ComplianceEngine
from elile.compliance.types import (
    CheckType,
    ENHANCED_TIER_CHECKS,
    Locale,
    RoleCategory,
)


class ValidationError(BaseModel):
    """A single validation error."""

    field: str
    message: str
    code: str


class ValidationResult(BaseModel):
    """Result of service configuration validation."""

    valid: bool
    errors: list[ValidationError] = Field(default_factory=list)
    warnings: list[ValidationError] = Field(default_factory=list)

    def add_error(self, field: str, message: str, code: str) -> None:
        """Add a validation error."""
        self.errors.append(ValidationError(field=field, message=message, code=code))
        self.valid = False

    def add_warning(self, field: str, message: str, code: str) -> None:
        """Add a validation warning."""
        self.warnings.append(ValidationError(field=field, message=message, code=code))


class ServiceConfigValidator:
    """Validator for service configurations.

    Validates service configurations against:
    - Tier constraints (D3 requires Enhanced)
    - Locale compatibility (not all checks in all locales)
    - Role category restrictions
    - Check type availability per tier
    """

    def __init__(self, compliance_engine: ComplianceEngine | None = None):
        """Initialize the validator.

        Args:
            compliance_engine: Compliance engine for rule evaluation.
                If None, uses default engine.
        """
        self._engine = compliance_engine or ComplianceEngine()

    def validate(
        self,
        config: ServiceConfiguration,
        locale: Locale,
        role_category: RoleCategory = RoleCategory.STANDARD,
    ) -> ValidationResult:
        """Validate a service configuration.

        Args:
            config: The service configuration to validate
            locale: The locale for compliance checking
            role_category: The role category

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult(valid=True)

        # Validate tier constraints
        self._validate_tier_constraints(config, result)

        # Validate degree constraints
        self._validate_degree_constraints(config, result)

        # Validate information types
        self._validate_information_types(config, locale, role_category, result)

        # Validate additional checks against locale
        self._validate_additional_checks(config, locale, role_category, result)

        # Validate excluded checks
        self._validate_excluded_checks(config, result)

        return result

    def _validate_tier_constraints(
        self,
        config: ServiceConfiguration,
        result: ValidationResult,
    ) -> None:
        """Validate tier-related constraints."""
        # D3 requires Enhanced tier
        if config.degrees == SearchDegree.D3 and config.tier != ServiceTier.ENHANCED:
            result.add_error(
                field="degrees",
                message="D3 (Extended Network) requires Enhanced service tier",
                code="d3_requires_enhanced",
            )

    def _validate_degree_constraints(
        self,
        config: ServiceConfiguration,
        result: ValidationResult,
    ) -> None:
        """Validate search degree constraints."""
        # Nothing to validate beyond tier constraint for now
        pass

    def _validate_information_types(
        self,
        config: ServiceConfiguration,
        locale: Locale,
        role_category: RoleCategory,
        result: ValidationResult,
    ) -> None:
        """Validate information types against tier and locale."""
        # Check if any enhanced-only types are explicitly added with standard tier
        for info_type in config.additional_checks:
            if info_type in _ENHANCED_ONLY_INFO_TYPES and config.tier != ServiceTier.ENHANCED:
                result.add_error(
                    field="additional_checks",
                    message=f"{info_type.value} requires Enhanced service tier",
                    code="info_type_requires_enhanced",
                )

    def _validate_additional_checks(
        self,
        config: ServiceConfiguration,
        locale: Locale,
        role_category: RoleCategory,
        result: ValidationResult,
    ) -> None:
        """Validate additional check types against locale compliance."""
        for info_type in config.additional_checks:
            check_type = _info_type_to_check_type(info_type)
            if check_type is None:
                continue

            check_result = self._engine.evaluate_check(
                locale=locale,
                check_type=check_type,
                role_category=role_category,
                tier=config.tier,
            )

            if not check_result.permitted:
                result.add_error(
                    field="additional_checks",
                    message=f"{info_type.value} not permitted: {check_result.block_reason}",
                    code="check_not_permitted",
                )

    def _validate_excluded_checks(
        self,
        config: ServiceConfiguration,
        result: ValidationResult,
    ) -> None:
        """Validate that excluded checks are valid."""
        # Warn if excluding core checks that might be required
        core_checks = {
            InformationType.IDENTITY,
            InformationType.SANCTIONS,
        }

        for info_type in config.excluded_checks:
            if info_type in core_checks:
                result.add_warning(
                    field="excluded_checks",
                    message=f"Excluding {info_type.value} may affect compliance",
                    code="excluding_core_check",
                )

    def validate_check_list(
        self,
        check_types: list[CheckType],
        locale: Locale,
        role_category: RoleCategory = RoleCategory.STANDARD,
        tier: ServiceTier = ServiceTier.STANDARD,
    ) -> ValidationResult:
        """Validate a list of check types.

        Args:
            check_types: Check types to validate
            locale: The locale for compliance
            role_category: The role category
            tier: The service tier

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult(valid=True)

        for check_type in check_types:
            check_result = self._engine.evaluate_check(
                locale=locale,
                check_type=check_type,
                role_category=role_category,
                tier=tier,
            )

            if not check_result.permitted:
                result.add_error(
                    field="check_types",
                    message=f"{check_type.value}: {check_result.block_reason}",
                    code="check_not_permitted",
                )
            elif check_result.requires_consent:
                result.add_warning(
                    field="check_types",
                    message=f"{check_type.value} requires explicit consent",
                    code="requires_consent",
                )

        return result

    def get_available_checks(
        self,
        locale: Locale,
        role_category: RoleCategory = RoleCategory.STANDARD,
        tier: ServiceTier = ServiceTier.STANDARD,
    ) -> list[CheckType]:
        """Get all available check types for a configuration.

        Args:
            locale: The locale
            role_category: The role category
            tier: The service tier

        Returns:
            List of permitted check types
        """
        return self._engine.get_permitted_checks(
            locale=locale,
            role_category=role_category,
            tier=tier,
        )

    def get_available_info_types(
        self,
        locale: Locale,
        role_category: RoleCategory = RoleCategory.STANDARD,
        tier: ServiceTier = ServiceTier.STANDARD,
    ) -> list[InformationType]:
        """Get all available information types for a configuration.

        Args:
            locale: The locale
            role_category: The role category
            tier: The service tier

        Returns:
            List of available information types
        """
        available: list[InformationType] = []

        for info_type in InformationType:
            # Check tier restriction
            if info_type in _ENHANCED_ONLY_INFO_TYPES and tier != ServiceTier.ENHANCED:
                continue

            # Check degree restriction
            if info_type == InformationType.NETWORK_D3 and tier != ServiceTier.ENHANCED:
                continue

            # Map to check type and verify compliance
            check_type = _info_type_to_check_type(info_type)
            if check_type is None:
                # No compliance restriction on this type
                available.append(info_type)
                continue

            check_result = self._engine.evaluate_check(
                locale=locale,
                check_type=check_type,
                role_category=role_category,
                tier=tier,
            )
            if check_result.permitted:
                available.append(info_type)

        return available


# Information types that require Enhanced tier
_ENHANCED_ONLY_INFO_TYPES: set[InformationType] = {
    InformationType.DIGITAL_FOOTPRINT,
    InformationType.NETWORK_D3,
}


def _info_type_to_check_type(info_type: InformationType) -> CheckType | None:
    """Map information type to check type for compliance validation.

    Args:
        info_type: The information type

    Returns:
        Corresponding check type, or None if no direct mapping
    """
    mapping: dict[InformationType, CheckType] = {
        InformationType.IDENTITY: CheckType.IDENTITY_BASIC,
        InformationType.CRIMINAL: CheckType.CRIMINAL_NATIONAL,
        InformationType.CIVIL: CheckType.CIVIL_LITIGATION,
        InformationType.FINANCIAL: CheckType.CREDIT_REPORT,
        InformationType.LICENSES: CheckType.LICENSE_VERIFICATION,
        InformationType.REGULATORY: CheckType.REGULATORY_ENFORCEMENT,
        InformationType.SANCTIONS: CheckType.SANCTIONS_OFAC,
        InformationType.ADVERSE_MEDIA: CheckType.ADVERSE_MEDIA,
        InformationType.DIGITAL_FOOTPRINT: CheckType.DIGITAL_FOOTPRINT,
    }
    return mapping.get(info_type)


def validate_service_config(
    config: ServiceConfiguration,
    locale: Locale,
    role_category: RoleCategory = RoleCategory.STANDARD,
) -> ValidationResult:
    """Validate a service configuration.

    Convenience function for quick validation.

    Args:
        config: The service configuration to validate
        locale: The locale for compliance checking
        role_category: The role category

    Returns:
        ValidationResult with errors and warnings
    """
    validator = ServiceConfigValidator()
    return validator.validate(config, locale, role_category)


def validate_or_raise(
    config: ServiceConfiguration,
    locale: Locale,
    role_category: RoleCategory = RoleCategory.STANDARD,
) -> None:
    """Validate a service configuration and raise on errors.

    Args:
        config: The service configuration to validate
        locale: The locale for compliance checking
        role_category: The role category

    Raises:
        ValueError: If validation fails
    """
    result = validate_service_config(config, locale, role_category)
    if not result.valid:
        error_messages = [f"{e.field}: {e.message}" for e in result.errors]
        raise ValueError(f"Invalid service configuration: {'; '.join(error_messages)}")
