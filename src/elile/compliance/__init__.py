"""Compliance framework for locale-aware background checks.

This package provides the compliance engine for enforcing jurisdiction-specific
rules on background checks, including:

- Locale-based restrictions (FCRA, GDPR, PIPEDA, etc.)
- Service tier constraints (Standard vs Enhanced)
- Role category requirements
- Consent management
- Lookback period enforcement

Usage:
    from elile.compliance import ComplianceEngine, Locale, CheckType

    engine = ComplianceEngine()
    result = engine.evaluate_check(
        locale=Locale.US,
        check_type=CheckType.CRIMINAL_NATIONAL,
        role_category=RoleCategory.FINANCIAL,
    )
    if result.permitted:
        # Proceed with check
        ...
"""

from elile.compliance.validation import (
    ServiceConfigValidator,
    validate_or_raise,
    validate_service_config,
    ValidationError,
    ValidationResult,
)
from elile.compliance.consent import (
    Consent,
    ConsentManager,
    ConsentResult,
    ConsentScope,
    ConsentVerificationMethod,
    create_consent,
    create_fcra_disclosure,
    FCRADisclosure,
)
from elile.compliance.engine import ComplianceEngine, get_compliance_engine
from elile.compliance.rules import ComplianceRule, RuleRepository
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

__all__ = [
    # Core types
    "Locale",
    "CheckType",
    "RoleCategory",
    "RestrictionType",
    # Result models
    "CheckRestriction",
    "CheckResult",
    "LocaleConfig",
    # Rules
    "ComplianceRule",
    "RuleRepository",
    # Engine
    "ComplianceEngine",
    "get_compliance_engine",
    # Consent
    "Consent",
    "ConsentManager",
    "ConsentResult",
    "ConsentScope",
    "ConsentVerificationMethod",
    "FCRADisclosure",
    "create_consent",
    "create_fcra_disclosure",
    # Validation
    "ServiceConfigValidator",
    "validate_service_config",
    "validate_or_raise",
    "ValidationError",
    "ValidationResult",
    # Constants
    "ENHANCED_TIER_CHECKS",
    "EXPLICIT_CONSENT_CHECKS",
    "HIRING_RESTRICTED_CHECKS",
]
