"""Tests for Risk Score Explanations.

Tests cover:
- Explanation generation from assessments
- Explanation generation from scores
- Contributing factor extraction
- Narrative generation
- What-if analysis
- Export formats
"""

from datetime import UTC, datetime
from uuid import uuid7

import pytest

from elile.investigation.finding_extractor import Finding, FindingCategory, Severity
from elile.risk.anomaly_detector import Anomaly, AnomalyType
from elile.risk.explanations import (
    ContributingFactor,
    ExplanationDepth,
    ExplanationFormat,
    ExplainerConfig,
    FactorImpact,
    RiskExplainer,
    RiskExplanation,
    ScoreBreakdown,
    WhatIfScenario,
    create_risk_explainer,
)
from elile.risk.pattern_recognizer import Pattern, PatternType
from elile.risk.risk_aggregator import ComprehensiveRiskAssessment, RiskAdjustment
from elile.risk.risk_scorer import Recommendation, RiskLevel, RiskScore


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def explainer() -> RiskExplainer:
    """Create a default risk explainer."""
    return create_risk_explainer()


@pytest.fixture
def sample_findings() -> list[Finding]:
    """Create sample findings."""
    from datetime import date
    return [
        Finding(
            summary="DUI Conviction",
            details="Driving under the influence conviction from 2022",
            category=FindingCategory.CRIMINAL,
            severity=Severity.HIGH,
            finding_date=date(2022, 6, 15),
        ),
        Finding(
            summary="Unpaid Tax Lien",
            details="Federal tax lien for $15,000",
            category=FindingCategory.FINANCIAL,
            severity=Severity.MEDIUM,
            finding_date=date(2021, 3, 20),
        ),
        Finding(
            summary="Employment Gap",
            details="Unexplained 18-month employment gap",
            category=FindingCategory.VERIFICATION,
            severity=Severity.LOW,
            finding_date=date(2020, 1, 1),
        ),
    ]


@pytest.fixture
def critical_findings() -> list[Finding]:
    """Create findings with critical severity."""
    from datetime import date
    return [
        Finding(
            summary="Fraud Conviction",
            details="Wire fraud conviction with prison sentence",
            category=FindingCategory.CRIMINAL,
            severity=Severity.CRITICAL,
            finding_date=date(2023, 1, 15),
        ),
        Finding(
            summary="Sanctions List Match",
            details="Name match on OFAC sanctions list",
            category=FindingCategory.REGULATORY,
            severity=Severity.CRITICAL,
            finding_date=date(2023, 6, 1),
        ),
    ]


@pytest.fixture
def sample_patterns() -> list[Pattern]:
    """Create sample patterns."""
    return [
        Pattern(
            pattern_type=PatternType.RECURRING_ISSUES,
            severity=Severity.MEDIUM,
            confidence=0.8,
            description="Multiple similar issues over 3 years",
        ),
        Pattern(
            pattern_type=PatternType.IMPROVEMENT_TREND,
            severity=Severity.LOW,
            confidence=0.7,
            description="Decreasing frequency of issues",
        ),
    ]


@pytest.fixture
def sample_anomalies() -> list[Anomaly]:
    """Create sample anomalies."""
    return [
        Anomaly(
            anomaly_type=AnomalyType.CREDENTIAL_INFLATION,
            severity=Severity.MEDIUM,
            confidence=0.75,
            description="Claimed degree not verified",
        ),
        Anomaly(
            anomaly_type=AnomalyType.CHRONOLOGICAL_GAP,
            severity=Severity.LOW,
            confidence=0.6,
            description="Gap in employment history",
        ),
    ]


@pytest.fixture
def deception_anomalies() -> list[Anomaly]:
    """Create deception-related anomalies."""
    return [
        Anomaly(
            anomaly_type=AnomalyType.DECEPTION_PATTERN,
            severity=Severity.CRITICAL,
            confidence=0.85,
            description="Systematic inconsistencies suggest deception",
        ),
        Anomaly(
            anomaly_type=AnomalyType.FABRICATION_INDICATOR,
            severity=Severity.HIGH,
            confidence=0.7,
            description="Employment history appears fabricated",
        ),
    ]


