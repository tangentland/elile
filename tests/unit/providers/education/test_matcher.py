"""Tests for education provider institution and degree matching."""

import pytest

from elile.providers.education.matcher import (
    DegreeTypeMatcher,
    InstitutionMatcher,
    create_institution_matcher,
)
from elile.providers.education.types import (
    Institution,
    InstitutionType,
    MatchConfidence,
)


class TestInstitutionMatcher:
    """Tests for InstitutionMatcher class."""

    @pytest.fixture
    def matcher(self) -> InstitutionMatcher:
        """Create a matcher instance."""
        return InstitutionMatcher()

    @pytest.fixture
    def sample_institutions(self) -> list[Institution]:
        """Create sample institutions for testing."""
        return [
            Institution(
                institution_id="MIT001",
                name="Massachusetts Institute of Technology",
                aliases=["MIT", "Mass Tech"],
                type=InstitutionType.UNIVERSITY,
            ),
            Institution(
                institution_id="HARV001",
                name="Harvard University",
                aliases=["Harvard", "Harvard College"],
                type=InstitutionType.UNIVERSITY,
            ),
            Institution(
                institution_id="UCLA001",
                name="University of California, Los Angeles",
                aliases=["UCLA", "UC Los Angeles"],
                type=InstitutionType.UNIVERSITY,
            ),
            Institution(
                institution_id="OSU001",
                name="Ohio State University",
                aliases=["OSU", "The Ohio State University"],
                type=InstitutionType.UNIVERSITY,
            ),
            Institution(
                institution_id="COMM001",
                name="Santa Monica Community College",
                aliases=["SMC", "Santa Monica College"],
                type=InstitutionType.COMMUNITY_COLLEGE,
            ),
        ]

    def test_normalize_name_lowercase(self, matcher: InstitutionMatcher) -> None:
        """Test name normalization converts to lowercase."""
        result = matcher.normalize_name("HARVARD UNIVERSITY")
        assert result == "harvard university"

    def test_normalize_name_removes_punctuation(self, matcher: InstitutionMatcher) -> None:
        """Test name normalization removes punctuation."""
        result = matcher.normalize_name("U.C.L.A.")
        assert "." not in result

    def test_normalize_name_removes_suffix(self, matcher: InstitutionMatcher) -> None:
        """Test name normalization removes common suffixes."""
        result = matcher.normalize_name("Some University Inc.")
        assert "inc" not in result.lower()

    def test_normalize_name_whitespace(self, matcher: InstitutionMatcher) -> None:
        """Test name normalization handles whitespace."""
        result = matcher.normalize_name("  Harvard    University  ")
        assert result == "harvard university"

    def test_expand_abbreviations_single(self, matcher: InstitutionMatcher) -> None:
        """Test abbreviation expansion with single abbreviation."""
        variants = matcher.expand_abbreviations("MIT")
        assert "MIT" in variants

    def test_expand_abbreviations_multiple(self, matcher: InstitutionMatcher) -> None:
        """Test abbreviation expansion with multiple abbreviations."""
        variants = matcher.expand_abbreviations("U of Michigan")
        assert "U of Michigan" in variants
        # Should expand "U" to "University"
        assert any("University" in v for v in variants)

    def test_calculate_score_exact_match(self, matcher: InstitutionMatcher) -> None:
        """Test score calculation for exact match."""
        score, reasons = matcher.calculate_score("Harvard University", "Harvard University")
        assert score == 1.0
        assert len(reasons) > 0

    def test_calculate_score_normalized_exact(self, matcher: InstitutionMatcher) -> None:
        """Test score calculation for normalized exact match."""
        score, reasons = matcher.calculate_score("HARVARD UNIVERSITY", "Harvard University")
        assert score == 1.0

    def test_calculate_score_partial_match(self, matcher: InstitutionMatcher) -> None:
        """Test score calculation for partial match."""
        score, _ = matcher.calculate_score("Harvard", "Harvard University")
        assert 0.5 < score < 1.0

    def test_calculate_score_no_match(self, matcher: InstitutionMatcher) -> None:
        """Test score calculation for no match."""
        score, _ = matcher.calculate_score("xyz abc 123", "Harvard University")
        assert score < 0.5

    def test_score_to_confidence_exact(self, matcher: InstitutionMatcher) -> None:
        """Test score to confidence conversion for exact match."""
        confidence = matcher.score_to_confidence(0.99)
        assert confidence == MatchConfidence.EXACT

    def test_score_to_confidence_high(self, matcher: InstitutionMatcher) -> None:
        """Test score to confidence conversion for high confidence."""
        confidence = matcher.score_to_confidence(0.90)
        assert confidence == MatchConfidence.HIGH

    def test_score_to_confidence_medium(self, matcher: InstitutionMatcher) -> None:
        """Test score to confidence conversion for medium confidence."""
        confidence = matcher.score_to_confidence(0.75)
        assert confidence == MatchConfidence.MEDIUM

    def test_score_to_confidence_low(self, matcher: InstitutionMatcher) -> None:
        """Test score to confidence conversion for low confidence."""
        confidence = matcher.score_to_confidence(0.60)
        assert confidence == MatchConfidence.LOW

    def test_score_to_confidence_no_match(self, matcher: InstitutionMatcher) -> None:
        """Test score to confidence conversion for no match."""
        confidence = matcher.score_to_confidence(0.40)
        assert confidence == MatchConfidence.NO_MATCH

    def test_find_matches_by_name(
        self,
        matcher: InstitutionMatcher,
        sample_institutions: list[Institution],
    ) -> None:
        """Test finding matches by institution name."""
        matches = matcher.find_matches("Harvard University", sample_institutions)
        assert len(matches) > 0
        assert matches[0].institution.institution_id == "HARV001"
        assert matches[0].confidence in (MatchConfidence.EXACT, MatchConfidence.HIGH)

    def test_find_matches_by_alias(
        self,
        matcher: InstitutionMatcher,
        sample_institutions: list[Institution],
    ) -> None:
        """Test finding matches by alias."""
        matches = matcher.find_matches("MIT", sample_institutions)
        assert len(matches) > 0
        assert matches[0].institution.institution_id == "MIT001"

    def test_find_matches_partial_name(
        self,
        matcher: InstitutionMatcher,
        sample_institutions: list[Institution],
    ) -> None:
        """Test finding matches by partial name."""
        matches = matcher.find_matches("Ohio State", sample_institutions)
        assert len(matches) > 0
        assert matches[0].institution.institution_id == "OSU001"

    def test_find_matches_fuzzy(
        self,
        matcher: InstitutionMatcher,
        sample_institutions: list[Institution],
    ) -> None:
        """Test fuzzy matching with typos."""
        matches = matcher.find_matches("Harverd University", sample_institutions)
        # Should still match Harvard with high confidence
        assert len(matches) > 0
        assert matches[0].institution.institution_id == "HARV001"

    def test_find_matches_max_results(
        self,
        matcher: InstitutionMatcher,
        sample_institutions: list[Institution],
    ) -> None:
        """Test max_results parameter."""
        matches = matcher.find_matches("University", sample_institutions, max_results=2)
        assert len(matches) <= 2

    def test_find_matches_sorted_by_score(
        self,
        matcher: InstitutionMatcher,
        sample_institutions: list[Institution],
    ) -> None:
        """Test that matches are sorted by score descending."""
        matches = matcher.find_matches("University", sample_institutions)
        scores = [m.score for m in matches]
        assert scores == sorted(scores, reverse=True)

    def test_find_matches_no_match(
        self,
        matcher: InstitutionMatcher,
        sample_institutions: list[Institution],
    ) -> None:
        """Test finding matches with no match."""
        matches = matcher.find_matches("Nonexistent University XYZ", sample_institutions)
        # May return no matches or very low confidence matches
        assert all(m.confidence != MatchConfidence.EXACT for m in matches)

    def test_match_single_found(
        self,
        matcher: InstitutionMatcher,
        sample_institutions: list[Institution],
    ) -> None:
        """Test match_single when match is found."""
        result = matcher.match_single("UCLA", sample_institutions)
        assert result is not None
        assert result.institution.institution_id == "UCLA001"

    def test_match_single_not_found(
        self,
        matcher: InstitutionMatcher,
        sample_institutions: list[Institution],
    ) -> None:
        """Test match_single when no match is found."""
        result = matcher.match_single("Completely Fake University XYZ", sample_institutions)
        # May be None or very low confidence
        if result is not None:
            assert result.confidence in (MatchConfidence.LOW, MatchConfidence.NO_MATCH)


