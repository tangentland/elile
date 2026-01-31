"""Default compliance rules for major jurisdictions.

This module provides the default compliance rules for supported locales,
implementing the regulations documented in the architecture:
- US: FCRA (7-year lookback, adverse action notices)
- EU: GDPR (Article 6/9, strict criminal data rules)
- UK: DBS + UK GDPR
- Canada: PIPEDA (RCMP for criminal)
- Australia: Privacy Act
- Brazil: LGPD

These rules are loaded by RuleRepository.with_default_rules().
"""

from elile.compliance.rules import ComplianceRule
from elile.compliance.types import (
    CheckType,
    Locale,
    RestrictionType,
    RoleCategory,
)


def get_default_rules() -> list[ComplianceRule]:
    """Get all default compliance rules.

    Returns:
        List of default compliance rules for all supported locales
    """
    rules: list[ComplianceRule] = []
    rules.extend(_us_rules())
    rules.extend(_eu_rules())
    rules.extend(_uk_rules())
    rules.extend(_canada_rules())
    rules.extend(_australia_rules())
    rules.extend(_brazil_rules())
    return rules


def _us_rules() -> list[ComplianceRule]:
    """US FCRA compliance rules."""
    rules = []

    # 7-year lookback for most criminal records
    criminal_types = [
        CheckType.CRIMINAL_NATIONAL,
        CheckType.CRIMINAL_STATE,
        CheckType.CRIMINAL_COUNTY,
        CheckType.CRIMINAL_FEDERAL,
    ]
    for check_type in criminal_types:
        rules.append(
            ComplianceRule(
                locale=Locale.US,
                check_type=check_type,
                permitted=True,
                restriction_type=RestrictionType.LOOKBACK_LIMITED,
                lookback_days=2555,  # ~7 years
                requires_consent=True,
                requires_disclosure=True,
                notes="FCRA 7-year lookback; pre-check disclosure required",
            )
        )

    # Credit checks require explicit consent and role justification
    rules.append(
        ComplianceRule(
            locale=Locale.US,
            check_type=CheckType.CREDIT_REPORT,
            permitted=True,
            restriction_type=RestrictionType.ROLE_RESTRICTED,
            requires_consent=True,
            requires_disclosure=True,
            permitted_roles=[
                RoleCategory.FINANCIAL,
                RoleCategory.EXECUTIVE,
                RoleCategory.GOVERNMENT,
            ],
            notes="FCRA: Credit checks only for positions with financial duties",
        )
    )
    rules.append(
        ComplianceRule(
            locale=Locale.US,
            check_type=CheckType.CREDIT_SCORE,
            permitted=True,
            restriction_type=RestrictionType.ROLE_RESTRICTED,
            requires_consent=True,
            requires_disclosure=True,
            permitted_roles=[
                RoleCategory.FINANCIAL,
                RoleCategory.EXECUTIVE,
            ],
            notes="FCRA: Credit score only for positions with significant financial duties",
        )
    )

    # 7-year lookback for civil records
    civil_types = [
        CheckType.CIVIL_LITIGATION,
        CheckType.CIVIL_JUDGMENTS,
        CheckType.BANKRUPTCY,
        CheckType.LIENS,
    ]
    for check_type in civil_types:
        rules.append(
            ComplianceRule(
                locale=Locale.US,
                check_type=check_type,
                permitted=True,
                restriction_type=RestrictionType.LOOKBACK_LIMITED,
                lookback_days=2555,  # 7 years
                requires_consent=True,
                notes="FCRA 7-year lookback for civil records",
            )
        )

    # Sanctions/watchlists - no lookback limit
    sanctions_types = [
        CheckType.SANCTIONS_OFAC,
        CheckType.SANCTIONS_UN,
        CheckType.SANCTIONS_EU,
        CheckType.SANCTIONS_PEP,
        CheckType.WATCHLIST_INTERPOL,
        CheckType.WATCHLIST_FBI,
    ]
    for check_type in sanctions_types:
        rules.append(
            ComplianceRule(
                locale=Locale.US,
                check_type=check_type,
                permitted=True,
                requires_consent=True,
                notes="No time limit on sanctions checks",
            )
        )

    # Employment/Education verification
    rules.extend([
        ComplianceRule(
            locale=Locale.US,
            check_type=CheckType.EMPLOYMENT_VERIFICATION,
            permitted=True,
            requires_consent=True,
            notes="Standard employment verification",
        ),
        ComplianceRule(
            locale=Locale.US,
            check_type=CheckType.EDUCATION_VERIFICATION,
            permitted=True,
            requires_consent=True,
            notes="Standard education verification",
        ),
    ])

    # Drug testing - role restricted
    rules.append(
        ComplianceRule(
            locale=Locale.US,
            check_type=CheckType.DRUG_TEST,
            permitted=True,
            restriction_type=RestrictionType.ROLE_RESTRICTED,
            requires_consent=True,
            permitted_roles=[
                RoleCategory.TRANSPORTATION,
                RoleCategory.GOVERNMENT,
                RoleCategory.SECURITY,
                RoleCategory.HEALTHCARE,
            ],
            notes="DOT/regulated positions or safety-sensitive roles",
        )
    )

    # California-specific rules
    rules.append(
        ComplianceRule(
            locale=Locale.US_CA,
            check_type=CheckType.CRIMINAL_COUNTY,
            permitted=True,
            restriction_type=RestrictionType.LOOKBACK_LIMITED,
            lookback_days=2555,
            requires_consent=True,
            requires_disclosure=True,
            notes="ICRAA: Additional California disclosures required",
        )
    )

    # New York Fair Chance Act
    rules.append(
        ComplianceRule(
            locale=Locale.US_NY,
            check_type=CheckType.CRIMINAL_COUNTY,
            permitted=True,
            restriction_type=RestrictionType.CONDITIONAL,
            lookback_days=2555,
            requires_consent=True,
            requires_disclosure=True,
            notes="NYC Fair Chance: Criminal checks only after conditional offer",
        )
    )

    return rules


