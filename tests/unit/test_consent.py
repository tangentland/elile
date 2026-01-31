"""Unit tests for consent management."""

from datetime import UTC, datetime, timedelta
from uuid import uuid7

import pytest

from elile.compliance.consent import (
    Consent,
    ConsentManager,
    ConsentScope,
    ConsentVerificationMethod,
    create_consent,
    create_fcra_disclosure,
    FCRADisclosure,
)
from elile.compliance.types import CheckType, Locale


class TestConsentScope:
    """Tests for ConsentScope enum."""

    def test_scope_values(self):
        """Test consent scope values."""
        assert ConsentScope.BACKGROUND_CHECK.value == "background_check"
        assert ConsentScope.CRIMINAL_RECORDS.value == "criminal_records"
        assert ConsentScope.CREDIT_CHECK.value == "credit_check"
        assert ConsentScope.DRUG_TESTING.value == "drug_testing"


class TestConsentVerificationMethod:
    """Tests for ConsentVerificationMethod enum."""

    def test_method_values(self):
        """Test verification method values."""
        assert ConsentVerificationMethod.E_SIGNATURE.value == "e_signature"
        assert ConsentVerificationMethod.WET_SIGNATURE.value == "wet_signature"
        assert ConsentVerificationMethod.HRIS_API.value == "hris_api"


class TestFCRADisclosure:
    """Tests for FCRADisclosure model."""

    def test_create_disclosure(self):
        """Test creating FCRA disclosure."""
        disclosure = FCRADisclosure(
            provided_at=datetime.now(UTC),
            method="email",
        )
        assert disclosure.standalone_disclosure is True
        assert disclosure.summary_of_rights is True
        assert disclosure.is_complete is True

    def test_incomplete_disclosure(self):
        """Test incomplete FCRA disclosure."""
        disclosure = FCRADisclosure(
            provided_at=datetime.now(UTC),
            method="email",
            standalone_disclosure=False,
        )
        assert disclosure.is_complete is False

    def test_state_disclosures(self):
        """Test state-specific disclosures."""
        disclosure = FCRADisclosure(
            provided_at=datetime.now(UTC),
            method="email",
            state_disclosures=["CA_ICRAA", "NY_FAIR_CHANCE"],
        )
        assert "CA_ICRAA" in disclosure.state_disclosures

    def test_investigative_disclosure(self):
        """Test investigative consumer report disclosure."""
        now = datetime.now(UTC)
        disclosure = FCRADisclosure(
            provided_at=now,
            method="email",
            investigative_disclosure=True,
            investigative_disclosure_at=now,
        )
        assert disclosure.investigative_disclosure is True


class TestConsent:
    """Tests for Consent model."""

    @pytest.fixture
    def subject_id(self):
        """Create test subject ID."""
        return uuid7()

    def test_create_consent(self, subject_id):
        """Test creating basic consent."""
        consent = Consent(
            subject_id=subject_id,
            scopes=[ConsentScope.BACKGROUND_CHECK],
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
        )
        assert consent.subject_id == subject_id
        assert ConsentScope.BACKGROUND_CHECK in consent.scopes
        assert consent.is_valid is True

    def test_consent_expiration(self, subject_id):
        """Test consent expiration."""
        past = datetime.now(UTC) - timedelta(days=1)
        consent = Consent(
            subject_id=subject_id,
            scopes=[ConsentScope.BACKGROUND_CHECK],
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
            expires_at=past,
        )
        assert consent.is_expired is True
        assert consent.is_valid is False

    def test_consent_not_expired(self, subject_id):
        """Test consent not expired."""
        future = datetime.now(UTC) + timedelta(days=365)
        consent = Consent(
            subject_id=subject_id,
            scopes=[ConsentScope.BACKGROUND_CHECK],
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
            expires_at=future,
        )
        assert consent.is_expired is False
        assert consent.is_valid is True

    def test_consent_revocation(self, subject_id):
        """Test consent revocation."""
        consent = Consent(
            subject_id=subject_id,
            scopes=[ConsentScope.BACKGROUND_CHECK],
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
            revoked_at=datetime.now(UTC),
            revocation_reason="Subject request",
        )
        assert consent.is_revoked is True
        assert consent.is_valid is False

    def test_covers_scope_direct(self, subject_id):
        """Test covers_scope with direct match."""
        consent = Consent(
            subject_id=subject_id,
            scopes=[ConsentScope.CRIMINAL_RECORDS],
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
        )
        assert consent.covers_scope(ConsentScope.CRIMINAL_RECORDS) is True
        assert consent.covers_scope(ConsentScope.CREDIT_CHECK) is False

    def test_covers_scope_background_check(self, subject_id):
        """Test that BACKGROUND_CHECK covers basic scopes."""
        consent = Consent(
            subject_id=subject_id,
            scopes=[ConsentScope.BACKGROUND_CHECK],
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
        )
        # Background check should cover these
        assert consent.covers_scope(ConsentScope.CRIMINAL_RECORDS) is True
        assert consent.covers_scope(ConsentScope.EMPLOYMENT_VERIFICATION) is True
        assert consent.covers_scope(ConsentScope.EDUCATION_VERIFICATION) is True

        # But not these special scopes
        assert consent.covers_scope(ConsentScope.CREDIT_CHECK) is False
        assert consent.covers_scope(ConsentScope.DRUG_TESTING) is False

    def test_covers_check_type(self, subject_id):
        """Test covers_check_type."""
        consent = Consent(
            subject_id=subject_id,
            scopes=[ConsentScope.CRIMINAL_RECORDS],
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
        )
        assert consent.covers_check_type(CheckType.CRIMINAL_NATIONAL) is True
        assert consent.covers_check_type(CheckType.CRIMINAL_STATE) is True
        assert consent.covers_check_type(CheckType.CREDIT_REPORT) is False

    def test_invalid_consent_doesnt_cover(self, subject_id):
        """Test that invalid consent doesn't cover anything."""
        consent = Consent(
            subject_id=subject_id,
            scopes=[ConsentScope.BACKGROUND_CHECK],
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
            revoked_at=datetime.now(UTC),
        )
        assert consent.covers_scope(ConsentScope.BACKGROUND_CHECK) is False


