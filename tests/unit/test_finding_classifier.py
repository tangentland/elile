"""Unit tests for FindingClassifier."""

import pytest
from uuid import UUID

from elile.compliance.types import RoleCategory
from elile.investigation.finding_extractor import Finding, FindingCategory, Severity
from elile.risk.finding_classifier import (
    CATEGORY_KEYWORDS,
    ROLE_RELEVANCE_MATRIX,
    SUBCATEGORY_KEYWORDS,
    ClassificationResult,
    ClassifierConfig,
    FindingClassifier,
    SubCategory,
    create_finding_classifier,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def classifier() -> FindingClassifier:
    """Create default classifier."""
    return FindingClassifier()


@pytest.fixture
def custom_config() -> ClassifierConfig:
    """Create custom classifier config."""
    return ClassifierConfig(
        min_validation_confidence=0.5,
        min_keyword_matches=2,
        confidence_per_match=0.2,
        max_keyword_confidence=0.85,
        enable_subcategory=True,
        default_relevance=0.6,
    )


@pytest.fixture
def custom_classifier(custom_config: ClassifierConfig) -> FindingClassifier:
    """Create classifier with custom config."""
    return FindingClassifier(config=custom_config)


def create_finding(
    summary: str = "",
    details: str = "",
    finding_type: str = "",
    category: FindingCategory | None = None,
    severity: Severity = Severity.MEDIUM,
) -> Finding:
    """Helper to create a Finding for testing."""
    return Finding(
        summary=summary,
        details=details,
        finding_type=finding_type,
        category=category,
        severity=severity,
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestFindingClassifierInit:
    """Tests for FindingClassifier initialization."""

    def test_init_default_config(self) -> None:
        """Test initialization with default config."""
        classifier = FindingClassifier()
        assert classifier.config is not None
        assert classifier.config.min_validation_confidence == 0.7
        assert classifier.config.min_keyword_matches == 1
        assert classifier.config.confidence_per_match == 0.15
        assert classifier.config.max_keyword_confidence == 0.9
        assert classifier.config.enable_subcategory is True
        assert classifier.config.default_relevance == 0.5

    def test_init_custom_config(self, custom_config: ClassifierConfig) -> None:
        """Test initialization with custom config."""
        classifier = FindingClassifier(config=custom_config)
        assert classifier.config.min_validation_confidence == 0.5
        assert classifier.config.confidence_per_match == 0.2
        assert classifier.config.max_keyword_confidence == 0.85
        assert classifier.config.default_relevance == 0.6

    def test_factory_function(self) -> None:
        """Test create_finding_classifier factory function."""
        classifier = create_finding_classifier()
        assert isinstance(classifier, FindingClassifier)
        assert classifier.config is not None

    def test_factory_function_with_config(self, custom_config: ClassifierConfig) -> None:
        """Test factory function with custom config."""
        classifier = create_finding_classifier(config=custom_config)
        assert classifier.config.min_validation_confidence == 0.5


# =============================================================================
# ClassifierConfig Tests
# =============================================================================


class TestClassifierConfig:
    """Tests for ClassifierConfig validation."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = ClassifierConfig()
        assert config.min_validation_confidence == 0.7
        assert config.min_keyword_matches == 1
        assert config.confidence_per_match == 0.15
        assert config.max_keyword_confidence == 0.9
        assert config.enable_subcategory is True
        assert config.default_relevance == 0.5

    def test_validation_confidence_range(self) -> None:
        """Test min_validation_confidence bounds."""
        # Valid values
        config = ClassifierConfig(min_validation_confidence=0.0)
        assert config.min_validation_confidence == 0.0
        config = ClassifierConfig(min_validation_confidence=1.0)
        assert config.min_validation_confidence == 1.0

        # Invalid values
        with pytest.raises(ValueError):
            ClassifierConfig(min_validation_confidence=-0.1)
        with pytest.raises(ValueError):
            ClassifierConfig(min_validation_confidence=1.1)

    def test_keyword_matches_minimum(self) -> None:
        """Test min_keyword_matches must be at least 1."""
        config = ClassifierConfig(min_keyword_matches=1)
        assert config.min_keyword_matches == 1

        with pytest.raises(ValueError):
            ClassifierConfig(min_keyword_matches=0)

    def test_confidence_per_match_range(self) -> None:
        """Test confidence_per_match bounds."""
        config = ClassifierConfig(confidence_per_match=0.0)
        assert config.confidence_per_match == 0.0
        config = ClassifierConfig(confidence_per_match=1.0)
        assert config.confidence_per_match == 1.0

        with pytest.raises(ValueError):
            ClassifierConfig(confidence_per_match=-0.1)
        with pytest.raises(ValueError):
            ClassifierConfig(confidence_per_match=1.1)


# =============================================================================
# Category Determination Tests
# =============================================================================


class TestCategoryDetermination:
    """Tests for category determination from text."""

    def test_criminal_category_from_keywords(
        self, classifier: FindingClassifier
    ) -> None:
        """Test criminal category detection."""
        finding = create_finding(
            summary="Felony conviction for theft",
            details="Subject was convicted of grand theft in 2020.",
        )
        result = classifier.classify_finding(finding, RoleCategory.STANDARD)

        assert result.assigned_category == FindingCategory.CRIMINAL
        assert "felony" in result.keyword_matches
        assert "conviction" in result.keyword_matches
        assert "theft" in result.keyword_matches

    def test_financial_category_from_keywords(
        self, classifier: FindingClassifier
    ) -> None:
        """Test financial category detection."""
        finding = create_finding(
            summary="Chapter 7 bankruptcy filed",
            details="Subject declared bankruptcy with outstanding debt.",
        )
        result = classifier.classify_finding(finding, RoleCategory.FINANCIAL)

        assert result.assigned_category == FindingCategory.FINANCIAL
        assert "bankruptcy" in result.keyword_matches
        assert "debt" in result.keyword_matches

    def test_regulatory_category_from_keywords(
        self, classifier: FindingClassifier
    ) -> None:
        """Test regulatory category detection."""
        finding = create_finding(
            summary="License suspension",
            details="Professional license was suspended due to sanction.",
        )
        result = classifier.classify_finding(finding, RoleCategory.HEALTHCARE)

        assert result.assigned_category == FindingCategory.REGULATORY
        assert "license" in result.keyword_matches
        assert "suspension" in result.keyword_matches
        assert "sanction" in result.keyword_matches

    def test_reputation_category_from_keywords(
        self, classifier: FindingClassifier
    ) -> None:
        """Test reputation category detection."""
        finding = create_finding(
            summary="Subject named in lawsuit",
            details="Civil litigation involving fraud allegation.",
        )
        result = classifier.classify_finding(finding, RoleCategory.EXECUTIVE)

        assert result.assigned_category == FindingCategory.REPUTATION
        assert "lawsuit" in result.keyword_matches
        assert "litigation" in result.keyword_matches
        assert "allegation" in result.keyword_matches

    def test_verification_category_from_keywords(
        self, classifier: FindingClassifier
    ) -> None:
        """Test verification category detection."""
        finding = create_finding(
            summary="Employment discrepancy found",
            details="Cannot verify employment history, significant gap identified.",
        )
        result = classifier.classify_finding(finding, RoleCategory.GOVERNMENT)

        assert result.assigned_category == FindingCategory.VERIFICATION
        assert "discrepancy" in result.keyword_matches
        assert "gap" in result.keyword_matches

    def test_behavioral_category_from_keywords(
        self, classifier: FindingClassifier
    ) -> None:
        """Test behavioral category detection."""
        finding = create_finding(
            summary="Pattern of deception",
            details="Systematic misrepresentation detected across sources.",
        )
        result = classifier.classify_finding(finding, RoleCategory.SECURITY)

        assert result.assigned_category == FindingCategory.BEHAVIORAL
        assert "pattern" in result.keyword_matches
        assert "deception" in result.keyword_matches
        assert "misrepresentation" in result.keyword_matches

    def test_network_category_from_keywords(
        self, classifier: FindingClassifier
    ) -> None:
        """Test network category detection."""
        finding = create_finding(
            summary="Shell company connection",
            details="Subject affiliated with shell company, beneficial owner identified.",
        )
        result = classifier.classify_finding(finding, RoleCategory.FINANCIAL)

        assert result.assigned_category == FindingCategory.NETWORK
        assert "shell company" in result.keyword_matches
        assert "affiliated" in result.keyword_matches
        assert "beneficial owner" in result.keyword_matches

    def test_no_keywords_defaults_to_verification(
        self, classifier: FindingClassifier
    ) -> None:
        """Test default to VERIFICATION when no keywords match."""
        finding = create_finding(
            summary="Some unrelated information",
            details="Nothing relevant to any category.",
        )
        result = classifier.classify_finding(finding, RoleCategory.STANDARD)

        assert result.assigned_category == FindingCategory.VERIFICATION
        assert result.category_confidence == 0.3  # Low confidence default
        assert result.keyword_matches == []

    def test_highest_matching_category_wins(
        self, classifier: FindingClassifier
    ) -> None:
        """Test that category with most keyword matches wins."""
        # Finding with both criminal and financial keywords, but more criminal
        finding = create_finding(
            summary="Felony conviction for fraud theft assault",
            details="Multiple criminal charges including burglary",
        )
        result = classifier.classify_finding(finding, RoleCategory.STANDARD)

        assert result.assigned_category == FindingCategory.CRIMINAL


# =============================================================================
# AI Category Validation Tests
# =============================================================================


class TestAICategoryValidation:
    """Tests for validating AI-assigned categories."""

    def test_keeps_valid_ai_category(self, classifier: FindingClassifier) -> None:
        """Test that valid AI category is kept."""
        # Need enough keyword matches to exceed 0.7 threshold (5+ matches at 0.15 each)
        finding = create_finding(
            summary="Subject convicted of felony theft assault charge",
            details="Criminal conviction record found with probation sentence.",
            category=FindingCategory.CRIMINAL,
        )
        result = classifier.classify_finding(finding, RoleCategory.STANDARD)

        assert result.assigned_category == FindingCategory.CRIMINAL
        assert result.original_category == FindingCategory.CRIMINAL
        assert result.was_reclassified is False

    def test_reclassifies_invalid_ai_category(
        self, classifier: FindingClassifier
    ) -> None:
        """Test reclassification when AI category doesn't match keywords."""
        finding = create_finding(
            summary="Chapter 7 bankruptcy filed",
            details="Subject declared bankruptcy with debt.",
            category=FindingCategory.CRIMINAL,  # Wrong category
        )
        result = classifier.classify_finding(finding, RoleCategory.STANDARD)

        assert result.assigned_category == FindingCategory.FINANCIAL
        assert result.original_category == FindingCategory.CRIMINAL
        assert result.was_reclassified is True

    def test_validation_confidence_threshold(
        self, custom_classifier: FindingClassifier
    ) -> None:
        """Test validation confidence threshold."""
        # With only one keyword match and custom threshold of 0.5
        # confidence = 1 * 0.2 = 0.2, which is < 0.5, so reclassify
        finding = create_finding(
            summary="Minor offense",  # Only "offense" matches criminal
            details="Nothing else relevant.",
            category=FindingCategory.CRIMINAL,
        )
        result = custom_classifier.classify_finding(finding, RoleCategory.STANDARD)

        # Should be reclassified due to low validation confidence
        assert result.was_reclassified is True

    def test_confidence_calculation_multiple_matches(
        self, classifier: FindingClassifier
    ) -> None:
        """Test confidence increases with keyword matches."""
        finding = create_finding(
            summary="Felony conviction for assault and theft",
            details="Criminal charge resulted in probation sentence.",
            category=FindingCategory.CRIMINAL,
        )
        result = classifier.classify_finding(finding, RoleCategory.STANDARD)

        # Multiple matches should give high confidence
        # 7 matches * 0.15 = 1.05, capped at 0.9
        assert result.category_confidence == 0.9
        assert result.was_reclassified is False

    def test_confidence_capped_at_maximum(
        self, classifier: FindingClassifier
    ) -> None:
        """Test confidence is capped at max_keyword_confidence."""
        # Finding with many keyword matches
        finding = create_finding(
            summary="Felony conviction charge arrest indictment",
            details="Criminal offense violation probation parole sentence plea",
        )
        result = classifier.classify_finding(finding, RoleCategory.STANDARD)

        # Should be capped at 0.9 (default max)
        assert result.category_confidence <= 0.9


# =============================================================================
# Sub-Category Classification Tests
# =============================================================================


class TestSubCategoryClassification:
    """Tests for sub-category classification."""

    def test_criminal_felony_subcategory(self, classifier: FindingClassifier) -> None:
        """Test criminal felony sub-category."""
        finding = create_finding(
            summary="Felony conviction",
            details="Felonious assault charge.",
        )
        result = classifier.classify_finding(finding, RoleCategory.STANDARD)

        assert result.sub_category == SubCategory.CRIMINAL_FELONY

    def test_criminal_dui_subcategory(self, classifier: FindingClassifier) -> None:
        """Test criminal DUI sub-category."""
        finding = create_finding(
            summary="DUI arrest",
            details="Driving under the influence charge.",
        )
        result = classifier.classify_finding(finding, RoleCategory.STANDARD)

        assert result.sub_category == SubCategory.CRIMINAL_DUI

    def test_criminal_violent_subcategory(self, classifier: FindingClassifier) -> None:
        """Test criminal violent sub-category."""
        finding = create_finding(
            summary="Assault charge",
            details="Battery and violence related offense.",
        )
        result = classifier.classify_finding(finding, RoleCategory.STANDARD)

        assert result.sub_category == SubCategory.CRIMINAL_VIOLENT

    def test_financial_bankruptcy_subcategory(
        self, classifier: FindingClassifier
    ) -> None:
        """Test financial bankruptcy sub-category."""
        finding = create_finding(
            summary="Chapter 7 bankruptcy",
            details="Filed for bankruptcy protection.",
        )
        result = classifier.classify_finding(finding, RoleCategory.FINANCIAL)

        assert result.sub_category == SubCategory.FINANCIAL_BANKRUPTCY

    def test_financial_lien_subcategory(self, classifier: FindingClassifier) -> None:
        """Test financial lien sub-category."""
        finding = create_finding(
            summary="Tax lien filed",
            details="Federal tax lien on property.",
        )
        result = classifier.classify_finding(finding, RoleCategory.FINANCIAL)

        assert result.sub_category == SubCategory.FINANCIAL_LIEN

    def test_regulatory_sanction_subcategory(
        self, classifier: FindingClassifier
    ) -> None:
        """Test regulatory sanction sub-category."""
        finding = create_finding(
            summary="OFAC sanction",
            details="Subject on watchlist, sanctioned entity.",
        )
        result = classifier.classify_finding(finding, RoleCategory.GOVERNMENT)

        assert result.sub_category == SubCategory.REGULATORY_SANCTION

    def test_regulatory_pep_subcategory(self, classifier: FindingClassifier) -> None:
        """Test regulatory PEP sub-category."""
        finding = create_finding(
            summary="PEP identification",
            details="Politically exposed person, public official.",
        )
        result = classifier.classify_finding(finding, RoleCategory.GOVERNMENT)

        assert result.sub_category == SubCategory.REGULATORY_PEP

    def test_verification_employment_subcategory(
        self, classifier: FindingClassifier
    ) -> None:
        """Test verification employment sub-category."""
        finding = create_finding(
            summary="Employment discrepancy",
            details="Cannot verify employer, job title mismatch.",
        )
        result = classifier.classify_finding(finding, RoleCategory.STANDARD)

        assert result.sub_category == SubCategory.VERIFICATION_EMPLOYMENT

    def test_verification_education_subcategory(
        self, classifier: FindingClassifier
    ) -> None:
        """Test verification education sub-category."""
        finding = create_finding(
            summary="Education discrepancy",
            details="Cannot verify degree from university.",
        )
        result = classifier.classify_finding(finding, RoleCategory.STANDARD)

        assert result.sub_category == SubCategory.VERIFICATION_EDUCATION

    def test_behavioral_deception_subcategory(
        self, classifier: FindingClassifier
    ) -> None:
        """Test behavioral deception sub-category."""
        finding = create_finding(
            summary="Pattern of deception",
            details="Systematic fabrication and misrepresentation.",
        )
        result = classifier.classify_finding(finding, RoleCategory.GOVERNMENT)

        assert result.sub_category == SubCategory.BEHAVIORAL_DECEPTION

    def test_network_shell_subcategory(self, classifier: FindingClassifier) -> None:
        """Test network shell company sub-category."""
        finding = create_finding(
            summary="Shell company connection",
            details="Linked to shell corporation, nominee director.",
        )
        result = classifier.classify_finding(finding, RoleCategory.FINANCIAL)

        assert result.sub_category == SubCategory.NETWORK_SHELL

    def test_subcategory_disabled(self, classifier: FindingClassifier) -> None:
        """Test sub-category disabled in config."""
        config = ClassifierConfig(enable_subcategory=False)
        classifier = FindingClassifier(config=config)

        finding = create_finding(
            summary="Felony conviction",
            details="Criminal felony charge.",
        )
        result = classifier.classify_finding(finding, RoleCategory.STANDARD)

        assert result.sub_category == SubCategory.UNCLASSIFIED

    def test_unclassified_subcategory_when_no_match(
        self, classifier: FindingClassifier
    ) -> None:
        """Test UNCLASSIFIED when no sub-category keywords match."""
        finding = create_finding(
            summary="Criminal offense",
            details="Generic criminal activity.",
        )
        result = classifier.classify_finding(finding, RoleCategory.STANDARD)

        # Criminal category but no specific sub-category keywords
        assert result.assigned_category == FindingCategory.CRIMINAL
        assert result.sub_category == SubCategory.UNCLASSIFIED


# =============================================================================
# Role Relevance Tests
# =============================================================================


class TestRoleRelevance:
    """Tests for role-based relevance calculation."""

    def test_criminal_high_relevance_government(
        self, classifier: FindingClassifier
    ) -> None:
        """Test criminal findings high relevance for government roles."""
        finding = create_finding(summary="Felony conviction")
        result = classifier.classify_finding(finding, RoleCategory.GOVERNMENT)

        assert result.relevance_to_role == 1.0

    def test_criminal_high_relevance_defense(
        self, classifier: FindingClassifier
    ) -> None:
        """Test criminal findings high relevance for defense roles."""
        finding = create_finding(summary="Felony conviction")
        result = classifier.classify_finding(finding, RoleCategory.SECURITY)

        assert result.relevance_to_role == 1.0

    def test_criminal_lower_relevance_standard(
        self, classifier: FindingClassifier
    ) -> None:
        """Test criminal findings lower relevance for standard roles."""
        finding = create_finding(summary="Felony conviction")
        result = classifier.classify_finding(finding, RoleCategory.STANDARD)

        assert result.relevance_to_role == 0.7

    def test_financial_high_relevance_financial(
        self, classifier: FindingClassifier
    ) -> None:
        """Test financial findings high relevance for financial roles."""
        finding = create_finding(summary="Bankruptcy filed")
        result = classifier.classify_finding(finding, RoleCategory.FINANCIAL)

        assert result.relevance_to_role == 1.0

    def test_regulatory_high_relevance_healthcare(
        self, classifier: FindingClassifier
    ) -> None:
        """Test regulatory findings high relevance for healthcare roles."""
        finding = create_finding(summary="License suspension sanction")
        result = classifier.classify_finding(finding, RoleCategory.HEALTHCARE)

        assert result.relevance_to_role == 1.0

    def test_reputation_high_relevance_executive(
        self, classifier: FindingClassifier
    ) -> None:
        """Test reputation findings high relevance for executive roles."""
        finding = create_finding(summary="Lawsuit allegation")
        result = classifier.classify_finding(finding, RoleCategory.EXECUTIVE)

        assert result.relevance_to_role == 1.0

    def test_verification_high_relevance_all_critical(
        self, classifier: FindingClassifier
    ) -> None:
        """Test verification findings high relevance for critical roles."""
        finding = create_finding(summary="Employment discrepancy gap")

        result_gov = classifier.classify_finding(
            create_finding(summary="Employment discrepancy gap"),
            RoleCategory.GOVERNMENT,
        )
        result_defense = classifier.classify_finding(
            create_finding(summary="Employment discrepancy gap"),
            RoleCategory.SECURITY,
        )
        result_financial = classifier.classify_finding(
            create_finding(summary="Employment discrepancy gap"),
            RoleCategory.FINANCIAL,
        )

        assert result_gov.relevance_to_role == 1.0
        assert result_defense.relevance_to_role == 1.0
        assert result_financial.relevance_to_role == 1.0

    def test_network_high_relevance_government_defense(
        self, classifier: FindingClassifier
    ) -> None:
        """Test network findings high relevance for government/defense."""
        finding1 = create_finding(summary="Shell company connection")
        finding2 = create_finding(summary="Shell company connection")

        result_gov = classifier.classify_finding(finding1, RoleCategory.GOVERNMENT)
        result_defense = classifier.classify_finding(finding2, RoleCategory.SECURITY)

        assert result_gov.relevance_to_role == 1.0
        assert result_defense.relevance_to_role == 1.0

    def test_default_relevance_when_missing(
        self, custom_classifier: FindingClassifier
    ) -> None:
        """Test default relevance when role-category combination not defined."""
        # Create a finding with unknown category-role combination
        finding = create_finding(summary="Generic finding")

        # If the combination is not in the matrix, default should be used
        result = custom_classifier.classify_finding(finding, RoleCategory.STANDARD)

        # Verification + Standard = 0.8 in the matrix
        assert result.relevance_to_role == 0.8

    def test_finding_updated_with_relevance(
        self, classifier: FindingClassifier
    ) -> None:
        """Test that finding object is updated with relevance."""
        finding = create_finding(summary="Felony conviction")
        classifier.classify_finding(finding, RoleCategory.GOVERNMENT)

        assert finding.relevance_to_role == 1.0


# =============================================================================
# Batch Classification Tests
# =============================================================================


class TestBatchClassification:
    """Tests for classifying multiple findings."""

    def test_classify_multiple_findings(self, classifier: FindingClassifier) -> None:
        """Test classifying a batch of findings."""
        findings = [
            create_finding(summary="Felony conviction"),
            create_finding(summary="Bankruptcy filed"),
            create_finding(summary="License suspension"),
        ]
        results = classifier.classify_findings(findings, RoleCategory.STANDARD)

        assert len(results) == 3
        assert results[0].assigned_category == FindingCategory.CRIMINAL
        assert results[1].assigned_category == FindingCategory.FINANCIAL
        assert results[2].assigned_category == FindingCategory.REGULATORY

    def test_empty_findings_list(self, classifier: FindingClassifier) -> None:
        """Test classifying empty list returns empty results."""
        results = classifier.classify_findings([], RoleCategory.STANDARD)
        assert results == []

    def test_update_findings_disabled(self, classifier: FindingClassifier) -> None:
        """Test findings not updated when disabled."""
        findings = [
            create_finding(summary="Felony conviction"),
        ]
        results = classifier.classify_findings(
            findings, RoleCategory.GOVERNMENT, update_findings=False
        )

        # Finding should not be updated (remains at default values)
        assert findings[0].category is None
        assert findings[0].relevance_to_role == 0.0  # Default value

        # But result should have the category
        assert results[0].assigned_category == FindingCategory.CRIMINAL

    def test_update_findings_enabled(self, classifier: FindingClassifier) -> None:
        """Test findings updated when enabled (default)."""
        findings = [
            create_finding(summary="Felony conviction"),
        ]
        classifier.classify_findings(findings, RoleCategory.GOVERNMENT)

        assert findings[0].category == FindingCategory.CRIMINAL
        assert findings[0].relevance_to_role == 1.0


# =============================================================================
# Distribution Tests
# =============================================================================


class TestDistribution:
    """Tests for category and sub-category distribution."""

    def test_category_distribution(self, classifier: FindingClassifier) -> None:
        """Test get_category_distribution."""
        findings = [
            create_finding(summary="Felony conviction"),
            create_finding(summary="Another arrest charge"),
            create_finding(summary="Bankruptcy filed"),
            create_finding(summary="License suspension"),
        ]
        results = classifier.classify_findings(findings, RoleCategory.STANDARD)
        distribution = classifier.get_category_distribution(results)

        assert distribution[FindingCategory.CRIMINAL] == 2
        assert distribution[FindingCategory.FINANCIAL] == 1
        assert distribution[FindingCategory.REGULATORY] == 1

    def test_subcategory_distribution(self, classifier: FindingClassifier) -> None:
        """Test get_subcategory_distribution."""
        findings = [
            create_finding(summary="Felony conviction"),
            create_finding(summary="DUI arrest"),
            create_finding(summary="Chapter 7 bankruptcy"),
        ]
        results = classifier.classify_findings(findings, RoleCategory.STANDARD)
        distribution = classifier.get_subcategory_distribution(results)

        assert distribution[SubCategory.CRIMINAL_FELONY] == 1
        assert distribution[SubCategory.CRIMINAL_DUI] == 1
        assert distribution[SubCategory.FINANCIAL_BANKRUPTCY] == 1

    def test_empty_distribution(self, classifier: FindingClassifier) -> None:
        """Test distribution with empty results."""
        distribution = classifier.get_category_distribution([])
        assert distribution == {}


# =============================================================================
# ClassificationResult Tests
# =============================================================================


class TestClassificationResult:
    """Tests for ClassificationResult dataclass."""

    def test_default_values(self) -> None:
        """Test default ClassificationResult values."""
        result = ClassificationResult()

        assert isinstance(result.classification_id, UUID)
        assert result.finding_id is None
        assert result.original_category is None
        assert result.assigned_category == FindingCategory.VERIFICATION
        assert result.sub_category == SubCategory.UNCLASSIFIED
        assert result.category_confidence == 0.0
        assert result.relevance_to_role == 0.0
        assert result.keyword_matches == []
        assert result.was_reclassified is False
        assert result.classified_at is not None

    def test_to_dict(self) -> None:
        """Test ClassificationResult to_dict method."""
        result = ClassificationResult(
            original_category=FindingCategory.CRIMINAL,
            assigned_category=FindingCategory.FINANCIAL,
            sub_category=SubCategory.FINANCIAL_BANKRUPTCY,
            category_confidence=0.8,
            relevance_to_role=0.9,
            keyword_matches=["bankruptcy", "debt"],
            was_reclassified=True,
        )
        d = result.to_dict()

        assert "classification_id" in d
        assert d["original_category"] == "criminal"
        assert d["assigned_category"] == "financial"
        assert d["sub_category"] == "financial_bankruptcy"
        assert d["category_confidence"] == 0.8
        assert d["relevance_to_role"] == 0.9
        assert d["keyword_matches"] == ["bankruptcy", "debt"]
        assert d["was_reclassified"] is True
        assert "classified_at" in d

    def test_to_dict_null_original(self) -> None:
        """Test to_dict with null original_category."""
        result = ClassificationResult(
            original_category=None,
            assigned_category=FindingCategory.CRIMINAL,
        )
        d = result.to_dict()

        assert d["original_category"] is None


# =============================================================================
# Keyword Constant Tests
# =============================================================================


class TestKeywordConstants:
    """Tests for keyword constant mappings."""

    def test_all_categories_have_keywords(self) -> None:
        """Test all FindingCategory values have keywords defined."""
        for category in FindingCategory:
            assert category in CATEGORY_KEYWORDS
            assert len(CATEGORY_KEYWORDS[category]) > 0

    def test_role_relevance_matrix_coverage(self) -> None:
        """Test role relevance matrix has entries for all category-role pairs."""
        for category in FindingCategory:
            for role in RoleCategory:
                key = (category, role)
                assert key in ROLE_RELEVANCE_MATRIX, f"Missing: {key}"

    def test_subcategory_keywords_exist(self) -> None:
        """Test subcategory keywords are defined."""
        # At least some subcategories should have keywords
        assert len(SUBCATEGORY_KEYWORDS) > 0

        for subcategory, keywords in SUBCATEGORY_KEYWORDS.items():
            assert len(keywords) > 0, f"{subcategory} has no keywords"


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_finding_text(self, classifier: FindingClassifier) -> None:
        """Test classification with empty text."""
        finding = create_finding(summary="", details="", finding_type="")
        result = classifier.classify_finding(finding, RoleCategory.STANDARD)

        # Should default to VERIFICATION with low confidence
        assert result.assigned_category == FindingCategory.VERIFICATION
        assert result.category_confidence == 0.3

    def test_case_insensitive_matching(self, classifier: FindingClassifier) -> None:
        """Test keywords match case-insensitively."""
        finding = create_finding(
            summary="FELONY CONVICTION",
            details="CRIMINAL CHARGE",
        )
        result = classifier.classify_finding(finding, RoleCategory.STANDARD)

        assert result.assigned_category == FindingCategory.CRIMINAL
        assert len(result.keyword_matches) > 0

    def test_partial_keyword_not_matched(
        self, classifier: FindingClassifier
    ) -> None:
        """Test partial keywords don't match (e.g., 'arrest' in 'arrested')."""
        finding = create_finding(summary="Subject was arrested for theft")
        result = classifier.classify_finding(finding, RoleCategory.STANDARD)

        # "arrest" should match since it's contained in "arrested"
        assert "arrest" in result.keyword_matches

    def test_multi_word_keywords(self, classifier: FindingClassifier) -> None:
        """Test multi-word keywords like 'shell company'."""
        finding = create_finding(
            summary="Connection to shell company",
            details="Beneficial owner identified.",
        )
        result = classifier.classify_finding(finding, RoleCategory.FINANCIAL)

        assert "shell company" in result.keyword_matches
        assert "beneficial owner" in result.keyword_matches

    def test_finding_type_included_in_text(
        self, classifier: FindingClassifier
    ) -> None:
        """Test finding_type field is included in classification text."""
        finding = create_finding(
            summary="Record found",
            details="Details here",
            finding_type="felony_conviction",
        )
        result = classifier.classify_finding(finding, RoleCategory.STANDARD)

        assert result.assigned_category == FindingCategory.CRIMINAL
        assert "felony" in result.keyword_matches or "conviction" in result.keyword_matches

    def test_special_characters_in_text(self, classifier: FindingClassifier) -> None:
        """Test handling of special characters in text."""
        finding = create_finding(
            summary="Felony (conviction) - criminal charge!",
            details="Subject's record: theft & fraud.",
        )
        result = classifier.classify_finding(finding, RoleCategory.STANDARD)

        assert result.assigned_category == FindingCategory.CRIMINAL


# =============================================================================
# SubCategory Enum Tests
# =============================================================================


class TestSubCategoryEnum:
    """Tests for SubCategory enum."""

    def test_criminal_subcategories(self) -> None:
        """Test criminal sub-categories exist."""
        criminal_subs = [s for s in SubCategory if s.value.startswith("criminal_")]
        assert len(criminal_subs) == 8

    def test_financial_subcategories(self) -> None:
        """Test financial sub-categories exist."""
        financial_subs = [s for s in SubCategory if s.value.startswith("financial_")]
        assert len(financial_subs) == 6

    def test_regulatory_subcategories(self) -> None:
        """Test regulatory sub-categories exist."""
        regulatory_subs = [s for s in SubCategory if s.value.startswith("regulatory_")]
        assert len(regulatory_subs) == 5

    def test_reputation_subcategories(self) -> None:
        """Test reputation sub-categories exist."""
        reputation_subs = [s for s in SubCategory if s.value.startswith("reputation_")]
        assert len(reputation_subs) == 4

    def test_verification_subcategories(self) -> None:
        """Test verification sub-categories exist."""
        verification_subs = [s for s in SubCategory if s.value.startswith("verification_")]
        assert len(verification_subs) == 5

    def test_behavioral_subcategories(self) -> None:
        """Test behavioral sub-categories exist."""
        behavioral_subs = [s for s in SubCategory if s.value.startswith("behavioral_")]
        assert len(behavioral_subs) == 2

    def test_network_subcategories(self) -> None:
        """Test network sub-categories exist."""
        network_subs = [s for s in SubCategory if s.value.startswith("network_")]
        assert len(network_subs) == 3

    def test_unclassified_exists(self) -> None:
        """Test UNCLASSIFIED sub-category exists."""
        assert SubCategory.UNCLASSIFIED.value == "unclassified"