def _eu_rules() -> list[ComplianceRule]:
    """EU GDPR compliance rules."""
    rules = []

    # Credit checks generally prohibited
    rules.extend([
        ComplianceRule(
            locale=Locale.EU,
            check_type=CheckType.CREDIT_REPORT,
            permitted=False,
            restriction_type=RestrictionType.BLOCKED,
            notes="GDPR Article 9: Credit checks generally prohibited for employment",
        ),
        ComplianceRule(
            locale=Locale.EU,
            check_type=CheckType.CREDIT_SCORE,
            permitted=False,
            restriction_type=RestrictionType.BLOCKED,
            notes="GDPR Article 9: Credit checks generally prohibited for employment",
        ),
    ])

    # Criminal checks only for regulated roles
    criminal_types = [
        CheckType.CRIMINAL_NATIONAL,
        CheckType.CRIMINAL_INTERNATIONAL,
    ]
    for check_type in criminal_types:
        rules.append(
            ComplianceRule(
                locale=Locale.EU,
                check_type=check_type,
                permitted=True,
                restriction_type=RestrictionType.ROLE_RESTRICTED,
                requires_consent=True,
                requires_disclosure=True,
                permitted_roles=[
                    RoleCategory.FINANCIAL,
                    RoleCategory.GOVERNMENT,
                    RoleCategory.EDUCATION,  # Working with minors
                    RoleCategory.HEALTHCARE,
                ],
                notes="GDPR Article 10: Criminal data only for regulated roles with legal basis",
            )
        )

    # SSN trace not applicable in EU
    rules.append(
        ComplianceRule(
            locale=Locale.EU,
            check_type=CheckType.SSN_TRACE,
            permitted=False,
            restriction_type=RestrictionType.BLOCKED,
            notes="SSN trace not applicable in EU jurisdictions",
        )
    )

    # Employment/education verification permitted with consent
    rules.extend([
        ComplianceRule(
            locale=Locale.EU,
            check_type=CheckType.EMPLOYMENT_VERIFICATION,
            permitted=True,
            requires_consent=True,
            requires_disclosure=True,
            notes="GDPR: Explicit consent required",
        ),
        ComplianceRule(
            locale=Locale.EU,
            check_type=CheckType.EDUCATION_VERIFICATION,
            permitted=True,
            requires_consent=True,
            requires_disclosure=True,
            notes="GDPR: Explicit consent required",
        ),
    ])

    # Sanctions checks permitted
    rules.append(
        ComplianceRule(
            locale=Locale.EU,
            check_type=CheckType.SANCTIONS_EU,
            permitted=True,
            requires_consent=True,
            notes="EU sanctions compliance required for regulated entities",
        )
    )

    # Social media - public only, with restrictions
    rules.append(
        ComplianceRule(
            locale=Locale.EU,
            check_type=CheckType.SOCIAL_MEDIA,
            permitted=True,
            restriction_type=RestrictionType.CONDITIONAL,
            requires_consent=True,
            requires_enhanced_tier=True,
            notes="GDPR: Public data only, exclude Article 9 content (race, religion, health)",
        )
    )

    # Drug testing generally prohibited
    rules.append(
        ComplianceRule(
            locale=Locale.EU,
            check_type=CheckType.DRUG_TEST,
            permitted=False,
            restriction_type=RestrictionType.BLOCKED,
            notes="GDPR Article 9: Health data processing generally prohibited",
        )
    )

    return rules