class TestInstitutionMatcherCustomThresholds:
    """Tests for InstitutionMatcher with custom thresholds."""

    def test_custom_thresholds(self) -> None:
        """Test matcher with custom thresholds."""
        matcher = InstitutionMatcher(
            exact_threshold=0.95,
            high_threshold=0.80,
            medium_threshold=0.60,
            low_threshold=0.40,
        )

        assert matcher.exact_threshold == 0.95
        assert matcher.high_threshold == 0.80
        assert matcher.medium_threshold == 0.60
        assert matcher.low_threshold == 0.40

    def test_custom_thresholds_affect_confidence(self) -> None:
        """Test that custom thresholds affect confidence classification."""
        strict_matcher = InstitutionMatcher(
            exact_threshold=0.999,
            high_threshold=0.95,
            medium_threshold=0.90,
            low_threshold=0.85,
        )

        lenient_matcher = InstitutionMatcher(
            exact_threshold=0.90,
            high_threshold=0.70,
            medium_threshold=0.50,
            low_threshold=0.30,
        )

        # Same score, different confidence
        strict_confidence = strict_matcher.score_to_confidence(0.85)
        lenient_confidence = lenient_matcher.score_to_confidence(0.85)

        assert strict_confidence == MatchConfidence.LOW
        assert lenient_confidence == MatchConfidence.HIGH