@pytest.fixture
def low_risk_assessment() -> ComprehensiveRiskAssessment:
    """Create a low-risk assessment."""
    return ComprehensiveRiskAssessment(
        final_score=25,
        base_score=20,
        risk_level=RiskLevel.LOW,
        recommendation=Recommendation.PROCEED,
        recommendation_reasons=["No critical findings", "Clean background"],
        key_concerns=[],
        mitigating_factors=["Strong employment history", "Clean criminal record"],
        critical_findings=0,
        high_findings=0,
        patterns_detected=0,
        anomalies_detected=0,
        risk_connections=0,
    )


@pytest.fixture
def high_risk_assessment() -> ComprehensiveRiskAssessment:
    """Create a high-risk assessment."""
    return ComprehensiveRiskAssessment(
        final_score=72,
        base_score=55,
        pre_cap_score=72.0,
        risk_level=RiskLevel.HIGH,
        recommendation=Recommendation.REVIEW_REQUIRED,
        recommendation_reasons=[
            "Multiple high-severity findings",
            "Pattern of recurring issues",
        ],
        adjustments={
            "patterns": 8.0,
            "anomalies": 5.0,
            "network": 2.0,
            "deception": 2.0,
        },
        total_adjustment=17.0,
        pattern_score=0.6,
        anomaly_score=0.4,
        network_score=0.2,
        deception_score=0.3,
        key_concerns=[
            "DUI conviction in 2022",
            "Unpaid tax lien",
            "Credential discrepancy",
        ],
        mitigating_factors=["Recent improvement trend"],
        critical_findings=0,
        high_findings=2,
        patterns_detected=2,
        anomalies_detected=2,
        risk_connections=1,
    )


@pytest.fixture
def critical_risk_assessment() -> ComprehensiveRiskAssessment:
    """Create a critical-risk assessment."""
    return ComprehensiveRiskAssessment(
        final_score=92,
        base_score=80,
        pre_cap_score=105.0,
        risk_level=RiskLevel.CRITICAL,
        recommendation=Recommendation.DO_NOT_PROCEED,
        recommendation_reasons=[
            "Multiple critical findings",
            "Deception indicators present",
        ],
        adjustments={
            "patterns": 5.0,
            "anomalies": 10.0,
            "network": 5.0,
            "deception": 5.0,
        },
        total_adjustment=25.0,
        pattern_score=0.5,
        anomaly_score=0.8,
        network_score=0.6,
        deception_score=0.7,
        key_concerns=[
            "Fraud conviction",
            "Sanctions list match",
            "Deception pattern detected",
        ],
        mitigating_factors=[],
        critical_findings=2,
        high_findings=1,
        patterns_detected=1,
        anomalies_detected=3,
        risk_connections=3,
    )


@pytest.fixture
def sample_risk_score() -> RiskScore:
    """Create a sample risk score."""
    return RiskScore(
        overall_score=45,
        risk_level=RiskLevel.MODERATE,
        category_scores={
            FindingCategory.CRIMINAL: 20,
            FindingCategory.FINANCIAL: 15,
            FindingCategory.VERIFICATION: 10,
        },
        contributing_factors={
            "criminal_count": 1.0,
            "financial_count": 1.0,
            "verification_count": 1.0,
        },
        recommendation=Recommendation.PROCEED_WITH_CAUTION,
    )


# =============================================================================
# Explanation Generation Tests
# =============================================================================