def _uk_rules() -> list[ComplianceRule]:
    """UK compliance rules (DBS + UK GDPR)."""
    rules = []

    # Criminal checks via DBS
    rules.append(
        ComplianceRule(
            locale=Locale.UK,
            check_type=CheckType.CRIMINAL_NATIONAL,
            permitted=True,
            restriction_type=RestrictionType.ROLE_RESTRICTED,
            requires_consent=True,
            requires_disclosure=True,
            permitted_roles=[
                RoleCategory.FINANCIAL,
                RoleCategory.GOVERNMENT,
                RoleCategory.EDUCATION,
                RoleCategory.HEALTHCARE,
                RoleCategory.SECURITY,
            ],
            notes="UK DBS: Standard/Enhanced checks for eligible roles only",
        )
    )

    # Credit checks restricted
    rules.append(
        ComplianceRule(
            locale=Locale.UK,
            check_type=CheckType.CREDIT_REPORT,
            permitted=True,
            restriction_type=RestrictionType.ROLE_RESTRICTED,
            requires_consent=True,
            permitted_roles=[RoleCategory.FINANCIAL],
            notes="UK: Credit checks only for financial roles",
        )
    )

    # Right to work verification
    rules.append(
        ComplianceRule(
            locale=Locale.UK,
            check_type=CheckType.IDENTITY_BASIC,
            permitted=True,
            requires_consent=True,
            notes="UK: Right to work verification required",
        )
    )

    return rules


