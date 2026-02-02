"""Security Team Investigation Report Content Builder.

This module provides the SecurityInvestigationBuilder for generating Security
Team investigation reports with threat assessment, connection network,
detailed findings, and evolution signals.

Architecture Reference: docs/architecture/08-reporting.md - Security Investigation Report

Note: Due to circular imports in the elile package structure, direct import
via `python -c "from elile.reporting.templates import ..."` may fail.
Imports work correctly in the test environment and application context.
The circular import involves: core.context -> agent.state -> agent.graph ->
agent.nodes -> risk -> core.logging -> core.context
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.compliance.types import RoleCategory
from elile.core.logging import get_logger
from elile.investigation.finding_extractor import FindingCategory, Severity
from elile.investigation.phases.network import ConnectionStrength, RelationType, RiskLevel
from elile.screening.result_compiler import CompiledResult

logger = get_logger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class ThreatLevel(str, Enum):
    """Overall insider threat assessment level."""

    MINIMAL = "minimal"  # Very low likelihood of insider threat
    LOW = "low"  # Low likelihood, standard monitoring
    MODERATE = "moderate"  # Moderate risk, enhanced monitoring recommended
    ELEVATED = "elevated"  # Elevated risk, active monitoring required
    HIGH = "high"  # High risk, immediate review required
    CRITICAL = "critical"  # Critical risk, immediate action required


class EvolutionTrend(str, Enum):
    """Direction of risk evolution."""

    IMPROVING = "improving"  # Risk decreasing over time
    STABLE = "stable"  # Risk unchanged
    DETERIORATING = "deteriorating"  # Risk increasing over time
    VOLATILE = "volatile"  # Risk fluctuating unpredictably
    NEW_CONCERNS = "new_concerns"  # New risk factors emerged


class SignalType(str, Enum):
    """Types of evolution signals."""

    RISK_INCREASE = "risk_increase"
    RISK_DECREASE = "risk_decrease"
    NEW_FINDING = "new_finding"
    RESOLVED_FINDING = "resolved_finding"
    BEHAVIOR_CHANGE = "behavior_change"
    NETWORK_CHANGE = "network_change"
    CATEGORY_CHANGE = "category_change"
    THRESHOLD_BREACH = "threshold_breach"


# Threat level thresholds based on risk score
THREAT_LEVEL_THRESHOLDS = {
    ThreatLevel.CRITICAL: 85,
    ThreatLevel.HIGH: 70,
    ThreatLevel.ELEVATED: 55,
    ThreatLevel.MODERATE: 40,
    ThreatLevel.LOW: 20,
    ThreatLevel.MINIMAL: 0,
}


# =============================================================================
# Data Models - Threat Assessment
# =============================================================================


@dataclass
class ThreatFactor:
    """A factor contributing to or mitigating threat assessment.

    Attributes:
        factor_id: Unique identifier.
        factor_type: Whether this is contributing or mitigating.
        category: Category of the factor (e.g., "criminal", "behavioral").
        description: Human-readable description.
        severity: Impact severity.
        confidence: Confidence in this assessment.
        evidence: Supporting evidence.
    """

    factor_id: UUID = field(default_factory=uuid7)
    factor_type: str = "contributing"  # contributing | mitigating
    category: str = ""
    description: str = ""
    severity: Severity = Severity.MEDIUM
    confidence: float = 0.5
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "factor_id": str(self.factor_id),
            "factor_type": self.factor_type,
            "category": self.category,
            "description": self.description,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


@dataclass
class ThreatAssessmentSection:
    """Threat assessment section of the security report.

    Attributes:
        section_id: Unique identifier.
        threat_level: Overall threat level.
        threat_score: Numeric threat score (0-100).
        contributing_factors: Factors that increase threat.
        mitigating_factors: Factors that reduce threat.
        primary_concerns: Top concern areas.
        recommended_actions: Suggested actions.
        assessment_confidence: Confidence in assessment.
        assessment_notes: Additional notes.
    """

    section_id: UUID = field(default_factory=uuid7)
    threat_level: ThreatLevel = ThreatLevel.LOW
    threat_score: int = 0
    contributing_factors: list[ThreatFactor] = field(default_factory=list)
    mitigating_factors: list[ThreatFactor] = field(default_factory=list)
    primary_concerns: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    assessment_confidence: float = 0.5
    assessment_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "section_id": str(self.section_id),
            "threat_level": self.threat_level.value,
            "threat_score": self.threat_score,
            "contributing_factors": [f.to_dict() for f in self.contributing_factors],
            "mitigating_factors": [f.to_dict() for f in self.mitigating_factors],
            "primary_concerns": self.primary_concerns,
            "recommended_actions": self.recommended_actions,
            "assessment_confidence": self.assessment_confidence,
            "assessment_notes": self.assessment_notes,
        }


# =============================================================================
# Data Models - Connection Network
# =============================================================================


@dataclass
class NetworkNode:
    """A node in the connection network visualization.

    Attributes:
        node_id: Unique node identifier.
        entity_id: Entity ID if applicable.
        label: Display label.
        entity_type: Type of entity (person, organization, etc.).
        is_subject: Whether this is the screening subject.
        depth: Distance from subject (0=subject, 1=direct, etc.).
        risk_level: Risk level of this node.
        risk_score: Numeric risk score.
        risk_factors: Factors contributing to risk.
    """

    node_id: UUID = field(default_factory=uuid7)
    entity_id: UUID | None = None
    label: str = ""
    entity_type: str = "unknown"
    is_subject: bool = False
    depth: int = 0
    risk_level: RiskLevel = RiskLevel.NONE
    risk_score: float = 0.0
    risk_factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for visualization."""
        return {
            "node_id": str(self.node_id),
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "label": self.label,
            "entity_type": self.entity_type,
            "is_subject": self.is_subject,
            "depth": self.depth,
            "risk_level": self.risk_level.value,
            "risk_score": self.risk_score,
            "risk_factors": self.risk_factors,
        }


