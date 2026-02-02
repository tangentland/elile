"""Default data retention policies by locale and data type.

This module defines the standard retention policies for different
jurisdictions and data types based on regulatory requirements.
"""

from uuid import uuid7

from elile.compliance.retention.types import (
    DataType,
    DeletionMethod,
    RetentionPolicy,
)
from elile.compliance.types import Locale

# Standard retention periods (days)
SEVEN_YEARS = 7 * 365  # 2555 days
FIVE_YEARS = 5 * 365  # 1825 days
THREE_YEARS = 3 * 365  # 1095 days
ONE_YEAR = 365
NINETY_DAYS = 90
THIRTY_DAYS = 30


def create_default_policies() -> list[RetentionPolicy]:
    """Create the default set of retention policies.

    Returns:
        List of default RetentionPolicy instances
    """
    policies = []

    # =========================================================================
    # Screening Results - 7 years (FCRA, SOX compliance)
    # =========================================================================
    policies.append(
        RetentionPolicy(
            policy_id=uuid7(),
            name="screening_result_default",
            description="Default retention for screening results (7 years per FCRA/SOX)",
            data_type=DataType.SCREENING_RESULT,
            locale=None,  # All locales
            retention_days=SEVEN_YEARS,
            archive_after_days=ONE_YEAR,
            deletion_method=DeletionMethod.ARCHIVE,
            archive_before_delete=True,
            regulatory_basis="FCRA Section 604(b)(3), SOX Section 802",
            subject_request_override=False,  # Cannot delete screening records early
            legal_hold_exempt=False,
        )
    )

    # =========================================================================
    # Screening Findings - 7 years
    # =========================================================================
    policies.append(
        RetentionPolicy(
            policy_id=uuid7(),
            name="screening_finding_default",
            description="Default retention for screening findings (7 years)",
            data_type=DataType.SCREENING_FINDING,
            locale=None,
            retention_days=SEVEN_YEARS,
            archive_after_days=ONE_YEAR,
            deletion_method=DeletionMethod.ARCHIVE,
            archive_before_delete=True,
            regulatory_basis="FCRA record retention requirements",
            subject_request_override=False,
        )
    )

    # =========================================================================
    # Raw Screening Data - 30 days (minimize exposure)
    # =========================================================================
    policies.append(
        RetentionPolicy(
            policy_id=uuid7(),
            name="screening_raw_data_default",
            description="Short retention for raw provider data (30 days)",
            data_type=DataType.SCREENING_RAW_DATA,
            locale=None,
            retention_days=THIRTY_DAYS,
            archive_after_days=None,  # No archive
            deletion_method=DeletionMethod.HARD_DELETE,
            regulatory_basis="Data minimization principle (GDPR Art. 5)",
            subject_request_override=True,
        )
    )

    # =========================================================================
    # Entity Profile - Duration + 7 years
    # =========================================================================
    policies.append(
        RetentionPolicy(
            policy_id=uuid7(),
            name="entity_profile_default",
            description="Entity profile retention (employment duration + 7 years)",
            data_type=DataType.ENTITY_PROFILE,
            locale=None,
            retention_days=SEVEN_YEARS,  # From last update/activity
            archive_after_days=THREE_YEARS,
            deletion_method=DeletionMethod.ANONYMIZE,
            archive_before_delete=True,
            regulatory_basis="Employment records retention",
            subject_request_override=True,  # GDPR erasure applies
        )
    )

    # =========================================================================
    # Entity Relations - 5 years
    # =========================================================================
    policies.append(
        RetentionPolicy(
            policy_id=uuid7(),
            name="entity_relation_default",
            description="Entity relationship data retention (5 years)",
            data_type=DataType.ENTITY_RELATION,
            locale=None,
            retention_days=FIVE_YEARS,
            archive_after_days=ONE_YEAR,
            deletion_method=DeletionMethod.ANONYMIZE,
            subject_request_override=True,
        )
    )

    # =========================================================================
    # Audit Logs - 7 years (immutable)
    # =========================================================================
    policies.append(
        RetentionPolicy(
            policy_id=uuid7(),
            name="audit_log_default",
            description="Audit log retention (7 years, immutable)",
            data_type=DataType.AUDIT_LOG,
            locale=None,
            retention_days=SEVEN_YEARS,
            archive_after_days=ONE_YEAR,
            deletion_method=DeletionMethod.ARCHIVE,  # Never hard delete
            archive_before_delete=True,
            regulatory_basis="SOX Section 802, compliance audit requirements",
            subject_request_override=False,  # Audit logs cannot be erased
            legal_hold_exempt=True,  # Always retained
        )
    )

    # =========================================================================
    # Consent Records - Employment + 7 years
    # =========================================================================
    policies.append(
        RetentionPolicy(
            policy_id=uuid7(),
            name="consent_record_default",
            description="Consent record retention (employment + 7 years)",
            data_type=DataType.CONSENT_RECORD,
            locale=None,
            retention_days=SEVEN_YEARS,
            archive_after_days=THREE_YEARS,
            deletion_method=DeletionMethod.ARCHIVE,
            archive_before_delete=True,
            regulatory_basis="GDPR consent documentation, FCRA consent requirements",
            subject_request_override=False,  # Must retain for compliance
        )
    )

    # =========================================================================
    # Disclosure Records - 7 years
    # =========================================================================
    policies.append(
        RetentionPolicy(
            policy_id=uuid7(),
            name="disclosure_record_default",
            description="FCRA/GDPR disclosure record retention (7 years)",
            data_type=DataType.DISCLOSURE_RECORD,
            locale=None,
            retention_days=SEVEN_YEARS,
            archive_after_days=THREE_YEARS,
            deletion_method=DeletionMethod.ARCHIVE,
            regulatory_basis="FCRA disclosure requirements",
            subject_request_override=False,
        )
    )

    # =========================================================================
    # Adverse Action Records - 7 years
    # =========================================================================
    policies.append(
        RetentionPolicy(
            policy_id=uuid7(),
            name="adverse_action_default",
            description="Adverse action documentation retention (7 years)",
            data_type=DataType.ADVERSE_ACTION,
            locale=None,
            retention_days=SEVEN_YEARS,
            archive_after_days=THREE_YEARS,
            deletion_method=DeletionMethod.ARCHIVE,
            regulatory_basis="FCRA adverse action requirements, EEOC guidelines",
            subject_request_override=False,
        )
    )

    # =========================================================================
    # Reports - 5 years
    # =========================================================================
    policies.append(
        RetentionPolicy(
            policy_id=uuid7(),
            name="report_default",
            description="Generated report retention (5 years)",
            data_type=DataType.REPORT,
            locale=None,
            retention_days=FIVE_YEARS,
            archive_after_days=ONE_YEAR,
            deletion_method=DeletionMethod.ARCHIVE,
            subject_request_override=True,
        )
    )

    # =========================================================================
    # Provider Response - 30 days (raw data minimization)
    # =========================================================================
    policies.append(
        RetentionPolicy(
            policy_id=uuid7(),
            name="provider_response_default",
            description="Raw provider API response retention (30 days)",
            data_type=DataType.PROVIDER_RESPONSE,
            locale=None,
            retention_days=THIRTY_DAYS,
            deletion_method=DeletionMethod.HARD_DELETE,
            regulatory_basis="Data minimization",
            subject_request_override=True,
        )
    )

    # =========================================================================
    # Cache Entries - 90 days
    # =========================================================================
    policies.append(
        RetentionPolicy(
            policy_id=uuid7(),
            name="cache_entry_default",
            description="Cache entry retention (90 days)",
            data_type=DataType.CACHE_ENTRY,
            locale=None,
            retention_days=NINETY_DAYS,
            deletion_method=DeletionMethod.HARD_DELETE,
            subject_request_override=True,
        )
    )

    # =========================================================================
    # Monitoring Alerts - 3 years
    # =========================================================================
    policies.append(
        RetentionPolicy(
            policy_id=uuid7(),
            name="monitoring_alert_default",
            description="Monitoring alert retention (3 years)",
            data_type=DataType.MONITORING_ALERT,
            locale=None,
            retention_days=THREE_YEARS,
            archive_after_days=ONE_YEAR,
            deletion_method=DeletionMethod.ARCHIVE,
            subject_request_override=True,
        )
    )

    # =========================================================================
    # Monitoring Checks - 1 year
    # =========================================================================
    policies.append(
        RetentionPolicy(
            policy_id=uuid7(),
            name="monitoring_check_default",
            description="Monitoring check record retention (1 year)",
            data_type=DataType.MONITORING_CHECK,
            locale=None,
            retention_days=ONE_YEAR,
            deletion_method=DeletionMethod.HARD_DELETE,
            subject_request_override=True,
        )
    )

    return policies