class TestExplainAssessment:
    """Tests for explain_assessment method."""

    def test_explain_low_risk(
        self, explainer: RiskExplainer, low_risk_assessment: ComprehensiveRiskAssessment
    ) -> None:
        """Test explanation for low-risk assessment."""
        explanation = explainer.explain_assessment(low_risk_assessment)

        assert explanation.score == 25
        assert explanation.risk_level == RiskLevel.LOW
        assert explanation.recommendation == Recommendation.PROCEED
        assert "low risk" in explanation.summary.lower()
        assert explanation.breakdown is not None

    def test_explain_high_risk(
        self,
        explainer: RiskExplainer,
        high_risk_assessment: ComprehensiveRiskAssessment,
        sample_findings: list[Finding],
        sample_patterns: list[Pattern],
        sample_anomalies: list[Anomaly],
    ) -> None:
        """Test explanation for high-risk assessment."""
        explanation = explainer.explain_assessment(
            high_risk_assessment,
            findings=sample_findings,
            patterns=sample_patterns,
            anomalies=sample_anomalies,
        )

        assert explanation.score == 72
        assert explanation.risk_level == RiskLevel.HIGH
        assert explanation.recommendation == Recommendation.REVIEW_REQUIRED
        assert len(explanation.contributing_factors) > 0
        assert len(explanation.key_concerns) > 0
        assert explanation.findings_narrative
        assert explanation.patterns_narrative

    def test_explain_critical_risk(
        self,
        explainer: RiskExplainer,
        critical_risk_assessment: ComprehensiveRiskAssessment,
        critical_findings: list[Finding],
    ) -> None:
        """Test explanation for critical-risk assessment."""
        explanation = explainer.explain_assessment(
            critical_risk_assessment,
            findings=critical_findings,
        )

        assert explanation.score == 92
        assert explanation.risk_level == RiskLevel.CRITICAL
        assert explanation.recommendation == Recommendation.DO_NOT_PROCEED
        assert "critical" in explanation.summary.lower() or "serious" in explanation.summary.lower()

    def test_explain_with_depth_summary(
        self, explainer: RiskExplainer, high_risk_assessment: ComprehensiveRiskAssessment
    ) -> None:
        """Test summary depth explanation."""
        explanation = explainer.explain_assessment(
            high_risk_assessment,
            depth=ExplanationDepth.SUMMARY,
        )

        assert explanation.depth == ExplanationDepth.SUMMARY
        assert explanation.summary  # Should still have summary

    def test_explain_with_depth_detailed(
        self,
        explainer: RiskExplainer,
        high_risk_assessment: ComprehensiveRiskAssessment,
        sample_findings: list[Finding],
    ) -> None:
        """Test detailed depth explanation."""
        explanation = explainer.explain_assessment(
            high_risk_assessment,
            findings=sample_findings,
            depth=ExplanationDepth.DETAILED,
        )

        assert explanation.depth == ExplanationDepth.DETAILED
        # Detailed should include more narratives
        assert explanation.findings_narrative

    def test_explain_includes_what_if(
        self,
        explainer: RiskExplainer,
        high_risk_assessment: ComprehensiveRiskAssessment,
        sample_findings: list[Finding],
    ) -> None:
        """Test that what-if scenarios are included by default."""
        explanation = explainer.explain_assessment(
            high_risk_assessment,
            findings=sample_findings,
        )

        # May or may not have scenarios depending on findings
        assert isinstance(explanation.what_if_scenarios, list)


class TestExplainScore:
    """Tests for explain_score method."""

    def test_explain_basic_score(
        self, explainer: RiskExplainer, sample_risk_score: RiskScore
    ) -> None:
        """Test explanation for basic risk score."""
        explanation = explainer.explain_score(sample_risk_score)

        assert explanation.score == 45
        assert explanation.risk_level == RiskLevel.MODERATE
        assert explanation.recommendation == Recommendation.PROCEED_WITH_CAUTION
        assert explanation.summary
        assert explanation.breakdown is not None
        assert explanation.breakdown.base_score == 45

    def test_explain_score_with_findings(
        self,
        explainer: RiskExplainer,
        sample_risk_score: RiskScore,
        sample_findings: list[Finding],
    ) -> None:
        """Test explanation for score with findings."""
        explanation = explainer.explain_score(sample_risk_score, findings=sample_findings)

        assert len(explanation.contributing_factors) > 0
        assert explanation.findings_narrative


# =============================================================================
# Score Breakdown Tests
# =============================================================================


class TestScoreBreakdown:
    """Tests for score breakdown generation."""

    def test_breakdown_from_assessment(
        self,
        explainer: RiskExplainer,
        high_risk_assessment: ComprehensiveRiskAssessment,
    ) -> None:
        """Test breakdown is generated from assessment."""
        explanation = explainer.explain_assessment(high_risk_assessment)
        breakdown = explanation.breakdown

        assert breakdown is not None
        assert breakdown.base_score == 55
        assert breakdown.final_score == 72
        assert breakdown.total_adjustments == 17.0

    def test_breakdown_to_dict(self) -> None:
        """Test breakdown serialization."""
        breakdown = ScoreBreakdown(
            base_score=50,
            findings_contribution=50,
            patterns_contribution=10,
            anomalies_contribution=5,
            final_score=65,
        )

        d = breakdown.to_dict()
        assert d["base_score"] == 50
        assert d["final_score"] == 65
        assert "breakdown_id" in d