@dataclass
class NetworkEdge:
    """An edge in the connection network visualization.

    Attributes:
        edge_id: Unique edge identifier.
        source_id: Source node ID.
        target_id: Target node ID.
        relation_type: Type of relationship.
        strength: Connection strength.
        is_current: Whether relationship is current.
        risk_factor: Risk transmission factor.
    """

    edge_id: UUID = field(default_factory=uuid7)
    source_id: UUID | None = None
    target_id: UUID | None = None
    relation_type: RelationType = RelationType.OTHER
    strength: ConnectionStrength = ConnectionStrength.MODERATE
    is_current: bool = True
    risk_factor: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for visualization."""
        return {
            "edge_id": str(self.edge_id),
            "source_id": str(self.source_id) if self.source_id else None,
            "target_id": str(self.target_id) if self.target_id else None,
            "relation_type": self.relation_type.value,
            "strength": self.strength.value,
            "is_current": self.is_current,
            "risk_factor": self.risk_factor,
        }


@dataclass
class RiskPath:
    """A path through which risk propagates to the subject.

    Attributes:
        path_id: Unique identifier.
        source_entity: Description of risk source.
        source_risk_level: Risk level at source.
        hops: Number of hops to subject.
        propagated_risk: Risk score reaching subject.
        risk_type: Type of risk.
        description: Path description.
    """

    path_id: UUID = field(default_factory=uuid7)
    source_entity: str = ""
    source_risk_level: RiskLevel = RiskLevel.NONE
    hops: int = 0
    propagated_risk: float = 0.0
    risk_type: str = ""
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path_id": str(self.path_id),
            "source_entity": self.source_entity,
            "source_risk_level": self.source_risk_level.value,
            "hops": self.hops,
            "propagated_risk": self.propagated_risk,
            "risk_type": self.risk_type,
            "description": self.description,
        }


@dataclass
class ConnectionNetworkSection:
    """Connection network section of the security report.

    Attributes:
        section_id: Unique identifier.
        nodes: Network nodes for visualization.
        edges: Network edges for visualization.
        risk_paths: Paths through which risk propagates.
        total_entities: Total entities in network.
        d2_entities: Count of direct (D2) connections.
        d3_entities: Count of extended (D3) connections.
        high_risk_connections: Count of high-risk connections.
        network_risk_score: Aggregate network risk score.
        centrality_score: Subject's network centrality.
    """

    section_id: UUID = field(default_factory=uuid7)
    nodes: list[NetworkNode] = field(default_factory=list)
    edges: list[NetworkEdge] = field(default_factory=list)
    risk_paths: list[RiskPath] = field(default_factory=list)
    total_entities: int = 0
    d2_entities: int = 0
    d3_entities: int = 0
    high_risk_connections: int = 0
    network_risk_score: float = 0.0
    centrality_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "section_id": str(self.section_id),
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "risk_paths": [p.to_dict() for p in self.risk_paths],
            "total_entities": self.total_entities,
            "d2_entities": self.d2_entities,
            "d3_entities": self.d3_entities,
            "high_risk_connections": self.high_risk_connections,
            "network_risk_score": self.network_risk_score,
            "centrality_score": self.centrality_score,
        }


# =============================================================================
# Data Models - Detailed Findings
# =============================================================================


@dataclass
class DetailedFinding:
    """A detailed finding with full context.

    Attributes:
        finding_id: Unique identifier.
        category: Finding category.
        summary: Brief summary.
        details: Full details.
        severity: Finding severity.
        confidence: Confidence in finding.
        sources: Data sources.
        date: Finding date if applicable.
        is_corroborated: Whether confirmed by multiple sources.
        relevance_to_role: Relevance to position.
        evidence: Supporting evidence.
        related_entities: Related entity IDs.
    """

    finding_id: UUID = field(default_factory=uuid7)
    category: FindingCategory = FindingCategory.VERIFICATION
    summary: str = ""
    details: str = ""
    severity: Severity = Severity.LOW
    confidence: float = 0.5
    sources: list[str] = field(default_factory=list)
    date: datetime | None = None
    is_corroborated: bool = False
    relevance_to_role: float = 0.5
    evidence: list[str] = field(default_factory=list)
    related_entities: list[UUID] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "finding_id": str(self.finding_id),
            "category": self.category.value,
            "summary": self.summary,
            "details": self.details,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "sources": self.sources,
            "date": self.date.isoformat() if self.date else None,
            "is_corroborated": self.is_corroborated,
            "relevance_to_role": self.relevance_to_role,
            "evidence": self.evidence,
            "related_entities": [str(e) for e in self.related_entities],
        }


@dataclass
class FindingsByCategory:
    """Findings grouped by category with statistics.

    Attributes:
        category: Finding category.
        findings: List of findings in this category.
        count: Total count.
        critical_count: Count of critical findings.
        high_count: Count of high severity findings.
        average_confidence: Average confidence.
    """

    category: FindingCategory = FindingCategory.VERIFICATION
    findings: list[DetailedFinding] = field(default_factory=list)
    count: int = 0
    critical_count: int = 0
    high_count: int = 0
    average_confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "findings": [f.to_dict() for f in self.findings],
            "count": self.count,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "average_confidence": self.average_confidence,
        }


@dataclass
class DetailedFindingsSection:
    """Detailed findings section of the security report.

    Attributes:
        section_id: Unique identifier.
        findings_by_category: Findings organized by category.
        total_findings: Total finding count.
        critical_findings: Critical finding count.
        high_findings: High severity count.
        corroborated_findings: Corroborated finding count.
        findings_list: Flat list of all findings.
    """

    section_id: UUID = field(default_factory=uuid7)
    findings_by_category: list[FindingsByCategory] = field(default_factory=list)
    total_findings: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    corroborated_findings: int = 0
    findings_list: list[DetailedFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "section_id": str(self.section_id),
            "findings_by_category": [c.to_dict() for c in self.findings_by_category],
            "total_findings": self.total_findings,
            "critical_findings": self.critical_findings,
            "high_findings": self.high_findings,
            "corroborated_findings": self.corroborated_findings,
        }


# =============================================================================
# Data Models - Evolution Signals
# =============================================================================


@dataclass
class EvolutionSignal:
    """A signal indicating change in risk profile.

    Attributes:
        signal_id: Unique identifier.
        signal_type: Type of signal.
        description: Description of the change.
        detected_at: When signal was detected.
        previous_value: Previous state/value.
        current_value: Current state/value.
        change_magnitude: Magnitude of change (0.0-1.0).
        significance: How significant is this change.
        related_findings: Related finding IDs.
    """

    signal_id: UUID = field(default_factory=uuid7)
    signal_type: SignalType = SignalType.NEW_FINDING
    description: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    previous_value: str = ""
    current_value: str = ""
    change_magnitude: float = 0.0
    significance: str = "low"  # low | medium | high
    related_findings: list[UUID] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "signal_id": str(self.signal_id),
            "signal_type": self.signal_type.value,
            "description": self.description,
            "detected_at": self.detected_at.isoformat(),
            "previous_value": self.previous_value,
            "current_value": self.current_value,
            "change_magnitude": self.change_magnitude,
            "significance": self.significance,
            "related_findings": [str(f) for f in self.related_findings],
        }


@dataclass
class EvolutionSignalsSection:
    """Evolution signals section of the security report.

    Attributes:
        section_id: Unique identifier.
        overall_trend: Overall risk trend.
        signals: List of evolution signals.
        baseline_score: Previous baseline score.
        current_score: Current score.
        score_change: Change in score.
        trend_period_days: Period over which trend is measured.
        high_significance_count: Count of high-significance signals.
        requires_attention: Whether evolution requires attention.
    """

    section_id: UUID = field(default_factory=uuid7)
    overall_trend: EvolutionTrend = EvolutionTrend.STABLE
    signals: list[EvolutionSignal] = field(default_factory=list)
    baseline_score: int = 0
    current_score: int = 0
    score_change: int = 0
    trend_period_days: int = 90
    high_significance_count: int = 0
    requires_attention: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "section_id": str(self.section_id),
            "overall_trend": self.overall_trend.value,
            "signals": [s.to_dict() for s in self.signals],
            "baseline_score": self.baseline_score,
            "current_score": self.current_score,
            "score_change": self.score_change,
            "trend_period_days": self.trend_period_days,
            "high_significance_count": self.high_significance_count,
            "requires_attention": self.requires_attention,
        }


# =============================================================================
# Complete Security Investigation Content
# =============================================================================


@dataclass
class SecurityInvestigationContent:
    """Complete Security Team investigation report content.

    This is the main output structure containing all sections
    of a Security Team investigation report.

    Attributes:
        content_id: Unique content identifier.
        screening_id: Reference to screening.
        tenant_id: Tenant that owns the screening.
        entity_id: Entity that was screened.
        generated_at: Generation timestamp.
        threat_assessment: Threat assessment section.
        connection_network: Connection network section.
        detailed_findings: Detailed findings section.
        evolution_signals: Evolution signals section.
        summary: Human-readable summary.
    """

    content_id: UUID = field(default_factory=uuid7)
    screening_id: UUID | None = None
    tenant_id: UUID | None = None
    entity_id: UUID | None = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Core sections
    threat_assessment: ThreatAssessmentSection = field(default_factory=ThreatAssessmentSection)
    connection_network: ConnectionNetworkSection = field(default_factory=ConnectionNetworkSection)
    detailed_findings: DetailedFindingsSection = field(default_factory=DetailedFindingsSection)
    evolution_signals: EvolutionSignalsSection = field(default_factory=EvolutionSignalsSection)

    # Summary
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content_id": str(self.content_id),
            "screening_id": str(self.screening_id) if self.screening_id else None,
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "generated_at": self.generated_at.isoformat(),
            "threat_assessment": self.threat_assessment.to_dict(),
            "connection_network": self.connection_network.to_dict(),
            "detailed_findings": self.detailed_findings.to_dict(),
            "evolution_signals": self.evolution_signals.to_dict(),
            "summary": self.summary,
        }


# =============================================================================
# Builder Configuration
# =============================================================================


class SecurityInvestigationConfig(BaseModel):
    """Configuration for SecurityInvestigationBuilder."""

    # Content settings
    max_findings: int = Field(default=100, ge=10, le=500, description="Max findings to include")
    max_network_nodes: int = Field(
        default=50, ge=5, le=200, description="Max network nodes to include"
    )
    max_risk_paths: int = Field(default=20, ge=5, le=100, description="Max risk paths to include")
    max_evolution_signals: int = Field(
        default=30, ge=5, le=100, description="Max evolution signals"
    )

    # Display settings
    include_raw_evidence: bool = Field(default=True, description="Include raw evidence in findings")
    include_related_entities: bool = Field(default=True, description="Include related entity IDs")
    include_network_visualization: bool = Field(
        default=True, description="Include network viz data"
    )

    # Threat level thresholds (can override defaults)
    critical_threshold: int = Field(default=85, ge=0, le=100)
    high_threshold: int = Field(default=70, ge=0, le=100)
    elevated_threshold: int = Field(default=55, ge=0, le=100)
    moderate_threshold: int = Field(default=40, ge=0, le=100)


# =============================================================================
# Security Investigation Builder
# =============================================================================


class SecurityInvestigationBuilder:
    """Builder for Security Team investigation report content.

    Transforms compiled screening results into comprehensive investigation
    documentation suitable for security teams and threat analysts.

    Example:
        ```python
        builder = SecurityInvestigationBuilder()

        # Build from compiled result
        content = builder.build(
            compiled_result=compiled,
            role_category=RoleCategory.EXECUTIVE,
        )

        # Access sections
        print(f"Threat Level: {content.threat_assessment.threat_level.value}")
        print(f"Network Nodes: {len(content.connection_network.nodes)}")
        print(f"Findings: {content.detailed_findings.total_findings}")
        ```

    Attributes:
        config: Builder configuration.
    """

    def __init__(self, config: SecurityInvestigationConfig | None = None) -> None:
        """Initialize the Security Investigation builder.

        Args:
            config: Builder configuration.
        """
        self.config = config or SecurityInvestigationConfig()

    def build(
        self,
        compiled_result: CompiledResult,
        role_category: RoleCategory = RoleCategory.STANDARD,
        baseline_score: int | None = None,
    ) -> SecurityInvestigationContent:
        """Build security investigation content from compiled screening result.

        Args:
            compiled_result: The compiled screening result.
            role_category: Role category for relevance scoring.
            baseline_score: Previous baseline score for evolution comparison.

        Returns:
            SecurityInvestigationContent with all sections populated.
        """
        logger.info(
            "Building security investigation content",
            screening_id=(
                str(compiled_result.screening_id) if compiled_result.screening_id else None
            ),
        )

        # Build each section
        threat_section = self._build_threat_assessment(compiled_result, role_category)
        network_section = self._build_connection_network(compiled_result)
        findings_section = self._build_detailed_findings(compiled_result, role_category)
        evolution_section = self._build_evolution_signals(compiled_result, baseline_score)

        # Generate summary
        summary = self._generate_summary(
            compiled_result, threat_section, network_section, findings_section
        )

        content = SecurityInvestigationContent(
            screening_id=compiled_result.screening_id,
            tenant_id=compiled_result.tenant_id,
            entity_id=compiled_result.entity_id,
            threat_assessment=threat_section,
            connection_network=network_section,
            detailed_findings=findings_section,
            evolution_signals=evolution_section,
            summary=summary,
        )

        logger.info(
            "Security investigation content built",
            content_id=str(content.content_id),
            threat_level=threat_section.threat_level.value,
            findings_count=findings_section.total_findings,
            network_nodes=len(network_section.nodes),
        )

        return content

    def _build_threat_assessment(
        self,
        compiled_result: CompiledResult,
        role_category: RoleCategory,
    ) -> ThreatAssessmentSection:
        """Build the threat assessment section.

        Args:
            compiled_result: The compiled screening result.
            role_category: Role category for context.

        Returns:
            ThreatAssessmentSection.
        """
        # Use risk score as basis for threat score
        threat_score = compiled_result.risk_score

        # Determine threat level based on thresholds
        threat_level = self._calculate_threat_level(threat_score)

        # Build contributing factors from findings summary
        contributing_factors: list[ThreatFactor] = []
        mitigating_factors: list[ThreatFactor] = []
        primary_concerns: list[str] = []

        findings_summary = compiled_result.findings_summary

        # Add critical findings as contributing factors
        for summary in findings_summary.critical_findings[: self.config.max_findings]:
            factor = ThreatFactor(
                category="critical",
                description=summary,
                severity=Severity.CRITICAL,
                confidence=0.8,
                evidence=[],
            )
            factor.factor_type = "contributing"
            contributing_factors.append(factor)
            if len(primary_concerns) < 5:
                primary_concerns.append(summary)

        # Add high severity findings as contributing factors
        for summary in findings_summary.high_findings[: self.config.max_findings]:
            factor = ThreatFactor(
                category="high",
                description=summary,
                severity=Severity.HIGH,
                confidence=0.7,
                evidence=[],
            )
            factor.factor_type = "contributing"
            contributing_factors.append(factor)
            if len(primary_concerns) < 5:
                primary_concerns.append(summary)

        # Add verified categories as mitigating factors
        for category, cat_summary in findings_summary.by_category.items():
            if cat_summary.total_findings == 0 or (
                cat_summary.critical_count == 0
                and cat_summary.high_count == 0
                and cat_summary.average_confidence >= 0.8
            ):
                mitigating_factors.append(
                    ThreatFactor(
                        factor_type="mitigating",
                        category=category.value,
                        description=f"Verified: {category.value} - no significant findings",
                        severity=Severity.LOW,
                        confidence=cat_summary.average_confidence,
                    )
                )

        # Generate recommended actions based on threat level
        recommended_actions = self._generate_threat_actions(
            threat_level, primary_concerns, role_category
        )

        # Calculate confidence based on data completeness
        total_types = compiled_result.investigation_summary.types_processed
        expected_types = 8  # Approximate expected information types
        confidence = min(1.0, total_types / expected_types)

        return ThreatAssessmentSection(
            threat_level=threat_level,
            threat_score=threat_score,
            contributing_factors=contributing_factors,
            mitigating_factors=mitigating_factors,
            primary_concerns=primary_concerns,
            recommended_actions=recommended_actions,
            assessment_confidence=confidence,
            assessment_notes=self._generate_assessment_notes(threat_level, compiled_result),
        )

    def _calculate_threat_level(self, threat_score: int) -> ThreatLevel:
        """Calculate threat level from score using configured thresholds."""
        if threat_score >= self.config.critical_threshold:
            return ThreatLevel.CRITICAL
        elif threat_score >= self.config.high_threshold:
            return ThreatLevel.HIGH
        elif threat_score >= self.config.elevated_threshold:
            return ThreatLevel.ELEVATED
        elif threat_score >= self.config.moderate_threshold:
            return ThreatLevel.MODERATE
        elif threat_score >= 20:
            return ThreatLevel.LOW
        else:
            return ThreatLevel.MINIMAL

    def _generate_threat_actions(
        self,
        threat_level: ThreatLevel,
        _concerns: list[str],
        role_category: RoleCategory,
    ) -> list[str]:
        """Generate recommended actions based on threat level."""
        actions = []

        if threat_level == ThreatLevel.CRITICAL:
            actions.extend(
                [
                    "Immediate security review required",
                    "Escalate to security leadership",
                    "Consider access restrictions pending investigation",
                ]
            )
        elif threat_level == ThreatLevel.HIGH:
            actions.extend(
                [
                    "Conduct enhanced security review",
                    "Schedule interview with security team",
                    "Implement enhanced monitoring if approved",
                ]
            )
        elif threat_level == ThreatLevel.ELEVATED:
            actions.extend(
                [
                    "Review with hiring manager and security",
                    "Consider additional background verification",
                    "Document risk acceptance if proceeding",
                ]
            )
        elif threat_level == ThreatLevel.MODERATE:
            actions.extend(
                [
                    "Standard security review recommended",
                    "Monitor during probationary period",
                ]
            )
        else:
            actions.append("Standard onboarding procedures appropriate")

        # Add role-specific recommendations
        if role_category in (RoleCategory.GOVERNMENT, RoleCategory.FINANCIAL):
            actions.append("Verify all regulatory requirements are met")
        if role_category == RoleCategory.EXECUTIVE:
            actions.append("Consider board-level notification")

        return actions

    def _generate_assessment_notes(
        self, threat_level: ThreatLevel, compiled_result: CompiledResult
    ) -> str:
        """Generate assessment notes."""
        parts = []

        if threat_level in (ThreatLevel.CRITICAL, ThreatLevel.HIGH):
            parts.append(
                "This assessment indicates significant security concerns that require "
                "immediate attention and review."
            )
        elif threat_level == ThreatLevel.ELEVATED:
            parts.append(
                "This assessment indicates elevated concerns that should be reviewed "
                "before proceeding."
            )
        else:
            parts.append(
                "This assessment indicates acceptable risk levels within normal parameters."
            )

        # Add investigation completeness note
        types_processed = compiled_result.investigation_summary.types_processed
        parts.append(f"Assessment based on {types_processed} information types processed.")

        return " ".join(parts)

    def _build_connection_network(
        self, compiled_result: CompiledResult
    ) -> ConnectionNetworkSection:
        """Build the connection network section.

        Args:
            compiled_result: The compiled screening result.

        Returns:
            ConnectionNetworkSection.
        """
        nodes: list[NetworkNode] = []
        edges: list[NetworkEdge] = []
        risk_paths: list[RiskPath] = []

        # Add subject node
        subject_node = NetworkNode(
            label="Subject",
            entity_type="individual",
            is_subject=True,
            depth=0,
            risk_level=RiskLevel.NONE,  # Subject's own risk is in findings
            risk_score=float(compiled_result.risk_score) / 100,
        )
        nodes.append(subject_node)

        # Get connection data from compiled result
        connection_summary = compiled_result.connection_summary
        d2_count = connection_summary.d2_entities
        d3_count = connection_summary.d3_entities

        # Generate network nodes from key risks (connection summary doesn't have detailed nodes)
        # We create placeholder nodes based on key_risks and high_risk_connections count
        for i, risk_desc in enumerate(connection_summary.key_risks):
            if i >= self.config.max_network_nodes - 1:  # -1 for subject node
                break

            # Determine risk level from description
            risk_level = RiskLevel.HIGH
            if "critical" in risk_desc.lower() or "sanctions" in risk_desc.lower():
                risk_level = RiskLevel.CRITICAL
            elif "moderate" in risk_desc.lower():
                risk_level = RiskLevel.MODERATE

            node = NetworkNode(
                label=f"Connection {i + 1}",
                entity_type="entity",
                is_subject=False,
                depth=1,  # Assume direct connection
                risk_level=risk_level,
                risk_score=0.7 if risk_level == RiskLevel.CRITICAL else 0.5,
                risk_factors=[risk_desc],
            )
            nodes.append(node)

            # Add edge from subject to this node
            edge = NetworkEdge(
                source_id=subject_node.node_id,
                target_id=node.node_id,
                relation_type=RelationType.OTHER,
                strength=ConnectionStrength.MODERATE,
                risk_factor=0.5,
            )
            edges.append(edge)

            # Create risk path
            risk_path = RiskPath(
                source_entity=node.label,
                source_risk_level=node.risk_level,
                hops=node.depth,
                propagated_risk=node.risk_score * (0.7 ** node.depth),
                risk_type="association",
                description=risk_desc,
            )
            risk_paths.append(risk_path)

        # Use high_risk_connections count from summary
        high_risk_count = connection_summary.high_risk_connections

        # Network risk score from summary
        network_risk = connection_summary.risk_propagation_score

        return ConnectionNetworkSection(
            nodes=nodes,
            edges=edges,
            risk_paths=risk_paths[: self.config.max_risk_paths],
            total_entities=connection_summary.entities_discovered,
            d2_entities=d2_count,
            d3_entities=d3_count,
            high_risk_connections=high_risk_count,
            network_risk_score=min(1.0, network_risk),
            centrality_score=0.0,  # Not available in summary
        )

    def _build_detailed_findings(
        self, compiled_result: CompiledResult, _role_category: RoleCategory
    ) -> DetailedFindingsSection:
        """Build the detailed findings section.

        Args:
            compiled_result: The compiled screening result.
            _role_category: Role category for relevance (reserved for future use).

        Returns:
            DetailedFindingsSection.
        """
        all_findings: list[DetailedFinding] = []
        findings_summary = compiled_result.findings_summary

        # Build detailed findings from summary data
        # First add critical findings
        for summary in findings_summary.critical_findings:
            detailed = DetailedFinding(
                category=FindingCategory.CRIMINAL,  # Default category for critical
                summary=summary,
                details="",
                severity=Severity.CRITICAL,
                confidence=0.8,
                sources=[],
                is_corroborated=False,
            )
            all_findings.append(detailed)

        # Add high severity findings
        for summary in findings_summary.high_findings:
            detailed = DetailedFinding(
                category=FindingCategory.VERIFICATION,  # Default category
                summary=summary,
                details="",
                severity=Severity.HIGH,
                confidence=0.7,
                sources=[],
                is_corroborated=False,
            )
            all_findings.append(detailed)

        # Group findings by category using CategorySummary data
        findings_by_cat: dict[FindingCategory, list[DetailedFinding]] = {}
        for finding in all_findings:
            if finding.category not in findings_by_cat:
                findings_by_cat[finding.category] = []
            findings_by_cat[finding.category].append(finding)

        # Build category summaries
        category_summaries: list[FindingsByCategory] = []
        for cat, findings_list in findings_by_cat.items():
            critical_count = sum(1 for f in findings_list if f.severity == Severity.CRITICAL)
            high_count = sum(1 for f in findings_list if f.severity == Severity.HIGH)
            avg_conf = (
                sum(f.confidence for f in findings_list) / len(findings_list)
                if findings_list
                else 0.0
            )

            category_summaries.append(
                FindingsByCategory(
                    category=cat,
                    findings=findings_list,
                    count=len(findings_list),
                    critical_count=critical_count,
                    high_count=high_count,
                    average_confidence=avg_conf,
                )
            )

        # Sort by severity (most severe first)
        category_summaries.sort(key=lambda c: c.critical_count + c.high_count, reverse=True)

        # Calculate totals
        total_critical = sum(c.critical_count for c in category_summaries)
        total_high = sum(c.high_count for c in category_summaries)
        total_corroborated = sum(1 for f in all_findings if f.is_corroborated)

        return DetailedFindingsSection(
            findings_by_category=category_summaries,
            total_findings=len(all_findings),
            critical_findings=total_critical,
            high_findings=total_high,
            corroborated_findings=total_corroborated,
            findings_list=all_findings,
        )

    def _build_evolution_signals(
        self, compiled_result: CompiledResult, baseline_score: int | None
    ) -> EvolutionSignalsSection:
        """Build the evolution signals section.

        Args:
            compiled_result: The compiled screening result.
            baseline_score: Previous baseline score for comparison.

        Returns:
            EvolutionSignalsSection.
        """
        signals: list[EvolutionSignal] = []
        current_score = compiled_result.risk_score
        baseline = baseline_score or 0

        # Calculate score change
        score_change = current_score - baseline

        # Determine overall trend
        if baseline_score is None:
            overall_trend = EvolutionTrend.NEW_CONCERNS  # First screening
        elif score_change > 15:
            overall_trend = EvolutionTrend.DETERIORATING
        elif score_change < -15:
            overall_trend = EvolutionTrend.IMPROVING
        elif abs(score_change) > 5:
            overall_trend = EvolutionTrend.VOLATILE
        else:
            overall_trend = EvolutionTrend.STABLE

        # Generate signals based on findings summary
        findings_summary = compiled_result.findings_summary
        if baseline_score is None:
            # First screening - critical findings are new
            for summary in findings_summary.critical_findings[:5]:
                signals.append(
                    EvolutionSignal(
                        signal_type=SignalType.NEW_FINDING,
                        description=f"New critical finding: {summary}",
                        previous_value="N/A",
                        current_value="critical",
                        change_magnitude=0.8,
                        significance="high",
                    )
                )
            # Add high findings too
            for summary in findings_summary.high_findings[:5]:
                signals.append(
                    EvolutionSignal(
                        signal_type=SignalType.NEW_FINDING,
                        description=f"New high finding: {summary}",
                        previous_value="N/A",
                        current_value="high",
                        change_magnitude=0.6,
                        significance="medium",
                    )
                )
        else:
            # Score change signal
            if abs(score_change) > 10:
                signals.append(
                    EvolutionSignal(
                        signal_type=(
                            SignalType.RISK_INCREASE
                            if score_change > 0
                            else SignalType.RISK_DECREASE
                        ),
                        description=f"Risk score changed by {score_change:+d} points",
                        previous_value=str(baseline),
                        current_value=str(current_score),
                        change_magnitude=min(1.0, abs(score_change) / 50),
                        significance="high" if abs(score_change) > 20 else "medium",
                    )
                )

        # Check for threshold breaches
        for level, threshold in THREAT_LEVEL_THRESHOLDS.items():
            if baseline is not None and baseline < threshold <= current_score:
                signals.append(
                    EvolutionSignal(
                        signal_type=SignalType.THRESHOLD_BREACH,
                        description=f"Risk score crossed into {level.value} threshold",
                        previous_value=str(baseline),
                        current_value=str(current_score),
                        change_magnitude=0.9,
                        significance="high",
                    )
                )
                break

        # Count high significance signals
        high_sig_count = sum(1 for s in signals if s.significance == "high")

        # Determine if attention required
        requires_attention = (
            overall_trend == EvolutionTrend.DETERIORATING
            or high_sig_count >= 2
            or current_score >= self.config.elevated_threshold
        )

        return EvolutionSignalsSection(
            overall_trend=overall_trend,
            signals=signals[: self.config.max_evolution_signals],
            baseline_score=baseline,
            current_score=current_score,
            score_change=score_change,
            high_significance_count=high_sig_count,
            requires_attention=requires_attention,
        )

    def _generate_summary(
        self,
        _compiled_result: CompiledResult,
        threat_section: ThreatAssessmentSection,
        network_section: ConnectionNetworkSection,
        findings_section: DetailedFindingsSection,
    ) -> str:
        """Generate human-readable summary.

        Args:
            _compiled_result: The compiled screening result (reserved for future use).
            threat_section: Threat assessment section.
            network_section: Connection network section.
            findings_section: Detailed findings section.

        Returns:
            Summary string.
        """
        parts = []

        # Threat level summary
        level = threat_section.threat_level
        if level in (ThreatLevel.CRITICAL, ThreatLevel.HIGH):
            parts.append(
                f"This subject presents a {level.value.upper()} insider threat risk "
                f"(score: {threat_section.threat_score}/100) requiring immediate attention."
            )
        elif level == ThreatLevel.ELEVATED:
            parts.append(
                f"This subject presents an ELEVATED threat risk "
                f"(score: {threat_section.threat_score}/100) requiring enhanced review."
            )
        else:
            parts.append(
                f"This subject presents a {level.value} threat risk "
                f"(score: {threat_section.threat_score}/100)."
            )

        # Findings summary
        if findings_section.critical_findings > 0:
            parts.append(
                f"Investigation identified {findings_section.critical_findings} critical "
                f"and {findings_section.high_findings} high-severity findings."
            )
        elif findings_section.high_findings > 0:
            parts.append(
                f"Investigation identified {findings_section.high_findings} high-severity findings."
            )
        else:
            parts.append(
                f"Investigation identified {findings_section.total_findings} findings "
                "with no critical or high-severity issues."
            )

        # Network summary
        if network_section.high_risk_connections > 0:
            parts.append(
                f"Network analysis revealed {network_section.high_risk_connections} "
                f"high-risk connections among {network_section.total_entities} entities."
            )
        elif network_section.total_entities > 0:
            parts.append(
                f"Network analysis reviewed {network_section.total_entities} connected entities "
                "with no high-risk associations identified."
            )

        # Primary concerns
        if threat_section.primary_concerns:
            top_concerns = threat_section.primary_concerns[:3]
            parts.append(f"Primary concerns: {'; '.join(top_concerns)}.")

        return " ".join(parts)


# =============================================================================
# Factory Functions
# =============================================================================


def create_security_investigation_builder(
    config: SecurityInvestigationConfig | None = None,
) -> SecurityInvestigationBuilder:
    """Factory function to create a Security Investigation builder.

    Args:
        config: Optional builder configuration.

    Returns:
        Configured SecurityInvestigationBuilder instance.
    """
    return SecurityInvestigationBuilder(config=config)
