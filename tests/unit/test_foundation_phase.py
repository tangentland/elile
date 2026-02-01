"""Tests for the FoundationPhaseHandler module.

Tests cover:
- Identity baseline verification
- Employment baseline verification
- Education baseline verification
- Baseline profile aggregation
- Phase execution and results
"""

import pytest
from datetime import date

from elile.agent.state import InformationType, ServiceTier
from elile.compliance.types import Locale
from elile.investigation.phases.foundation import (
    BaselineProfile,
    EducationBaseline,
    EmploymentBaseline,
    FoundationConfig,
    FoundationPhaseHandler,
    FoundationPhaseResult,
    IdentityBaseline,
    VerificationStatus,
    create_foundation_phase_handler,
)


class TestVerificationStatus:
    """Tests for VerificationStatus enum."""

    def test_all_statuses_exist(self) -> None:
        """Test all expected statuses exist."""
        assert VerificationStatus.VERIFIED.value == "verified"
        assert VerificationStatus.PARTIAL.value == "partial"
        assert VerificationStatus.UNVERIFIED.value == "unverified"
        assert VerificationStatus.CONFLICTING.value == "conflicting"
        assert VerificationStatus.NOT_FOUND.value == "not_found"
        assert VerificationStatus.PENDING.value == "pending"


class TestIdentityBaseline:
    """Tests for IdentityBaseline dataclass."""

    def test_identity_baseline_defaults(self) -> None:
        """Test default identity baseline values."""
        identity = IdentityBaseline()
        assert identity.legal_name == ""
        assert identity.name_status == VerificationStatus.PENDING
        assert identity.is_verified is False

    def test_identity_is_verified(self) -> None:
        """Test identity verification check."""
        identity = IdentityBaseline(
            legal_name="John Smith",
            name_status=VerificationStatus.VERIFIED,
            dob_status=VerificationStatus.VERIFIED,
        )
        assert identity.is_verified is True

    def test_identity_not_verified_without_dob(self) -> None:
        """Test identity not verified without DOB."""
        identity = IdentityBaseline(
            legal_name="John Smith",
            name_status=VerificationStatus.VERIFIED,
            dob_status=VerificationStatus.PENDING,
        )
        assert identity.is_verified is False

    def test_overall_status_verified(self) -> None:
        """Test overall status when all verified."""
        identity = IdentityBaseline(
            name_status=VerificationStatus.VERIFIED,
            dob_status=VerificationStatus.VERIFIED,
            ssn_status=VerificationStatus.VERIFIED,
            address_status=VerificationStatus.VERIFIED,
        )
        assert identity.overall_status == VerificationStatus.VERIFIED

    def test_overall_status_partial(self) -> None:
        """Test overall status when partially verified."""
        identity = IdentityBaseline(
            name_status=VerificationStatus.VERIFIED,
            dob_status=VerificationStatus.PENDING,
        )
        assert identity.overall_status == VerificationStatus.PARTIAL

    def test_overall_status_conflicting(self) -> None:
        """Test overall status when conflicting data."""
        identity = IdentityBaseline(
            name_status=VerificationStatus.VERIFIED,
            dob_status=VerificationStatus.CONFLICTING,
        )
        assert identity.overall_status == VerificationStatus.CONFLICTING

    def test_identity_to_dict(self) -> None:
        """Test identity serialization."""
        identity = IdentityBaseline(
            legal_name="John Smith",
            name_status=VerificationStatus.VERIFIED,
            confidence=0.85,
        )
        d = identity.to_dict()
        assert d["legal_name"] == "John Smith"
        assert d["name_status"] == "verified"
        assert d["confidence"] == 0.85


class TestEmploymentBaseline:
    """Tests for EmploymentBaseline dataclass."""

    def test_employment_baseline_defaults(self) -> None:
        """Test default employment baseline values."""
        employment = EmploymentBaseline()
        assert employment.employer_count == 0
        assert employment.status == VerificationStatus.PENDING

    def test_add_employer(self) -> None:
        """Test adding employer to history."""
        employment = EmploymentBaseline()
        employment.add_employer(
            employer_name="Acme Corp",
            title="Software Engineer",
            start_date=date(2020, 1, 1),
            verified=True,
            source="work_number",
        )
        assert employment.employer_count == 1
        assert employment.verified_employer_count == 1

    def test_multiple_employers(self) -> None:
        """Test multiple employers with mixed verification."""
        employment = EmploymentBaseline()
        employment.add_employer("Company A", verified=True)
        employment.add_employer("Company B", verified=False)
        employment.add_employer("Company C", verified=True)

        assert employment.employer_count == 3
        assert employment.verified_employer_count == 2


class TestEducationBaseline:
    """Tests for EducationBaseline dataclass."""

    def test_education_baseline_defaults(self) -> None:
        """Test default education baseline values."""
        education = EducationBaseline()
        assert education.credential_count == 0
        assert education.status == VerificationStatus.PENDING

    def test_add_credential(self) -> None:
        """Test adding education credential."""
        education = EducationBaseline()
        education.add_credential(
            institution="State University",
            degree="Bachelor of Science",
            field_of_study="Computer Science",
            graduation_date=date(2015, 5, 15),
            verified=True,
        )
        assert education.credential_count == 1
        assert education.verified_credential_count == 1


