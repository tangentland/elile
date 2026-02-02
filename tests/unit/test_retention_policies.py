"""Tests for data retention policies."""

import pytest

from elile.compliance.retention.policies import (
    create_default_policies,
    create_eu_policies,
    create_uk_policies,
    create_ca_policies,
    create_br_policies,
    get_default_policies,
    get_policies_for_locale,
    get_policy_for_data_type,
    SEVEN_YEARS,
    THIRTY_DAYS,
)
from elile.compliance.retention.types import (
    DataType,
    DeletionMethod,
)
from elile.compliance.types import Locale


class TestDefaultPolicies:
    """Tests for default retention policies."""

    def test_create_default_policies(self) -> None:
        """Test creating default policies."""
        policies = create_default_policies()

        assert len(policies) > 0
        # Should have policies for all major data types
        data_types = {p.data_type for p in policies}
        assert DataType.SCREENING_RESULT in data_types
        assert DataType.AUDIT_LOG in data_types
        assert DataType.CONSENT_RECORD in data_types

    def test_screening_result_policy(self) -> None:
        """Test screening result default policy."""
        policies = create_default_policies()
        policy = next(p for p in policies if p.data_type == DataType.SCREENING_RESULT)

        assert policy.retention_days == SEVEN_YEARS
        assert policy.locale is None  # All locales
        assert policy.subject_request_override is False  # Cannot delete early
        assert "FCRA" in policy.regulatory_basis

    def test_audit_log_policy(self) -> None:
        """Test audit log policy (immutable)."""
        policies = create_default_policies()
        policy = next(p for p in policies if p.data_type == DataType.AUDIT_LOG)

        assert policy.retention_days == SEVEN_YEARS
        assert policy.subject_request_override is False  # Cannot be erased
        assert policy.legal_hold_exempt is True  # Always retained

    def test_raw_data_minimal_retention(self) -> None:
        """Test raw data has minimal retention."""
        policies = create_default_policies()
        policy = next(p for p in policies if p.data_type == DataType.SCREENING_RAW_DATA)

        assert policy.retention_days == THIRTY_DAYS
        assert policy.deletion_method == DeletionMethod.HARD_DELETE
        assert policy.subject_request_override is True


class TestLocaleSpecificPolicies:
    """Tests for locale-specific policies."""

    def test_eu_policies(self) -> None:
        """Test EU-specific policies."""
        policies = create_eu_policies()

        assert len(policies) > 0
        for policy in policies:
            assert policy.locale == Locale.EU

    def test_eu_raw_data_shorter_retention(self) -> None:
        """Test EU has shorter raw data retention."""
        eu_policies = create_eu_policies()
        raw_policy = next(
            (p for p in eu_policies if p.data_type == DataType.SCREENING_RAW_DATA),
            None,
        )

        assert raw_policy is not None
        assert raw_policy.retention_days == 14  # Shorter than default 30

    def test_eu_entity_profile_erasure(self) -> None:
        """Test EU entity profile allows erasure."""
        eu_policies = create_eu_policies()
        profile_policy = next(
            (p for p in eu_policies if p.data_type == DataType.ENTITY_PROFILE),
            None,
        )

        assert profile_policy is not None
        assert profile_policy.subject_request_override is True
        assert "GDPR" in profile_policy.regulatory_basis

    def test_uk_policies(self) -> None:
        """Test UK-specific policies."""
        policies = create_uk_policies()

        assert len(policies) > 0
        for policy in policies:
            assert policy.locale == Locale.UK

    def test_ca_policies(self) -> None:
        """Test Canada-specific policies."""
        policies = create_ca_policies()

        assert len(policies) > 0
        for policy in policies:
            assert policy.locale == Locale.CA

    def test_br_policies(self) -> None:
        """Test Brazil-specific policies."""
        policies = create_br_policies()

        assert len(policies) > 0
        for policy in policies:
            assert policy.locale == Locale.BR