class TestDegreeTypeMatcher:
    """Tests for DegreeTypeMatcher class."""

    def test_infer_bachelor_bs(self) -> None:
        """Test inferring bachelor's degree from B.S."""
        result = DegreeTypeMatcher.infer_degree_type("B.S.")
        assert result == "bachelor"

    def test_infer_bachelor_ba(self) -> None:
        """Test inferring bachelor's degree from B.A."""
        result = DegreeTypeMatcher.infer_degree_type("B.A.")
        assert result == "bachelor"

    def test_infer_bachelor_full(self) -> None:
        """Test inferring bachelor's degree from full name."""
        result = DegreeTypeMatcher.infer_degree_type("Bachelor of Science")
        assert result == "bachelor"

    def test_infer_master_ms(self) -> None:
        """Test inferring master's degree from M.S."""
        result = DegreeTypeMatcher.infer_degree_type("M.S.")
        assert result == "master"

    def test_infer_master_mba(self) -> None:
        """Test inferring master's degree from MBA."""
        result = DegreeTypeMatcher.infer_degree_type("MBA")
        assert result == "master"

    def test_infer_master_full(self) -> None:
        """Test inferring master's degree from full name."""
        result = DegreeTypeMatcher.infer_degree_type("Master of Business Administration")
        assert result == "master"

    def test_infer_doctorate_phd(self) -> None:
        """Test inferring doctorate from Ph.D."""
        result = DegreeTypeMatcher.infer_degree_type("Ph.D.")
        assert result == "doctorate"

    def test_infer_doctorate_edd(self) -> None:
        """Test inferring doctorate from Ed.D."""
        result = DegreeTypeMatcher.infer_degree_type("Ed.D.")
        assert result == "doctorate"

    def test_infer_doctorate_full(self) -> None:
        """Test inferring doctorate from full name."""
        result = DegreeTypeMatcher.infer_degree_type("Doctor of Philosophy")
        assert result == "doctorate"

    def test_infer_professional_md(self) -> None:
        """Test inferring professional degree from M.D."""
        result = DegreeTypeMatcher.infer_degree_type("M.D.")
        assert result == "professional"

    def test_infer_professional_jd(self) -> None:
        """Test inferring professional degree from J.D."""
        result = DegreeTypeMatcher.infer_degree_type("J.D.")
        assert result == "professional"

    def test_infer_associate_as(self) -> None:
        """Test inferring associate degree from A.S."""
        result = DegreeTypeMatcher.infer_degree_type("A.S.")
        assert result == "associate"

    def test_infer_associate_full(self) -> None:
        """Test inferring associate degree from full name."""
        result = DegreeTypeMatcher.infer_degree_type("Associate of Arts")
        assert result == "associate"

    def test_infer_certificate(self) -> None:
        """Test inferring certificate."""
        result = DegreeTypeMatcher.infer_degree_type("Certificate in Project Management")
        assert result == "certificate"

    def test_infer_diploma(self) -> None:
        """Test inferring diploma."""
        result = DegreeTypeMatcher.infer_degree_type("Diploma in Nursing")
        assert result == "diploma"

    def test_infer_unknown(self) -> None:
        """Test returning unknown for unrecognized degree."""
        result = DegreeTypeMatcher.infer_degree_type("Some Random Credential")
        assert result == "unknown"

    def test_case_insensitive(self) -> None:
        """Test that matching is case insensitive."""
        result = DegreeTypeMatcher.infer_degree_type("BACHELOR OF SCIENCE")
        assert result == "bachelor"