class TestBaselineProfile:
    """Tests for BaselineProfile dataclass."""

    def test_baseline_profile_defaults(self) -> None:
        """Test default baseline profile values."""
        profile = BaselineProfile()
        assert profile.overall_confidence == 0.0
        assert profile.is_complete is False

    def test_calculate_confidence(self) -> None:
        """Test confidence calculation."""
        profile = BaselineProfile()
        profile.identity.confidence = 0.9
        profile.employment.confidence = 0.8
        profile.education.confidence = 0.7

        confidence = profile.calculate_confidence()
        assert confidence == pytest.approx(0.8)
        assert profile.overall_confidence == pytest.approx(0.8)

    def test_is_complete(self) -> None:
        """Test completion check."""
        profile = BaselineProfile()
        profile.identity.name_status = VerificationStatus.VERIFIED
        profile.identity.dob_status = VerificationStatus.VERIFIED
        profile.employment.status = VerificationStatus.VERIFIED
        profile.education.status = VerificationStatus.VERIFIED

        assert profile.is_complete is True


class TestFoundationConfig:
    """Tests for FoundationConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = FoundationConfig()
        assert config.require_identity_verification is True
        assert config.employment_lookback_years == 7
        assert config.min_identity_confidence == 0.8


class TestFoundationPhaseResult:
    """Tests for FoundationPhaseResult."""

    def test_result_defaults(self) -> None:
        """Test default result values."""
        result = FoundationPhaseResult()
        assert result.success is True
        assert result.all_complete is False

    def test_all_complete(self) -> None:
        """Test all_complete property."""
        result = FoundationPhaseResult(
            identity_complete=True,
            employment_complete=True,
            education_complete=True,
        )
        assert result.all_complete is True

    def test_to_dict(self) -> None:
        """Test result serialization."""
        result = FoundationPhaseResult(
            success=True,
            identity_complete=True,
            queries_executed=5,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["identity_complete"] is True
        assert d["queries_executed"] == 5


class TestFoundationPhaseHandler:
    """Tests for FoundationPhaseHandler."""

    @pytest.fixture
    def handler(self) -> FoundationPhaseHandler:
        """Create a handler with default config."""
        return FoundationPhaseHandler()

    @pytest.mark.asyncio
    async def test_execute_with_full_data(self, handler: FoundationPhaseHandler) -> None:
        """Test execution with full subject data."""
        result = await handler.execute(
            subject_name="John Smith",
            subject_dob=date(1985, 3, 15),
            subject_ssn_last4="1234",
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
        )

        assert result.success is True
        assert result.identity_complete is True
        assert result.profile.identity.legal_name == "John Smith"
        assert result.profile.identity.date_of_birth == date(1985, 3, 15)
        assert result.profile.identity.ssn_last4 == "1234"

    @pytest.mark.asyncio
    async def test_execute_with_minimal_data(self, handler: FoundationPhaseHandler) -> None:
        """Test execution with minimal subject data."""
        result = await handler.execute(
            subject_name="Jane Doe",
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
        )

        assert result.success is True
        # Without DOB, identity not fully verified
        assert result.profile.identity.name_status == VerificationStatus.VERIFIED
        assert result.profile.identity.dob_status == VerificationStatus.PENDING

    @pytest.mark.asyncio
    async def test_execute_tracks_types(self, handler: FoundationPhaseHandler) -> None:
        """Test that execution tracks verified/pending types."""
        result = await handler.execute(
            subject_name="John Smith",
            subject_dob=date(1985, 3, 15),
        )

        # Identity should be verified
        assert InformationType.IDENTITY in result.profile.types_verified
        # Employment and education pending (stub implementation)
        assert InformationType.EMPLOYMENT in result.profile.types_pending
        assert InformationType.EDUCATION in result.profile.types_pending

    @pytest.mark.asyncio
    async def test_execute_calculates_confidence(self, handler: FoundationPhaseHandler) -> None:
        """Test that execution calculates confidence."""
        result = await handler.execute(
            subject_name="John Smith",
            subject_dob=date(1985, 3, 15),
            subject_ssn_last4="1234",
        )

        # Identity confidence should be 1.0 (all verified)
        assert result.profile.identity.confidence == 1.0
        # Overall confidence should be set
        assert result.profile.overall_confidence > 0

    @pytest.mark.asyncio
    async def test_execute_records_timing(self, handler: FoundationPhaseHandler) -> None:
        """Test that execution records timing."""
        result = await handler.execute(subject_name="John Smith")

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.duration_ms >= 0

    def test_custom_config(self) -> None:
        """Test handler with custom configuration."""
        config = FoundationConfig(
            employment_lookback_years=10,
            require_education_verification=False,
        )
        handler = FoundationPhaseHandler(config=config)

        assert handler.config.employment_lookback_years == 10
        assert handler.config.require_education_verification is False


class TestCreateFoundationPhaseHandler:
    """Tests for factory function."""

    def test_create_with_defaults(self) -> None:
        """Test creating handler with defaults."""
        handler = create_foundation_phase_handler()
        assert isinstance(handler, FoundationPhaseHandler)

    def test_create_with_config(self) -> None:
        """Test creating handler with custom config."""
        config = FoundationConfig(employment_lookback_years=5)
        handler = create_foundation_phase_handler(config=config)
        assert handler.config.employment_lookback_years == 5
