"""Unit tests for the ResultCompiler.

Tests the ResultCompiler that aggregates SAR results, findings,
risk assessments, and connections into comprehensive screening results.
"""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from elile.agent.state import InformationType
from elile.investigation.finding_extractor import (
    DataSourceRef,
    Finding,
    FindingCategory,
    Severity,
)
from elile.investigation.models import CompletionReason, SARIterationState, SARTypeState
from elile.investigation.phases.network import (
    ConnectionStrength,
    DiscoveredEntity,
    EntityRelation,
    EntityType,
    RelationType,
    RiskConnection,
    RiskLevel,
)
from elile.risk.risk_aggregator import (
    AssessmentConfidence,
    ComprehensiveRiskAssessment,
    RiskAdjustment,
)
from elile.risk.risk_scorer import Recommendation
from elile.risk.risk_scorer import RiskLevel as RiskScoreLevel
from elile.screening.result_compiler import (
    INFO_TYPE_TO_CATEGORY,
    CategorySummary,
    CompiledResult,
    CompilerConfig,
    ConnectionSummary,
    FindingsSummary,
    InvestigationSummary,
    ResultCompiler,
    SARSummary,
    SummaryFormat,
    create_result_compiler,
)
from elile.screening.types import ScreeningPhaseResult, ScreeningStatus

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def compiler() -> ResultCompiler:
    """Create a default ResultCompiler."""
    return create_result_compiler()


@pytest.fixture
def sample_findings() -> list[Finding]:
    """Create sample findings for testing."""
    return [
        Finding(
            finding_type="felony_conviction",
            category=FindingCategory.CRIMINAL,
            summary="Felony conviction for fraud in 2019",
            details="Subject convicted of wire fraud in federal court.",
            severity=Severity.CRITICAL,
            confidence=0.95,
            relevance_to_role=0.9,
            corroborated=True,
            finding_date=date(2019, 5, 15),
            sources=[
                DataSourceRef(provider_id="sterling", provider_name="Sterling", query_type="criminal"),
            ],
        ),
        Finding(
            finding_type="dui_conviction",
            category=FindingCategory.CRIMINAL,
            summary="DUI conviction in 2021",
            details="Subject convicted of DUI in state court.",
            severity=Severity.HIGH,
            confidence=0.90,
            relevance_to_role=0.6,
            corroborated=False,
            finding_date=date(2021, 8, 20),
            sources=[
                DataSourceRef(provider_id="checkr", provider_name="Checkr", query_type="criminal"),
            ],
        ),
        Finding(
            finding_type="bankruptcy",
            category=FindingCategory.FINANCIAL,
            summary="Chapter 7 bankruptcy filed in 2020",
            details="Subject filed for Chapter 7 bankruptcy.",
            severity=Severity.MEDIUM,
            confidence=0.85,
            relevance_to_role=0.7,
            corroborated=True,
            finding_date=date(2020, 3, 10),
            sources=[
                DataSourceRef(provider_id="experian", provider_name="Experian", query_type="financial"),
                DataSourceRef(provider_id="transunion", provider_name="TransUnion", query_type="financial"),
            ],
        ),
        Finding(
            finding_type="license_revoked",
            category=FindingCategory.REGULATORY,
            summary="Professional license suspended",
            details="CPA license suspended for 6 months.",
            severity=Severity.HIGH,
            confidence=0.80,
            relevance_to_role=0.95,
            corroborated=False,
            finding_date=date(2022, 1, 5),
            sources=[
                DataSourceRef(provider_id="licenseverify", provider_name="LicenseVerify", query_type="regulatory"),
            ],
        ),
        Finding(
            finding_type="employment_gap",
            category=FindingCategory.VERIFICATION,
            summary="Unexplained 18-month employment gap",
            details="Gap in employment history from 2018-2019.",
            severity=Severity.LOW,
            confidence=0.70,
            relevance_to_role=0.4,
            corroborated=False,
            finding_date=None,
            sources=[
                DataSourceRef(provider_id="worknumber", provider_name="WorkNumber", query_type="employment"),
            ],
        ),
    ]