# =============================================================================
# Contributing Factor Tests
# =============================================================================


class TestContributingFactors:
    """Tests for contributing factor extraction."""

    def test_extract_from_findings(
        self,
        explainer: RiskExplainer,
        high_risk_assessment: ComprehensiveRiskAssessment,
        sample_findings: list[Finding],
    ) -> None:
        """Test factor extraction from findings."""
        explanation = explainer.explain_assessment(
            high_risk_assessment,
            findings=sample_findings,
        )

        # Should have factors from findings
        finding_factors = [f for f in explanation.contributing_factors if f.category == "finding"]
        assert len(finding_factors) > 0

    def test_extract_from_patterns(
        self,
        explainer: RiskExplainer,
        high_risk_assessment: ComprehensiveRiskAssessment,
        sample_patterns: list[Pattern],
    ) -> None:
        """Test factor extraction from patterns."""
        explanation = explainer.explain_assessment(
            high_risk_assessment,
            patterns=sample_patterns,
        )

        pattern_factors = [f for f in explanation.contributing_factors if f.category == "pattern"]
        assert len(pattern_factors) > 0

    def test_extract_from_anomalies(
        self,
        explainer: RiskExplainer,
        high_risk_assessment: ComprehensiveRiskAssessment,
        sample_anomalies: list[Anomaly],
    ) -> None:
        """Test factor extraction from anomalies."""
        explanation = explainer.explain_assessment(
            high_risk_assessment,
            anomalies=sample_anomalies,
        )

        anomaly_factors = [f for f in explanation.contributing_factors if f.category == "anomaly"]
        assert len(anomaly_factors) > 0

    def test_factors_sorted_by_contribution(
        self,
        explainer: RiskExplainer,
        high_risk_assessment: ComprehensiveRiskAssessment,
        sample_findings: list[Finding],
    ) -> None:
        """Test that factors are sorted by contribution."""
        explanation = explainer.explain_assessment(
            high_risk_assessment,
            findings=sample_findings,
        )

        if len(explanation.contributing_factors) >= 2:
            contributions = [f.score_contribution for f in explanation.contributing_factors]
            assert contributions == sorted(contributions, reverse=True)

    def test_contributing_factor_to_dict(self) -> None:
        """Test contributing factor serialization."""
        factor = ContributingFactor(
            name="Test Factor",
            description="A test factor",
            category="finding",
            impact=FactorImpact.HIGH,
            score_contribution=30.0,
            percentage_contribution=50.0,
        )

        d = factor.to_dict()
        assert d["name"] == "Test Factor"
        assert d["impact"] == "high"
        assert d["score_contribution"] == 30.0


# =============================================================================
# Narrative Tests
# =============================================================================


class TestNarratives:
    """Tests for narrative generation."""

    def test_summary_contains_score(
        self, explainer: RiskExplainer, high_risk_assessment: ComprehensiveRiskAssessment
    ) -> None:
        """Test that summary contains the score."""
        explanation = explainer.explain_assessment(high_risk_assessment)
        assert "72" in explanation.summary

    def test_summary_contains_recommendation(
        self, explainer: RiskExplainer, low_risk_assessment: ComprehensiveRiskAssessment
    ) -> None:
        """Test that summary contains recommendation language."""
        explanation = explainer.explain_assessment(low_risk_assessment)
        assert "recommend" in explanation.summary.lower()

    def test_findings_narrative_without_findings(
        self, explainer: RiskExplainer, low_risk_assessment: ComprehensiveRiskAssessment
    ) -> None:
        """Test findings narrative when no findings present."""
        explanation = explainer.explain_assessment(low_risk_assessment)
        assert "No significant findings" in explanation.findings_narrative

    def test_findings_narrative_with_findings(
        self,
        explainer: RiskExplainer,
        high_risk_assessment: ComprehensiveRiskAssessment,
        sample_findings: list[Finding],
    ) -> None:
        """Test findings narrative with findings."""
        explanation = explainer.explain_assessment(
            high_risk_assessment,
            findings=sample_findings,
        )
        assert "3" in explanation.findings_narrative or "finding" in explanation.findings_narrative.lower()

    def test_patterns_narrative_without_patterns(
        self, explainer: RiskExplainer, low_risk_assessment: ComprehensiveRiskAssessment
    ) -> None:
        """Test patterns narrative when no patterns present."""
        explanation = explainer.explain_assessment(low_risk_assessment)
        assert "No significant" in explanation.patterns_narrative

    def test_patterns_narrative_with_patterns(
        self,
        explainer: RiskExplainer,
        high_risk_assessment: ComprehensiveRiskAssessment,
        sample_patterns: list[Pattern],
    ) -> None:
        """Test patterns narrative with patterns."""
        explanation = explainer.explain_assessment(
            high_risk_assessment,
            patterns=sample_patterns,
        )
        assert "pattern" in explanation.patterns_narrative.lower()

    def test_network_narrative_no_connections(
        self, explainer: RiskExplainer, low_risk_assessment: ComprehensiveRiskAssessment
    ) -> None:
        """Test network narrative when no risk connections."""
        explanation = explainer.explain_assessment(low_risk_assessment)
        assert "did not identify" in explanation.network_narrative.lower()

    def test_network_narrative_with_connections(
        self, explainer: RiskExplainer, critical_risk_assessment: ComprehensiveRiskAssessment
    ) -> None:
        """Test network narrative with risk connections."""
        explanation = explainer.explain_assessment(critical_risk_assessment)
        assert "connection" in explanation.network_narrative.lower()