class TestConsentManager:
    """Tests for ConsentManager."""

    @pytest.fixture
    def manager(self):
        """Create consent manager."""
        return ConsentManager()

    @pytest.fixture
    def subject_id(self):
        """Create test subject ID."""
        return uuid7()

    def test_register_consent(self, manager, subject_id):
        """Test registering consent."""
        consent = Consent(
            subject_id=subject_id,
            scopes=[ConsentScope.BACKGROUND_CHECK],
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
        )
        manager.register_consent(consent)

        consents = manager.get_consents(subject_id)
        assert len(consents) == 1

    def test_get_consents_empty(self, manager, subject_id):
        """Test getting consents when none registered."""
        consents = manager.get_consents(subject_id)
        assert len(consents) == 0

    def test_get_valid_consents(self, manager, subject_id):
        """Test getting only valid consents."""
        # Register valid consent
        valid_consent = Consent(
            subject_id=subject_id,
            scopes=[ConsentScope.BACKGROUND_CHECK],
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
        )
        manager.register_consent(valid_consent)

        # Register expired consent
        expired_consent = Consent(
            subject_id=subject_id,
            scopes=[ConsentScope.CREDIT_CHECK],
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        manager.register_consent(expired_consent)

        valid = manager.get_valid_consents(subject_id)
        assert len(valid) == 1
        assert valid[0].consent_id == valid_consent.consent_id

    def test_verify_consent_success(self, manager, subject_id):
        """Test successful consent verification."""
        consent = Consent(
            subject_id=subject_id,
            scopes=[ConsentScope.BACKGROUND_CHECK],
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
        )
        manager.register_consent(consent)

        result = manager.verify_consent(
            subject_id,
            [ConsentScope.CRIMINAL_RECORDS],
        )
        assert result.valid is True
        assert len(result.missing_scopes) == 0

    def test_verify_consent_missing(self, manager, subject_id):
        """Test consent verification with missing scope."""
        consent = Consent(
            subject_id=subject_id,
            scopes=[ConsentScope.BACKGROUND_CHECK],
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
        )
        manager.register_consent(consent)

        result = manager.verify_consent(
            subject_id,
            [ConsentScope.CREDIT_CHECK],  # Not covered by BACKGROUND_CHECK
        )
        assert result.valid is False
        assert ConsentScope.CREDIT_CHECK in result.missing_scopes

    def test_verify_consent_no_consent(self, manager, subject_id):
        """Test consent verification with no consent."""
        result = manager.verify_consent(
            subject_id,
            [ConsentScope.BACKGROUND_CHECK],
        )
        assert result.valid is False
        assert len(result.errors) > 0

    def test_verify_check_types(self, manager, subject_id):
        """Test verifying check types."""
        consent = Consent(
            subject_id=subject_id,
            scopes=[ConsentScope.CRIMINAL_RECORDS, ConsentScope.CREDIT_CHECK],
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
        )
        manager.register_consent(consent)

        result = manager.verify_check_types(
            subject_id,
            [CheckType.CRIMINAL_NATIONAL, CheckType.CREDIT_REPORT],
        )
        assert result.valid is True

    def test_verify_fcra_disclosure_success(self, manager):
        """Test FCRA disclosure verification success."""
        consent = Consent(
            subject_id=uuid7(),
            scopes=[ConsentScope.BACKGROUND_CHECK],
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
            fcra_disclosure=FCRADisclosure(
                provided_at=datetime.now(UTC),
                method="email",
            ),
        )

        valid, errors = manager.verify_fcra_disclosure(consent, Locale.US)
        assert valid is True
        assert len(errors) == 0

    def test_verify_fcra_disclosure_missing(self, manager):
        """Test FCRA disclosure verification with missing disclosure."""
        consent = Consent(
            subject_id=uuid7(),
            scopes=[ConsentScope.BACKGROUND_CHECK],
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
        )

        valid, errors = manager.verify_fcra_disclosure(consent, Locale.US)
        assert valid is False
        assert "No FCRA disclosure record" in errors

    def test_verify_fcra_disclosure_california(self, manager):
        """Test FCRA disclosure verification for California."""
        consent = Consent(
            subject_id=uuid7(),
            scopes=[ConsentScope.BACKGROUND_CHECK],
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
            fcra_disclosure=FCRADisclosure(
                provided_at=datetime.now(UTC),
                method="email",
                state_disclosures=[],  # Missing CA_ICRAA
            ),
        )

        valid, errors = manager.verify_fcra_disclosure(consent, Locale.US_CA)
        assert valid is False
        assert any("California" in e for e in errors)

    def test_verify_fcra_disclosure_non_us(self, manager):
        """Test FCRA disclosure not required for non-US."""
        consent = Consent(
            subject_id=uuid7(),
            scopes=[ConsentScope.BACKGROUND_CHECK],
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
            # No FCRA disclosure
        )

        valid, errors = manager.verify_fcra_disclosure(consent, Locale.EU)
        assert valid is True  # FCRA doesn't apply

    def test_revoke_consent(self, manager, subject_id):
        """Test revoking consent."""
        consent = Consent(
            subject_id=subject_id,
            scopes=[ConsentScope.BACKGROUND_CHECK],
            verification_method=ConsentVerificationMethod.E_SIGNATURE,
        )
        manager.register_consent(consent)

        result = manager.revoke_consent(consent.consent_id, "Test revocation")
        assert result is True

        # Verify consent is now invalid
        valid_consents = manager.get_valid_consents(subject_id)
        assert len(valid_consents) == 0

    def test_revoke_consent_not_found(self, manager):
        """Test revoking non-existent consent."""
        result = manager.revoke_consent(uuid7())
        assert result is False


class TestCreateConsent:
    """Tests for create_consent helper."""

    def test_create_basic_consent(self):
        """Test creating basic consent."""
        subject_id = uuid7()
        consent = create_consent(
            subject_id=subject_id,
            scopes=[ConsentScope.BACKGROUND_CHECK],
        )
        assert consent.subject_id == subject_id
        assert consent.verification_method == ConsentVerificationMethod.E_SIGNATURE
        assert consent.locale == Locale.US

    def test_create_consent_with_expiry(self):
        """Test creating consent with custom expiry."""
        consent = create_consent(
            subject_id=uuid7(),
            scopes=[ConsentScope.BACKGROUND_CHECK],
            expires_in_days=30,
        )
        assert consent.expires_at is not None
        delta = consent.expires_at - consent.granted_at
        assert delta.days == 30

    def test_create_consent_no_expiry(self):
        """Test creating consent with no expiry."""
        consent = create_consent(
            subject_id=uuid7(),
            scopes=[ConsentScope.BACKGROUND_CHECK],
            expires_in_days=None,
        )
        assert consent.expires_at is None


class TestCreateFCRADisclosure:
    """Tests for create_fcra_disclosure helper."""

    def test_create_basic_disclosure(self):
        """Test creating basic FCRA disclosure."""
        disclosure = create_fcra_disclosure()
        assert disclosure.standalone_disclosure is True
        assert disclosure.summary_of_rights is True
        assert disclosure.method == "e_signature"

    def test_create_disclosure_with_states(self):
        """Test creating disclosure with state disclosures."""
        disclosure = create_fcra_disclosure(
            state_disclosures=["CA_ICRAA", "NY_FAIR_CHANCE"],
        )
        assert "CA_ICRAA" in disclosure.state_disclosures
        assert "NY_FAIR_CHANCE" in disclosure.state_disclosures

    def test_create_investigative_disclosure(self):
        """Test creating investigative disclosure."""
        disclosure = create_fcra_disclosure(investigative=True)
        assert disclosure.investigative_disclosure is True
        assert disclosure.investigative_disclosure_at is not None