@pytest.fixture
def sample_sar_results() -> dict[InformationType, SARTypeState]:
    """Create sample SAR results for testing."""
    results: dict[InformationType, SARTypeState] = {}

    # Identity type - completed successfully
    identity_state = SARTypeState(info_type=InformationType.IDENTITY)
    identity_iter = SARIterationState(iteration_number=1)
    identity_iter.queries_executed = 3
    identity_iter.new_facts_this_iteration = 5
    identity_iter.confidence_score = 0.92
    identity_state.complete_iteration(identity_iter)  # Use proper method
    identity_state.completion_reason = CompletionReason.CONFIDENCE_MET
    identity_state.final_confidence = 0.92
    results[InformationType.IDENTITY] = identity_state

    # Criminal type - completed with max iterations
    criminal_state = SARTypeState(info_type=InformationType.CRIMINAL)
    for i in range(3):
        criminal_iter = SARIterationState(iteration_number=i + 1)
        criminal_iter.queries_executed = 5
        criminal_iter.new_facts_this_iteration = 3
        criminal_iter.confidence_score = 0.6 + (i * 0.1)
        criminal_state.complete_iteration(criminal_iter)  # Use proper method
    criminal_state.completion_reason = CompletionReason.MAX_ITERATIONS
    criminal_state.final_confidence = 0.80
    results[InformationType.CRIMINAL] = criminal_state

    # Financial type - completed with diminishing returns
    financial_state = SARTypeState(info_type=InformationType.FINANCIAL)
    financial_iter = SARIterationState(iteration_number=1)
    financial_iter.queries_executed = 4
    financial_iter.new_facts_this_iteration = 2
    financial_iter.confidence_score = 0.75
    financial_state.complete_iteration(financial_iter)  # Use proper method
    financial_state.completion_reason = CompletionReason.DIMINISHING_RETURNS
    financial_state.final_confidence = 0.75
    results[InformationType.FINANCIAL] = financial_state

    # Sanctions type - skipped
    sanctions_state = SARTypeState(info_type=InformationType.SANCTIONS)
    sanctions_state.completion_reason = CompletionReason.SKIPPED
    sanctions_state.final_confidence = 0.0
    results[InformationType.SANCTIONS] = sanctions_state

    return results


@pytest.fixture
def sample_risk_assessment() -> ComprehensiveRiskAssessment:
    """Create sample risk assessment for testing."""
    return ComprehensiveRiskAssessment(
        entity_id=uuid4(),
        screening_id=uuid4(),
        final_score=72,
        base_score=65,
        pre_cap_score=72.0,
        risk_level=RiskScoreLevel.HIGH,
        recommendation=Recommendation.REVIEW_REQUIRED,
        recommendation_reasons=[
            "3 high-severity finding(s)",
            "Behavioral patterns detected",
        ],
        adjustments={"patterns": 5.0, "anomalies": 2.0},
        adjustment_details=[
            RiskAdjustment(source="patterns", amount=5.0, reason="2 patterns detected"),
            RiskAdjustment(source="anomalies", amount=2.0, reason="1 anomaly detected"),
        ],
        total_adjustment=7.0,
        pattern_score=0.4,
        anomaly_score=0.2,
        network_score=0.0,
        deception_score=0.1,
        confidence_level=AssessmentConfidence.HIGH,
        confidence_factors=["Good finding coverage", "Pattern analysis completed"],
        critical_findings=1,
        high_findings=2,
        patterns_detected=2,
        anomalies_detected=1,
        risk_connections=0,
        summary="Overall risk score: 72/100 (high). Recommendation: Review Required",
        key_concerns=["CRITICAL: Felony conviction for fraud", "HIGH: DUI conviction"],
        mitigating_factors=[],
    )


@pytest.fixture
def sample_connections() -> list[DiscoveredEntity]:
    """Create sample discovered entities for testing."""
    return [
        DiscoveredEntity(
            entity_type=EntityType.COMPANY,
            name="Suspicious Holdings LLC",
            discovery_degree=2,
            is_sanctioned=False,
            is_pep=False,
            risk_indicators=["shell_company_indicator"],
            confidence=0.85,
        ),
        DiscoveredEntity(
            entity_type=EntityType.PERSON,
            name="John Associate",
            discovery_degree=2,
            is_sanctioned=False,
            is_pep=True,
            risk_indicators=["pep"],
            confidence=0.90,
        ),
        DiscoveredEntity(
            entity_type=EntityType.COMPANY,
            name="Sanctioned Corp",
            discovery_degree=3,
            is_sanctioned=True,
            is_pep=False,
            risk_indicators=["ofac_sanction"],
            confidence=0.95,
        ),
    ]