def create_eu_policies() -> list[RetentionPolicy]:
    """Create EU-specific retention policies with GDPR compliance.

    EU policies generally have shorter retention where possible
    due to GDPR data minimization requirements.

    Returns:
        List of EU-specific RetentionPolicy instances
    """
    policies = []

    # EU: Screening raw data - even shorter retention
    policies.append(
        RetentionPolicy(
            policy_id=uuid7(),
            name="screening_raw_data_eu",
            description="EU raw data retention (14 days per GDPR minimization)",
            data_type=DataType.SCREENING_RAW_DATA,
            locale=Locale.EU,
            retention_days=14,
            deletion_method=DeletionMethod.HARD_DELETE,
            regulatory_basis="GDPR Article 5(1)(c) - data minimization",
            subject_request_override=True,
        )
    )

    # EU: Entity profile - subject request always honored
    policies.append(
        RetentionPolicy(
            policy_id=uuid7(),
            name="entity_profile_eu",
            description="EU entity profile with enhanced erasure rights",
            data_type=DataType.ENTITY_PROFILE,
            locale=Locale.EU,
            retention_days=FIVE_YEARS,  # Shorter than default
            archive_after_days=ONE_YEAR,
            deletion_method=DeletionMethod.ANONYMIZE,
            regulatory_basis="GDPR Article 17 - right to erasure",
            subject_request_override=True,
        )
    )

    # EU: Provider response - minimal retention
    policies.append(
        RetentionPolicy(
            policy_id=uuid7(),
            name="provider_response_eu",
            description="EU provider response (14 days)",
            data_type=DataType.PROVIDER_RESPONSE,
            locale=Locale.EU,
            retention_days=14,
            deletion_method=DeletionMethod.HARD_DELETE,
            regulatory_basis="GDPR data minimization",
            subject_request_override=True,
        )
    )

    return policies


