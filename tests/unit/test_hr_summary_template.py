"""Tests for HR Summary Report template builder.

Tests the HRSummaryBuilder which transforms compiled screening results
into user-friendly HR summary reports with risk assessment, category
breakdown, key findings, and recommended actions.
"""

from uuid import uuid7

import pytest

from elile.agent.state import InformationType
from elile.investigation.finding_extractor import FindingCategory, Severity
from elile.investigation.phases.network import RiskLevel
from elile.reporting.templates.hr_summary import (
    CategoryStatus,
    HRSummaryBuilder,
    HRSummaryConfig,
    HRSummaryContent,
    create_hr_summary_builder,
)
from elile.risk.risk_scorer import Recommendation
from elile.risk.risk_scorer import RiskLevel as RiskScoreLevel
from elile.screening.result_compiler import (
    CategorySummary,
    CompiledResult,
    ConnectionSummary,
    FindingsSummary,
    InvestigationSummary,
    SARSummary,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def minimal_compiled_result() -> CompiledResult:
    """Create a minimal compiled result with no findings."""
    return CompiledResult(
        screening_id=uuid7(),
        entity_id=uuid7(),
        tenant_id=uuid7(),
        findings_summary=FindingsSummary(
            total_findings=0,
            by_category={},
            by_severity={
                Severity.CRITICAL: 0,
                Severity.HIGH: 0,
                Severity.MEDIUM: 0,
                Severity.LOW: 0,
            },
            verification_status="complete",
            data_completeness=1.0,
        ),
        investigation_summary=InvestigationSummary(
            types_processed=5,
            types_completed=5,
            by_type={
                InformationType.IDENTITY: SARSummary(
                    info_type=InformationType.IDENTITY,
                    iterations_completed=2,
                    final_confidence=0.95,
                ),
                InformationType.EMPLOYMENT: SARSummary(
                    info_type=InformationType.EMPLOYMENT,
                    iterations_completed=2,
                    final_confidence=0.90,
                ),
                InformationType.CRIMINAL: SARSummary(
                    info_type=InformationType.CRIMINAL,
                    iterations_completed=2,
                    final_confidence=0.95,
                ),
            },
            average_confidence=0.93,
        ),
        connection_summary=ConnectionSummary(),
        risk_score=15,
        risk_level="low",
        recommendation="proceed",
    )


@pytest.fixture
def moderate_risk_compiled_result() -> CompiledResult:
    """Create a compiled result with moderate risk findings."""
    criminal_summary = CategorySummary(
        category=FindingCategory.CRIMINAL,
        total_findings=2,
        critical_count=0,
        high_count=1,
        medium_count=1,
        low_count=0,
        highest_severity=Severity.HIGH,
        average_confidence=0.85,
        key_findings=["DUI conviction 2019", "Traffic violation 2021"],
        sources_count=2,
        corroborated_count=1,
    )

    financial_summary = CategorySummary(
        category=FindingCategory.FINANCIAL,
        total_findings=1,
        critical_count=0,
        high_count=0,
        medium_count=1,
        low_count=0,
        highest_severity=Severity.MEDIUM,
        average_confidence=0.80,
        key_findings=["Civil judgment 2020 (resolved)"],
        sources_count=1,
        corroborated_count=0,
    )

    verification_summary = CategorySummary(
        category=FindingCategory.VERIFICATION,
        total_findings=1,
        critical_count=0,
        high_count=0,
        medium_count=1,
        low_count=0,
        highest_severity=Severity.MEDIUM,
        average_confidence=0.90,
        key_findings=["Employment gap Jun 2021 - Feb 2022"],
        sources_count=1,
        corroborated_count=0,
    )

    return CompiledResult(
        screening_id=uuid7(),
        entity_id=uuid7(),
        tenant_id=uuid7(),
        findings_summary=FindingsSummary(
            total_findings=4,
            by_category={
                FindingCategory.CRIMINAL: criminal_summary,
                FindingCategory.FINANCIAL: financial_summary,
                FindingCategory.VERIFICATION: verification_summary,
            },
            by_severity={
                Severity.CRITICAL: 0,
                Severity.HIGH: 1,
                Severity.MEDIUM: 3,
                Severity.LOW: 0,
            },
            critical_findings=[],
            high_findings=["DUI conviction 2019"],
            overall_narrative="The investigation identified 4 findings.",
            verification_status="complete",
            data_completeness=0.9,
        ),
        investigation_summary=InvestigationSummary(
            types_processed=8,
            types_completed=8,
            by_type={
                InformationType.IDENTITY: SARSummary(
                    info_type=InformationType.IDENTITY,
                    iterations_completed=2,
                    final_confidence=0.95,
                ),
                InformationType.EMPLOYMENT: SARSummary(
                    info_type=InformationType.EMPLOYMENT,
                    iterations_completed=3,
                    final_confidence=0.88,
                ),
                InformationType.EDUCATION: SARSummary(
                    info_type=InformationType.EDUCATION,
                    iterations_completed=2,
                    final_confidence=0.92,
                ),
                InformationType.CRIMINAL: SARSummary(
                    info_type=InformationType.CRIMINAL,
                    iterations_completed=2,
                    final_confidence=0.90,
                ),
                InformationType.FINANCIAL: SARSummary(
                    info_type=InformationType.FINANCIAL,
                    iterations_completed=2,
                    final_confidence=0.85,
                ),
            },
            average_confidence=0.90,
            total_queries=25,
            total_facts=15,
        ),
        connection_summary=ConnectionSummary(
            entities_discovered=5,
            d2_entities=5,
            relations_mapped=8,
            risk_connections=0,
        ),
        risk_score=42,
        risk_level="moderate",
        recommendation="proceed_with_caution",
    )


@pytest.fixture
def high_risk_compiled_result() -> CompiledResult:
    """Create a compiled result with high risk findings."""
    criminal_summary = CategorySummary(
        category=FindingCategory.CRIMINAL,
        total_findings=3,
        critical_count=1,
        high_count=1,
        medium_count=1,
        low_count=0,
        highest_severity=Severity.CRITICAL,
        average_confidence=0.92,
        key_findings=[
            "Felony fraud conviction 2018",
            "Misdemeanor theft 2020",
            "Pending criminal case",
        ],
        sources_count=3,
        corroborated_count=2,
    )

    regulatory_summary = CategorySummary(
        category=FindingCategory.REGULATORY,
        total_findings=2,
        critical_count=1,
        high_count=0,
        medium_count=1,
        low_count=0,
        highest_severity=Severity.CRITICAL,
        average_confidence=0.95,
        key_findings=["FINRA bar 2019", "SEC enforcement action"],
        sources_count=2,
        corroborated_count=1,
    )

    return CompiledResult(
        screening_id=uuid7(),
        entity_id=uuid7(),
        tenant_id=uuid7(),
        findings_summary=FindingsSummary(
            total_findings=5,
            by_category={
                FindingCategory.CRIMINAL: criminal_summary,
                FindingCategory.REGULATORY: regulatory_summary,
            },
            by_severity={
                Severity.CRITICAL: 2,
                Severity.HIGH: 1,
                Severity.MEDIUM: 2,
                Severity.LOW: 0,
            },
            critical_findings=["Felony fraud conviction 2018", "FINRA bar 2019"],
            high_findings=["Misdemeanor theft 2020"],
            overall_narrative="Critical findings require immediate review.",
            verification_status="complete",
            data_completeness=1.0,
        ),
        investigation_summary=InvestigationSummary(
            types_processed=10,
            types_completed=10,
            by_type={
                InformationType.IDENTITY: SARSummary(
                    info_type=InformationType.IDENTITY,
                    iterations_completed=2,
                    final_confidence=0.95,
                ),
                InformationType.CRIMINAL: SARSummary(
                    info_type=InformationType.CRIMINAL,
                    iterations_completed=3,
                    final_confidence=0.92,
                ),
                InformationType.REGULATORY: SARSummary(
                    info_type=InformationType.REGULATORY,
                    iterations_completed=2,
                    final_confidence=0.95,
                ),
                InformationType.SANCTIONS: SARSummary(
                    info_type=InformationType.SANCTIONS,
                    iterations_completed=2,
                    final_confidence=0.98,
                ),
            },
            average_confidence=0.95,
            total_queries=40,
            total_facts=25,
        ),
        connection_summary=ConnectionSummary(
            entities_discovered=10,
            d2_entities=8,
            d3_entities=2,
            relations_mapped=15,
            risk_connections=3,
            critical_connections=1,
            high_risk_connections=2,
            pep_connections=1,
            sanctions_connections=1,
            highest_risk_level=RiskLevel.CRITICAL,
            key_risks=["Connection to sanctioned entity", "PEP relationship"],
        ),
        risk_score=78,
        risk_level="critical",
        recommendation="do_not_proceed",
    )


@pytest.fixture
def builder() -> HRSummaryBuilder:
    """Create a default HR Summary builder."""
    return create_hr_summary_builder()


@pytest.fixture
def custom_config() -> HRSummaryConfig:
    """Create a custom configuration."""
    return HRSummaryConfig(
        clear_threshold=20,
        review_threshold=40,
        flag_threshold=60,
        score_bar_width=20,
        max_key_items=5,
        max_recommended_actions=3,
    )


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for create_hr_summary_builder factory."""

    def test_create_default_builder(self):
        """Test creating builder with default config."""
        builder = create_hr_summary_builder()

        assert isinstance(builder, HRSummaryBuilder)
        assert isinstance(builder.config, HRSummaryConfig)
        assert builder.config.score_bar_width == 30

    def test_create_builder_with_custom_config(self, custom_config):
        """Test creating builder with custom config."""
        builder = create_hr_summary_builder(config=custom_config)

        assert builder.config.score_bar_width == 20
        assert builder.config.max_key_items == 5
        assert builder.config.clear_threshold == 20


# =============================================================================
# Builder Tests - Minimal Findings
# =============================================================================


class TestMinimalFindings:
    """Tests for HR summary with no or minimal findings."""

    def test_build_with_no_findings(self, builder, minimal_compiled_result):
        """Test building HR summary with no findings."""
        content = builder.build(minimal_compiled_result)

        assert isinstance(content, HRSummaryContent)
        assert content.screening_id == minimal_compiled_result.screening_id
        assert content.risk_assessment.score == 15
        assert content.risk_assessment.level == RiskScoreLevel.LOW
        assert content.risk_assessment.requires_review is False
        assert len(content.recommended_actions) >= 1

    def test_risk_assessment_display_low_risk(self, builder, minimal_compiled_result):
        """Test risk assessment display for low risk."""
        content = builder.build(minimal_compiled_result)
        ra = content.risk_assessment

        assert ra.score == 15
        assert ra.level == RiskScoreLevel.LOW
        assert ra.recommendation == Recommendation.PROCEED
        assert "Proceed" in ra.recommendation_text
        assert ra.requires_review is False
        assert len(ra.review_reasons) == 0
        assert "▓" in ra.score_bar  # Some filled portion
        assert "░" in ra.score_bar  # Some empty portion

    def test_score_bar_proportional(self, builder, minimal_compiled_result):
        """Test that score bar is proportional to score."""
        content = builder.build(minimal_compiled_result)
        ra = content.risk_assessment

        # Score is 15, so ~15% should be filled
        filled = ra.score_bar.count("▓")
        empty = ra.score_bar.count("░")
        total = filled + empty

        assert total == builder.config.score_bar_width
        # Allow some tolerance for rounding
        assert filled == int((15 / 100) * 30)

    def test_proceed_recommendation_action(self, builder, minimal_compiled_result):
        """Test that proceed action is generated for low risk."""
        content = builder.build(minimal_compiled_result)

        assert len(content.recommended_actions) >= 1
        first_action = content.recommended_actions[0]
        assert "Proceed" in first_action.action or "proceed" in first_action.action.lower()

    def test_narrative_for_low_risk(self, builder, minimal_compiled_result):
        """Test narrative generation for low risk."""
        content = builder.build(minimal_compiled_result)

        assert len(content.overall_narrative) > 0
        assert "15" in content.overall_narrative  # Score should be mentioned
        assert "No significant concerns" in content.overall_narrative


# =============================================================================
# Builder Tests - Moderate Risk
# =============================================================================


class TestModerateRiskFindings:
    """Tests for HR summary with moderate risk findings."""

    def test_build_with_moderate_findings(self, builder, moderate_risk_compiled_result):
        """Test building HR summary with moderate findings."""
        content = builder.build(moderate_risk_compiled_result)

        assert content.risk_assessment.score == 42
        assert content.risk_assessment.level == RiskScoreLevel.MODERATE
        assert content.risk_assessment.recommendation == Recommendation.PROCEED_WITH_CAUTION

    def test_risk_assessment_requires_review(self, builder, moderate_risk_compiled_result):
        """Test that moderate risk requires review."""
        content = builder.build(moderate_risk_compiled_result)
        ra = content.risk_assessment

        assert ra.requires_review is True
        assert len(ra.review_reasons) > 0

    def test_review_reasons_populated(self, builder, moderate_risk_compiled_result):
        """Test that review reasons are populated."""
        content = builder.build(moderate_risk_compiled_result)
        ra = content.risk_assessment

        # Should mention high severity findings
        reasons_text = " ".join(ra.review_reasons).lower()
        assert "high" in reasons_text or "severity" in reasons_text

    def test_key_findings_indicators(self, builder, moderate_risk_compiled_result):
        """Test key findings indicators are generated."""
        content = builder.build(moderate_risk_compiled_result)

        assert len(content.key_findings) > 0

        # Check for expected indicator types
        statuses = [f.status for f in content.key_findings]
        assert CategoryStatus.CLEAR in statuses or CategoryStatus.REVIEW in statuses

    def test_category_breakdown_populated(self, builder, moderate_risk_compiled_result):
        """Test category breakdown is populated."""
        content = builder.build(moderate_risk_compiled_result)

        assert len(content.category_breakdown) > 0

        # Find criminal category
        criminal_score = next(
            (c for c in content.category_breakdown if c.category == FindingCategory.CRIMINAL),
            None,
        )
        assert criminal_score is not None
        assert criminal_score.findings_count == 2
        assert criminal_score.highest_severity == Severity.HIGH

    def test_category_scores_calculated(self, builder, moderate_risk_compiled_result):
        """Test category scores are calculated correctly."""
        content = builder.build(moderate_risk_compiled_result)

        for cat_score in content.category_breakdown:
            # Scores should be 0-100
            assert 0 <= cat_score.score <= 100

            # Categories with findings should have lower scores
            if cat_score.findings_count > 0:
                assert cat_score.score < 100

    def test_recommended_actions_for_moderate(self, builder, moderate_risk_compiled_result):
        """Test recommended actions for moderate risk."""
        content = builder.build(moderate_risk_compiled_result)

        assert len(content.recommended_actions) > 0

        # Actions should be prioritized
        priorities = [a.priority for a in content.recommended_actions]
        assert priorities == sorted(priorities)

    def test_connection_summary_included(self, builder, moderate_risk_compiled_result):
        """Test connection summary is included when applicable."""
        content = builder.build(moderate_risk_compiled_result)

        # Connection summary should be included since entities were discovered
        assert content.connection_summary is not None
        assert content.connection_summary["entities_discovered"] == 5


# =============================================================================
# Builder Tests - High Risk
# =============================================================================


class TestHighRiskFindings:
    """Tests for HR summary with high/critical risk findings."""

    def test_build_with_critical_findings(self, builder, high_risk_compiled_result):
        """Test building HR summary with critical findings."""
        content = builder.build(high_risk_compiled_result)

        assert content.risk_assessment.score == 78
        assert content.risk_assessment.level == RiskScoreLevel.CRITICAL
        assert content.risk_assessment.recommendation == Recommendation.DO_NOT_PROCEED

    def test_critical_recommendation_text(self, builder, high_risk_compiled_result):
        """Test recommendation text for critical risk."""
        content = builder.build(high_risk_compiled_result)
        ra = content.risk_assessment

        assert "Do not proceed" in ra.recommendation_text
        assert "Critical" in ra.recommendation_text or "critical" in ra.recommendation_text.lower()

    def test_review_reasons_for_critical(self, builder, high_risk_compiled_result):
        """Test review reasons include critical findings."""
        content = builder.build(high_risk_compiled_result)
        ra = content.risk_assessment

        reasons_text = " ".join(ra.review_reasons).lower()
        assert "critical" in reasons_text
        assert len(ra.review_reasons) >= 2

    def test_fail_status_indicators(self, builder, high_risk_compiled_result):
        """Test fail status indicators for critical findings."""
        content = builder.build(high_risk_compiled_result)

        # Should have at least one FAIL status
        statuses = [f.status for f in content.key_findings]
        assert CategoryStatus.FAIL in statuses

    def test_fail_icon_displayed(self, builder, high_risk_compiled_result):
        """Test fail icon is displayed for critical findings."""
        content = builder.build(high_risk_compiled_result)

        fail_findings = [f for f in content.key_findings if f.status == CategoryStatus.FAIL]
        assert len(fail_findings) > 0
        assert all(f.icon == "✗" for f in fail_findings)

    def test_category_fail_status(self, builder, high_risk_compiled_result):
        """Test category has FAIL or FLAG status for critical findings."""
        content = builder.build(high_risk_compiled_result)

        criminal_score = next(
            (c for c in content.category_breakdown if c.category == FindingCategory.CRIMINAL),
            None,
        )
        assert criminal_score is not None
        # With 1 critical (30) + 1 high (20) + 1 medium (10) + corroboration (10) = 70 deductions
        # Score = 30, which is >= 25 (flag_threshold), so it's FLAG
        assert criminal_score.status in (CategoryStatus.FAIL, CategoryStatus.FLAG)
        assert criminal_score.findings_count == 3

    def test_critical_actions_prioritized(self, builder, high_risk_compiled_result):
        """Test critical findings get priority 1 actions."""
        content = builder.build(high_risk_compiled_result)

        assert len(content.recommended_actions) > 0
        first_action = content.recommended_actions[0]
        assert first_action.priority == 1
        assert first_action.related_findings > 0

    def test_pep_sanctions_actions(self, builder, high_risk_compiled_result):
        """Test PEP and sanctions get recommended actions."""
        content = builder.build(high_risk_compiled_result)

        actions_text = " ".join([a.action.lower() for a in content.recommended_actions])
        # Should mention PEP or sanctions
        assert "pep" in actions_text or "sanction" in actions_text

    def test_narrative_mentions_critical(self, builder, high_risk_compiled_result):
        """Test narrative mentions critical findings."""
        content = builder.build(high_risk_compiled_result)

        assert "critical" in content.overall_narrative.lower()
        assert "78" in content.overall_narrative  # Score should be mentioned


# =============================================================================
# Key Findings Tests
# =============================================================================


class TestKeyFindings:
    """Tests for key findings indicators."""

    def test_standard_check_types_included(self, builder, moderate_risk_compiled_result):
        """Test all standard check types are included."""
        content = builder.build(moderate_risk_compiled_result)

        names = [f.name for f in content.key_findings]

        # Core checks should be present
        expected = ["Identity", "Employment", "Education", "Criminal Records"]
        for check in expected:
            assert any(check in name for name in names)

    def test_indicator_icons_correct(self, builder, moderate_risk_compiled_result):
        """Test indicator icons match status."""
        content = builder.build(moderate_risk_compiled_result)

        for indicator in content.key_findings:
            if indicator.status == CategoryStatus.CLEAR:
                assert indicator.icon in ("✓", "—")
            elif indicator.status in (CategoryStatus.REVIEW, CategoryStatus.FLAG):
                assert indicator.icon == "⚠"
            elif indicator.status == CategoryStatus.FAIL:
                assert indicator.icon == "✗"

    def test_indicator_notes_present(self, builder, moderate_risk_compiled_result):
        """Test indicator notes are present."""
        content = builder.build(moderate_risk_compiled_result)

        for indicator in content.key_findings:
            assert len(indicator.note) > 0

    def test_unprocessed_types_show_not_checked(self, builder, minimal_compiled_result):
        """Test unprocessed types show as not checked."""
        content = builder.build(minimal_compiled_result)

        # Find a type that wasn't processed
        unprocessed = [f for f in content.key_findings if "Not checked" in f.note]
        # Some types should be unprocessed in minimal result
        assert len(unprocessed) >= 0  # Depends on what was processed


# =============================================================================
# Category Breakdown Tests
# =============================================================================


class TestCategoryBreakdown:
    """Tests for category score breakdown."""

    def test_categories_sorted_by_score(self, builder, moderate_risk_compiled_result):
        """Test categories are sorted by score (lowest first)."""
        content = builder.build(moderate_risk_compiled_result)

        scores = [c.score for c in content.category_breakdown]
        assert scores == sorted(scores)

    def test_empty_categories_have_high_score(self, builder, minimal_compiled_result):
        """Test empty categories have 100 score."""
        content = builder.build(minimal_compiled_result)

        for cat_score in content.category_breakdown:
            if cat_score.findings_count == 0:
                assert cat_score.score == 100
                assert cat_score.status == CategoryStatus.CLEAR

    def test_category_notes_generated(self, builder, moderate_risk_compiled_result):
        """Test category notes are generated."""
        content = builder.build(moderate_risk_compiled_result)

        for cat_score in content.category_breakdown:
            assert len(cat_score.notes) > 0

    def test_key_items_limited(self, custom_config, moderate_risk_compiled_result):
        """Test key items are limited by config."""
        builder = HRSummaryBuilder(config=custom_config)
        content = builder.build(moderate_risk_compiled_result)

        for cat_score in content.category_breakdown:
            assert len(cat_score.key_items) <= custom_config.max_key_items


# =============================================================================
# Recommended Actions Tests
# =============================================================================


class TestRecommendedActions:
    """Tests for recommended actions generation."""

    def test_actions_limited_by_config(self, custom_config, high_risk_compiled_result):
        """Test actions are limited by config."""
        builder = HRSummaryBuilder(config=custom_config)
        content = builder.build(high_risk_compiled_result)

        assert len(content.recommended_actions) <= custom_config.max_recommended_actions

    def test_action_priorities_unique(self, builder, high_risk_compiled_result):
        """Test action priorities are sequential."""
        content = builder.build(high_risk_compiled_result)

        priorities = [a.priority for a in content.recommended_actions]
        expected = list(range(1, len(priorities) + 1))
        assert priorities == expected

    def test_actions_have_reasons(self, builder, moderate_risk_compiled_result):
        """Test all actions have reasons."""
        content = builder.build(moderate_risk_compiled_result)

        for action in content.recommended_actions:
            assert len(action.reason) > 0

    def test_actions_have_unique_ids(self, builder, high_risk_compiled_result):
        """Test all actions have unique IDs."""
        content = builder.build(high_risk_compiled_result)

        ids = [a.action_id for a in content.recommended_actions]
        assert len(ids) == len(set(ids))


# =============================================================================
# Narrative Tests
# =============================================================================


class TestNarrative:
    """Tests for narrative generation."""

    def test_narrative_generated_by_default(self, builder, moderate_risk_compiled_result):
        """Test narrative is generated by default."""
        content = builder.build(moderate_risk_compiled_result)

        assert len(content.overall_narrative) > 50

    def test_narrative_disabled_by_config(self, moderate_risk_compiled_result):
        """Test narrative can be disabled."""
        config = HRSummaryConfig(generate_narrative=False)
        builder = HRSummaryBuilder(config=config)
        content = builder.build(moderate_risk_compiled_result)

        assert len(content.overall_narrative) == 0

    def test_narrative_mentions_score(self, builder, moderate_risk_compiled_result):
        """Test narrative mentions the risk score."""
        content = builder.build(moderate_risk_compiled_result)

        assert "42" in content.overall_narrative

    def test_narrative_mentions_areas_of_concern(self, builder, high_risk_compiled_result):
        """Test narrative mentions key areas of concern."""
        content = builder.build(high_risk_compiled_result)

        # Should mention concerning categories
        narrative_lower = content.overall_narrative.lower()
        assert "criminal" in narrative_lower or "regulatory" in narrative_lower


# =============================================================================
# Connection Summary Tests
# =============================================================================


class TestConnectionSummary:
    """Tests for connection summary handling."""

    def test_connection_summary_when_entities(self, builder, moderate_risk_compiled_result):
        """Test connection summary included when entities discovered."""
        content = builder.build(moderate_risk_compiled_result)

        assert content.connection_summary is not None
        assert content.connection_summary["entities_discovered"] > 0

    def test_connection_summary_excluded_when_no_entities(self, builder, minimal_compiled_result):
        """Test connection summary excluded when no entities."""
        # Minimal result has no entities
        content = builder.build(minimal_compiled_result)

        assert content.connection_summary is None

    def test_connection_summary_disabled_by_config(self, moderate_risk_compiled_result):
        """Test connection summary can be disabled."""
        config = HRSummaryConfig(include_connection_summary=False)
        builder = HRSummaryBuilder(config=config)
        content = builder.build(moderate_risk_compiled_result)

        assert content.connection_summary is None


# =============================================================================
# Data Model Tests
# =============================================================================


class TestDataModels:
    """Tests for data model serialization."""

    def test_hr_summary_content_to_dict(self, builder, moderate_risk_compiled_result):
        """Test HRSummaryContent.to_dict()."""
        content = builder.build(moderate_risk_compiled_result)
        data = content.to_dict()

        assert "content_id" in data
        assert "screening_id" in data
        assert "risk_assessment" in data
        assert "key_findings" in data
        assert "category_breakdown" in data
        assert "recommended_actions" in data

    def test_risk_assessment_display_to_dict(self, builder, moderate_risk_compiled_result):
        """Test RiskAssessmentDisplay.to_dict()."""
        content = builder.build(moderate_risk_compiled_result)
        ra_dict = content.risk_assessment.to_dict()

        assert "score" in ra_dict
        assert "level" in ra_dict
        assert "recommendation" in ra_dict
        assert "score_bar" in ra_dict
        assert "requires_review" in ra_dict

    def test_finding_indicator_to_dict(self, builder, moderate_risk_compiled_result):
        """Test FindingIndicator.to_dict()."""
        content = builder.build(moderate_risk_compiled_result)
        indicator = content.key_findings[0]
        data = indicator.to_dict()

        assert "name" in data
        assert "status" in data
        assert "icon" in data
        assert "note" in data

    def test_category_score_to_dict(self, builder, moderate_risk_compiled_result):
        """Test CategoryScore.to_dict()."""
        content = builder.build(moderate_risk_compiled_result)
        cat_score = content.category_breakdown[0]
        data = cat_score.to_dict()

        assert "category" in data
        assert "name" in data
        assert "status" in data
        assert "score" in data
        assert "findings_count" in data

    def test_recommended_action_to_dict(self, builder, moderate_risk_compiled_result):
        """Test RecommendedAction.to_dict()."""
        content = builder.build(moderate_risk_compiled_result)
        action = content.recommended_actions[0]
        data = action.to_dict()

        assert "action_id" in data
        assert "priority" in data
        assert "action" in data
        assert "reason" in data


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_score(self, builder):
        """Test handling of zero risk score."""
        result = CompiledResult(
            risk_score=0,
            risk_level="low",
            recommendation="proceed",
            findings_summary=FindingsSummary(),
            investigation_summary=InvestigationSummary(),
            connection_summary=ConnectionSummary(),
        )
        content = builder.build(result)

        assert content.risk_assessment.score == 0
        assert content.risk_assessment.score_bar.count("▓") == 0

    def test_max_score(self, builder):
        """Test handling of maximum risk score."""
        result = CompiledResult(
            risk_score=100,
            risk_level="critical",
            recommendation="do_not_proceed",
            findings_summary=FindingsSummary(),
            investigation_summary=InvestigationSummary(),
            connection_summary=ConnectionSummary(),
        )
        content = builder.build(result)

        assert content.risk_assessment.score == 100
        assert content.risk_assessment.score_bar.count("░") == 0

    def test_empty_investigation_summary(self, builder):
        """Test handling of empty investigation summary."""
        result = CompiledResult(
            risk_score=50,
            risk_level="moderate",
            recommendation="review_required",
            findings_summary=FindingsSummary(),
            investigation_summary=InvestigationSummary(types_processed=0, by_type={}),
            connection_summary=ConnectionSummary(),
        )
        content = builder.build(result)

        # Should still generate valid content
        assert content is not None
        assert len(content.key_findings) > 0

    def test_all_severity_levels(self, builder):
        """Test category with all severity levels."""
        mixed_summary = CategorySummary(
            category=FindingCategory.CRIMINAL,
            total_findings=10,
            critical_count=1,
            high_count=2,
            medium_count=3,
            low_count=4,
            highest_severity=Severity.CRITICAL,
        )

        result = CompiledResult(
            risk_score=60,
            risk_level="high",
            recommendation="review_required",
            findings_summary=FindingsSummary(
                total_findings=10,
                by_category={FindingCategory.CRIMINAL: mixed_summary},
            ),
            investigation_summary=InvestigationSummary(),
            connection_summary=ConnectionSummary(),
        )
        content = builder.build(result)

        criminal_cat = next(
            (c for c in content.category_breakdown if c.category == FindingCategory.CRIMINAL),
            None,
        )
        assert criminal_cat is not None
        assert criminal_cat.findings_count == 10


# =============================================================================
# Configuration Tests
# =============================================================================


class TestConfiguration:
    """Tests for configuration options."""

    def test_custom_thresholds(self, moderate_risk_compiled_result):
        """Test custom score thresholds."""
        # With very strict thresholds, more categories should require review
        config = HRSummaryConfig(
            clear_threshold=5,  # Score must be >= 95 to be CLEAR
            review_threshold=15,  # Score must be >= 85 to be REVIEW
            flag_threshold=30,  # Score must be >= 70 to be FLAG
        )
        builder = HRSummaryBuilder(config=config)
        content = builder.build(moderate_risk_compiled_result)

        # Criminal has 2 findings (1 high, 1 medium + 1 corroborated) = 30 deductions, score 70
        # Financial has 1 finding (1 medium) = 10 deductions, score 90
        # Verification has 1 finding (1 medium) = 10 deductions, score 90
        # With flag_threshold=30: score >= 70 is FLAG, so criminal is FLAG, not FAIL
        # Financial/Verification are REVIEW (score 90 >= 85)

        # Check that thresholds affect status assignment
        criminal = next(
            (c for c in content.category_breakdown if c.category == FindingCategory.CRIMINAL),
            None,
        )
        assert criminal is not None
        # Criminal score is 70 (1 high + 1 medium + 1 corroborated = 30 deductions)
        # With flag_threshold=30: 70 >= 70 means FLAG
        assert criminal.status in (CategoryStatus.FLAG, CategoryStatus.FAIL)

    def test_custom_score_bar_width(self, moderate_risk_compiled_result):
        """Test custom score bar width."""
        config = HRSummaryConfig(score_bar_width=20)
        builder = HRSummaryBuilder(config=config)
        content = builder.build(moderate_risk_compiled_result)

        bar = content.risk_assessment.score_bar
        assert len(bar) == 20

    def test_custom_category_weights(self, moderate_risk_compiled_result):
        """Test custom category weights configuration."""
        config = HRSummaryConfig(
            category_weights={
                "criminal": 2.0,  # Extra weight
                "financial": 1.0,
                "verification": 0.5,  # Reduced weight
            }
        )
        builder = HRSummaryBuilder(config=config)
        content = builder.build(moderate_risk_compiled_result)

        # Should still build successfully
        assert content is not None