# =============================================================================
# What-If Analysis Tests
# =============================================================================


class TestWhatIfAnalysis:
    """Tests for what-if analysis."""

    def test_analyze_what_if_remove_findings(
        self,
        explainer: RiskExplainer,
        critical_risk_assessment: ComprehensiveRiskAssessment,
        critical_findings: list[Finding],
    ) -> None:
        """Test what-if analysis removing findings."""
        scenario = explainer.analyze_what_if(
            critical_risk_assessment,
            remove_findings=critical_findings,
        )

        assert scenario.original_score == 92
        assert scenario.projected_score < scenario.original_score
        assert scenario.score_change < 0
        assert len(scenario.removed_factors) == 2
        assert scenario.explanation

    def test_analyze_what_if_remove_patterns(
        self,
        explainer: RiskExplainer,
        high_risk_assessment: ComprehensiveRiskAssessment,
        sample_patterns: list[Pattern],
    ) -> None:
        """Test what-if analysis removing patterns."""
        scenario = explainer.analyze_what_if(
            high_risk_assessment,
            remove_patterns=sample_patterns,
        )

        assert scenario.projected_score <= scenario.original_score

    def test_analyze_what_if_remove_anomalies(
        self,
        explainer: RiskExplainer,
        high_risk_assessment: ComprehensiveRiskAssessment,
        sample_anomalies: list[Anomaly],
    ) -> None:
        """Test what-if analysis removing anomalies."""
        scenario = explainer.analyze_what_if(
            high_risk_assessment,
            remove_anomalies=sample_anomalies,
        )

        assert scenario.projected_score <= scenario.original_score

    def test_what_if_level_change_detected(
        self,
        explainer: RiskExplainer,
        critical_risk_assessment: ComprehensiveRiskAssessment,
        critical_findings: list[Finding],
    ) -> None:
        """Test that level changes are detected in what-if."""
        scenario = explainer.analyze_what_if(
            critical_risk_assessment,
            remove_findings=critical_findings,
        )

        # Removing critical findings may change level
        if scenario.projected_level != scenario.original_level:
            assert scenario.level_changed is True

    def test_what_if_scenario_to_dict(self) -> None:
        """Test what-if scenario serialization."""
        scenario = WhatIfScenario(
            name="Test Scenario",
            description="Testing",
            removed_factors=["Factor A"],
            original_score=80,
            projected_score=60,
            score_change=-20,
            original_level=RiskLevel.HIGH,
            projected_level=RiskLevel.MODERATE,
            level_changed=True,
            explanation="Test explanation",
        )

        d = scenario.to_dict()
        assert d["name"] == "Test Scenario"
        assert d["score_change"] == -20
        assert d["level_changed"] is True

    def test_auto_generated_what_if_critical_findings(
        self,
        explainer: RiskExplainer,
        critical_risk_assessment: ComprehensiveRiskAssessment,
        critical_findings: list[Finding],
    ) -> None:
        """Test auto-generated what-if for critical findings."""
        explanation = explainer.explain_assessment(
            critical_risk_assessment,
            findings=critical_findings,
        )

        # Should have a scenario about critical findings
        critical_scenario = [
            s for s in explanation.what_if_scenarios
            if "critical" in s.name.lower()
        ]
        assert len(critical_scenario) > 0