def _canada_rules() -> list[ComplianceRule]:
    """Canada PIPEDA compliance rules."""
    rules = []

    # Criminal checks require RCMP
    rules.extend([
        ComplianceRule(
            locale=Locale.CA,
            check_type=CheckType.CRIMINAL_NATIONAL,
            permitted=True,
            requires_consent=True,
            requires_disclosure=True,
            notes="PIPEDA: RCMP criminal record check required",
        ),
        ComplianceRule(
            locale=Locale.CA,
            check_type=CheckType.CRIMINAL_INTERNATIONAL,
            permitted=True,
            requires_consent=True,
            requires_disclosure=True,
            notes="PIPEDA: International checks with consent",
        ),
    ])

    # Credit checks permitted with consent
    rules.append(
        ComplianceRule(
            locale=Locale.CA,
            check_type=CheckType.CREDIT_REPORT,
            permitted=True,
            restriction_type=RestrictionType.ROLE_RESTRICTED,
            requires_consent=True,
            permitted_roles=[
                RoleCategory.FINANCIAL,
                RoleCategory.EXECUTIVE,
            ],
            notes="PIPEDA: Credit checks with written consent for relevant roles",
        )
    )

    # Employment verification
    rules.append(
        ComplianceRule(
            locale=Locale.CA,
            check_type=CheckType.EMPLOYMENT_VERIFICATION,
            permitted=True,
            requires_consent=True,
            notes="PIPEDA: Consent required for employment verification",
        )
    )

    # Quebec-specific (stricter privacy)
    rules.append(
        ComplianceRule(
            locale=Locale.CA_QC,
            check_type=CheckType.CREDIT_REPORT,
            permitted=True,
            restriction_type=RestrictionType.ROLE_RESTRICTED,
            requires_consent=True,
            requires_disclosure=True,
            permitted_roles=[RoleCategory.FINANCIAL],
            notes="Quebec Bill 64: Stricter consent and disclosure requirements",
        )
    )

    return rules


def _australia_rules() -> list[ComplianceRule]:
    """Australia Privacy Act compliance rules."""
    rules = []

    # Criminal checks (National Police Check)
    rules.append(
        ComplianceRule(
            locale=Locale.AU,
            check_type=CheckType.CRIMINAL_NATIONAL,
            permitted=True,
            requires_consent=True,
            notes="AU: National Police Check via AFP",
        )
    )

    # Working with children checks
    rules.append(
        ComplianceRule(
            locale=Locale.AU,
            check_type=CheckType.CRIMINAL_STATE,
            role_category=RoleCategory.EDUCATION,
            permitted=True,
            requires_consent=True,
            notes="AU: Working With Children Check (state-based)",
        )
    )

    # Credit checks
    rules.append(
        ComplianceRule(
            locale=Locale.AU,
            check_type=CheckType.CREDIT_REPORT,
            permitted=True,
            restriction_type=RestrictionType.ROLE_RESTRICTED,
            requires_consent=True,
            permitted_roles=[RoleCategory.FINANCIAL],
            notes="AU Privacy Act: Credit checks with consent for financial roles",
        )
    )

    # Employment verification
    rules.append(
        ComplianceRule(
            locale=Locale.AU,
            check_type=CheckType.EMPLOYMENT_VERIFICATION,
            permitted=True,
            requires_consent=True,
            notes="AU Privacy Act: Consent required",
        )
    )

    return rules


def _brazil_rules() -> list[ComplianceRule]:
    """Brazil LGPD compliance rules."""
    rules = []

    # Criminal checks restricted
    rules.append(
        ComplianceRule(
            locale=Locale.BR,
            check_type=CheckType.CRIMINAL_NATIONAL,
            permitted=True,
            restriction_type=RestrictionType.ROLE_RESTRICTED,
            requires_consent=True,
            requires_disclosure=True,
            permitted_roles=[
                RoleCategory.FINANCIAL,
                RoleCategory.GOVERNMENT,
                RoleCategory.SECURITY,
            ],
            notes="LGPD: Criminal checks only for roles with legal basis",
        )
    )

    # Credit checks prohibited for hiring
    rules.append(
        ComplianceRule(
            locale=Locale.BR,
            check_type=CheckType.CREDIT_REPORT,
            permitted=False,
            restriction_type=RestrictionType.BLOCKED,
            notes="LGPD: Credit checks prohibited for employment decisions",
        )
    )

    # Employment verification
    rules.append(
        ComplianceRule(
            locale=Locale.BR,
            check_type=CheckType.EMPLOYMENT_VERIFICATION,
            permitted=True,
            requires_consent=True,
            requires_disclosure=True,
            notes="LGPD: Explicit consent and purpose limitation required",
        )
    )

    return rules