@pytest.fixture
def sample_relations() -> list[EntityRelation]:
    """Create sample entity relations for testing."""
    return [
        EntityRelation(
            relation_type=RelationType.OWNERSHIP,
            strength=ConnectionStrength.STRONG,
            confidence=0.85,
        ),
        EntityRelation(
            relation_type=RelationType.BUSINESS_PARTNER,
            strength=ConnectionStrength.MODERATE,
            confidence=0.75,
        ),
    ]


@pytest.fixture
def sample_risk_connections() -> list[RiskConnection]:
    """Create sample risk connections for testing."""
    return [
        RiskConnection(
            risk_level=RiskLevel.CRITICAL,
            risk_types=["sanctions_connection"],
            path_length=3,
            risk_factors=["Entity on OFAC list"],
            recommendations=["Terminate relationship"],
            requires_review=True,
            confidence=0.95,
            risk_category="sanctions",
            risk_description="Connected to sanctioned entity via 2-hop path",
        ),
        RiskConnection(
            risk_level=RiskLevel.HIGH,
            risk_types=["pep_connection"],
            path_length=2,
            risk_factors=["PEP relationship"],
            recommendations=["Enhanced due diligence"],
            requires_review=True,
            confidence=0.90,
            risk_category="pep",
            risk_description="Direct connection to PEP",
        ),
    ]


# =============================================================================
# Tests: Basic Compilation
# =============================================================================


