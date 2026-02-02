"""Tests for education provider type definitions."""

from datetime import date, datetime
from uuid import uuid7

import pytest

from elile.providers.education.types import (
    AccreditationType,
    ClaimedEducation,
    DegreeType,
    DiplomaMilDetectedError,
    EducationDiscrepancy,
    EducationProviderConfig,
    EducationProviderError,
    EducationVerificationResult,
    Institution,
    InstitutionMatchResult,
    InstitutionNotFoundError,
    InstitutionType,
    MatchConfidence,
    VerificationFailedError,
    VerificationStatus,
    VerifiedEducation,
)


class TestDegreeType:
    """Tests for DegreeType enum."""

    def test_undergraduate_degrees(self) -> None:
        """Test undergraduate degree types exist."""
        assert DegreeType.ASSOCIATE == "associate"
        assert DegreeType.BACHELOR == "bachelor"

    def test_graduate_degrees(self) -> None:
        """Test graduate degree types exist."""
        assert DegreeType.MASTER == "master"
        assert DegreeType.DOCTORATE == "doctorate"

    def test_professional_degree(self) -> None:
        """Test professional degree type exists."""
        assert DegreeType.PROFESSIONAL == "professional"

    def test_certification_types(self) -> None:
        """Test certification types exist."""
        assert DegreeType.CERTIFICATE == "certificate"
        assert DegreeType.DIPLOMA == "diploma"

    def test_unknown_type(self) -> None:
        """Test unknown degree type exists."""
        assert DegreeType.UNKNOWN == "unknown"
        assert DegreeType.NON_DEGREE == "non_degree"


class TestInstitutionType:
    """Tests for InstitutionType enum."""

    def test_university_types(self) -> None:
        """Test university types exist."""
        assert InstitutionType.UNIVERSITY == "university"
        assert InstitutionType.COLLEGE == "college"
        assert InstitutionType.COMMUNITY_COLLEGE == "community_college"

    def test_technical_types(self) -> None:
        """Test technical/trade school types exist."""
        assert InstitutionType.TECHNICAL_SCHOOL == "technical_school"
        assert InstitutionType.TRADE_SCHOOL == "trade_school"

    def test_graduate_types(self) -> None:
        """Test graduate school types exist."""
        assert InstitutionType.GRADUATE_SCHOOL == "graduate_school"
        assert InstitutionType.PROFESSIONAL_SCHOOL == "professional_school"

    def test_online_and_foreign(self) -> None:
        """Test online and foreign institution types."""
        assert InstitutionType.ONLINE_UNIVERSITY == "online_university"
        assert InstitutionType.FOREIGN_INSTITUTION == "foreign_institution"


class TestAccreditationType:
    """Tests for AccreditationType enum."""

    def test_regional_accreditors(self) -> None:
        """Test regional accreditor types exist."""
        assert AccreditationType.REGIONAL_HLC == "regional_hlc"
        assert AccreditationType.REGIONAL_MSCHE == "regional_msche"
        assert AccreditationType.REGIONAL_NECHE == "regional_neche"
        assert AccreditationType.REGIONAL_NWCCU == "regional_nwccu"
        assert AccreditationType.REGIONAL_SACSCOC == "regional_sacscoc"
        assert AccreditationType.REGIONAL_WASC == "regional_wasc"

    def test_other_accreditation_types(self) -> None:
        """Test other accreditation types."""
        assert AccreditationType.NATIONAL == "national"
        assert AccreditationType.PROGRAMMATIC == "programmatic"
        assert AccreditationType.INTERNATIONAL == "international"

    def test_status_types(self) -> None:
        """Test accreditation status types."""
        assert AccreditationType.UNACCREDITED == "unaccredited"
        assert AccreditationType.REVOKED == "revoked"
        assert AccreditationType.PENDING == "pending"
        assert AccreditationType.UNKNOWN == "unknown"


