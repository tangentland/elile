"""Result Compiler for aggregating screening results.

This module provides the ResultCompiler that:
1. Aggregates SAR results across all information types
2. Compiles findings summaries with category breakdowns
3. Incorporates risk assessment and recommendations
4. Formats data for report generation
5. Builds comprehensive screening results

Architecture Reference: docs/architecture/03-screening.md
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.agent.state import InformationType
from elile.core.logging import get_logger
from elile.investigation.finding_extractor import Finding, FindingCategory, Severity
from elile.investigation.models import CompletionReason, SARTypeState
from elile.investigation.phases.network import (
    DiscoveredEntity,
    EntityRelation,
    RiskConnection,
    RiskLevel,
)
from elile.risk.risk_aggregator import ComprehensiveRiskAssessment
from elile.screening.types import (
    ScreeningCostSummary,
    ScreeningPhaseResult,
    ScreeningResult,
    ScreeningStatus,
)

logger = get_logger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class SummaryFormat(str, Enum):
    """Format for findings summaries."""

    BRIEF = "brief"  # Single sentence per category
    STANDARD = "standard"  # Paragraph per category
    DETAILED = "detailed"  # Full details with examples


# Information type to category mapping for findings aggregation
INFO_TYPE_TO_CATEGORY: dict[InformationType, FindingCategory] = {
    InformationType.IDENTITY: FindingCategory.VERIFICATION,
    InformationType.EMPLOYMENT: FindingCategory.VERIFICATION,
    InformationType.EDUCATION: FindingCategory.VERIFICATION,
    InformationType.CRIMINAL: FindingCategory.CRIMINAL,
    InformationType.CIVIL: FindingCategory.REGULATORY,
    InformationType.FINANCIAL: FindingCategory.FINANCIAL,
    InformationType.LICENSES: FindingCategory.REGULATORY,
    InformationType.REGULATORY: FindingCategory.REGULATORY,
    InformationType.SANCTIONS: FindingCategory.REGULATORY,
    InformationType.ADVERSE_MEDIA: FindingCategory.REPUTATION,
    InformationType.DIGITAL_FOOTPRINT: FindingCategory.REPUTATION,
    InformationType.NETWORK_D2: FindingCategory.NETWORK,
    InformationType.NETWORK_D3: FindingCategory.NETWORK,
    InformationType.RECONCILIATION: FindingCategory.BEHAVIORAL,
}


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class CategorySummary:
    """Summary of findings for a single category.

    Attributes:
        category: The finding category.
        total_findings: Number of findings in this category.
        critical_count: Number of critical findings.
        high_count: Number of high severity findings.
        medium_count: Number of medium severity findings.
        low_count: Number of low severity findings.
        highest_severity: The highest severity in this category.
        average_confidence: Average confidence across findings.
        key_findings: List of key finding summaries.
        sources_count: Number of unique data sources.
        corroborated_count: Number of corroborated findings.
    """

    category: FindingCategory = FindingCategory.VERIFICATION
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    highest_severity: Severity | None = None
    average_confidence: float = 0.0
    key_findings: list[str] = field(default_factory=list)
    sources_count: int = 0
    corroborated_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "total_findings": self.total_findings,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "highest_severity": self.highest_severity.value if self.highest_severity else None,
            "average_confidence": self.average_confidence,
            "key_findings": self.key_findings,
            "sources_count": self.sources_count,
            "corroborated_count": self.corroborated_count,
        }


@dataclass
class FindingsSummary:
    """Aggregated summary of all findings across categories.

    Provides a high-level overview of findings suitable for
    executive summaries and HR reports.

    Attributes:
        summary_id: Unique identifier for this summary.
        total_findings: Total number of findings.
        by_category: Breakdown by finding category.
        by_severity: Breakdown by severity level.
        critical_findings: List of critical finding summaries.
        high_findings: List of high severity finding summaries.
        overall_narrative: Human-readable narrative summary.
        data_completeness: Percentage of data sources that returned data.
        verification_status: Overall verification status.
        generated_at: When this summary was generated.
    """

    summary_id: UUID = field(default_factory=uuid7)
    total_findings: int = 0
    by_category: dict[FindingCategory, CategorySummary] = field(default_factory=dict)
    by_severity: dict[Severity, int] = field(default_factory=dict)
    critical_findings: list[str] = field(default_factory=list)
    high_findings: list[str] = field(default_factory=list)
    overall_narrative: str = ""
    data_completeness: float = 1.0
    verification_status: str = "complete"
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "summary_id": str(self.summary_id),
            "total_findings": self.total_findings,
            "by_category": {k.value: v.to_dict() for k, v in self.by_category.items()},
            "by_severity": {k.value: v for k, v in self.by_severity.items()},
            "critical_findings": self.critical_findings,
            "high_findings": self.high_findings,
            "overall_narrative": self.overall_narrative,
            "data_completeness": self.data_completeness,
            "verification_status": self.verification_status,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class SARSummary:
    """Summary of SAR loop results for a single information type.

    Attributes:
        info_type: The information type.
        iterations_completed: Number of SAR iterations.
        final_confidence: Final confidence score (0.0-1.0).
        queries_executed: Total queries executed.
        facts_extracted: Total facts extracted.
        completion_reason: Why the SAR loop completed.
        duration_ms: Processing time in milliseconds.
        findings_count: Number of findings from this type.
    """

    info_type: InformationType = InformationType.IDENTITY
    iterations_completed: int = 0
    final_confidence: float = 0.0
    queries_executed: int = 0
    facts_extracted: int = 0
    completion_reason: CompletionReason | None = None
    duration_ms: float = 0.0
    findings_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "info_type": self.info_type.value,
            "iterations_completed": self.iterations_completed,
            "final_confidence": self.final_confidence,
            "queries_executed": self.queries_executed,
            "facts_extracted": self.facts_extracted,
            "completion_reason": self.completion_reason.value if self.completion_reason else None,
            "duration_ms": self.duration_ms,
            "findings_count": self.findings_count,
        }


@dataclass
class InvestigationSummary:
    """Summary of the complete investigation.

    Provides overview of SAR loop execution across all types.

    Attributes:
        summary_id: Unique identifier for this summary.
        types_processed: Number of information types processed.
        types_completed: Number that completed successfully.
        types_failed: Number that failed.
        types_skipped: Number that were skipped.
        by_type: Per-type summaries.
        total_iterations: Total SAR iterations across all types.
        total_queries: Total queries executed.
        total_facts: Total facts extracted.
        average_confidence: Average confidence across types.
        lowest_confidence_type: Type with lowest confidence.
        total_duration_ms: Total processing time.
    """

    summary_id: UUID = field(default_factory=uuid7)
    types_processed: int = 0
    types_completed: int = 0
    types_failed: int = 0
    types_skipped: int = 0
    by_type: dict[InformationType, SARSummary] = field(default_factory=dict)
    total_iterations: int = 0
    total_queries: int = 0
    total_facts: int = 0
    average_confidence: float = 0.0
    lowest_confidence_type: InformationType | None = None
    total_duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "summary_id": str(self.summary_id),
            "types_processed": self.types_processed,
            "types_completed": self.types_completed,
            "types_failed": self.types_failed,
            "types_skipped": self.types_skipped,
            "by_type": {k.value: v.to_dict() for k, v in self.by_type.items()},
            "total_iterations": self.total_iterations,
            "total_queries": self.total_queries,
            "total_facts": self.total_facts,
            "average_confidence": self.average_confidence,
            "lowest_confidence_type": (
                self.lowest_confidence_type.value if self.lowest_confidence_type else None
            ),
            "total_duration_ms": self.total_duration_ms,
        }


@dataclass
class ConnectionSummary:
    """Summary of entity connections (D2/D3 analysis).

    Attributes:
        summary_id: Unique identifier for this summary.
        entities_discovered: Total entities discovered.
        d2_entities: Entities at D2 (direct connections).
        d3_entities: Entities at D3 (extended network).
        relations_mapped: Total relationships mapped.
        risk_connections: Number of risky connections.
        critical_connections: Number of critical risk connections.
        high_risk_connections: Number of high risk connections.
        pep_connections: Number of PEP connections.
        sanctions_connections: Number of sanctioned entity connections.
        shell_company_connections: Number of shell company connections.
        highest_risk_level: Highest risk level found.
        risk_propagation_score: Overall risk propagation score.
        key_risks: List of key risk descriptions.
    """

    summary_id: UUID = field(default_factory=uuid7)
    entities_discovered: int = 0
    d2_entities: int = 0
    d3_entities: int = 0
    relations_mapped: int = 0
    risk_connections: int = 0
    critical_connections: int = 0
    high_risk_connections: int = 0
    pep_connections: int = 0
    sanctions_connections: int = 0
    shell_company_connections: int = 0
    highest_risk_level: RiskLevel = RiskLevel.NONE
    risk_propagation_score: float = 0.0
    key_risks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "summary_id": str(self.summary_id),
            "entities_discovered": self.entities_discovered,
            "d2_entities": self.d2_entities,
            "d3_entities": self.d3_entities,
            "relations_mapped": self.relations_mapped,
            "risk_connections": self.risk_connections,
            "critical_connections": self.critical_connections,
            "high_risk_connections": self.high_risk_connections,
            "pep_connections": self.pep_connections,
            "sanctions_connections": self.sanctions_connections,
            "shell_company_connections": self.shell_company_connections,
            "highest_risk_level": self.highest_risk_level.value,
            "risk_propagation_score": self.risk_propagation_score,
            "key_risks": self.key_risks,
        }


@dataclass
class CompiledResult:
    """Complete compiled screening result.

    This is the internal result structure used by the ResultCompiler
    before converting to ScreeningResult for API responses.

    Attributes:
        result_id: Unique identifier.
        screening_id: Reference to screening request.
        entity_id: Entity that was screened.
        tenant_id: Tenant that requested screening.
        findings_summary: Aggregated findings summary.
        investigation_summary: SAR loop execution summary.
        connection_summary: Network analysis summary.
        risk_assessment: Comprehensive risk assessment.
        risk_score: Final risk score (0-100).
        risk_level: Risk level classification.
        recommendation: Action recommendation.
        cost_summary: Cost breakdown.
        compiled_at: When this result was compiled.
    """

    result_id: UUID = field(default_factory=uuid7)
    screening_id: UUID | None = None
    entity_id: UUID | None = None
    tenant_id: UUID | None = None

    # Summaries
    findings_summary: FindingsSummary = field(default_factory=FindingsSummary)
    investigation_summary: InvestigationSummary = field(default_factory=InvestigationSummary)
    connection_summary: ConnectionSummary = field(default_factory=ConnectionSummary)

    # Risk assessment
    risk_assessment: ComprehensiveRiskAssessment | None = None
    risk_score: int = 0
    risk_level: str = "low"
    recommendation: str = "proceed"

    # Cost
    cost_summary: ScreeningCostSummary = field(default_factory=ScreeningCostSummary)

    # Timing
    compiled_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "result_id": str(self.result_id),
            "screening_id": str(self.screening_id) if self.screening_id else None,
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "findings_summary": self.findings_summary.to_dict(),
            "investigation_summary": self.investigation_summary.to_dict(),
            "connection_summary": self.connection_summary.to_dict(),
            "risk_assessment": self.risk_assessment.to_dict() if self.risk_assessment else None,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "recommendation": self.recommendation,
            "cost_summary": self.cost_summary.to_dict(),
            "compiled_at": self.compiled_at.isoformat(),
        }


class CompilerConfig(BaseModel):
    """Configuration for ResultCompiler."""

    # Summary settings
    summary_format: SummaryFormat = Field(
        default=SummaryFormat.STANDARD, description="Format for summaries"
    )
    max_key_findings: int = Field(
        default=5, ge=1, le=20, description="Max key findings per category"
    )
    max_critical_findings: int = Field(
        default=10, ge=1, le=50, description="Max critical findings to include"
    )

    # Narrative settings
    include_narrative: bool = Field(default=True, description="Generate narrative summaries")
    narrative_style: str = Field(default="professional", description="Narrative writing style")

    # Connection settings
    max_risk_descriptions: int = Field(
        default=10, ge=1, le=50, description="Max risk descriptions"
    )

    # Filtering
    min_finding_confidence: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Min confidence to include finding"
    )


# =============================================================================
# Result Compiler
# =============================================================================


class ResultCompiler:
    """Compiles screening results from SAR loop outputs.

    The ResultCompiler aggregates data from multiple sources:
    - SAR loop results (per-type states and statistics)
    - Findings extracted during investigation
    - Risk assessment from the RiskAggregator
    - Entity connections from network analysis

    It produces comprehensive summaries suitable for:
    - Report generation (all report types)
    - API responses
    - Audit logging

    Example:
        ```python
        compiler = ResultCompiler()

        # Compile results
        compiled = compiler.compile_results(
            sar_results=sar_states,
            findings=all_findings,
            risk_assessment=risk_assessment,
            connections=connections,
            relations=relations,
            risk_connections=risk_connections,
        )

        # Convert to screening result
        screening_result = compiler.to_screening_result(
            compiled=compiled,
            screening_id=screening_id,
            phases=phase_results,
        )
        ```
    """

    def __init__(self, config: CompilerConfig | None = None):
        """Initialize the result compiler.

        Args:
            config: Compiler configuration.
        """
        self.config = config or CompilerConfig()

    def compile_results(
        self,
        sar_results: dict[InformationType, SARTypeState],
        findings: list[Finding],
        risk_assessment: ComprehensiveRiskAssessment,
        connections: list[DiscoveredEntity] | None = None,
        relations: list[EntityRelation] | None = None,
        risk_connections: list[RiskConnection] | None = None,
        screening_id: UUID | None = None,
        entity_id: UUID | None = None,
        tenant_id: UUID | None = None,
    ) -> CompiledResult:
        """Compile complete screening results.

        Args:
            sar_results: SAR loop results per information type.
            findings: All findings extracted during investigation.
            risk_assessment: Comprehensive risk assessment.
            connections: Discovered entities (D2/D3).
            relations: Entity relationships.
            risk_connections: Risky connections identified.
            screening_id: Screening request ID.
            entity_id: Entity being screened.
            tenant_id: Tenant ID.

        Returns:
            CompiledResult with all summaries.
        """
        connections = connections or []
        relations = relations or []
        risk_connections = risk_connections or []

        logger.info(
            "Compiling results",
            sar_types=len(sar_results),
            findings=len(findings),
            connections=len(connections),
            risk_score=risk_assessment.final_score,
        )

        # Compile findings summary
        findings_summary = self._compile_findings_summary(findings)

        # Compile investigation summary
        investigation_summary = self._compile_investigation_summary(sar_results, findings)

        # Compile connection summary
        connection_summary = self._compile_connection_summary(
            connections, relations, risk_connections
        )

        # Create compiled result
        compiled = CompiledResult(
            screening_id=screening_id,
            entity_id=entity_id,
            tenant_id=tenant_id,
            findings_summary=findings_summary,
            investigation_summary=investigation_summary,
            connection_summary=connection_summary,
            risk_assessment=risk_assessment,
            risk_score=risk_assessment.final_score,
            risk_level=risk_assessment.risk_level.value,
            recommendation=risk_assessment.recommendation.value,
        )

        logger.info(
            "Results compiled",
            result_id=str(compiled.result_id),
            total_findings=findings_summary.total_findings,
            risk_score=compiled.risk_score,
        )

        return compiled

    def _compile_findings_summary(self, findings: list[Finding]) -> FindingsSummary:
        """Compile findings into an aggregated summary.

        Args:
            findings: All findings to summarize.

        Returns:
            FindingsSummary with category breakdowns.
        """
        # Filter by confidence
        filtered_findings = [
            f for f in findings if f.confidence >= self.config.min_finding_confidence
        ]

        # Group by category
        by_category: dict[FindingCategory, list[Finding]] = {}
        for finding in filtered_findings:
            category = finding.category or FindingCategory.VERIFICATION
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(finding)

        # Build category summaries
        category_summaries: dict[FindingCategory, CategorySummary] = {}
        for category, cat_findings in by_category.items():
            category_summaries[category] = self._build_category_summary(category, cat_findings)

        # Count by severity
        by_severity: dict[Severity, int] = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 0,
            Severity.MEDIUM: 0,
            Severity.LOW: 0,
        }
        for finding in filtered_findings:
            by_severity[finding.severity] = by_severity.get(finding.severity, 0) + 1

        # Extract critical and high findings
        critical_findings = [
            f.summary[:100] for f in filtered_findings if f.severity == Severity.CRITICAL
        ][: self.config.max_critical_findings]

        high_findings = [f.summary[:100] for f in filtered_findings if f.severity == Severity.HIGH][
            : self.config.max_critical_findings
        ]

        # Generate narrative
        narrative = self._generate_findings_narrative(
            filtered_findings, category_summaries, by_severity
        )

        # Calculate data completeness (ratio of categories with findings)
        expected_categories = len(FindingCategory)
        categories_with_data = len(by_category)
        data_completeness = categories_with_data / expected_categories if expected_categories > 0 else 1.0

        return FindingsSummary(
            total_findings=len(filtered_findings),
            by_category=category_summaries,
            by_severity=by_severity,
            critical_findings=critical_findings,
            high_findings=high_findings,
            overall_narrative=narrative,
            data_completeness=data_completeness,
            verification_status="complete" if data_completeness > 0.5 else "partial",
        )

    def _build_category_summary(
        self, category: FindingCategory, findings: list[Finding]
    ) -> CategorySummary:
        """Build summary for a single category.

        Args:
            category: The finding category.
            findings: Findings in this category.

        Returns:
            CategorySummary for the category.
        """
        if not findings:
            return CategorySummary(category=category)

        # Count by severity
        critical_count = sum(1 for f in findings if f.severity == Severity.CRITICAL)
        high_count = sum(1 for f in findings if f.severity == Severity.HIGH)
        medium_count = sum(1 for f in findings if f.severity == Severity.MEDIUM)
        low_count = sum(1 for f in findings if f.severity == Severity.LOW)

        # Determine highest severity
        highest_severity = Severity.LOW
        if critical_count > 0:
            highest_severity = Severity.CRITICAL
        elif high_count > 0:
            highest_severity = Severity.HIGH
        elif medium_count > 0:
            highest_severity = Severity.MEDIUM

        # Calculate average confidence
        avg_confidence = sum(f.confidence for f in findings) / len(findings)

        # Extract key findings (highest severity first)
        sorted_findings = sorted(
            findings,
            key=lambda f: (
                [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW].index(f.severity),
                -f.confidence,
            ),
        )
        key_findings = [f.summary[:100] for f in sorted_findings][: self.config.max_key_findings]

        # Count unique sources
        sources: set[str] = set()
        for f in findings:
            for source in f.sources:
                sources.add(source.provider_id)

        # Count corroborated
        corroborated_count = sum(1 for f in findings if f.corroborated)

        return CategorySummary(
            category=category,
            total_findings=len(findings),
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            highest_severity=highest_severity,
            average_confidence=avg_confidence,
            key_findings=key_findings,
            sources_count=len(sources),
            corroborated_count=corroborated_count,
        )

    def _compile_investigation_summary(
        self,
        sar_results: dict[InformationType, SARTypeState],
        findings: list[Finding],
    ) -> InvestigationSummary:
        """Compile SAR loop results into investigation summary.

        Args:
            sar_results: SAR type states from investigation.
            findings: Findings for counting per-type.

        Returns:
            InvestigationSummary with execution statistics.
        """
        # Count findings per type (using category mapping)
        findings_by_type: dict[InformationType, int] = {}
        for finding in findings:
            category = finding.category or FindingCategory.VERIFICATION
            # Find info types that map to this category
            for info_type, mapped_category in INFO_TYPE_TO_CATEGORY.items():
                if mapped_category == category:
                    findings_by_type[info_type] = findings_by_type.get(info_type, 0) + 1
                    break

        # Build per-type summaries
        by_type: dict[InformationType, SARSummary] = {}
        total_iterations = 0
        total_queries = 0
        total_facts = 0
        confidences: list[float] = []

        types_completed = 0
        types_failed = 0
        types_skipped = 0

        for info_type, state in sar_results.items():
            sar_summary = SARSummary(
                info_type=info_type,
                iterations_completed=len(state.iterations),
                final_confidence=state.final_confidence,
                queries_executed=state.total_queries_executed,
                facts_extracted=state.total_facts_extracted,
                completion_reason=state.completion_reason,
                duration_ms=0.0,  # Would be calculated from iteration timings
                findings_count=findings_by_type.get(info_type, 0),
            )
            by_type[info_type] = sar_summary

            total_iterations += len(state.iterations)
            total_queries += state.total_queries_executed
            total_facts += state.total_facts_extracted

            if state.final_confidence > 0:
                confidences.append(state.final_confidence)

            # Count completion status
            if state.completion_reason == CompletionReason.SKIPPED:
                types_skipped += 1
            elif state.completion_reason == CompletionReason.ERROR:
                types_failed += 1
            else:
                types_completed += 1

        # Calculate averages
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        lowest_confidence = min(confidences) if confidences else 0.0
        lowest_type = None
        for info_type, state in sar_results.items():
            if state.final_confidence == lowest_confidence:
                lowest_type = info_type
                break

        return InvestigationSummary(
            types_processed=len(sar_results),
            types_completed=types_completed,
            types_failed=types_failed,
            types_skipped=types_skipped,
            by_type=by_type,
            total_iterations=total_iterations,
            total_queries=total_queries,
            total_facts=total_facts,
            average_confidence=avg_confidence,
            lowest_confidence_type=lowest_type,
            total_duration_ms=0.0,  # Would be calculated from phase timings
        )

    def _compile_connection_summary(
        self,
        connections: list[DiscoveredEntity],
        relations: list[EntityRelation],
        risk_connections: list[RiskConnection],
    ) -> ConnectionSummary:
        """Compile network analysis into connection summary.

        Args:
            connections: Discovered entities.
            relations: Entity relationships.
            risk_connections: Risky connections identified.

        Returns:
            ConnectionSummary with network analysis.
        """
        if not connections:
            return ConnectionSummary()

        # Count by discovery degree
        d2_count = sum(1 for c in connections if c.discovery_degree == 2)
        d3_count = sum(1 for c in connections if c.discovery_degree == 3)

        # Count special connection types
        pep_count = sum(1 for c in connections if c.is_pep)
        sanctions_count = sum(1 for c in connections if c.is_sanctioned)
        shell_count = sum(
            1 for c in connections if c.entity_type.value in ("shell_company",)
        )

        # Count risk connections by level
        critical_count = sum(
            1 for r in risk_connections if r.risk_level == RiskLevel.CRITICAL
        )
        high_count = sum(1 for r in risk_connections if r.risk_level == RiskLevel.HIGH)

        # Determine highest risk level
        highest_risk = RiskLevel.NONE
        for r in risk_connections:
            if r.risk_level == RiskLevel.CRITICAL:
                highest_risk = RiskLevel.CRITICAL
                break
            elif r.risk_level == RiskLevel.HIGH and highest_risk != RiskLevel.CRITICAL:
                highest_risk = RiskLevel.HIGH
            elif r.risk_level == RiskLevel.MODERATE and highest_risk not in (
                RiskLevel.CRITICAL,
                RiskLevel.HIGH,
            ):
                highest_risk = RiskLevel.MODERATE
            elif r.risk_level == RiskLevel.LOW and highest_risk == RiskLevel.NONE:
                highest_risk = RiskLevel.LOW

        # Calculate propagation score (simple average of risk connection scores)
        propagation_scores = [
            getattr(r, "propagated_risk", 0.0) for r in risk_connections if hasattr(r, "propagated_risk")
        ]
        propagation_score = (
            sum(propagation_scores) / len(propagation_scores) if propagation_scores else 0.0
        )

        # Extract key risk descriptions
        key_risks = [r.risk_description[: 100] for r in risk_connections if r.risk_description][
            : self.config.max_risk_descriptions
        ]

        return ConnectionSummary(
            entities_discovered=len(connections),
            d2_entities=d2_count,
            d3_entities=d3_count,
            relations_mapped=len(relations),
            risk_connections=len(risk_connections),
            critical_connections=critical_count,
            high_risk_connections=high_count,
            pep_connections=pep_count,
            sanctions_connections=sanctions_count,
            shell_company_connections=shell_count,
            highest_risk_level=highest_risk,
            risk_propagation_score=propagation_score,
            key_risks=key_risks,
        )

    def _generate_findings_narrative(
        self,
        findings: list[Finding],
        by_category: dict[FindingCategory, CategorySummary],
        by_severity: dict[Severity, int],
    ) -> str:
        """Generate human-readable narrative summary.

        Args:
            findings: All findings.
            by_category: Category summaries.
            by_severity: Severity counts.

        Returns:
            Narrative summary string.
        """
        if not self.config.include_narrative:
            return ""

        if not findings:
            return "No adverse findings were identified during the background screening investigation."

        parts = []

        # Overall summary
        total = len(findings)
        critical = by_severity.get(Severity.CRITICAL, 0)
        high = by_severity.get(Severity.HIGH, 0)

        if critical > 0:
            parts.append(
                f"The investigation identified {total} findings, including {critical} critical"
                + (f" and {high} high severity items" if high > 0 else " severity items")
                + " requiring immediate attention."
            )
        elif high > 0:
            parts.append(
                f"The investigation identified {total} findings, including {high} high severity "
                "items that warrant further review."
            )
        else:
            parts.append(
                f"The investigation identified {total} findings. No critical or high severity "
                "issues were detected."
            )

        # Category highlights
        for category, summary in sorted(
            by_category.items(), key=lambda x: x[1].total_findings, reverse=True
        ):
            if summary.total_findings > 0:
                category_name = category.value.replace("_", " ").title()
                if summary.critical_count > 0:
                    parts.append(
                        f"{category_name}: {summary.total_findings} findings with "
                        f"{summary.critical_count} critical."
                    )
                elif summary.high_count > 0:
                    parts.append(
                        f"{category_name}: {summary.total_findings} findings with "
                        f"{summary.high_count} high severity."
                    )

        return " ".join(parts)

    def to_screening_result(
        self,
        compiled: CompiledResult,
        screening_id: UUID,
        phases: list[ScreeningPhaseResult] | None = None,
        status: ScreeningStatus = ScreeningStatus.COMPLETE,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> ScreeningResult:
        """Convert compiled result to ScreeningResult for API.

        Args:
            compiled: The compiled result.
            screening_id: Screening request ID.
            phases: Phase timing results.
            status: Screening status.
            started_at: When screening started.
            completed_at: When screening completed.

        Returns:
            ScreeningResult suitable for API response.
        """
        phases = phases or []
        started_at = started_at or datetime.now(UTC)
        completed_at = completed_at or datetime.now(UTC)

        # Count findings by severity
        findings_summary = compiled.findings_summary
        critical = findings_summary.by_severity.get(Severity.CRITICAL, 0)
        high = findings_summary.by_severity.get(Severity.HIGH, 0)

        return ScreeningResult(
            result_id=compiled.result_id,
            screening_id=screening_id,
            tenant_id=compiled.tenant_id,
            entity_id=compiled.entity_id,
            status=status,
            risk_assessment_id=compiled.risk_assessment.assessment_id if compiled.risk_assessment else None,
            risk_score=compiled.risk_score,
            risk_level=compiled.risk_level,
            recommendation=compiled.recommendation,
            reports=[],  # Reports are generated separately
            phases=phases,
            cost_summary=compiled.cost_summary,
            started_at=started_at,
            completed_at=completed_at,
            findings_count=findings_summary.total_findings,
            critical_findings=critical,
            high_findings=high,
            data_sources_queried=compiled.investigation_summary.total_queries,
            queries_executed=compiled.investigation_summary.total_queries,
        )


def create_result_compiler(config: CompilerConfig | None = None) -> ResultCompiler:
    """Factory function to create a result compiler.

    Args:
        config: Optional compiler configuration.

    Returns:
        Configured ResultCompiler instance.
    """
    return ResultCompiler(config=config)