class TestBasicCompilation:
    """Tests for basic result compilation."""

    def test_create_result_compiler(self):
        """Test factory function creates compiler."""
        compiler = create_result_compiler()
        assert compiler is not None
        assert isinstance(compiler.config, CompilerConfig)

    def test_create_with_config(self):
        """Test factory with custom config."""
        config = CompilerConfig(summary_format=SummaryFormat.DETAILED, max_key_findings=10)
        compiler = create_result_compiler(config)
        assert compiler.config.summary_format == SummaryFormat.DETAILED
        assert compiler.config.max_key_findings == 10

    def test_compile_empty_results(self, compiler: ResultCompiler):
        """Test compilation with empty inputs."""
        assessment = ComprehensiveRiskAssessment(final_score=0, risk_level=RiskScoreLevel.LOW)

        result = compiler.compile_results(
            sar_results={},
            findings=[],
            risk_assessment=assessment,
        )

        assert isinstance(result, CompiledResult)
        assert result.risk_score == 0
        assert result.findings_summary.total_findings == 0
        assert result.investigation_summary.types_processed == 0

    def test_compile_with_findings(
        self,
        compiler: ResultCompiler,
        sample_findings: list[Finding],
        sample_sar_results: dict[InformationType, SARTypeState],
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test compilation with findings."""
        result = compiler.compile_results(
            sar_results=sample_sar_results,
            findings=sample_findings,
            risk_assessment=sample_risk_assessment,
        )

        assert result.risk_score == 72
        assert result.risk_level == "high"
        assert result.recommendation == "review_required"
        assert result.findings_summary.total_findings == 5

    def test_compile_with_connections(
        self,
        compiler: ResultCompiler,
        sample_findings: list[Finding],
        sample_sar_results: dict[InformationType, SARTypeState],
        sample_risk_assessment: ComprehensiveRiskAssessment,
        sample_connections: list[DiscoveredEntity],
        sample_relations: list[EntityRelation],
        sample_risk_connections: list[RiskConnection],
    ):
        """Test compilation with network connections."""
        result = compiler.compile_results(
            sar_results=sample_sar_results,
            findings=sample_findings,
            risk_assessment=sample_risk_assessment,
            connections=sample_connections,
            relations=sample_relations,
            risk_connections=sample_risk_connections,
        )

        assert result.connection_summary.entities_discovered == 3
        assert result.connection_summary.d2_entities == 2
        assert result.connection_summary.d3_entities == 1
        assert result.connection_summary.pep_connections == 1
        assert result.connection_summary.sanctions_connections == 1

    def test_compile_with_ids(
        self,
        compiler: ResultCompiler,
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test compilation with screening/entity/tenant IDs."""
        screening_id = uuid4()
        entity_id = uuid4()
        tenant_id = uuid4()

        result = compiler.compile_results(
            sar_results={},
            findings=[],
            risk_assessment=sample_risk_assessment,
            screening_id=screening_id,
            entity_id=entity_id,
            tenant_id=tenant_id,
        )

        assert result.screening_id == screening_id
        assert result.entity_id == entity_id
        assert result.tenant_id == tenant_id


# =============================================================================
# Tests: Findings Summary
# =============================================================================


class TestFindingsSummary:
    """Tests for findings summary compilation."""

    def test_findings_by_category(
        self,
        compiler: ResultCompiler,
        sample_findings: list[Finding],
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test findings are grouped by category."""
        result = compiler.compile_results(
            sar_results={},
            findings=sample_findings,
            risk_assessment=sample_risk_assessment,
        )

        summary = result.findings_summary

        # Check criminal category
        assert FindingCategory.CRIMINAL in summary.by_category
        criminal = summary.by_category[FindingCategory.CRIMINAL]
        assert criminal.total_findings == 2
        assert criminal.critical_count == 1
        assert criminal.high_count == 1

    def test_findings_by_severity(
        self,
        compiler: ResultCompiler,
        sample_findings: list[Finding],
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test findings are counted by severity."""
        result = compiler.compile_results(
            sar_results={},
            findings=sample_findings,
            risk_assessment=sample_risk_assessment,
        )

        by_severity = result.findings_summary.by_severity
        assert by_severity[Severity.CRITICAL] == 1
        assert by_severity[Severity.HIGH] == 2
        assert by_severity[Severity.MEDIUM] == 1
        assert by_severity[Severity.LOW] == 1

    def test_critical_findings_extracted(
        self,
        compiler: ResultCompiler,
        sample_findings: list[Finding],
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test critical findings are extracted."""
        result = compiler.compile_results(
            sar_results={},
            findings=sample_findings,
            risk_assessment=sample_risk_assessment,
        )

        assert len(result.findings_summary.critical_findings) == 1
        assert "felony" in result.findings_summary.critical_findings[0].lower()

    def test_high_findings_extracted(
        self,
        compiler: ResultCompiler,
        sample_findings: list[Finding],
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test high severity findings are extracted."""
        result = compiler.compile_results(
            sar_results={},
            findings=sample_findings,
            risk_assessment=sample_risk_assessment,
        )

        assert len(result.findings_summary.high_findings) == 2

    def test_category_summary_key_findings(
        self,
        compiler: ResultCompiler,
        sample_findings: list[Finding],
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test key findings are included in category summary."""
        result = compiler.compile_results(
            sar_results={},
            findings=sample_findings,
            risk_assessment=sample_risk_assessment,
        )

        criminal = result.findings_summary.by_category[FindingCategory.CRIMINAL]
        assert len(criminal.key_findings) == 2
        # Should be sorted by severity (critical first)
        assert "felony" in criminal.key_findings[0].lower()

    def test_category_summary_sources_count(
        self,
        compiler: ResultCompiler,
        sample_findings: list[Finding],
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test source counting in category summary."""
        result = compiler.compile_results(
            sar_results={},
            findings=sample_findings,
            risk_assessment=sample_risk_assessment,
        )

        financial = result.findings_summary.by_category[FindingCategory.FINANCIAL]
        assert financial.sources_count == 2  # experian and transunion

    def test_category_summary_corroboration(
        self,
        compiler: ResultCompiler,
        sample_findings: list[Finding],
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test corroboration counting."""
        result = compiler.compile_results(
            sar_results={},
            findings=sample_findings,
            risk_assessment=sample_risk_assessment,
        )

        # Financial finding is corroborated
        financial = result.findings_summary.by_category[FindingCategory.FINANCIAL]
        assert financial.corroborated_count == 1

    def test_confidence_filtering(
        self,
        compiler: ResultCompiler,
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test low confidence findings are filtered."""
        config = CompilerConfig(min_finding_confidence=0.8)
        compiler = ResultCompiler(config)

        findings = [
            Finding(
                category=FindingCategory.CRIMINAL,
                summary="High confidence finding",
                severity=Severity.HIGH,
                confidence=0.9,
            ),
            Finding(
                category=FindingCategory.CRIMINAL,
                summary="Low confidence finding",
                severity=Severity.HIGH,
                confidence=0.5,  # Below threshold
            ),
        ]

        result = compiler.compile_results(
            sar_results={},
            findings=findings,
            risk_assessment=sample_risk_assessment,
        )

        assert result.findings_summary.total_findings == 1

    def test_narrative_generation(
        self,
        compiler: ResultCompiler,
        sample_findings: list[Finding],
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test narrative is generated."""
        result = compiler.compile_results(
            sar_results={},
            findings=sample_findings,
            risk_assessment=sample_risk_assessment,
        )

        narrative = result.findings_summary.overall_narrative
        assert narrative != ""
        assert "5 findings" in narrative or "critical" in narrative.lower()

    def test_narrative_disabled(
        self,
        sample_findings: list[Finding],
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test narrative can be disabled."""
        config = CompilerConfig(include_narrative=False)
        compiler = ResultCompiler(config)

        result = compiler.compile_results(
            sar_results={},
            findings=sample_findings,
            risk_assessment=sample_risk_assessment,
        )

        assert result.findings_summary.overall_narrative == ""

    def test_empty_findings_narrative(
        self, compiler: ResultCompiler, sample_risk_assessment: ComprehensiveRiskAssessment
    ):
        """Test narrative for no findings."""
        result = compiler.compile_results(
            sar_results={},
            findings=[],
            risk_assessment=sample_risk_assessment,
        )

        narrative = result.findings_summary.overall_narrative
        assert "no adverse findings" in narrative.lower()


# =============================================================================
# Tests: Investigation Summary
# =============================================================================


class TestInvestigationSummary:
    """Tests for investigation summary compilation."""

    def test_investigation_summary_types(
        self,
        compiler: ResultCompiler,
        sample_sar_results: dict[InformationType, SARTypeState],
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test investigation summary captures type counts."""
        result = compiler.compile_results(
            sar_results=sample_sar_results,
            findings=[],
            risk_assessment=sample_risk_assessment,
        )

        summary = result.investigation_summary
        assert summary.types_processed == 4
        assert summary.types_completed == 3  # identity, criminal, financial
        assert summary.types_skipped == 1  # sanctions

    def test_investigation_summary_totals(
        self,
        compiler: ResultCompiler,
        sample_sar_results: dict[InformationType, SARTypeState],
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test investigation summary calculates totals."""
        result = compiler.compile_results(
            sar_results=sample_sar_results,
            findings=[],
            risk_assessment=sample_risk_assessment,
        )

        summary = result.investigation_summary
        # identity: 1 iter, criminal: 3 iter, financial: 1 iter, sanctions: 0
        assert summary.total_iterations == 5
        # identity: 3, criminal: 15, financial: 4
        assert summary.total_queries == 22
        # identity: 5, criminal: 9, financial: 2
        assert summary.total_facts == 16

    def test_investigation_summary_confidence(
        self,
        compiler: ResultCompiler,
        sample_sar_results: dict[InformationType, SARTypeState],
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test average confidence calculation."""
        result = compiler.compile_results(
            sar_results=sample_sar_results,
            findings=[],
            risk_assessment=sample_risk_assessment,
        )

        summary = result.investigation_summary
        # Average of 0.92, 0.80, 0.75 (excluding skipped)
        expected_avg = (0.92 + 0.80 + 0.75) / 3
        assert abs(summary.average_confidence - expected_avg) < 0.01

    def test_lowest_confidence_type(
        self,
        compiler: ResultCompiler,
        sample_sar_results: dict[InformationType, SARTypeState],
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test lowest confidence type is identified."""
        result = compiler.compile_results(
            sar_results=sample_sar_results,
            findings=[],
            risk_assessment=sample_risk_assessment,
        )

        summary = result.investigation_summary
        assert summary.lowest_confidence_type == InformationType.FINANCIAL

    def test_per_type_summary(
        self,
        compiler: ResultCompiler,
        sample_sar_results: dict[InformationType, SARTypeState],
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test per-type summaries are created."""
        result = compiler.compile_results(
            sar_results=sample_sar_results,
            findings=[],
            risk_assessment=sample_risk_assessment,
        )

        summary = result.investigation_summary
        assert InformationType.IDENTITY in summary.by_type

        identity = summary.by_type[InformationType.IDENTITY]
        assert identity.iterations_completed == 1
        assert identity.final_confidence == 0.92
        assert identity.completion_reason == CompletionReason.CONFIDENCE_MET


# =============================================================================
# Tests: Connection Summary
# =============================================================================


class TestConnectionSummary:
    """Tests for connection summary compilation."""

    def test_connection_summary_counts(
        self,
        compiler: ResultCompiler,
        sample_connections: list[DiscoveredEntity],
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test connection counts are correct."""
        result = compiler.compile_results(
            sar_results={},
            findings=[],
            risk_assessment=sample_risk_assessment,
            connections=sample_connections,
        )

        summary = result.connection_summary
        assert summary.entities_discovered == 3
        assert summary.d2_entities == 2
        assert summary.d3_entities == 1

    def test_connection_summary_special_types(
        self,
        compiler: ResultCompiler,
        sample_connections: list[DiscoveredEntity],
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test special connection types are counted."""
        result = compiler.compile_results(
            sar_results={},
            findings=[],
            risk_assessment=sample_risk_assessment,
            connections=sample_connections,
        )

        summary = result.connection_summary
        assert summary.pep_connections == 1
        assert summary.sanctions_connections == 1

    def test_connection_summary_risk_levels(
        self,
        compiler: ResultCompiler,
        sample_connections: list[DiscoveredEntity],
        sample_risk_connections: list[RiskConnection],
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test risk connection levels are counted."""
        result = compiler.compile_results(
            sar_results={},
            findings=[],
            risk_assessment=sample_risk_assessment,
            connections=sample_connections,  # Need connections for summary to work
            risk_connections=sample_risk_connections,
        )

        summary = result.connection_summary
        assert summary.risk_connections == 2
        assert summary.critical_connections == 1
        assert summary.high_risk_connections == 1
        assert summary.highest_risk_level == RiskLevel.CRITICAL

    def test_connection_summary_key_risks(
        self,
        compiler: ResultCompiler,
        sample_connections: list[DiscoveredEntity],
        sample_risk_connections: list[RiskConnection],
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test key risks are extracted."""
        result = compiler.compile_results(
            sar_results={},
            findings=[],
            risk_assessment=sample_risk_assessment,
            connections=sample_connections,  # Need connections for summary to work
            risk_connections=sample_risk_connections,
        )

        summary = result.connection_summary
        assert len(summary.key_risks) == 2

    def test_empty_connections(
        self, compiler: ResultCompiler, sample_risk_assessment: ComprehensiveRiskAssessment
    ):
        """Test handling of empty connections."""
        result = compiler.compile_results(
            sar_results={},
            findings=[],
            risk_assessment=sample_risk_assessment,
            connections=[],
        )

        summary = result.connection_summary
        assert summary.entities_discovered == 0
        assert summary.highest_risk_level == RiskLevel.NONE


# =============================================================================
# Tests: Screening Result Conversion
# =============================================================================


class TestScreeningResultConversion:
    """Tests for converting to ScreeningResult."""

    def test_to_screening_result(
        self,
        compiler: ResultCompiler,
        sample_findings: list[Finding],
        sample_sar_results: dict[InformationType, SARTypeState],
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test conversion to ScreeningResult."""
        screening_id = uuid4()

        compiled = compiler.compile_results(
            sar_results=sample_sar_results,
            findings=sample_findings,
            risk_assessment=sample_risk_assessment,
        )

        result = compiler.to_screening_result(
            compiled=compiled,
            screening_id=screening_id,
            status=ScreeningStatus.COMPLETE,
        )

        assert result.screening_id == screening_id
        assert result.status == ScreeningStatus.COMPLETE
        assert result.risk_score == 72
        assert result.risk_level == "high"
        assert result.recommendation == "review_required"
        assert result.findings_count == 5
        assert result.critical_findings == 1
        assert result.high_findings == 2

    def test_to_screening_result_with_phases(
        self,
        compiler: ResultCompiler,
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test conversion with phase results."""
        screening_id = uuid4()
        phases = [
            ScreeningPhaseResult(phase_name="validation", status="complete"),
            ScreeningPhaseResult(phase_name="investigation", status="complete"),
        ]

        compiled = compiler.compile_results(
            sar_results={},
            findings=[],
            risk_assessment=sample_risk_assessment,
        )

        result = compiler.to_screening_result(
            compiled=compiled,
            screening_id=screening_id,
            phases=phases,
        )

        assert len(result.phases) == 2

    def test_to_screening_result_timing(
        self,
        compiler: ResultCompiler,
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test conversion with timing info."""
        screening_id = uuid4()
        started = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        completed = datetime(2024, 1, 1, 10, 5, 0, tzinfo=UTC)

        compiled = compiler.compile_results(
            sar_results={},
            findings=[],
            risk_assessment=sample_risk_assessment,
        )

        result = compiler.to_screening_result(
            compiled=compiled,
            screening_id=screening_id,
            started_at=started,
            completed_at=completed,
        )

        assert result.started_at == started
        assert result.completed_at == completed
        assert result.duration_seconds == 300.0  # 5 minutes


# =============================================================================
# Tests: Data Models
# =============================================================================


class TestDataModels:
    """Tests for data model serialization."""

    def test_category_summary_to_dict(self):
        """Test CategorySummary serialization."""
        summary = CategorySummary(
            category=FindingCategory.CRIMINAL,
            total_findings=5,
            critical_count=1,
            highest_severity=Severity.CRITICAL,
            average_confidence=0.85,
            key_findings=["Finding 1", "Finding 2"],
        )

        data = summary.to_dict()
        assert data["category"] == "criminal"
        assert data["total_findings"] == 5
        assert data["highest_severity"] == "critical"

    def test_findings_summary_to_dict(self):
        """Test FindingsSummary serialization."""
        summary = FindingsSummary(
            total_findings=10,
            overall_narrative="Test narrative",
        )

        data = summary.to_dict()
        assert data["total_findings"] == 10
        assert "summary_id" in data

    def test_investigation_summary_to_dict(self):
        """Test InvestigationSummary serialization."""
        summary = InvestigationSummary(
            types_processed=5,
            types_completed=4,
            total_iterations=10,
        )

        data = summary.to_dict()
        assert data["types_processed"] == 5
        assert data["types_completed"] == 4

    def test_connection_summary_to_dict(self):
        """Test ConnectionSummary serialization."""
        summary = ConnectionSummary(
            entities_discovered=10,
            risk_connections=2,
            highest_risk_level=RiskLevel.HIGH,
        )

        data = summary.to_dict()
        assert data["entities_discovered"] == 10
        assert data["highest_risk_level"] == "high"

    def test_compiled_result_to_dict(
        self,
        compiler: ResultCompiler,
        sample_findings: list[Finding],
        sample_risk_assessment: ComprehensiveRiskAssessment,
    ):
        """Test CompiledResult serialization."""
        result = compiler.compile_results(
            sar_results={},
            findings=sample_findings,
            risk_assessment=sample_risk_assessment,
        )

        data = result.to_dict()
        assert "result_id" in data
        assert "findings_summary" in data
        assert "investigation_summary" in data
        assert "connection_summary" in data
        assert data["risk_score"] == 72


# =============================================================================
# Tests: Info Type to Category Mapping
# =============================================================================


class TestInfoTypeCategoryMapping:
    """Tests for information type to category mapping."""

    def test_criminal_maps_to_criminal(self):
        """Test criminal info type maps to criminal category."""
        assert INFO_TYPE_TO_CATEGORY[InformationType.CRIMINAL] == FindingCategory.CRIMINAL

    def test_financial_maps_to_financial(self):
        """Test financial info type maps to financial category."""
        assert INFO_TYPE_TO_CATEGORY[InformationType.FINANCIAL] == FindingCategory.FINANCIAL

    def test_identity_maps_to_verification(self):
        """Test identity info type maps to verification category."""
        assert INFO_TYPE_TO_CATEGORY[InformationType.IDENTITY] == FindingCategory.VERIFICATION

    def test_network_maps_to_network(self):
        """Test network info types map to network category."""
        assert INFO_TYPE_TO_CATEGORY[InformationType.NETWORK_D2] == FindingCategory.NETWORK
        assert INFO_TYPE_TO_CATEGORY[InformationType.NETWORK_D3] == FindingCategory.NETWORK

    def test_adverse_media_maps_to_reputation(self):
        """Test adverse media maps to reputation category."""
        assert INFO_TYPE_TO_CATEGORY[InformationType.ADVERSE_MEDIA] == FindingCategory.REPUTATION


# =============================================================================
# Tests: Configuration
# =============================================================================


class TestConfiguration:
    """Tests for compiler configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CompilerConfig()
        assert config.summary_format == SummaryFormat.STANDARD
        assert config.max_key_findings == 5
        assert config.include_narrative is True
        assert config.min_finding_confidence == 0.3

    def test_config_validation(self):
        """Test configuration validation."""
        # max_key_findings must be positive
        with pytest.raises(ValueError):
            CompilerConfig(max_key_findings=0)

        # min_finding_confidence must be 0-1
        with pytest.raises(ValueError):
            CompilerConfig(min_finding_confidence=1.5)

    def test_config_applied(self):
        """Test configuration is applied during compilation."""
        config = CompilerConfig(max_key_findings=2)
        compiler = ResultCompiler(config)

        findings = [
            Finding(category=FindingCategory.CRIMINAL, summary=f"Finding {i}", severity=Severity.HIGH, confidence=0.8)
            for i in range(5)
        ]

        assessment = ComprehensiveRiskAssessment(final_score=50, risk_level=RiskScoreLevel.MODERATE)

        result = compiler.compile_results(
            sar_results={},
            findings=findings,
            risk_assessment=assessment,
        )

        criminal = result.findings_summary.by_category[FindingCategory.CRIMINAL]
        assert len(criminal.key_findings) == 2  # Capped at config value


# =============================================================================
# Tests: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_findings_without_category(
        self, compiler: ResultCompiler, sample_risk_assessment: ComprehensiveRiskAssessment
    ):
        """Test handling findings without category."""
        findings = [
            Finding(
                summary="Finding without category",
                severity=Severity.MEDIUM,
                confidence=0.8,
                category=None,  # No category
            )
        ]

        result = compiler.compile_results(
            sar_results={},
            findings=findings,
            risk_assessment=sample_risk_assessment,
        )

        # Should default to VERIFICATION
        assert FindingCategory.VERIFICATION in result.findings_summary.by_category

    def test_findings_without_sources(
        self, compiler: ResultCompiler, sample_risk_assessment: ComprehensiveRiskAssessment
    ):
        """Test handling findings without sources."""
        findings = [
            Finding(
                category=FindingCategory.CRIMINAL,
                summary="Finding without sources",
                severity=Severity.HIGH,
                confidence=0.8,
                sources=[],  # No sources
            )
        ]

        result = compiler.compile_results(
            sar_results={},
            findings=findings,
            risk_assessment=sample_risk_assessment,
        )

        criminal = result.findings_summary.by_category[FindingCategory.CRIMINAL]
        assert criminal.sources_count == 0

    def test_sar_results_with_error(
        self, compiler: ResultCompiler, sample_risk_assessment: ComprehensiveRiskAssessment
    ):
        """Test handling SAR results with error completion."""
        error_state = SARTypeState(info_type=InformationType.CRIMINAL)
        error_state.completion_reason = CompletionReason.ERROR
        error_state.final_confidence = 0.0

        result = compiler.compile_results(
            sar_results={InformationType.CRIMINAL: error_state},
            findings=[],
            risk_assessment=sample_risk_assessment,
        )

        summary = result.investigation_summary
        assert summary.types_failed == 1

    def test_very_long_finding_summary(
        self, compiler: ResultCompiler, sample_risk_assessment: ComprehensiveRiskAssessment
    ):
        """Test handling very long finding summaries."""
        long_summary = "A" * 500  # Very long summary
        findings = [
            Finding(
                category=FindingCategory.CRIMINAL,
                summary=long_summary,
                severity=Severity.CRITICAL,
                confidence=0.9,
            )
        ]

        result = compiler.compile_results(
            sar_results={},
            findings=findings,
            risk_assessment=sample_risk_assessment,
        )

        # Critical findings should be truncated
        assert len(result.findings_summary.critical_findings[0]) <= 100

    def test_all_low_severity_findings(
        self, compiler: ResultCompiler, sample_risk_assessment: ComprehensiveRiskAssessment
    ):
        """Test handling all low severity findings."""
        findings = [
            Finding(
                category=FindingCategory.VERIFICATION,
                summary=f"Low finding {i}",
                severity=Severity.LOW,
                confidence=0.7,
            )
            for i in range(3)
        ]

        result = compiler.compile_results(
            sar_results={},
            findings=findings,
            risk_assessment=sample_risk_assessment,
        )

        assert len(result.findings_summary.critical_findings) == 0
        assert len(result.findings_summary.high_findings) == 0
        assert result.findings_summary.by_severity[Severity.LOW] == 3


# =============================================================================
# Tests: SAR Summary Model
# =============================================================================


class TestSARSummaryModel:
    """Tests for SARSummary data model."""

    def test_sar_summary_to_dict(self):
        """Test SARSummary serialization."""
        summary = SARSummary(
            info_type=InformationType.CRIMINAL,
            iterations_completed=3,
            final_confidence=0.85,
            queries_executed=15,
            facts_extracted=10,
            completion_reason=CompletionReason.CONFIDENCE_MET,
            duration_ms=5000.0,
            findings_count=5,
        )

        data = summary.to_dict()
        assert data["info_type"] == "criminal"
        assert data["iterations_completed"] == 3
        assert data["final_confidence"] == 0.85
        assert data["completion_reason"] == "confidence_met"