class TestPolicyLookup:
    """Tests for policy lookup functions."""

    def test_get_default_policies(self) -> None:
        """Test getting all default policies."""
        policies = get_default_policies()

        # Should include all default + locale-specific
        assert len(policies) > 10

        # Should be cached (same object returned)
        policies2 = get_default_policies()
        assert policies is policies2

    def test_get_policy_for_data_type_default(self) -> None:
        """Test getting default policy for data type."""
        policy = get_policy_for_data_type(DataType.SCREENING_RESULT)

        assert policy is not None
        assert policy.data_type == DataType.SCREENING_RESULT
        assert policy.locale is None  # Default policy

    def test_get_policy_for_data_type_locale_specific(self) -> None:
        """Test getting locale-specific policy."""
        policy = get_policy_for_data_type(DataType.SCREENING_RAW_DATA, Locale.EU)

        assert policy is not None
        assert policy.data_type == DataType.SCREENING_RAW_DATA
        assert policy.locale == Locale.EU
        assert policy.retention_days == 14  # EU-specific

    def test_get_policy_for_data_type_fallback(self) -> None:
        """Test falling back to default when no locale-specific policy."""
        # Audit logs don't have locale-specific policies
        policy = get_policy_for_data_type(DataType.AUDIT_LOG, Locale.JP)

        assert policy is not None
        assert policy.data_type == DataType.AUDIT_LOG
        assert policy.locale is None  # Fell back to default

    def test_get_policies_for_locale(self) -> None:
        """Test getting all policies for a locale."""
        policies = get_policies_for_locale(Locale.EU)

        # Should have a policy for each data type
        data_types = {p.data_type for p in policies}
        assert DataType.SCREENING_RESULT in data_types
        assert DataType.ENTITY_PROFILE in data_types

    def test_get_policies_for_locale_priority(self) -> None:
        """Test that locale-specific policies override defaults."""
        policies = get_policies_for_locale(Locale.EU)
        raw_policy = next(p for p in policies if p.data_type == DataType.SCREENING_RAW_DATA)

        # Should be EU-specific (14 days) not default (30 days)
        assert raw_policy.retention_days == 14
        assert raw_policy.locale == Locale.EU


class TestPolicyCompliance:
    """Tests for policy compliance characteristics."""

    def test_screening_policies_not_erasable(self) -> None:
        """Test that screening results cannot be erased early."""
        policies = create_default_policies()

        for policy in policies:
            if policy.data_type in (
                DataType.SCREENING_RESULT,
                DataType.SCREENING_FINDING,
                DataType.CONSENT_RECORD,
                DataType.DISCLOSURE_RECORD,
                DataType.ADVERSE_ACTION,
            ):
                assert policy.subject_request_override is False

    def test_raw_data_erasable(self) -> None:
        """Test that raw data can be erased."""
        policies = create_default_policies()

        for policy in policies:
            if policy.data_type in (
                DataType.SCREENING_RAW_DATA,
                DataType.PROVIDER_RESPONSE,
                DataType.CACHE_ENTRY,
            ):
                assert policy.subject_request_override is True

    def test_all_policies_have_regulatory_basis(self) -> None:
        """Test that compliance-critical policies have regulatory basis."""
        policies = create_default_policies()

        compliance_critical = [
            DataType.SCREENING_RESULT,
            DataType.AUDIT_LOG,
            DataType.CONSENT_RECORD,
            DataType.DISCLOSURE_RECORD,
            DataType.ADVERSE_ACTION,
        ]

        for policy in policies:
            if policy.data_type in compliance_critical:
                assert policy.regulatory_basis is not None

    def test_archive_policies(self) -> None:
        """Test that long-term data has archive settings."""
        policies = create_default_policies()

        for policy in policies:
            if policy.retention_days >= 365 * 5:  # 5+ years
                # Should either archive before delete or use archive method
                assert (
                    policy.archive_before_delete
                    or policy.deletion_method == DeletionMethod.ARCHIVE
                    or policy.archive_after_days is not None
                )