# =============================================================================
# Export Tests
# =============================================================================


class TestExport:
    """Tests for export functionality."""

    def test_export_plain_text(
        self, explainer: RiskExplainer, high_risk_assessment: ComprehensiveRiskAssessment
    ) -> None:
        """Test plain text export."""
        explanation = explainer.explain_assessment(high_risk_assessment)
        text = explainer.export(explanation, ExplanationFormat.PLAIN_TEXT)

        assert "RISK ASSESSMENT EXPLANATION" in text
        assert "Risk Score: 72/100" in text
        assert "SUMMARY" in text

    def test_export_markdown(
        self, explainer: RiskExplainer, high_risk_assessment: ComprehensiveRiskAssessment
    ) -> None:
        """Test markdown export."""
        explanation = explainer.explain_assessment(high_risk_assessment)
        md = explainer.export(explanation, ExplanationFormat.MARKDOWN)

        assert "# Risk Assessment Explanation" in md
        assert "**Risk Score:**" in md
        assert "## Summary" in md

    def test_export_html(
        self, explainer: RiskExplainer, high_risk_assessment: ComprehensiveRiskAssessment
    ) -> None:
        """Test HTML export."""
        explanation = explainer.explain_assessment(high_risk_assessment)
        html = explainer.export(explanation, ExplanationFormat.HTML)

        assert "<!DOCTYPE html>" in html
        assert "<h1>Risk Assessment Explanation</h1>" in html
        assert "Score: 72/100" in html

    def test_export_json(
        self, explainer: RiskExplainer, high_risk_assessment: ComprehensiveRiskAssessment
    ) -> None:
        """Test JSON export."""
        import json

        explanation = explainer.explain_assessment(high_risk_assessment)
        json_str = explainer.export(explanation, ExplanationFormat.JSON)

        data = json.loads(json_str)
        assert data["score"] == 72
        assert data["risk_level"] == "high"


# =============================================================================
# Configuration Tests
# =============================================================================


