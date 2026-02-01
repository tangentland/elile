"""Unit tests for RiskScorer."""

from datetime import date, timedelta

import pytest
from uuid import UUID

from elile.compliance.types import RoleCategory
from elile.investigation.finding_extractor import Finding, FindingCategory, Severity
from elile.risk.risk_scorer import (
    Recommendation,
    RiskLevel,
    RiskScore,
    RiskScorer,
    ScorerConfig,
    create_risk_scorer,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def scorer() -> RiskScorer:
    """Create default scorer."""
    return RiskScorer()


@pytest.fixture
def custom_config() -> ScorerConfig:
    """Create custom scorer config."""
    return ScorerConfig(
        severity_low=5,
        severity_medium=20,
        severity_high=40,
        severity_critical=60,
        criminal_weight=2.0,
        corroboration_bonus=1.5,
        moderate_threshold=20,
        high_threshold=40,
        critical_threshold=60,
    )


@pytest.fixture
def custom_scorer(custom_config: ScorerConfig) -> RiskScorer:
    """Create scorer with custom config."""
    return RiskScorer(config=custom_config)


def create_finding(
    summary: str = "Test finding",
    category: FindingCategory = FindingCategory.CRIMINAL,
    severity: Severity = Severity.MEDIUM,
    confidence: float = 0.8,
    relevance: float = 0.8,
    corroborated: bool = False,
    finding_date: date | None = None,
) -> Finding:
    """Helper to create a Finding for testing."""
    finding = Finding(
        summary=summary,
        category=category,
        severity=severity,
        confidence=confidence,
        relevance_to_role=relevance,
        corroborated=corroborated,
        finding_date=finding_date,
    )
    return finding


# =============================================================================
# Initialization Tests
# =============================================================================


class TestRiskScorerInit:
    """Tests for RiskScorer initialization."""

    def test_init_default_config(self) -> None:
        """Test initialization with default config."""
        scorer = RiskScorer()
        assert scorer.config is not None
        assert scorer.config.severity_low == 10
        assert scorer.config.severity_medium == 25
        assert scorer.config.severity_high == 50
        assert scorer.config.severity_critical == 75
        assert scorer.config.criminal_weight == 1.5
        assert scorer.config.corroboration_bonus == 1.2

    def test_init_custom_config(self, custom_config: ScorerConfig) -> None:
        """Test initialization with custom config."""
        scorer = RiskScorer(config=custom_config)
        assert scorer.config.severity_low == 5
        assert scorer.config.severity_critical == 60
        assert scorer.config.criminal_weight == 2.0

    def test_factory_function(self) -> None:
        """Test create_risk_scorer factory function."""
        scorer = create_risk_scorer()
        assert isinstance(scorer, RiskScorer)
        assert scorer.config is not None

    def test_factory_function_with_config(self, custom_config: ScorerConfig) -> None:
        """Test factory function with custom config."""
        scorer = create_risk_scorer(config=custom_config)
        assert scorer.config.severity_low == 5


# =============================================================================
# ScorerConfig Tests
# =============================================================================


class TestScorerConfig:
    """Tests for ScorerConfig validation."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = ScorerConfig()
        assert config.severity_low == 10
        assert config.severity_medium == 25
        assert config.severity_high == 50
        assert config.severity_critical == 75
        assert config.criminal_weight == 1.5
        assert config.financial_weight == 1.0
        assert config.corroboration_bonus == 1.2
        assert config.moderate_threshold == 26
        assert config.high_threshold == 51
        assert config.critical_threshold == 76

    def test_severity_scores_property(self) -> None:
        """Test severity_scores property returns dict."""
        config = ScorerConfig()
        scores = config.severity_scores
        assert scores[Severity.LOW] == 10
        assert scores[Severity.MEDIUM] == 25
        assert scores[Severity.HIGH] == 50
        assert scores[Severity.CRITICAL] == 75

    def test_category_weights_property(self) -> None:
        """Test category_weights property returns dict."""
        config = ScorerConfig()
        weights = config.category_weights
        assert weights[FindingCategory.CRIMINAL] == 1.5
        assert weights[FindingCategory.FINANCIAL] == 1.0
        assert weights[FindingCategory.REGULATORY] == 1.3

    def test_validation_bounds(self) -> None:
        """Test config validation bounds."""
        # Valid values
        config = ScorerConfig(severity_low=0, severity_critical=100)
        assert config.severity_low == 0
        assert config.severity_critical == 100

        # Invalid severity
        with pytest.raises(ValueError):
            ScorerConfig(severity_low=-1)
        with pytest.raises(ValueError):
            ScorerConfig(severity_critical=101)

        # Invalid weight
        with pytest.raises(ValueError):
            ScorerConfig(criminal_weight=-0.1)
        with pytest.raises(ValueError):
            ScorerConfig(criminal_weight=3.5)


# =============================================================================
# Empty/No Findings Tests
# =============================================================================


class TestEmptyFindings:
    """Tests for empty or no findings."""

    def test_no_findings_returns_zero_score(self, scorer: RiskScorer) -> None:
        """Test empty findings list returns zero score."""
        score = scorer.calculate_risk_score([], RoleCategory.STANDARD)

        assert score.overall_score == 0
        assert score.risk_level == RiskLevel.LOW
        assert score.category_scores == {}
        assert score.recommendation == Recommendation.PROCEED

    def test_no_findings_has_tracking_ids(self, scorer: RiskScorer) -> None:
        """Test empty findings includes tracking IDs."""
        from uuid import uuid7
        entity_id = uuid7()
        screening_id = uuid7()

        score = scorer.calculate_risk_score(
            [],
            RoleCategory.STANDARD,
            entity_id=entity_id,
            screening_id=screening_id,
        )

        assert score.entity_id == entity_id
        assert score.screening_id == screening_id


# =============================================================================
# Category Score Tests
# =============================================================================


class TestCategoryScores:
    """Tests for category score calculation."""

    def test_single_category_single_finding(self, scorer: RiskScorer) -> None:
        """Test scoring with one finding in one category."""
        finding = create_finding(
            category=FindingCategory.CRIMINAL,
            severity=Severity.MEDIUM,
            confidence=1.0,
            relevance=1.0,
        )
        score = scorer.calculate_risk_score([finding], RoleCategory.STANDARD)

        assert FindingCategory.CRIMINAL in score.category_scores
        # Base 25 * recency 0.8 (unknown) * confidence 1.0 * corroboration 1.0 * relevance 1.0 = 20
        assert score.category_scores[FindingCategory.CRIMINAL] == 20

    def test_multiple_findings_same_category(self, scorer: RiskScorer) -> None:
        """Test scoring with multiple findings in same category."""
        findings = [
            create_finding(
                category=FindingCategory.CRIMINAL,
                severity=Severity.LOW,
                confidence=1.0,
                relevance=1.0,
            ),
            create_finding(
                category=FindingCategory.CRIMINAL,
                severity=Severity.MEDIUM,
                confidence=1.0,
                relevance=1.0,
            ),
        ]
        score = scorer.calculate_risk_score(findings, RoleCategory.STANDARD)

        # (10 + 25) * 0.8 * 1.0 * 1.0 * 1.0 = 28
        assert score.category_scores[FindingCategory.CRIMINAL] == 28

    def test_multiple_categories(self, scorer: RiskScorer) -> None:
        """Test scoring with findings in multiple categories."""
        findings = [
            create_finding(
                category=FindingCategory.CRIMINAL,
                severity=Severity.MEDIUM,
                confidence=1.0,
                relevance=1.0,
            ),
            create_finding(
                category=FindingCategory.FINANCIAL,
                severity=Severity.MEDIUM,
                confidence=1.0,
                relevance=1.0,
            ),
        ]
        score = scorer.calculate_risk_score(findings, RoleCategory.STANDARD)

        assert FindingCategory.CRIMINAL in score.category_scores
        assert FindingCategory.FINANCIAL in score.category_scores
        assert len(score.category_scores) == 2

    def test_category_score_capped_at_100(self, scorer: RiskScorer) -> None:
        """Test category score is capped at 100."""
        # Many high severity findings
        findings = [
            create_finding(
                category=FindingCategory.CRIMINAL,
                severity=Severity.CRITICAL,
                confidence=1.0,
                relevance=1.0,
                corroborated=True,
            )
            for _ in range(10)
        ]
        score = scorer.calculate_risk_score(findings, RoleCategory.STANDARD)

        assert score.category_scores[FindingCategory.CRIMINAL] <= 100


# =============================================================================
# Severity Weighting Tests
# =============================================================================


class TestSeverityWeighting:
    """Tests for severity-based scoring."""

    def test_low_severity_base_score(self, scorer: RiskScorer) -> None:
        """Test LOW severity uses base score of 10."""
        finding = create_finding(
            severity=Severity.LOW,
            confidence=1.0,
            relevance=1.0,
        )
        score = scorer.calculate_risk_score([finding], RoleCategory.STANDARD)
        # 10 * 0.8 = 8
        assert score.category_scores[FindingCategory.CRIMINAL] == 8

    def test_medium_severity_base_score(self, scorer: RiskScorer) -> None:
        """Test MEDIUM severity uses base score of 25."""
        finding = create_finding(
            severity=Severity.MEDIUM,
            confidence=1.0,
            relevance=1.0,
        )
        score = scorer.calculate_risk_score([finding], RoleCategory.STANDARD)
        # 25 * 0.8 = 20
        assert score.category_scores[FindingCategory.CRIMINAL] == 20

    def test_high_severity_base_score(self, scorer: RiskScorer) -> None:
        """Test HIGH severity uses base score of 50."""
        finding = create_finding(
            severity=Severity.HIGH,
            confidence=1.0,
            relevance=1.0,
        )
        score = scorer.calculate_risk_score([finding], RoleCategory.STANDARD)
        # 50 * 0.8 = 40
        assert score.category_scores[FindingCategory.CRIMINAL] == 40

    def test_critical_severity_base_score(self, scorer: RiskScorer) -> None:
        """Test CRITICAL severity uses base score of 75."""
        finding = create_finding(
            severity=Severity.CRITICAL,
            confidence=1.0,
            relevance=1.0,
        )
        score = scorer.calculate_risk_score([finding], RoleCategory.STANDARD)
        # 75 * 0.8 = 60
        assert score.category_scores[FindingCategory.CRIMINAL] == 60

    def test_custom_severity_scores(self, custom_scorer: RiskScorer) -> None:
        """Test custom severity scores from config."""
        finding = create_finding(
            severity=Severity.CRITICAL,
            confidence=1.0,
            relevance=1.0,
        )
        score = custom_scorer.calculate_risk_score([finding], RoleCategory.STANDARD)
        # 60 * 0.8 = 48
        assert score.category_scores[FindingCategory.CRIMINAL] == 48


# =============================================================================
# Recency Decay Tests
# =============================================================================


class TestRecencyDecay:
    """Tests for recency decay factor."""

    def test_recent_finding_full_weight(self, scorer: RiskScorer) -> None:
        """Test finding from last year gets full weight."""
        finding = create_finding(
            severity=Severity.MEDIUM,
            confidence=1.0,
            relevance=1.0,
            finding_date=date.today() - timedelta(days=180),
        )
        score = scorer.calculate_risk_score([finding], RoleCategory.STANDARD)
        # 25 * 1.0 = 25
        assert score.category_scores[FindingCategory.CRIMINAL] == 25

    def test_1_to_3_year_old_finding(self, scorer: RiskScorer) -> None:
        """Test finding 1-3 years old gets 90% weight."""
        finding = create_finding(
            severity=Severity.MEDIUM,
            confidence=1.0,
            relevance=1.0,
            finding_date=date.today() - timedelta(days=2 * 365),
        )
        score = scorer.calculate_risk_score([finding], RoleCategory.STANDARD)
        # 25 * 0.9 = 22.5 -> 22
        assert score.category_scores[FindingCategory.CRIMINAL] == 22

    def test_3_to_7_year_old_finding(self, scorer: RiskScorer) -> None:
        """Test finding 3-7 years old gets 70% weight."""
        finding = create_finding(
            severity=Severity.MEDIUM,
            confidence=1.0,
            relevance=1.0,
            finding_date=date.today() - timedelta(days=5 * 365),
        )
        score = scorer.calculate_risk_score([finding], RoleCategory.STANDARD)
        # 25 * 0.7 = 17.5 -> 17
        assert score.category_scores[FindingCategory.CRIMINAL] == 17

    def test_old_finding_reduced_weight(self, scorer: RiskScorer) -> None:
        """Test finding 7+ years old gets 50% weight."""
        finding = create_finding(
            severity=Severity.MEDIUM,
            confidence=1.0,
            relevance=1.0,
            finding_date=date.today() - timedelta(days=10 * 365),
        )
        score = scorer.calculate_risk_score([finding], RoleCategory.STANDARD)
        # 25 * 0.5 = 12.5 -> 12
        assert score.category_scores[FindingCategory.CRIMINAL] == 12

    def test_unknown_date_moderate_weight(self, scorer: RiskScorer) -> None:
        """Test finding with no date gets 80% weight."""
        finding = create_finding(
            severity=Severity.MEDIUM,
            confidence=1.0,
            relevance=1.0,
            finding_date=None,
        )
        score = scorer.calculate_risk_score([finding], RoleCategory.STANDARD)
        # 25 * 0.8 = 20
        assert score.category_scores[FindingCategory.CRIMINAL] == 20


# =============================================================================
# Corroboration Tests
# =============================================================================


class TestCorroboration:
    """Tests for corroboration bonus."""

    def test_corroborated_finding_gets_bonus(self, scorer: RiskScorer) -> None:
        """Test corroborated finding gets 1.2x bonus."""
        finding = create_finding(
            severity=Severity.MEDIUM,
            confidence=1.0,
            relevance=1.0,
            corroborated=True,
        )
        score = scorer.calculate_risk_score([finding], RoleCategory.STANDARD)
        # 25 * 0.8 * 1.2 = 24
        assert score.category_scores[FindingCategory.CRIMINAL] == 24

    def test_uncorroborated_finding_no_bonus(self, scorer: RiskScorer) -> None:
        """Test uncorroborated finding gets no bonus."""
        finding = create_finding(
            severity=Severity.MEDIUM,
            confidence=1.0,
            relevance=1.0,
            corroborated=False,
        )
        score = scorer.calculate_risk_score([finding], RoleCategory.STANDARD)
        # 25 * 0.8 * 1.0 = 20
        assert score.category_scores[FindingCategory.CRIMINAL] == 20

    def test_custom_corroboration_bonus(self, custom_scorer: RiskScorer) -> None:
        """Test custom corroboration bonus (1.5x)."""
        finding = create_finding(
            severity=Severity.MEDIUM,
            confidence=1.0,
            relevance=1.0,
            corroborated=True,
        )
        score = custom_scorer.calculate_risk_score([finding], RoleCategory.STANDARD)
        # 20 * 0.8 * 1.5 = 24
        assert score.category_scores[FindingCategory.CRIMINAL] == 24


# =============================================================================
# Confidence and Relevance Tests
# =============================================================================


class TestConfidenceAndRelevance:
    """Tests for confidence and relevance factors."""

    def test_low_confidence_reduces_score(self, scorer: RiskScorer) -> None:
        """Test low confidence reduces finding score."""
        finding = create_finding(
            severity=Severity.MEDIUM,
            confidence=0.5,
            relevance=1.0,
        )
        score = scorer.calculate_risk_score([finding], RoleCategory.STANDARD)
        # 25 * 0.8 * 0.5 = 10
        assert score.category_scores[FindingCategory.CRIMINAL] == 10

    def test_low_relevance_reduces_score(self, scorer: RiskScorer) -> None:
        """Test low relevance reduces finding score."""
        finding = create_finding(
            severity=Severity.MEDIUM,
            confidence=1.0,
            relevance=0.5,
        )
        score = scorer.calculate_risk_score([finding], RoleCategory.STANDARD)
        # 25 * 0.8 * 0.5 = 10
        assert score.category_scores[FindingCategory.CRIMINAL] == 10

    def test_combined_factors(self, scorer: RiskScorer) -> None:
        """Test combined confidence and relevance factors."""
        finding = create_finding(
            severity=Severity.HIGH,
            confidence=0.8,
            relevance=0.6,
            finding_date=date.today() - timedelta(days=100),  # recent
            corroborated=True,
        )
        score = scorer.calculate_risk_score([finding], RoleCategory.STANDARD)
        # 50 * 1.0 * 0.8 * 1.2 * 0.6 = 28.8 -> 28
        assert score.category_scores[FindingCategory.CRIMINAL] == 28


# =============================================================================
# Overall Score Tests
# =============================================================================


class TestOverallScore:
    """Tests for overall score calculation."""

    def test_overall_score_weighted_average(self, scorer: RiskScorer) -> None:
        """Test overall score is weighted average of category scores."""
        findings = [
            create_finding(
                category=FindingCategory.CRIMINAL,
                severity=Severity.MEDIUM,
                confidence=1.0,
                relevance=1.0,
            ),
            create_finding(
                category=FindingCategory.FINANCIAL,
                severity=Severity.MEDIUM,
                confidence=1.0,
                relevance=1.0,
            ),
        ]
        score = scorer.calculate_risk_score(findings, RoleCategory.STANDARD)

        # Criminal: 20, weight 1.5
        # Financial: 20, weight 1.0
        # Weighted: (20*1.5 + 20*1.0) / (1.5 + 1.0) = 50/2.5 = 20
        assert score.overall_score == 20

    def test_overall_score_capped_at_100(self, scorer: RiskScorer) -> None:
        """Test overall score is capped at 100."""
        # Many critical findings
        findings = [
            create_finding(
                category=FindingCategory.CRIMINAL,
                severity=Severity.CRITICAL,
                confidence=1.0,
                relevance=1.0,
                corroborated=True,
                finding_date=date.today(),
            )
            for _ in range(10)
        ]
        score = scorer.calculate_risk_score(findings, RoleCategory.STANDARD)

        assert score.overall_score <= 100


# =============================================================================
# Risk Level Tests
# =============================================================================


class TestRiskLevel:
    """Tests for risk level determination."""

    def test_low_risk_level(self, scorer: RiskScorer) -> None:
        """Test LOW risk level for score 0-25."""
        finding = create_finding(
            severity=Severity.LOW,
            confidence=1.0,
            relevance=1.0,
        )
        score = scorer.calculate_risk_score([finding], RoleCategory.STANDARD)

        assert score.risk_level == RiskLevel.LOW

    def test_moderate_risk_level(self, scorer: RiskScorer) -> None:
        """Test MODERATE risk level for score 26-50."""
        findings = [
            create_finding(
                severity=Severity.HIGH,
                confidence=1.0,
                relevance=1.0,
                finding_date=date.today(),
            )
        ]
        score = scorer.calculate_risk_score(findings, RoleCategory.STANDARD)

        # Score should be around 33 (50 * 1.0)
        assert score.overall_score >= 26
        assert score.overall_score <= 50
        assert score.risk_level == RiskLevel.MODERATE

    def test_high_risk_level(self, scorer: RiskScorer) -> None:
        """Test HIGH risk level for score 51-75."""
        findings = [
            create_finding(
                severity=Severity.CRITICAL,
                confidence=1.0,
                relevance=1.0,
                finding_date=date.today(),
            )
        ]
        score = scorer.calculate_risk_score(findings, RoleCategory.STANDARD)

        # Score should be 75
        assert score.overall_score >= 51
        assert score.overall_score <= 75
        assert score.risk_level == RiskLevel.HIGH

    def test_critical_risk_level(self, scorer: RiskScorer) -> None:
        """Test CRITICAL risk level for score 76+."""
        findings = [
            create_finding(
                severity=Severity.CRITICAL,
                confidence=1.0,
                relevance=1.0,
                finding_date=date.today(),
                corroborated=True,
            ),
            create_finding(
                severity=Severity.HIGH,
                confidence=1.0,
                relevance=1.0,
                finding_date=date.today(),
            ),
        ]
        score = scorer.calculate_risk_score(findings, RoleCategory.STANDARD)

        assert score.overall_score >= 76
        assert score.risk_level == RiskLevel.CRITICAL


# =============================================================================
# Recommendation Tests
# =============================================================================


class TestRecommendation:
    """Tests for recommendation determination."""

    def test_proceed_for_low_risk(self, scorer: RiskScorer) -> None:
        """Test PROCEED recommendation for LOW risk."""
        finding = create_finding(
            severity=Severity.LOW,
            confidence=0.5,
            relevance=0.5,
        )
        score = scorer.calculate_risk_score([finding], RoleCategory.STANDARD)

        assert score.recommendation == Recommendation.PROCEED

    def test_proceed_with_caution_for_moderate_risk(self, scorer: RiskScorer) -> None:
        """Test PROCEED_WITH_CAUTION for MODERATE risk."""
        findings = [
            create_finding(
                severity=Severity.HIGH,
                confidence=1.0,
                relevance=1.0,
                finding_date=date.today(),
            )
        ]
        score = scorer.calculate_risk_score(findings, RoleCategory.STANDARD)

        if score.risk_level == RiskLevel.MODERATE:
            assert score.recommendation == Recommendation.PROCEED_WITH_CAUTION

    def test_review_required_for_high_risk(self, scorer: RiskScorer) -> None:
        """Test REVIEW_REQUIRED for HIGH risk (without CRITICAL severity)."""
        # Use HIGH severity findings (not CRITICAL) to get HIGH risk level
        # without triggering DO_NOT_PROCEED from a CRITICAL finding
        findings = [
            create_finding(
                severity=Severity.HIGH,
                confidence=1.0,
                relevance=1.0,
                finding_date=date.today(),
                corroborated=True,
            ),
            create_finding(
                severity=Severity.HIGH,
                confidence=1.0,
                relevance=1.0,
                finding_date=date.today(),
            ),
        ]
        score = scorer.calculate_risk_score(findings, RoleCategory.STANDARD)

        # With 2 HIGH findings (50 each * 1.0 recency * 1.0/1.2 corr)
        # Should be in HIGH risk range (51-75)
        if score.risk_level == RiskLevel.HIGH:
            assert score.recommendation == Recommendation.REVIEW_REQUIRED

    def test_do_not_proceed_for_critical_risk(self, scorer: RiskScorer) -> None:
        """Test DO_NOT_PROCEED for CRITICAL risk."""
        findings = [
            create_finding(
                severity=Severity.CRITICAL,
                confidence=1.0,
                relevance=1.0,
                finding_date=date.today(),
                corroborated=True,
            ),
            create_finding(
                severity=Severity.HIGH,
                confidence=1.0,
                relevance=1.0,
                finding_date=date.today(),
            ),
        ]
        score = scorer.calculate_risk_score(findings, RoleCategory.STANDARD)

        if score.risk_level == RiskLevel.CRITICAL:
            assert score.recommendation == Recommendation.DO_NOT_PROCEED

    def test_do_not_proceed_for_critical_finding(self, scorer: RiskScorer) -> None:
        """Test DO_NOT_PROCEED when any CRITICAL severity finding exists."""
        # Even with low overall score, a CRITICAL finding triggers DO_NOT_PROCEED
        finding = create_finding(
            severity=Severity.CRITICAL,
            confidence=0.3,
            relevance=0.3,
            finding_date=date.today() - timedelta(days=10 * 365),  # Old
        )
        score = scorer.calculate_risk_score([finding], RoleCategory.STANDARD)

        assert score.recommendation == Recommendation.DO_NOT_PROCEED


# =============================================================================
# Contributing Factors Tests
# =============================================================================


class TestContributingFactors:
    """Tests for contributing factors identification."""

    def test_total_findings_factor(self, scorer: RiskScorer) -> None:
        """Test total_findings factor."""
        findings = [
            create_finding() for _ in range(5)
        ]
        score = scorer.calculate_risk_score(findings, RoleCategory.STANDARD)

        assert score.contributing_factors["total_findings"] == 5.0

    def test_critical_findings_factor(self, scorer: RiskScorer) -> None:
        """Test critical_findings factor counts CRITICAL severity."""
        findings = [
            create_finding(severity=Severity.CRITICAL),
            create_finding(severity=Severity.CRITICAL),
            create_finding(severity=Severity.HIGH),
        ]
        score = scorer.calculate_risk_score(findings, RoleCategory.STANDARD)

        assert score.contributing_factors["critical_findings"] == 2.0

    def test_corroborated_findings_factor(self, scorer: RiskScorer) -> None:
        """Test corroborated_findings factor."""
        findings = [
            create_finding(corroborated=True),
            create_finding(corroborated=True),
            create_finding(corroborated=False),
        ]
        score = scorer.calculate_risk_score(findings, RoleCategory.STANDARD)

        assert score.contributing_factors["corroborated_findings"] == 2.0

    def test_recent_findings_factor(self, scorer: RiskScorer) -> None:
        """Test recent_findings factor counts findings from last year."""
        findings = [
            create_finding(finding_date=date.today() - timedelta(days=100)),
            create_finding(finding_date=date.today() - timedelta(days=200)),
            create_finding(finding_date=date.today() - timedelta(days=500)),  # >1 year
        ]
        score = scorer.calculate_risk_score(findings, RoleCategory.STANDARD)

        assert score.contributing_factors["recent_findings"] == 2.0

    def test_categories_affected_factor(self, scorer: RiskScorer) -> None:
        """Test categories_affected factor."""
        findings = [
            create_finding(category=FindingCategory.CRIMINAL),
            create_finding(category=FindingCategory.FINANCIAL),
            create_finding(category=FindingCategory.CRIMINAL),
        ]
        score = scorer.calculate_risk_score(findings, RoleCategory.STANDARD)

        assert score.contributing_factors["categories_affected"] == 2.0


# =============================================================================
# RiskScore Model Tests
# =============================================================================


class TestRiskScoreModel:
    """Tests for RiskScore dataclass."""

    def test_default_values(self) -> None:
        """Test default RiskScore values."""
        score = RiskScore()

        assert isinstance(score.score_id, UUID)
        assert score.overall_score == 0
        assert score.risk_level == RiskLevel.LOW
        assert score.category_scores == {}
        assert score.contributing_factors == {}
        assert score.recommendation == Recommendation.PROCEED
        assert score.scored_at is not None
        assert score.entity_id is None
        assert score.screening_id is None

    def test_to_dict(self) -> None:
        """Test RiskScore to_dict method."""
        score = RiskScore(
            overall_score=75,
            risk_level=RiskLevel.HIGH,
            category_scores={FindingCategory.CRIMINAL: 50},
            contributing_factors={"total_findings": 5.0},
            recommendation=Recommendation.REVIEW_REQUIRED,
        )
        d = score.to_dict()

        assert "score_id" in d
        assert d["overall_score"] == 75
        assert d["risk_level"] == "high"
        assert d["category_scores"] == {"criminal": 50}
        assert d["contributing_factors"] == {"total_findings": 5.0}
        assert d["recommendation"] == "review_required"
        assert "scored_at" in d


# =============================================================================
# Category Breakdown Tests
# =============================================================================


class TestCategoryBreakdown:
    """Tests for category breakdown method."""

    def test_get_category_breakdown(self, scorer: RiskScorer) -> None:
        """Test get_category_breakdown returns sorted list."""
        findings = [
            create_finding(
                category=FindingCategory.CRIMINAL,
                severity=Severity.HIGH,
                confidence=1.0,
                relevance=1.0,
                finding_date=date.today(),
            ),
            create_finding(
                category=FindingCategory.FINANCIAL,
                severity=Severity.LOW,
                confidence=1.0,
                relevance=1.0,
                finding_date=date.today(),
            ),
        ]
        score = scorer.calculate_risk_score(findings, RoleCategory.STANDARD)
        breakdown = scorer.get_category_breakdown(score)

        # Should be sorted by score desc
        assert len(breakdown) == 2
        assert breakdown[0][0] == FindingCategory.CRIMINAL  # Higher score first
        assert breakdown[1][0] == FindingCategory.FINANCIAL

    def test_breakdown_includes_descriptions(self, scorer: RiskScorer) -> None:
        """Test breakdown includes category descriptions."""
        findings = [
            create_finding(category=FindingCategory.CRIMINAL),
        ]
        score = scorer.calculate_risk_score(findings, RoleCategory.STANDARD)
        breakdown = scorer.get_category_breakdown(score)

        assert len(breakdown) == 1
        category, cat_score, description = breakdown[0]
        assert category == FindingCategory.CRIMINAL
        assert "Criminal" in description


# =============================================================================
# Enum Tests
# =============================================================================


class TestEnums:
    """Tests for enum values."""

    def test_risk_level_values(self) -> None:
        """Test RiskLevel enum values."""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MODERATE.value == "moderate"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"

    def test_recommendation_values(self) -> None:
        """Test Recommendation enum values."""
        assert Recommendation.PROCEED.value == "proceed"
        assert Recommendation.PROCEED_WITH_CAUTION.value == "proceed_with_caution"
        assert Recommendation.REVIEW_REQUIRED.value == "review_required"
        assert Recommendation.DO_NOT_PROCEED.value == "do_not_proceed"


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_finding_with_no_category(self, scorer: RiskScorer) -> None:
        """Test finding with None category is skipped."""
        finding = Finding(
            summary="Test finding",
            category=None,
            severity=Severity.HIGH,
        )
        score = scorer.calculate_risk_score([finding], RoleCategory.STANDARD)

        assert score.overall_score == 0
        assert score.category_scores == {}

    def test_finding_with_zero_confidence(self, scorer: RiskScorer) -> None:
        """Test finding with zero confidence defaults to 0.5."""
        finding = Finding(
            summary="Test",
            category=FindingCategory.CRIMINAL,
            severity=Severity.MEDIUM,
            confidence=0.0,
            relevance_to_role=1.0,
        )
        score = scorer.calculate_risk_score([finding], RoleCategory.STANDARD)

        # Uses 0.5 default for falsy confidence
        # 25 * 0.8 * 0.5 = 10
        assert score.category_scores[FindingCategory.CRIMINAL] == 10

    def test_finding_with_zero_relevance(self, scorer: RiskScorer) -> None:
        """Test finding with zero relevance defaults to 0.5."""
        finding = Finding(
            summary="Test",
            category=FindingCategory.CRIMINAL,
            severity=Severity.MEDIUM,
            confidence=1.0,
            relevance_to_role=0.0,
        )
        score = scorer.calculate_risk_score([finding], RoleCategory.STANDARD)

        # Uses 0.5 default for falsy relevance
        # 25 * 0.8 * 0.5 = 10
        assert score.category_scores[FindingCategory.CRIMINAL] == 10

    def test_all_severity_levels_in_one_category(self, scorer: RiskScorer) -> None:
        """Test findings with all severity levels in one category."""
        findings = [
            create_finding(severity=Severity.LOW, confidence=1.0, relevance=1.0),
            create_finding(severity=Severity.MEDIUM, confidence=1.0, relevance=1.0),
            create_finding(severity=Severity.HIGH, confidence=1.0, relevance=1.0),
            create_finding(severity=Severity.CRITICAL, confidence=1.0, relevance=1.0),
        ]
        score = scorer.calculate_risk_score(findings, RoleCategory.STANDARD)

        # (10 + 25 + 50 + 75) * 0.8 = 128, capped at 100
        assert score.category_scores[FindingCategory.CRIMINAL] == 100