class TestCreateInstitutionMatcher:
    """Tests for create_institution_matcher factory function."""

    def test_create_default_matcher(self) -> None:
        """Test creating matcher with defaults."""
        matcher = create_institution_matcher()
        assert isinstance(matcher, InstitutionMatcher)
        assert matcher.exact_threshold == 0.99
        assert matcher.high_threshold == 0.85

    def test_create_custom_matcher(self) -> None:
        """Test creating matcher with custom thresholds."""
        matcher = create_institution_matcher(
            exact_threshold=0.95,
            high_threshold=0.80,
            medium_threshold=0.65,
            low_threshold=0.50,
        )

        assert matcher.exact_threshold == 0.95
        assert matcher.high_threshold == 0.80
        assert matcher.medium_threshold == 0.65
        assert matcher.low_threshold == 0.50


class TestAbbreviationExpansion:
    """Tests for abbreviation expansion in institution matching."""

    @pytest.fixture
    def matcher(self) -> InstitutionMatcher:
        """Create a matcher instance."""
        return InstitutionMatcher()

    def test_expand_univ_to_university(self, matcher: InstitutionMatcher) -> None:
        """Test expanding 'Univ' to 'University'."""
        variants = matcher.expand_abbreviations("Univ of Michigan")
        assert any("University" in v for v in variants)

    def test_expand_tech_to_technology(self, matcher: InstitutionMatcher) -> None:
        """Test expanding 'Tech' to 'Technology'."""
        variants = matcher.expand_abbreviations("Georgia Tech")
        assert any("Technology" in v or "Technical" in v for v in variants)

    def test_expand_st_to_state_or_saint(self, matcher: InstitutionMatcher) -> None:
        """Test expanding 'St' to 'State' or 'Saint'."""
        variants = matcher.expand_abbreviations("St Louis Univ")
        # Should have variants with both State and Saint
        assert any("State" in v or "Saint" in v for v in variants)

    def test_expand_cc_to_community_college(self, matcher: InstitutionMatcher) -> None:
        """Test expanding 'CC' to 'Community College'."""
        variants = matcher.expand_abbreviations("Santa Monica CC")
        assert any("Community College" in v for v in variants)

    def test_expand_ampersand_to_and(self, matcher: InstitutionMatcher) -> None:
        """Test expanding '&' to 'and'."""
        variants = matcher.expand_abbreviations("Arts & Sciences")
        assert any("and" in v for v in variants)