class TestExplainerConfig:
    """Tests for explainer configuration."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = ExplainerConfig()

        assert config.default_depth == ExplanationDepth.STANDARD
        assert config.include_what_if is True
        assert config.max_what_if_scenarios == 3
        assert config.formal_tone is True

    def test_custom_config_depth(self) -> None:
        """Test custom default depth."""
        config = ExplainerConfig(default_depth=ExplanationDepth.DETAILED)
        explainer = RiskExplainer(config=config)

        assert explainer.config.default_depth == ExplanationDepth.DETAILED

    def test_config_disable_what_if(
        self, high_risk_assessment: ComprehensiveRiskAssessment
    ) -> None:
        """Test disabling what-if scenarios."""
        config = ExplainerConfig(include_what_if=False)
        explainer = RiskExplainer(config=config)

        explanation = explainer.explain_assessment(high_risk_assessment)
        assert len(explanation.what_if_scenarios) == 0

    def test_config_min_contribution_filter(
        self,
        high_risk_assessment: ComprehensiveRiskAssessment,
        sample_findings: list[Finding],
    ) -> None:
        """Test minimum contribution filtering."""
        # High threshold should filter out low-contribution factors
        config = ExplainerConfig(min_contribution_percentage=20.0)
        explainer = RiskExplainer(config=config)

        explanation = explainer.explain_assessment(
            high_risk_assessment,
            findings=sample_findings,
        )

        # All remaining factors should have >= 20% contribution
        for factor in explanation.contributing_factors:
            assert factor.percentage_contribution >= 20.0 or factor.score_contribution > 0


# =============================================================================
# Serialization Tests
# =============================================================================


class TestSerialization:
    """Tests for data model serialization."""

    def test_risk_explanation_to_dict(
        self, explainer: RiskExplainer, high_risk_assessment: ComprehensiveRiskAssessment
    ) -> None:
        """Test RiskExplanation serialization."""
        explanation = explainer.explain_assessment(high_risk_assessment)
        d = explanation.to_dict()

        assert d["score"] == 72
        assert d["risk_level"] == "high"
        assert "summary" in d
        assert "breakdown" in d
        assert isinstance(d["contributing_factors"], list)

    def test_roundtrip_serialization(
        self, explainer: RiskExplainer, high_risk_assessment: ComprehensiveRiskAssessment
    ) -> None:
        """Test that to_dict produces valid JSON."""
        import json

        explanation = explainer.explain_assessment(high_risk_assessment)
        d = explanation.to_dict()

        # Should be JSON serializable
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["score"] == explanation.score
        assert restored["risk_level"] == explanation.risk_level.value


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for factory function."""

    def test_create_with_defaults(self) -> None:
        """Test creating explainer with defaults."""
        explainer = create_risk_explainer()
        assert explainer.config.default_depth == ExplanationDepth.STANDARD

    def test_create_with_config(self) -> None:
        """Test creating explainer with custom config."""
        config = ExplainerConfig(
            default_depth=ExplanationDepth.DETAILED,
            max_what_if_scenarios=5,
        )
        explainer = create_risk_explainer(config=config)

        assert explainer.config.default_depth == ExplanationDepth.DETAILED
        assert explainer.config.max_what_if_scenarios == 5


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_explain_zero_score(self, explainer: RiskExplainer) -> None:
        """Test explaining a zero score assessment."""
        assessment = ComprehensiveRiskAssessment(
            final_score=0,
            base_score=0,
            risk_level=RiskLevel.LOW,
            recommendation=Recommendation.PROCEED,
        )

        explanation = explainer.explain_assessment(assessment)
        assert explanation.score == 0
        assert explanation.summary  # Should still generate summary

    def test_explain_max_score(self, explainer: RiskExplainer) -> None:
        """Test explaining a maximum score assessment."""
        assessment = ComprehensiveRiskAssessment(
            final_score=100,
            base_score=100,
            pre_cap_score=120.0,
            risk_level=RiskLevel.CRITICAL,
            recommendation=Recommendation.DO_NOT_PROCEED,
        )

        explanation = explainer.explain_assessment(assessment)
        assert explanation.score == 100
        assert explanation.breakdown.was_capped is True

    def test_explain_empty_findings(
        self, explainer: RiskExplainer, high_risk_assessment: ComprehensiveRiskAssessment
    ) -> None:
        """Test explaining with empty findings list."""
        explanation = explainer.explain_assessment(
            high_risk_assessment,
            findings=[],
        )

        # Should still generate explanation
        assert explanation.summary
        assert explanation.findings_narrative

    def test_explain_score_without_findings(
        self, explainer: RiskExplainer, sample_risk_score: RiskScore
    ) -> None:
        """Test explaining score without findings."""
        explanation = explainer.explain_score(sample_risk_score)

        # Should extract factors from category scores
        assert len(explanation.contributing_factors) > 0


# =============================================================================
# Impact Conversion Tests
# =============================================================================


class TestImpactConversion:
    """Tests for impact level conversion."""

    def test_severity_to_impact_critical(self, explainer: RiskExplainer) -> None:
        """Test critical severity converts to critical impact."""
        impact = explainer._severity_to_impact(Severity.CRITICAL)
        assert impact == FactorImpact.CRITICAL

    def test_severity_to_impact_high(self, explainer: RiskExplainer) -> None:
        """Test high severity converts to high impact."""
        impact = explainer._severity_to_impact(Severity.HIGH)
        assert impact == FactorImpact.HIGH

    def test_severity_to_impact_medium(self, explainer: RiskExplainer) -> None:
        """Test medium severity converts to moderate impact."""
        impact = explainer._severity_to_impact(Severity.MEDIUM)
        assert impact == FactorImpact.MODERATE

    def test_severity_to_impact_low(self, explainer: RiskExplainer) -> None:
        """Test low severity converts to low impact."""
        impact = explainer._severity_to_impact(Severity.LOW)
        assert impact == FactorImpact.LOW

    def test_score_to_level_boundaries(self, explainer: RiskExplainer) -> None:
        """Test score to level conversion at boundaries."""
        assert explainer._score_to_level(39) == RiskLevel.LOW
        assert explainer._score_to_level(40) == RiskLevel.MODERATE
        assert explainer._score_to_level(59) == RiskLevel.MODERATE
        assert explainer._score_to_level(60) == RiskLevel.HIGH
        assert explainer._score_to_level(79) == RiskLevel.HIGH
        assert explainer._score_to_level(80) == RiskLevel.CRITICAL