def create_uk_policies() -> list[RetentionPolicy]:
    """Create UK-specific retention policies.

    Post-Brexit UK GDPR maintains similar principles to EU GDPR.

    Returns:
        List of UK-specific RetentionPolicy instances
    """
    # UK policies are similar to EU but with UK DBS requirements
    policies = []

    policies.append(
        RetentionPolicy(
            policy_id=uuid7(),
            name="screening_raw_data_uk",
            description="UK raw data retention (14 days)",
            data_type=DataType.SCREENING_RAW_DATA,
            locale=Locale.UK,
            retention_days=14,
            deletion_method=DeletionMethod.HARD_DELETE,
            regulatory_basis="UK GDPR - data minimization",
            subject_request_override=True,
        )
    )

    return policies


def create_ca_policies() -> list[RetentionPolicy]:
    """Create Canada-specific retention policies.

    PIPEDA compliance requirements.

    Returns:
        List of Canada-specific RetentionPolicy instances
    """
    policies = []

    policies.append(
        RetentionPolicy(
            policy_id=uuid7(),
            name="screening_result_ca",
            description="Canada screening result retention (6 years)",
            data_type=DataType.SCREENING_RESULT,
            locale=Locale.CA,
            retention_days=6 * 365,  # 6 years
            archive_after_days=ONE_YEAR,
            deletion_method=DeletionMethod.ARCHIVE,
            regulatory_basis="PIPEDA Principle 4.5 - limiting retention",
            subject_request_override=True,
        )
    )

    return policies


def create_br_policies() -> list[RetentionPolicy]:
    """Create Brazil-specific retention policies.

    LGPD compliance requirements.

    Returns:
        List of Brazil-specific RetentionPolicy instances
    """
    policies = []

    policies.append(
        RetentionPolicy(
            policy_id=uuid7(),
            name="entity_profile_br",
            description="Brazil entity profile retention per LGPD",
            data_type=DataType.ENTITY_PROFILE,
            locale=Locale.BR,
            retention_days=FIVE_YEARS,
            archive_after_days=ONE_YEAR,
            deletion_method=DeletionMethod.ANONYMIZE,
            regulatory_basis="LGPD Article 16 - data elimination",
            subject_request_override=True,
        )
    )

    return policies


# Global policy registry
_DEFAULT_POLICIES: list[RetentionPolicy] | None = None


def get_default_policies() -> list[RetentionPolicy]:
    """Get all default retention policies.

    Returns:
        Combined list of all default and locale-specific policies
    """
    global _DEFAULT_POLICIES

    if _DEFAULT_POLICIES is None:
        _DEFAULT_POLICIES = (
            create_default_policies()
            + create_eu_policies()
            + create_uk_policies()
            + create_ca_policies()
            + create_br_policies()
        )

    return _DEFAULT_POLICIES


def get_policy_for_data_type(
    data_type: DataType,
    locale: Locale | None = None,
) -> RetentionPolicy | None:
    """Get the most specific policy for a data type and locale.

    Args:
        data_type: Type of data
        locale: Optional locale for locale-specific policy

    Returns:
        Most specific matching policy, or None if no match
    """
    policies = get_default_policies()

    # First try locale-specific policy
    if locale is not None:
        for policy in policies:
            if policy.data_type == data_type and policy.locale == locale:
                return policy

    # Fall back to default (locale=None) policy
    for policy in policies:
        if policy.data_type == data_type and policy.locale is None:
            return policy

    return None


def get_policies_for_locale(locale: Locale) -> list[RetentionPolicy]:
    """Get all policies applicable to a locale.

    Returns locale-specific policies plus default policies.

    Args:
        locale: The locale to get policies for

    Returns:
        List of applicable policies
    """
    policies = get_default_policies()
    applicable = []

    # Get locale-specific policies
    locale_policies = {p.data_type: p for p in policies if p.locale == locale}

    # Get default policies
    default_policies = {p.data_type: p for p in policies if p.locale is None}

    # Merge: locale-specific overrides default
    for data_type in DataType:
        if data_type in locale_policies:
            applicable.append(locale_policies[data_type])
        elif data_type in default_policies:
            applicable.append(default_policies[data_type])

    return applicable
