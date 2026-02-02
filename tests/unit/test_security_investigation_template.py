"""Unit tests for Security Investigation Report Content Builder.

Tests the SecurityInvestigationBuilder for generating Security Team
investigation reports with threat assessment, connection network,
detailed findings, and evolution signals.
"""

from datetime import UTC, datetime
from uuid import uuid7

import pytest

from elile.compliance.types import RoleCategory
from elile.investigation.finding_extractor import FindingCategory, Severity
from elile.investigation.phases.network import RiskLevel
from elile.reporting.templates.security_investigation import (
    ConnectionNetworkSection,
    DetailedFinding,
    DetailedFindingsSection,
    EvolutionSignal,
    EvolutionSignalsSection,
    EvolutionTrend,
    FindingsByCategory,
    NetworkEdge,
    NetworkNode,
    RiskPath,
    SecurityInvestigationBuilder,
    SecurityInvestigationConfig,
    SecurityInvestigationContent,
    SignalType,
    ThreatAssessmentSection,
    ThreatFactor,
    ThreatLevel,
    create_security_investigation_builder,
)
from elile.screening.result_compiler import (
    CategorySummary,
    CompiledResult,
    ConnectionSummary,
    FindingsSummary,
    InvestigationSummary,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_findings_summary() -> FindingsSummary:
    """Create a sample findings summary for testing."""
    return FindingsSummary(
        total_findings=5,
        by_category={
            FindingCategory.CRIMINAL: CategorySummary(
                category=FindingCategory.CRIMINAL,
                total_findings=2,
                critical_count=1,
                high_count=1,
                medium_count=0,
                low_count=0,
                highest_severity=Severity.CRITICAL,
                average_confidence=0.85,
                key_findings=["Felony conviction 2020", "DUI 2019"],
            ),
            FindingCategory.FINANCIAL: CategorySummary(
                category=FindingCategory.FINANCIAL,
                total_findings=1,
                critical_count=0,
                high_count=0,
                medium_count=1,
                low_count=0,
                highest_severity=Severity.MEDIUM,
                average_confidence=0.9,
                key_findings=["Resolved judgment"],
            ),
        },
        by_severity={
            Severity.CRITICAL: 1,
            Severity.HIGH: 1,
            Severity.MEDIUM: 1,
            Severity.LOW: 2,
        },
        critical_findings=["Felony conviction for theft in 2020"],
        high_findings=["DUI conviction in 2019", "Employment discrepancy"],
        overall_narrative="Subject has criminal history requiring review.",
    )


@pytest.fixture
def sample_connection_summary() -> ConnectionSummary:
    """Create a sample connection summary for testing."""
    return ConnectionSummary(
        entities_discovered=15,
        d2_entities=10,
        d3_entities=5,
        relations_mapped=20,
        risk_connections=3,
        high_risk_connections=2,
        pep_connections=1,
        sanctions_connections=0,
        shell_company_connections=0,
        highest_risk_level=RiskLevel.HIGH,
        risk_propagation_score=0.45,
        key_risks=[
            "Connected to PEP family member",
            "Business association with high-risk entity",
        ],
    )


@pytest.fixture
def sample_investigation_summary() -> InvestigationSummary:
    """Create a sample investigation summary for testing."""
    return InvestigationSummary(
        types_processed=8,
        types_completed=7,
        types_failed=1,
        total_queries=25,
        total_iterations=3,
    )


@pytest.fixture
def sample_compiled_result(
    sample_findings_summary: FindingsSummary,
    sample_connection_summary: ConnectionSummary,
    sample_investigation_summary: InvestigationSummary,
) -> CompiledResult:
    """Create a sample compiled result for testing."""
    return CompiledResult(
        screening_id=uuid7(),
        entity_id=uuid7(),
        tenant_id=uuid7(),
        findings_summary=sample_findings_summary,
        connection_summary=sample_connection_summary,
        investigation_summary=sample_investigation_summary,
        risk_score=65,
        risk_level="high",
        recommendation="review_required",
    )


@pytest.fixture
def builder() -> SecurityInvestigationBuilder:
    """Create a default builder."""
    return SecurityInvestigationBuilder()


# =============================================================================
# Test Data Models - Threat Assessment
# =============================================================================


class TestThreatFactor:
    """Tests for ThreatFactor dataclass."""

    def test_default_values(self) -> None:
        """Test ThreatFactor default values."""
        factor = ThreatFactor()
        assert factor.factor_type == "contributing"
        assert factor.category == ""
        assert factor.description == ""
        assert factor.severity == Severity.MEDIUM
        assert factor.confidence == 0.5
        assert factor.evidence == []

    def test_custom_values(self) -> None:
        """Test ThreatFactor with custom values."""
        factor = ThreatFactor(
            factor_type="mitigating",
            category="verification",
            description="Identity verified",
            severity=Severity.LOW,
            confidence=0.95,
            evidence=["SSN match", "DOB match"],
        )
        assert factor.factor_type == "mitigating"
        assert factor.category == "verification"
        assert factor.description == "Identity verified"
        assert factor.severity == Severity.LOW
        assert factor.confidence == 0.95
        assert len(factor.evidence) == 2

    def test_to_dict(self) -> None:
        """Test ThreatFactor serialization."""
        factor = ThreatFactor(
            category="criminal",
            description="Felony conviction",
            severity=Severity.CRITICAL,
        )
        d = factor.to_dict()
        assert d["category"] == "criminal"
        assert d["description"] == "Felony conviction"
        assert d["severity"] == "critical"
        assert "factor_id" in d


class TestThreatAssessmentSection:
    """Tests for ThreatAssessmentSection dataclass."""

    def test_default_values(self) -> None:
        """Test ThreatAssessmentSection default values."""
        section = ThreatAssessmentSection()
        assert section.threat_level == ThreatLevel.LOW
        assert section.threat_score == 0
        assert section.contributing_factors == []
        assert section.mitigating_factors == []
        assert section.primary_concerns == []
        assert section.recommended_actions == []

    def test_custom_values(self) -> None:
        """Test ThreatAssessmentSection with custom values."""
        contributing = [ThreatFactor(description="Issue 1")]
        mitigating = [ThreatFactor(factor_type="mitigating", description="Clear 1")]
        section = ThreatAssessmentSection(
            threat_level=ThreatLevel.HIGH,
            threat_score=75,
            contributing_factors=contributing,
            mitigating_factors=mitigating,
            primary_concerns=["Criminal history"],
            recommended_actions=["Enhanced monitoring"],
            assessment_confidence=0.85,
        )
        assert section.threat_level == ThreatLevel.HIGH
        assert section.threat_score == 75
        assert len(section.contributing_factors) == 1
        assert len(section.mitigating_factors) == 1
        assert section.assessment_confidence == 0.85

    def test_to_dict(self) -> None:
        """Test ThreatAssessmentSection serialization."""
        section = ThreatAssessmentSection(
            threat_level=ThreatLevel.ELEVATED,
            threat_score=55,
        )
        d = section.to_dict()
        assert d["threat_level"] == "elevated"
        assert d["threat_score"] == 55
        assert "section_id" in d


# =============================================================================
# Test Data Models - Connection Network
# =============================================================================


class TestNetworkNode:
    """Tests for NetworkNode dataclass."""

    def test_default_values(self) -> None:
        """Test NetworkNode default values."""
        node = NetworkNode()
        assert node.label == ""
        assert node.entity_type == "unknown"
        assert node.is_subject is False
        assert node.depth == 0
        assert node.risk_level == RiskLevel.NONE
        assert node.risk_score == 0.0
        assert node.risk_factors == []

    def test_subject_node(self) -> None:
        """Test creating a subject node."""
        node = NetworkNode(
            label="Subject",
            entity_type="individual",
            is_subject=True,
            depth=0,
        )
        assert node.is_subject is True
        assert node.depth == 0
        assert node.label == "Subject"

    def test_to_dict(self) -> None:
        """Test NetworkNode serialization."""
        node = NetworkNode(
            label="Entity 1",
            risk_level=RiskLevel.HIGH,
            risk_score=0.75,
        )
        d = node.to_dict()
        assert d["label"] == "Entity 1"
        assert d["risk_level"] == "high"
        assert d["risk_score"] == 0.75


class TestNetworkEdge:
    """Tests for NetworkEdge dataclass."""

    def test_default_values(self) -> None:
        """Test NetworkEdge default values."""
        edge = NetworkEdge()
        assert edge.source_id is None
        assert edge.target_id is None
        assert edge.is_current is True
        assert edge.risk_factor == 0.5

    def test_to_dict(self) -> None:
        """Test NetworkEdge serialization."""
        source = uuid7()
        target = uuid7()
        edge = NetworkEdge(
            source_id=source,
            target_id=target,
            risk_factor=0.8,
        )
        d = edge.to_dict()
        assert d["source_id"] == str(source)
        assert d["target_id"] == str(target)
        assert d["risk_factor"] == 0.8


class TestRiskPath:
    """Tests for RiskPath dataclass."""

    def test_default_values(self) -> None:
        """Test RiskPath default values."""
        path = RiskPath()
        assert path.source_entity == ""
        assert path.hops == 0
        assert path.propagated_risk == 0.0

    def test_custom_values(self) -> None:
        """Test RiskPath with custom values."""
        path = RiskPath(
            source_entity="Sanctioned Entity",
            source_risk_level=RiskLevel.CRITICAL,
            hops=2,
            propagated_risk=0.49,
            risk_type="sanctions_connection",
            description="Connection to sanctioned entity via intermediary",
        )
        assert path.source_entity == "Sanctioned Entity"
        assert path.source_risk_level == RiskLevel.CRITICAL
        assert path.hops == 2
        assert path.propagated_risk == 0.49


class TestConnectionNetworkSection:
    """Tests for ConnectionNetworkSection dataclass."""

    def test_default_values(self) -> None:
        """Test ConnectionNetworkSection default values."""
        section = ConnectionNetworkSection()
        assert section.nodes == []
        assert section.edges == []
        assert section.risk_paths == []
        assert section.total_entities == 0
        assert section.high_risk_connections == 0

    def test_to_dict(self) -> None:
        """Test ConnectionNetworkSection serialization."""
        section = ConnectionNetworkSection(
            total_entities=15,
            d2_entities=10,
            d3_entities=5,
            high_risk_connections=2,
            network_risk_score=0.45,
        )
        d = section.to_dict()
        assert d["total_entities"] == 15
        assert d["d2_entities"] == 10
        assert d["d3_entities"] == 5
        assert d["high_risk_connections"] == 2


# =============================================================================
# Test Data Models - Detailed Findings
# =============================================================================


class TestDetailedFinding:
    """Tests for DetailedFinding dataclass."""

    def test_default_values(self) -> None:
        """Test DetailedFinding default values."""
        finding = DetailedFinding()
        assert finding.category == FindingCategory.VERIFICATION
        assert finding.summary == ""
        assert finding.severity == Severity.LOW
        assert finding.confidence == 0.5
        assert finding.is_corroborated is False

    def test_custom_values(self) -> None:
        """Test DetailedFinding with custom values."""
        finding = DetailedFinding(
            category=FindingCategory.CRIMINAL,
            summary="Felony conviction",
            details="Grand theft in 2020",
            severity=Severity.CRITICAL,
            confidence=0.95,
            sources=["court_records", "criminal_db"],
            is_corroborated=True,
            relevance_to_role=0.9,
        )
        assert finding.category == FindingCategory.CRIMINAL
        assert finding.severity == Severity.CRITICAL
        assert finding.is_corroborated is True
        assert len(finding.sources) == 2

    def test_to_dict(self) -> None:
        """Test DetailedFinding serialization."""
        now = datetime.now(UTC)
        finding = DetailedFinding(
            category=FindingCategory.FINANCIAL,
            summary="Bankruptcy",
            severity=Severity.HIGH,
            date=now,
        )
        d = finding.to_dict()
        assert d["category"] == "financial"
        assert d["summary"] == "Bankruptcy"
        assert d["severity"] == "high"
        assert d["date"] == now.isoformat()


class TestFindingsByCategory:
    """Tests for FindingsByCategory dataclass."""

    def test_default_values(self) -> None:
        """Test FindingsByCategory default values."""
        findings = FindingsByCategory()
        assert findings.category == FindingCategory.VERIFICATION
        assert findings.findings == []
        assert findings.count == 0
        assert findings.critical_count == 0

    def test_with_findings(self) -> None:
        """Test FindingsByCategory with findings."""
        finding_list = [
            DetailedFinding(severity=Severity.CRITICAL),
            DetailedFinding(severity=Severity.HIGH),
        ]
        findings = FindingsByCategory(
            category=FindingCategory.CRIMINAL,
            findings=finding_list,
            count=2,
            critical_count=1,
            high_count=1,
            average_confidence=0.85,
        )
        assert findings.count == 2
        assert findings.critical_count == 1
        assert findings.high_count == 1


class TestDetailedFindingsSection:
    """Tests for DetailedFindingsSection dataclass."""

    def test_default_values(self) -> None:
        """Test DetailedFindingsSection default values."""
        section = DetailedFindingsSection()
        assert section.findings_by_category == []
        assert section.total_findings == 0
        assert section.critical_findings == 0

    def test_to_dict(self) -> None:
        """Test DetailedFindingsSection serialization."""
        section = DetailedFindingsSection(
            total_findings=10,
            critical_findings=2,
            high_findings=3,
            corroborated_findings=5,
        )
        d = section.to_dict()
        assert d["total_findings"] == 10
        assert d["critical_findings"] == 2
        assert d["high_findings"] == 3


# =============================================================================
# Test Data Models - Evolution Signals
# =============================================================================


class TestEvolutionSignal:
    """Tests for EvolutionSignal dataclass."""

    def test_default_values(self) -> None:
        """Test EvolutionSignal default values."""
        signal = EvolutionSignal()
        assert signal.signal_type == SignalType.NEW_FINDING
        assert signal.description == ""
        assert signal.change_magnitude == 0.0
        assert signal.significance == "low"

    def test_custom_values(self) -> None:
        """Test EvolutionSignal with custom values."""
        signal = EvolutionSignal(
            signal_type=SignalType.RISK_INCREASE,
            description="Risk score increased by 20 points",
            previous_value="45",
            current_value="65",
            change_magnitude=0.4,
            significance="high",
        )
        assert signal.signal_type == SignalType.RISK_INCREASE
        assert signal.change_magnitude == 0.4
        assert signal.significance == "high"

    def test_to_dict(self) -> None:
        """Test EvolutionSignal serialization."""
        signal = EvolutionSignal(
            signal_type=SignalType.THRESHOLD_BREACH,
            description="Crossed high threshold",
        )
        d = signal.to_dict()
        assert d["signal_type"] == "threshold_breach"


class TestEvolutionSignalsSection:
    """Tests for EvolutionSignalsSection dataclass."""

    def test_default_values(self) -> None:
        """Test EvolutionSignalsSection default values."""
        section = EvolutionSignalsSection()
        assert section.overall_trend == EvolutionTrend.STABLE
        assert section.signals == []
        assert section.baseline_score == 0
        assert section.requires_attention is False

    def test_deteriorating_trend(self) -> None:
        """Test EvolutionSignalsSection with deteriorating trend."""
        section = EvolutionSignalsSection(
            overall_trend=EvolutionTrend.DETERIORATING,
            baseline_score=40,
            current_score=65,
            score_change=25,
            high_significance_count=2,
            requires_attention=True,
        )
        assert section.overall_trend == EvolutionTrend.DETERIORATING
        assert section.score_change == 25
        assert section.requires_attention is True

    def test_to_dict(self) -> None:
        """Test EvolutionSignalsSection serialization."""
        section = EvolutionSignalsSection(
            overall_trend=EvolutionTrend.IMPROVING,
            score_change=-15,
        )
        d = section.to_dict()
        assert d["overall_trend"] == "improving"
        assert d["score_change"] == -15


# =============================================================================
# Test Security Investigation Content
# =============================================================================


class TestSecurityInvestigationContent:
    """Tests for SecurityInvestigationContent dataclass."""

    def test_default_values(self) -> None:
        """Test SecurityInvestigationContent default values."""
        content = SecurityInvestigationContent()
        assert content.screening_id is None
        assert content.summary == ""
        assert content.threat_assessment is not None
        assert content.connection_network is not None
        assert content.detailed_findings is not None
        assert content.evolution_signals is not None

    def test_with_ids(self) -> None:
        """Test SecurityInvestigationContent with IDs."""
        screening_id = uuid7()
        tenant_id = uuid7()
        entity_id = uuid7()
        content = SecurityInvestigationContent(
            screening_id=screening_id,
            tenant_id=tenant_id,
            entity_id=entity_id,
        )
        assert content.screening_id == screening_id
        assert content.tenant_id == tenant_id
        assert content.entity_id == entity_id

    def test_to_dict(self) -> None:
        """Test SecurityInvestigationContent serialization."""
        content = SecurityInvestigationContent(
            summary="High risk subject requiring review.",
        )
        d = content.to_dict()
        assert d["summary"] == "High risk subject requiring review."
        assert "content_id" in d
        assert "generated_at" in d
        assert "threat_assessment" in d
        assert "connection_network" in d
        assert "detailed_findings" in d
        assert "evolution_signals" in d


# =============================================================================
# Test Security Investigation Config
# =============================================================================


class TestSecurityInvestigationConfig:
    """Tests for SecurityInvestigationConfig."""

    def test_default_values(self) -> None:
        """Test default config values."""
        config = SecurityInvestigationConfig()
        assert config.max_findings == 100
        assert config.max_network_nodes == 50
        assert config.max_risk_paths == 20
        assert config.critical_threshold == 85
        assert config.high_threshold == 70
        assert config.elevated_threshold == 55

    def test_custom_values(self) -> None:
        """Test custom config values."""
        config = SecurityInvestigationConfig(
            max_findings=50,
            max_network_nodes=25,
            critical_threshold=90,
            include_raw_evidence=False,
        )
        assert config.max_findings == 50
        assert config.max_network_nodes == 25
        assert config.critical_threshold == 90
        assert config.include_raw_evidence is False

    def test_validation_bounds(self) -> None:
        """Test config validation bounds."""
        with pytest.raises(ValueError):
            SecurityInvestigationConfig(max_findings=5)  # Below minimum 10

        with pytest.raises(ValueError):
            SecurityInvestigationConfig(critical_threshold=150)  # Above 100


# =============================================================================
# Test Security Investigation Builder
# =============================================================================


class TestSecurityInvestigationBuilder:
    """Tests for SecurityInvestigationBuilder."""

    def test_initialization(self) -> None:
        """Test builder initialization."""
        builder = SecurityInvestigationBuilder()
        assert builder.config is not None
        assert builder.config.max_findings == 100

    def test_initialization_with_config(self) -> None:
        """Test builder initialization with config."""
        config = SecurityInvestigationConfig(max_findings=50)
        builder = SecurityInvestigationBuilder(config=config)
        assert builder.config.max_findings == 50

    def test_build_minimal_result(self) -> None:
        """Test building from minimal compiled result."""
        builder = SecurityInvestigationBuilder()
        result = CompiledResult()
        content = builder.build(result)

        assert content is not None
        assert content.threat_assessment.threat_level == ThreatLevel.MINIMAL
        assert content.threat_assessment.threat_score == 0
        assert len(content.connection_network.nodes) == 1  # Subject node
        assert content.detailed_findings.total_findings == 0

    def test_build_with_findings(
        self,
        sample_compiled_result: CompiledResult,
    ) -> None:
        """Test building from result with findings."""
        builder = SecurityInvestigationBuilder()
        content = builder.build(sample_compiled_result)

        assert content is not None
        assert content.threat_assessment.threat_score == 65
        assert content.threat_assessment.threat_level == ThreatLevel.ELEVATED
        assert content.detailed_findings.total_findings > 0

    def test_build_with_role_category(
        self,
        sample_compiled_result: CompiledResult,
    ) -> None:
        """Test building with specific role category."""
        builder = SecurityInvestigationBuilder()
        content = builder.build(
            sample_compiled_result,
            role_category=RoleCategory.GOVERNMENT,
        )

        # Should have role-specific recommendations
        actions = content.threat_assessment.recommended_actions
        assert any("regulatory" in a.lower() for a in actions)

    def test_build_with_baseline_score(
        self,
        sample_compiled_result: CompiledResult,
    ) -> None:
        """Test building with baseline score for evolution comparison."""
        builder = SecurityInvestigationBuilder()
        content = builder.build(
            sample_compiled_result,
            baseline_score=40,
        )

        # Should detect score change
        assert content.evolution_signals.baseline_score == 40
        assert content.evolution_signals.current_score == 65
        assert content.evolution_signals.score_change == 25
        assert content.evolution_signals.overall_trend == EvolutionTrend.DETERIORATING


class TestThreatLevelCalculation:
    """Tests for threat level calculation."""

    def test_critical_threshold(self) -> None:
        """Test critical threat level threshold."""
        builder = SecurityInvestigationBuilder()
        result = CompiledResult(risk_score=90)
        content = builder.build(result)
        assert content.threat_assessment.threat_level == ThreatLevel.CRITICAL

    def test_high_threshold(self) -> None:
        """Test high threat level threshold."""
        builder = SecurityInvestigationBuilder()
        result = CompiledResult(risk_score=75)
        content = builder.build(result)
        assert content.threat_assessment.threat_level == ThreatLevel.HIGH

    def test_elevated_threshold(self) -> None:
        """Test elevated threat level threshold."""
        builder = SecurityInvestigationBuilder()
        result = CompiledResult(risk_score=60)
        content = builder.build(result)
        assert content.threat_assessment.threat_level == ThreatLevel.ELEVATED

    def test_moderate_threshold(self) -> None:
        """Test moderate threat level threshold."""
        builder = SecurityInvestigationBuilder()
        result = CompiledResult(risk_score=45)
        content = builder.build(result)
        assert content.threat_assessment.threat_level == ThreatLevel.MODERATE

    def test_low_threshold(self) -> None:
        """Test low threat level threshold."""
        builder = SecurityInvestigationBuilder()
        result = CompiledResult(risk_score=25)
        content = builder.build(result)
        assert content.threat_assessment.threat_level == ThreatLevel.LOW

    def test_minimal_threshold(self) -> None:
        """Test minimal threat level threshold."""
        builder = SecurityInvestigationBuilder()
        result = CompiledResult(risk_score=10)
        content = builder.build(result)
        assert content.threat_assessment.threat_level == ThreatLevel.MINIMAL

    def test_custom_thresholds(self) -> None:
        """Test with custom threshold configuration."""
        config = SecurityInvestigationConfig(
            critical_threshold=95,
            high_threshold=80,
            elevated_threshold=60,
            moderate_threshold=40,
        )
        builder = SecurityInvestigationBuilder(config=config)
        result = CompiledResult(risk_score=85)
        content = builder.build(result)
        # With custom thresholds, 85 should be HIGH not CRITICAL
        assert content.threat_assessment.threat_level == ThreatLevel.HIGH


class TestConnectionNetworkBuilding:
    """Tests for connection network building."""

    def test_subject_node_always_included(self) -> None:
        """Test that subject node is always included."""
        builder = SecurityInvestigationBuilder()
        result = CompiledResult()
        content = builder.build(result)

        nodes = content.connection_network.nodes
        assert len(nodes) >= 1
        subject_nodes = [n for n in nodes if n.is_subject]
        assert len(subject_nodes) == 1
        assert subject_nodes[0].label == "Subject"

    def test_network_with_key_risks(
        self,
        sample_compiled_result: CompiledResult,
    ) -> None:
        """Test network building with key risks."""
        builder = SecurityInvestigationBuilder()
        content = builder.build(sample_compiled_result)

        network = content.connection_network
        assert network.total_entities == 15
        assert network.d2_entities == 10
        assert network.d3_entities == 5
        assert network.high_risk_connections == 2

    def test_risk_paths_generated(
        self,
        sample_compiled_result: CompiledResult,
    ) -> None:
        """Test that risk paths are generated from key risks."""
        builder = SecurityInvestigationBuilder()
        content = builder.build(sample_compiled_result)

        risk_paths = content.connection_network.risk_paths
        # Should have paths from key risks
        assert len(risk_paths) > 0


class TestEvolutionSignalsBuilding:
    """Tests for evolution signals building."""

    def test_first_screening_trend(self) -> None:
        """Test trend for first screening (no baseline)."""
        builder = SecurityInvestigationBuilder()
        result = CompiledResult(risk_score=50)
        content = builder.build(result, baseline_score=None)

        assert content.evolution_signals.overall_trend == EvolutionTrend.NEW_CONCERNS
        assert content.evolution_signals.baseline_score == 0

    def test_improving_trend(self) -> None:
        """Test improving trend detection."""
        builder = SecurityInvestigationBuilder()
        result = CompiledResult(risk_score=30)
        content = builder.build(result, baseline_score=60)

        assert content.evolution_signals.overall_trend == EvolutionTrend.IMPROVING
        assert content.evolution_signals.score_change == -30

    def test_deteriorating_trend(self) -> None:
        """Test deteriorating trend detection."""
        builder = SecurityInvestigationBuilder()
        result = CompiledResult(risk_score=70)
        content = builder.build(result, baseline_score=40)

        assert content.evolution_signals.overall_trend == EvolutionTrend.DETERIORATING
        assert content.evolution_signals.score_change == 30

    def test_stable_trend(self) -> None:
        """Test stable trend detection."""
        builder = SecurityInvestigationBuilder()
        result = CompiledResult(risk_score=52)
        content = builder.build(result, baseline_score=50)

        assert content.evolution_signals.overall_trend == EvolutionTrend.STABLE
        assert content.evolution_signals.score_change == 2

    def test_volatile_trend(self) -> None:
        """Test volatile trend detection (moderate change)."""
        builder = SecurityInvestigationBuilder()
        result = CompiledResult(risk_score=60)
        content = builder.build(result, baseline_score=50)

        assert content.evolution_signals.overall_trend == EvolutionTrend.VOLATILE
        assert content.evolution_signals.score_change == 10

    def test_requires_attention_flag(self) -> None:
        """Test requires_attention flag."""
        builder = SecurityInvestigationBuilder()
        # High score should require attention
        result = CompiledResult(risk_score=80)
        content = builder.build(result, baseline_score=40)

        assert content.evolution_signals.requires_attention is True


class TestSummaryGeneration:
    """Tests for summary generation."""

    def test_summary_includes_threat_level(
        self,
        sample_compiled_result: CompiledResult,
    ) -> None:
        """Test that summary includes threat level."""
        builder = SecurityInvestigationBuilder()
        content = builder.build(sample_compiled_result)

        assert "elevated" in content.summary.lower() or "threat" in content.summary.lower()

    def test_summary_includes_findings_count(
        self,
        sample_compiled_result: CompiledResult,
    ) -> None:
        """Test that summary includes findings information."""
        builder = SecurityInvestigationBuilder()
        content = builder.build(sample_compiled_result)

        # Summary should mention findings
        assert "finding" in content.summary.lower() or "investigation" in content.summary.lower()

    def test_summary_for_critical_threat(self) -> None:
        """Test summary for critical threat level."""
        builder = SecurityInvestigationBuilder()
        findings_summary = FindingsSummary(
            critical_findings=["Major security concern"],
        )
        result = CompiledResult(
            risk_score=90,
            findings_summary=findings_summary,
        )
        content = builder.build(result)

        assert "critical" in content.summary.lower()


# =============================================================================
# Test Factory Function
# =============================================================================


class TestFactoryFunction:
    """Tests for factory function."""

    def test_create_security_investigation_builder(self) -> None:
        """Test factory function creates builder."""
        builder = create_security_investigation_builder()
        assert builder is not None
        assert isinstance(builder, SecurityInvestigationBuilder)

    def test_create_with_config(self) -> None:
        """Test factory function with config."""
        config = SecurityInvestigationConfig(max_findings=50)
        builder = create_security_investigation_builder(config=config)
        assert builder.config.max_findings == 50


# =============================================================================
# Test Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_zero_risk_score(self) -> None:
        """Test with zero risk score."""
        builder = SecurityInvestigationBuilder()
        result = CompiledResult(risk_score=0)
        content = builder.build(result)

        assert content.threat_assessment.threat_score == 0
        assert content.threat_assessment.threat_level == ThreatLevel.MINIMAL

    def test_max_risk_score(self) -> None:
        """Test with maximum risk score."""
        builder = SecurityInvestigationBuilder()
        result = CompiledResult(risk_score=100)
        content = builder.build(result)

        assert content.threat_assessment.threat_score == 100
        assert content.threat_assessment.threat_level == ThreatLevel.CRITICAL

    def test_empty_findings_summary(self) -> None:
        """Test with empty findings summary."""
        builder = SecurityInvestigationBuilder()
        result = CompiledResult(findings_summary=FindingsSummary())
        content = builder.build(result)

        assert content.detailed_findings.total_findings == 0
        assert content.detailed_findings.critical_findings == 0

    def test_empty_connection_summary(self) -> None:
        """Test with empty connection summary."""
        builder = SecurityInvestigationBuilder()
        result = CompiledResult(connection_summary=ConnectionSummary())
        content = builder.build(result)

        # Should still have subject node
        assert len(content.connection_network.nodes) == 1
        assert content.connection_network.total_entities == 0

    def test_all_ids_preserved(self) -> None:
        """Test that all IDs are preserved in content."""
        builder = SecurityInvestigationBuilder()
        screening_id = uuid7()
        entity_id = uuid7()
        tenant_id = uuid7()
        result = CompiledResult(
            screening_id=screening_id,
            entity_id=entity_id,
            tenant_id=tenant_id,
        )
        content = builder.build(result)

        assert content.screening_id == screening_id
        assert content.entity_id == entity_id
        assert content.tenant_id == tenant_id