class TestVerificationStatus:
    """Tests for VerificationStatus enum."""

    def test_positive_statuses(self) -> None:
        """Test positive verification statuses."""
        assert VerificationStatus.VERIFIED == "verified"
        assert VerificationStatus.PARTIAL_MATCH == "partial_match"

    def test_negative_statuses(self) -> None:
        """Test negative verification statuses."""
        assert VerificationStatus.NOT_VERIFIED == "not_verified"
        assert VerificationStatus.DISCREPANCY == "discrepancy"
        assert VerificationStatus.NO_RECORD == "no_record"
        assert VerificationStatus.DIPLOMA_MILL == "diploma_mill"

    def test_pending_statuses(self) -> None:
        """Test pending verification statuses."""
        assert VerificationStatus.PENDING == "pending"
        assert VerificationStatus.UNABLE_TO_VERIFY == "unable_to_verify"


class TestMatchConfidence:
    """Tests for MatchConfidence enum."""

    def test_confidence_levels(self) -> None:
        """Test all confidence levels exist."""
        assert MatchConfidence.EXACT == "exact"
        assert MatchConfidence.HIGH == "high"
        assert MatchConfidence.MEDIUM == "medium"
        assert MatchConfidence.LOW == "low"
        assert MatchConfidence.NO_MATCH == "no_match"


class TestInstitution:
    """Tests for Institution model."""

    def test_institution_creation(self) -> None:
        """Test basic institution creation."""
        inst = Institution(
            institution_id="MIT001",
            name="Massachusetts Institute of Technology",
        )
        assert inst.institution_id == "MIT001"
        assert inst.name == "Massachusetts Institute of Technology"
        assert inst.type == InstitutionType.UNKNOWN
        assert inst.country == "US"
        assert inst.is_active is True
        assert inst.is_diploma_mill is False

    def test_institution_with_all_fields(self) -> None:
        """Test institution with all fields populated."""
        inst = Institution(
            institution_id="HARV001",
            name="Harvard University",
            aliases=["Harvard", "Harvard College"],
            type=InstitutionType.UNIVERSITY,
            city="Cambridge",
            state_province="MA",
            country="US",
            accreditation=AccreditationType.REGIONAL_NECHE,
            accreditor_name="New England Commission of Higher Education",
            ope_id="00215600",
            ipeds_id="166027",
            nsc_code="002155",
            is_active=True,
            is_diploma_mill=False,
            founded_year=1636,
            website="https://www.harvard.edu",
        )

        assert inst.institution_id == "HARV001"
        assert inst.name == "Harvard University"
        assert len(inst.aliases) == 2
        assert "Harvard" in inst.aliases
        assert inst.type == InstitutionType.UNIVERSITY
        assert inst.city == "Cambridge"
        assert inst.state_province == "MA"
        assert inst.accreditation == AccreditationType.REGIONAL_NECHE
        assert inst.founded_year == 1636
        assert inst.website == "https://www.harvard.edu"

    def test_institution_aliases_default_empty(self) -> None:
        """Test that aliases default to empty list."""
        inst = Institution(institution_id="TEST", name="Test University")
        assert inst.aliases == []

    def test_diploma_mill_flag(self) -> None:
        """Test diploma mill flag."""
        inst = Institution(
            institution_id="FAKE001",
            name="Fake University",
            is_diploma_mill=True,
        )
        assert inst.is_diploma_mill is True


class TestClaimedEducation:
    """Tests for ClaimedEducation model."""

    def test_minimal_claimed_education(self) -> None:
        """Test minimal claimed education."""
        claimed = ClaimedEducation(institution_name="MIT")
        assert claimed.institution_name == "MIT"
        assert claimed.degree_type == DegreeType.UNKNOWN
        assert claimed.degree_title is None
        assert claimed.major is None

    def test_full_claimed_education(self) -> None:
        """Test fully populated claimed education."""
        claimed = ClaimedEducation(
            institution_name="Stanford University",
            degree_type=DegreeType.BACHELOR,
            degree_title="Bachelor of Science",
            major="Computer Science",
            minor="Mathematics",
            graduation_date=date(2020, 6, 15),
            enrollment_start=date(2016, 9, 1),
            enrollment_end=date(2020, 6, 15),
            gpa=3.85,
            honors=["Magna Cum Laude", "Dean's List"],
        )

        assert claimed.institution_name == "Stanford University"
        assert claimed.degree_type == DegreeType.BACHELOR
        assert claimed.major == "Computer Science"
        assert claimed.minor == "Mathematics"
        assert claimed.gpa == 3.85
        assert len(claimed.honors) == 2

    def test_gpa_validation(self) -> None:
        """Test GPA validation bounds."""
        # Valid GPA
        claimed = ClaimedEducation(institution_name="Test", gpa=4.0)
        assert claimed.gpa == 4.0

        claimed = ClaimedEducation(institution_name="Test", gpa=0.0)
        assert claimed.gpa == 0.0

        # Invalid GPA - above 4.0
        with pytest.raises(ValueError):
            ClaimedEducation(institution_name="Test", gpa=4.5)

        # Invalid GPA - below 0.0
        with pytest.raises(ValueError):
            ClaimedEducation(institution_name="Test", gpa=-0.5)


