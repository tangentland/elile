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

from elile.compliance.consent import (
    Consent,
    ConsentManager,
    ConsentResult,
    ConsentScope,
    ConsentVerificationMethod,
    FCRADisclosure,
    create_consent,
    create_fcra_disclosure,
)
from elile.compliance.engine import ComplianceEngine, get_compliance_engine
from elile.compliance.erasure import (
    AnonymizationConfig,
    AnonymizationMethod,
    AnonymizationResult,
    create_anonymizer,
    DataAnonymizer,
    ErasedItem,
    ErasureBlockedException,
    ErasureConfirmationReport,
    ErasureExemption,
    ErasureOperation,
    ErasureService,
    ErasureServiceConfig,
    ErasureStatus,
    ErasureType,
    ErasureVerificationError,
    get_erasure_service,
    initialize_erasure_service,
    LegalHoldException,
    RetainedItem,
)
from elile.compliance.retention import (
    DataType,
    DeletionMethod,
    ErasureRequest,
    RetentionAction,
    RetentionManager,
    RetentionManagerConfig,
    RetentionPolicy,
    RetentionRecord,
    RetentionReport,
    RetentionStatus,
    get_default_policies,
    get_policies_for_locale,
    get_policy_for_data_type,
    get_retention_manager,
    initialize_retention_manager,
)
from elile.compliance.rules import ComplianceRule, RuleRepository
from elile.compliance.types import (
    ENHANCED_TIER_CHECKS,
    EXPLICIT_CONSENT_CHECKS,
    HIRING_RESTRICTED_CHECKS,
    CheckRestriction,
    CheckResult,
    CheckType,
    Locale,
    LocaleConfig,
    RestrictionType,
    RoleCategory,
)
from elile.compliance.validation import (
    ServiceConfigValidator,
    ValidationError,
    ValidationResult,
    validate_or_raise,
    validate_service_config,
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
    # Retention
    "DataType",
    "DeletionMethod",
    "ErasureRequest",
    "get_default_policies",
    "get_policies_for_locale",
    "get_policy_for_data_type",
    "get_retention_manager",
    "initialize_retention_manager",
    "RetentionAction",
    "RetentionManager",
    "RetentionManagerConfig",
    "RetentionPolicy",
    "RetentionRecord",
    "RetentionReport",
    "RetentionStatus",
    # GDPR Erasure
    "AnonymizationConfig",
    "AnonymizationMethod",
    "AnonymizationResult",
    "create_anonymizer",
    "DataAnonymizer",
    "ErasedItem",
    "ErasureBlockedException",
    "ErasureConfirmationReport",
    "ErasureExemption",
    "ErasureOperation",
    "ErasureService",
    "ErasureServiceConfig",
    "ErasureStatus",
    "ErasureType",
    "ErasureVerificationError",
    "get_erasure_service",
    "initialize_erasure_service",
    "LegalHoldException",
    "RetainedItem",
]