class TestVerifiedEducation:
    """Tests for VerifiedEducation model."""

    def test_verified_education_creation(self) -> None:
        """Test verified education creation."""
        inst = Institution(institution_id="MIT001", name="MIT")
        verified = VerifiedEducation(
            institution=inst,
            degree_type=DegreeType.BACHELOR,
            degree_title="Bachelor of Science",
            major="Computer Science",
            graduation_date=date(2020, 5, 15),
            degree_conferred=True,
        )

        assert verified.institution.institution_id == "MIT001"
        assert verified.degree_type == DegreeType.BACHELOR
        assert verified.degree_conferred is True
        assert verified.verification_source == "NSC"

    def test_verified_education_defaults(self) -> None:
        """Test verified education default values."""
        inst = Institution(institution_id="TEST", name="Test")
        verified = VerifiedEducation(
            institution=inst,
            degree_type=DegreeType.BACHELOR,
        )

        assert verified.degree_conferred is False
        assert verified.verification_source == "NSC"
        assert isinstance(verified.verified_at, datetime)


class TestEducationDiscrepancy:
    """Tests for EducationDiscrepancy model."""

    def test_discrepancy_creation(self) -> None:
        """Test discrepancy creation."""
        discrepancy = EducationDiscrepancy(
            field="graduation_date",
            claimed_value="2020-05-15",
            verified_value="2020-12-15",
            severity="medium",
            explanation="Graduation date differs by 7 months",
        )

        assert discrepancy.field == "graduation_date"
        assert discrepancy.claimed_value == "2020-05-15"
        assert discrepancy.verified_value == "2020-12-15"
        assert discrepancy.severity == "medium"

    def test_discrepancy_default_severity(self) -> None:
        """Test default severity is medium."""
        discrepancy = EducationDiscrepancy(
            field="major",
            claimed_value="CS",
            verified_value="Computer Science",
            explanation="Minor difference",
        )
        assert discrepancy.severity == "medium"


class TestEducationVerificationResult:
    """Tests for EducationVerificationResult model."""

    def test_verification_result_creation(self) -> None:
        """Test verification result creation."""
        verification_id = uuid7()
        claimed = ClaimedEducation(institution_name="MIT")

        result = EducationVerificationResult(
            verification_id=verification_id,
            subject_name="John Smith",
            claimed=claimed,
        )

        assert result.verification_id == verification_id
        assert result.subject_name == "John Smith"
        assert result.status == VerificationStatus.PENDING
        assert result.institution_match == MatchConfidence.NO_MATCH

    def test_has_discrepancies(self) -> None:
        """Test has_discrepancies method."""
        claimed = ClaimedEducation(institution_name="MIT")
        result = EducationVerificationResult(
            verification_id=uuid7(),
            subject_name="John Smith",
            claimed=claimed,
        )

        assert result.has_discrepancies() is False

        result.discrepancies.append(
            EducationDiscrepancy(
                field="degree",
                claimed_value="BS",
                verified_value="BA",
                explanation="Degree type differs",
            )
        )
        assert result.has_discrepancies() is True

    def test_get_high_severity_discrepancies(self) -> None:
        """Test filtering high severity discrepancies."""
        claimed = ClaimedEducation(institution_name="MIT")
        result = EducationVerificationResult(
            verification_id=uuid7(),
            subject_name="John Smith",
            claimed=claimed,
            discrepancies=[
                EducationDiscrepancy(
                    field="degree",
                    claimed_value="PhD",
                    verified_value="None",
                    severity="high",
                    explanation="No degree conferred",
                ),
                EducationDiscrepancy(
                    field="major",
                    claimed_value="CS",
                    verified_value="Computer Science",
                    severity="low",
                    explanation="Abbreviation difference",
                ),
            ],
        )

        high_severity = result.get_high_severity_discrepancies()
        assert len(high_severity) == 1
        assert high_severity[0].field == "degree"

    def test_is_diploma_mill(self) -> None:
        """Test is_diploma_mill method."""
        claimed = ClaimedEducation(institution_name="Fake U")
        result = EducationVerificationResult(
            verification_id=uuid7(),
            subject_name="John Smith",
            claimed=claimed,
        )

        assert result.is_diploma_mill() is False

        # Test with flags
        result.diploma_mill_flags = ["Known diploma mill"]
        assert result.is_diploma_mill() is True

        # Test with status
        result.diploma_mill_flags = []
        result.status = VerificationStatus.DIPLOMA_MILL
        assert result.is_diploma_mill() is True


class TestInstitutionMatchResult:
    """Tests for InstitutionMatchResult model."""

    def test_match_result_creation(self) -> None:
        """Test match result creation."""
        inst = Institution(institution_id="MIT001", name="MIT")
        match = InstitutionMatchResult(
            institution=inst,
            confidence=MatchConfidence.HIGH,
            score=0.92,
            match_reasons=["Name similarity", "Alias match"],
        )

        assert match.institution.institution_id == "MIT001"
        assert match.confidence == MatchConfidence.HIGH
        assert match.score == 0.92
        assert len(match.match_reasons) == 2


class TestEducationProviderConfig:
    """Tests for EducationProviderConfig model."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = EducationProviderConfig()

        assert config.nsc_api_key is None
        assert config.nsc_api_url == "https://api.studentclearinghouse.org/v1"
        assert config.enable_diploma_mill_detection is True
        assert config.enable_international is True
        assert config.cache_ttl_seconds == 86400
        assert config.timeout_ms == 30000
        assert config.min_match_score == 0.70

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = EducationProviderConfig(
            nsc_api_key="test-key",
            enable_diploma_mill_detection=False,
            min_match_score=0.80,
        )

        assert config.nsc_api_key == "test-key"
        assert config.enable_diploma_mill_detection is False
        assert config.min_match_score == 0.80

    def test_min_match_score_validation(self) -> None:
        """Test min_match_score validation."""
        # Valid scores
        config = EducationProviderConfig(min_match_score=0.0)
        assert config.min_match_score == 0.0

        config = EducationProviderConfig(min_match_score=1.0)
        assert config.min_match_score == 1.0

        # Invalid scores
        with pytest.raises(ValueError):
            EducationProviderConfig(min_match_score=-0.1)

        with pytest.raises(ValueError):
            EducationProviderConfig(min_match_score=1.1)


class TestExceptions:
    """Tests for education provider exceptions."""

    def test_education_provider_error(self) -> None:
        """Test base exception."""
        error = EducationProviderError("Test error", {"key": "value"})
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.details == {"key": "value"}

    def test_institution_not_found_error(self) -> None:
        """Test institution not found exception."""
        error = InstitutionNotFoundError("Unknown University")
        assert "Unknown University" in str(error)
        assert error.institution_name == "Unknown University"
        assert error.details["institution_name"] == "Unknown University"

    def test_verification_failed_error(self) -> None:
        """Test verification failed exception."""
        verification_id = uuid7()
        error = VerificationFailedError(verification_id, "API timeout")
        assert str(verification_id) in str(error)
        assert "API timeout" in str(error)
        assert error.verification_id == verification_id
        assert error.reason == "API timeout"

    def test_diploma_mill_detected_error(self) -> None:
        """Test diploma mill detected exception."""
        flags = ["Known diploma mill", "Unaccredited"]
        error = DiplomaMilDetectedError("Fake University", flags)
        assert "Fake University" in str(error)
        assert error.institution_name == "Fake University"
        assert error.flags == flags
