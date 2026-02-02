"""Degree handlers for different investigation depths.

This module implements handlers for D1 (subject-only), D2 (direct connections),
and D3 (extended network) investigations.

D3 Enhanced Features (Task 7.8):
- Manual review checkpoint integration
- Extended source coverage tracking
- Detailed reporting capabilities
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from uuid_utils import uuid7

from elile.agent.state import (
    InformationType,
    KnowledgeBase,
    SearchDegree,
    ServiceTier,
)
from elile.compliance.types import Locale, RoleCategory
from elile.core.context import RequestContext, get_current_context_or_none
from elile.investigation.checkpoint import (
    CheckpointData,
    CheckpointManager,
    CheckpointReason,
    create_checkpoint_manager,
)
from elile.investigation.finding_extractor import Finding
from elile.investigation.models import SARPhase
from elile.investigation.phases.network import (
    ConnectionStrength,
    DiscoveredEntity,
    EntityRelation,
    EntityType,
    RiskConnection,
    RiskLevel,
)
from elile.investigation.sar_orchestrator import InvestigationResult, SARLoopOrchestrator
from elile.risk.connection_analyzer import (
    ConnectionAnalysisResult,
    ConnectionAnalyzer,
    create_connection_analyzer,
)

# =============================================================================
# D3 Review Point Types (Task 7.8 Enhancement)
# =============================================================================


class D3ReviewPointType(str, Enum):
    """Types of manual review points in D3 investigation."""

    HIGH_RISK_ENTITY = "high_risk_entity"  # Entity with risk >= threshold
    NETWORK_CLUSTER = "network_cluster"  # Dense cluster of connections
    CROSS_JURISDICTIONAL = "cross_jurisdictional"  # Cross-border connections
    SANCTIONS_HIT = "sanctions_hit"  # Potential sanctions match
    PEP_CONNECTION = "pep_connection"  # Politically exposed person connection
    ADVERSE_MEDIA = "adverse_media"  # Significant adverse media findings
    DATA_CONFLICT = "data_conflict"  # Conflicting information across sources
    DEPTH_THRESHOLD = "depth_threshold"  # Network depth exceeds threshold


@dataclass
class D3ReviewPoint:
    """A point in D3 investigation requiring manual review.

    Review points are automatically created when certain conditions are met
    during comprehensive D3 investigations, ensuring human oversight of
    critical findings.
    """

    review_id: UUID = field(default_factory=uuid7)
    review_type: D3ReviewPointType = D3ReviewPointType.HIGH_RISK_ENTITY
    entity_id: UUID | None = None
    entity_name: str = ""
    description: str = ""
    severity: str = "medium"  # low, medium, high, critical
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    reviewed: bool = False
    reviewed_at: datetime | None = None
    reviewer_notes: str = ""
    decision: str = ""  # continue, escalate, terminate

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "review_id": str(self.review_id),
            "review_type": self.review_type.value,
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "entity_name": self.entity_name,
            "description": self.description,
            "severity": self.severity,
            "created_at": self.created_at.isoformat(),
            "reviewed": self.reviewed,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewer_notes": self.reviewer_notes,
            "decision": self.decision,
        }


@dataclass
class D3SourceCoverage:
    """Tracks source coverage for D3 comprehensive investigations.

    D3 investigations should cover extended source types beyond D1/D2
    for thorough network analysis.
    """

    # Core sources (inherited from D1/D2)
    identity_sources_used: list[str] = field(default_factory=list)
    employment_sources_used: list[str] = field(default_factory=list)
    education_sources_used: list[str] = field(default_factory=list)

    # Extended sources (D3 specific)
    sanctions_sources_used: list[str] = field(default_factory=list)
    pep_sources_used: list[str] = field(default_factory=list)
    adverse_media_sources_used: list[str] = field(default_factory=list)
    corporate_registry_sources_used: list[str] = field(default_factory=list)
    court_record_sources_used: list[str] = field(default_factory=list)
    social_media_sources_used: list[str] = field(default_factory=list)

    # Coverage metrics
    total_sources_queried: int = 0
    sources_with_hits: int = 0
    sources_with_errors: int = 0
    coverage_score: float = 0.0  # 0.0-1.0

    def calculate_coverage_score(self) -> float:
        """Calculate overall source coverage score."""
        all_sources = (
            self.identity_sources_used
            + self.employment_sources_used
            + self.education_sources_used
            + self.sanctions_sources_used
            + self.pep_sources_used
            + self.adverse_media_sources_used
            + self.corporate_registry_sources_used
            + self.court_record_sources_used
            + self.social_media_sources_used
        )
        if not all_sources:
            return 0.0

        unique_sources = set(all_sources)
        # Weight critical sources higher
        critical_coverage = sum(
            1
            for s in unique_sources
            if any(x in s.lower() for x in ["sanctions", "pep", "watchlist", "ofac", "adverse"])
        )
        base_coverage = len(unique_sources) / max(self.total_sources_queried, 1)
        critical_bonus = min(critical_coverage * 0.1, 0.3)

        self.coverage_score = min(1.0, base_coverage + critical_bonus)
        return self.coverage_score

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "identity_sources": self.identity_sources_used,
            "employment_sources": self.employment_sources_used,
            "education_sources": self.education_sources_used,
            "sanctions_sources": self.sanctions_sources_used,
            "pep_sources": self.pep_sources_used,
            "adverse_media_sources": self.adverse_media_sources_used,
            "corporate_registry_sources": self.corporate_registry_sources_used,
            "court_record_sources": self.court_record_sources_used,
            "social_media_sources": self.social_media_sources_used,
            "total_sources_queried": self.total_sources_queried,
            "sources_with_hits": self.sources_with_hits,
            "sources_with_errors": self.sources_with_errors,
            "coverage_score": self.coverage_score,
        }


# =============================================================================
# Configuration
# =============================================================================


class DegreeHandlerConfig(BaseModel):
    """Configuration for degree handlers."""

    # D1 configuration
    d1_max_facts_per_type: int = Field(default=100, description="Max facts per info type")

    # D2 configuration
    d2_max_entities: int = Field(default=10, description="Max entities to investigate in D2")
    d2_min_relevance: float = Field(default=0.5, description="Min relevance score for D2")

    # D3 configuration
    d3_max_entities: int = Field(default=25, description="Max entities to investigate in D3")
    d3_min_relevance: float = Field(default=0.4, description="Min relevance score for D3")
    d3_max_depth: int = Field(default=2, description="Max hops from subject")

    # D3 Enhanced configuration (Task 7.8)
    d3_enable_review_points: bool = Field(
        default=True, description="Enable manual review checkpoints"
    )
    d3_review_risk_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Risk threshold for review point"
    )
    d3_review_on_sanctions_hit: bool = Field(
        default=True, description="Create review point on sanctions hit"
    )
    d3_review_on_pep_connection: bool = Field(
        default=True, description="Create review point on PEP connection"
    )
    d3_checkpoint_interval: int = Field(
        default=5, ge=1, description="Entities between auto-checkpoints"
    )
    d3_extended_sources: bool = Field(default=True, description="Enable extended source coverage")

    # Entity prioritization weights
    weight_relationship_strength: float = Field(default=0.3, description="Weight for relationship")
    weight_entity_risk: float = Field(default=0.4, description="Weight for entity risk")
    weight_data_availability: float = Field(default=0.3, description="Weight for data availability")


# =============================================================================
# Result Models
# =============================================================================


@dataclass
class D1Result:
    """Result from D1 (subject-only) investigation.

    Contains findings about the subject and entities discovered
    (but not investigated) during the process.
    """

    result_id: UUID = field(default_factory=uuid7)
    findings: list[Finding] = field(default_factory=list)
    discovered_entities: list[DiscoveredEntity] = field(default_factory=list)
    entity_queue: list[DiscoveredEntity] = field(default_factory=list)  # Empty for D1
    knowledge_base: KnowledgeBase | None = None
    investigation_result: InvestigationResult | None = None

    # Statistics
    total_facts: int = 0
    total_queries: int = 0
    types_completed: int = 0

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    @property
    def duration_seconds(self) -> float | None:
        """Get duration in seconds."""
        if self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "result_id": str(self.result_id),
            "findings_count": len(self.findings),
            "discovered_entities_count": len(self.discovered_entities),
            "entity_queue_count": len(self.entity_queue),
            "total_facts": self.total_facts,
            "total_queries": self.total_queries,
            "types_completed": self.types_completed,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class D2Result:
    """Result from D2 (direct connections) investigation.

    Contains findings from investigating direct connections discovered
    during D1, plus connection analysis.
    """

    result_id: UUID = field(default_factory=uuid7)
    d1_result: D1Result | None = None

    # Entity investigation results
    entity_findings: dict[UUID, list[Finding]] = field(default_factory=dict)
    investigated_entities: list[DiscoveredEntity] = field(default_factory=list)

    # Connection analysis
    connections: list[EntityRelation] = field(default_factory=list)
    risk_connections: list[RiskConnection] = field(default_factory=list)
    connection_analysis: ConnectionAnalysisResult | None = None

    # Statistics
    entities_investigated: int = 0
    entities_skipped: int = 0
    total_propagated_risk: float = 0.0

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    @property
    def duration_seconds(self) -> float | None:
        """Get duration in seconds."""
        if self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "result_id": str(self.result_id),
            "d1_result": self.d1_result.to_dict() if self.d1_result else None,
            "entities_investigated": self.entities_investigated,
            "entities_skipped": self.entities_skipped,
            "connections_count": len(self.connections),
            "risk_connections_count": len(self.risk_connections),
            "total_propagated_risk": self.total_propagated_risk,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class D3Result:
    """Result from D3 (extended network) investigation.

    Contains findings from investigating extended network (2+ hops),
    including entities discovered through D2 connections.

    Task 7.8 Enhanced Features:
    - Manual review points for critical findings
    - Extended source coverage tracking
    - Checkpoint references for resume capability
    """

    result_id: UUID = field(default_factory=uuid7)
    d2_result: D2Result | None = None

    # Extended network investigation
    extended_entity_findings: dict[UUID, list[Finding]] = field(default_factory=dict)
    extended_entities: list[DiscoveredEntity] = field(default_factory=list)

    # Extended connection analysis
    extended_connections: list[EntityRelation] = field(default_factory=list)
    extended_risk_connections: list[RiskConnection] = field(default_factory=list)
    extended_connection_analysis: ConnectionAnalysisResult | None = None

    # Network metrics
    network_depth: int = 0
    network_breadth: int = 0

    # Statistics
    extended_entities_investigated: int = 0
    extended_entities_skipped: int = 0
    total_network_risk: float = 0.0

    # Task 7.8 Enhanced: Manual review points
    review_points: list[D3ReviewPoint] = field(default_factory=list)
    pending_reviews: int = 0
    reviews_completed: int = 0

    # Task 7.8 Enhanced: Source coverage
    source_coverage: D3SourceCoverage | None = None

    # Task 7.8 Enhanced: Checkpoint references
    checkpoint_ids: list[UUID] = field(default_factory=list)
    last_checkpoint_id: UUID | None = None
    investigation_id: UUID | None = None

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    @property
    def duration_seconds(self) -> float | None:
        """Get duration in seconds."""
        if self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def has_pending_reviews(self) -> bool:
        """Check if there are pending review points."""
        return self.pending_reviews > 0

    @property
    def review_summary(self) -> dict[str, int]:
        """Get summary of review points by type."""
        summary: dict[str, int] = {}
        for rp in self.review_points:
            key = rp.review_type.value
            summary[key] = summary.get(key, 0) + 1
        return summary

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "result_id": str(self.result_id),
            "d2_result": self.d2_result.to_dict() if self.d2_result else None,
            "extended_entities_investigated": self.extended_entities_investigated,
            "extended_entities_skipped": self.extended_entities_skipped,
            "network_depth": self.network_depth,
            "network_breadth": self.network_breadth,
            "total_network_risk": self.total_network_risk,
            # Task 7.8 Enhanced fields
            "review_points": [rp.to_dict() for rp in self.review_points],
            "pending_reviews": self.pending_reviews,
            "reviews_completed": self.reviews_completed,
            "review_summary": self.review_summary,
            "source_coverage": self.source_coverage.to_dict() if self.source_coverage else None,
            "checkpoint_ids": [str(cid) for cid in self.checkpoint_ids],
            "last_checkpoint_id": str(self.last_checkpoint_id) if self.last_checkpoint_id else None,
            "investigation_id": str(self.investigation_id) if self.investigation_id else None,
            # Timing
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
        }


# =============================================================================
# D1 Handler
# =============================================================================


class D1Handler:
    """Handles D1 (subject-only) investigations.

    D1 investigations process the subject's data across all information types
    but do not investigate discovered entities. Entities found during
    investigation are recorded but placed in an empty queue.
    """

    def __init__(
        self,
        sar_orchestrator: SARLoopOrchestrator | None = None,
        config: DegreeHandlerConfig | None = None,
    ) -> None:
        """Initialize D1 handler.

        Args:
            sar_orchestrator: SAR loop orchestrator for investigations.
            config: Handler configuration.
        """
        self.sar_orchestrator = sar_orchestrator
        self.config = config or DegreeHandlerConfig()

    async def execute_d1(
        self,
        knowledge_base: KnowledgeBase,
        subject_name: str,  # noqa: ARG002 - reserved for audit logging
        locale: Locale,
        tier: ServiceTier,
        role_category: RoleCategory,
        available_providers: list[str],
        entity_id: UUID | None = None,
        tenant_id: UUID | None = None,
        ctx: RequestContext | None = None,
    ) -> D1Result:
        """Execute D1 (subject-only) investigation.

        Args:
            knowledge_base: Knowledge base to populate.
            subject_name: Subject's name (reserved for audit logging).
            locale: Geographic locale.
            tier: Service tier.
            role_category: Job role category.
            available_providers: List of available provider IDs.
            entity_id: Optional entity ID.
            tenant_id: Optional tenant ID.
            ctx: Optional request context.

        Returns:
            D1Result with findings and discovered entities.
        """
        ctx = ctx or get_current_context_or_none()
        result = D1Result()

        # Execute SAR loop for subject
        if self.sar_orchestrator:
            investigation_result = await self.sar_orchestrator.execute_investigation(
                knowledge_base=knowledge_base,
                subject_identifiers=None,
                locale=locale,
                tier=tier,
                role_category=role_category,
                available_providers=available_providers,
                entity_id=entity_id,
                tenant_id=tenant_id,
            )

            result.investigation_result = investigation_result
            result.knowledge_base = knowledge_base
            result.total_facts = investigation_result.total_facts
            result.total_queries = investigation_result.total_queries
            result.types_completed = investigation_result.types_completed

            # Extract findings from investigation result
            result.findings = self._extract_findings(investigation_result)

            # Extract discovered entities from knowledge base
            result.discovered_entities = self._extract_entities(knowledge_base)

        # D1 does not investigate discovered entities - empty queue
        result.entity_queue = []

        result.completed_at = datetime.now(UTC)
        return result

    def _extract_findings(self, investigation_result: InvestigationResult) -> list[Finding]:
        """Extract findings from investigation result.

        Args:
            investigation_result: SAR loop investigation result.

        Returns:
            List of findings.
        """
        findings: list[Finding] = []

        # Extract findings from each type result
        for type_result in investigation_result.type_results.values():
            if hasattr(type_result, "findings") and type_result.findings:
                findings.extend(type_result.findings)

        return findings

    def _extract_entities(self, knowledge_base: KnowledgeBase) -> list[DiscoveredEntity]:
        """Extract discovered entities from knowledge base.

        Args:
            knowledge_base: Knowledge base with accumulated facts.

        Returns:
            List of discovered entities.
        """
        entities: list[DiscoveredEntity] = []

        # Extract discovered people
        if knowledge_base.discovered_people:
            for person in knowledge_base.discovered_people:
                entities.append(
                    DiscoveredEntity(
                        entity_id=uuid7(),
                        entity_type=EntityType.PERSON,
                        name=person.name,
                        discovery_degree=2,
                        confidence=0.7,
                        source_providers=["knowledge_base"],
                        metadata={"relationship": "associated"},
                    )
                )

        # Extract discovered organizations
        if knowledge_base.discovered_orgs:
            for org in knowledge_base.discovered_orgs:
                entities.append(
                    DiscoveredEntity(
                        entity_id=uuid7(),
                        entity_type=EntityType.ORGANIZATION,
                        name=org.name,
                        discovery_degree=2,
                        confidence=0.8,
                        source_providers=["knowledge_base"],
                        metadata={"relationship": "organization"},
                    )
                )

        # Extract employers
        if knowledge_base.employers:
            for employer in knowledge_base.employers:
                entities.append(
                    DiscoveredEntity(
                        entity_id=uuid7(),
                        entity_type=EntityType.ORGANIZATION,
                        name=employer.employer_name,
                        discovery_degree=2,
                        confidence=0.9,
                        source_providers=["employment_verification"],
                        metadata={"relationship": "employer"},
                    )
                )

        return entities


# =============================================================================
# D2 Handler
# =============================================================================


class D2Handler:
    """Handles D2 (direct connections) investigations.

    D2 investigations process direct connections discovered during D1,
    investigating entities that have direct relationships with the subject.
    """

    def __init__(
        self,
        sar_orchestrator: SARLoopOrchestrator | None = None,
        connection_analyzer: ConnectionAnalyzer | None = None,
        config: DegreeHandlerConfig | None = None,
    ) -> None:
        """Initialize D2 handler.

        Args:
            sar_orchestrator: SAR loop orchestrator for investigations.
            connection_analyzer: Connection risk analyzer.
            config: Handler configuration.
        """
        self.sar_orchestrator = sar_orchestrator
        self.connection_analyzer = connection_analyzer or create_connection_analyzer()
        self.config = config or DegreeHandlerConfig()

    async def execute_d2(
        self,
        d1_result: D1Result,
        locale: Locale,
        tier: ServiceTier,
        role_category: RoleCategory,
        available_providers: list[str],
        tenant_id: UUID | None = None,
        ctx: RequestContext | None = None,
    ) -> D2Result:
        """Execute D2 (direct connections) investigation.

        Args:
            d1_result: Result from D1 investigation.
            locale: Geographic locale.
            tier: Service tier.
            role_category: Job role category.
            available_providers: List of available provider IDs.
            tenant_id: Optional tenant ID.
            ctx: Optional request context.

        Returns:
            D2Result with entity findings and connections.
        """
        ctx = ctx or get_current_context_or_none()
        result = D2Result(d1_result=d1_result)

        # Prioritize entities for investigation
        prioritized = self._prioritize_entities(
            d1_result.discovered_entities,
            self.config.d2_max_entities,
        )

        result.entities_skipped = len(d1_result.discovered_entities) - len(prioritized)

        # Investigate each prioritized entity
        for entity in prioritized:
            entity_findings = await self._investigate_entity(
                entity=entity,
                locale=locale,
                tier=tier,
                role_category=role_category,
                available_providers=available_providers,
                tenant_id=tenant_id,
            )
            result.entity_findings[entity.entity_id] = entity_findings
            result.investigated_entities.append(entity)

        result.entities_investigated = len(result.investigated_entities)

        # Build connections from investigated entities
        result.connections = self._build_connections(
            d1_result.discovered_entities,
            result.investigated_entities,
        )

        # Analyze connection risks
        if self.connection_analyzer and result.investigated_entities:
            result.connection_analysis = self.connection_analyzer.analyze_connections(
                subject_entity=self._create_subject_entity(d1_result),
                discovered_entities=result.investigated_entities,
                relations=result.connections,
                degree=SearchDegree.D2,
            )

            if result.connection_analysis:
                result.risk_connections = result.connection_analysis.risk_connections_found
                result.total_propagated_risk = result.connection_analysis.total_propagated_risk

        result.completed_at = datetime.now(UTC)
        return result

    def _prioritize_entities(
        self,
        entities: list[DiscoveredEntity],
        max_count: int,
    ) -> list[DiscoveredEntity]:
        """Prioritize entities for investigation.

        Args:
            entities: Discovered entities.
            max_count: Maximum entities to return.

        Returns:
            Prioritized list of entities.
        """
        if not entities:
            return []

        # Calculate priority score for each entity
        scored: list[tuple[float, DiscoveredEntity]] = []
        for entity in entities:
            score = self._calculate_entity_priority(entity)
            if score >= self.config.d2_min_relevance:
                scored.append((score, entity))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Return top N
        return [entity for _, entity in scored[:max_count]]

    def _calculate_entity_priority(self, entity: DiscoveredEntity) -> float:
        """Calculate priority score for entity.

        Args:
            entity: Discovered entity.

        Returns:
            Priority score (0.0-1.0).
        """
        score = 0.0

        # Relationship strength component (from metadata)
        relationship = (
            entity.metadata.get("relationship", "unknown") if entity.metadata else "unknown"
        )
        relationship_score = self._get_relationship_score(relationship)
        score += relationship_score * self.config.weight_relationship_strength

        # Entity risk component (based on type and flags)
        risk_score = self._get_entity_risk_score(entity)
        score += risk_score * self.config.weight_entity_risk

        # Data availability component (confidence as proxy)
        score += entity.confidence * self.config.weight_data_availability

        return min(1.0, score)

    def _get_relationship_score(self, relationship: str) -> float:
        """Get score for relationship type.

        Args:
            relationship: Relationship type.

        Returns:
            Score (0.0-1.0).
        """
        relationship_scores = {
            "employer": 0.9,
            "business_partner": 0.85,
            "family": 0.8,
            "financial": 0.85,
            "legal": 0.8,
            "associated": 0.6,
            "social": 0.4,
            "educational": 0.3,
        }
        return relationship_scores.get(relationship.lower(), 0.5)

    def _get_entity_risk_score(self, entity: DiscoveredEntity) -> float:
        """Get risk score for entity.

        Args:
            entity: Discovered entity.

        Returns:
            Risk score (0.0-1.0).
        """
        score = 0.5  # Base score

        # Adjust based on entity type
        if entity.entity_type == EntityType.ORGANIZATION:
            score += 0.1  # Organizations often have more data

        # Adjust based on risk level if available
        if hasattr(entity, "risk_level"):
            risk_adjustments = {
                RiskLevel.CRITICAL: 0.4,
                RiskLevel.HIGH: 0.3,
                RiskLevel.MODERATE: 0.1,
                RiskLevel.LOW: 0.0,
            }
            score += risk_adjustments.get(entity.risk_level, 0.0)

        return min(1.0, score)

    async def _investigate_entity(
        self,
        entity: DiscoveredEntity,
        locale: Locale,  # noqa: ARG002 - reserved for compliance filtering
        tier: ServiceTier,  # noqa: ARG002 - reserved for provider selection
        role_category: RoleCategory,  # noqa: ARG002 - reserved for depth adjustment
        available_providers: list[str],  # noqa: ARG002 - reserved for provider calls
        tenant_id: UUID | None = None,  # noqa: ARG002 - reserved for multi-tenant isolation
    ) -> list[Finding]:
        """Investigate a single entity.

        This method signature is reserved for full implementation.
        Parameters are defined for interface consistency with D3Handler.

        Args:
            entity: Entity to investigate.
            locale: Geographic locale (reserved for compliance filtering).
            tier: Service tier (reserved for provider selection).
            role_category: Job role category (reserved for depth adjustment).
            available_providers: Available provider IDs (reserved for provider calls).
            tenant_id: Optional tenant ID (reserved for multi-tenant isolation).

        Returns:
            List of findings for the entity.
        """
        findings: list[Finding] = []

        # Limited investigation for connected entities
        # Focus on sanctions, PEP, and adverse media checks
        if self.sar_orchestrator:
            # Create knowledge base for entity
            entity_kb = KnowledgeBase()
            entity_kb.confirmed_names.append(entity.name)

            # Execute limited SAR loop (sanctions/regulatory only)
            # In a full implementation, this would run a subset of information types
            pass

        return findings

    def _build_connections(
        self,
        all_entities: list[DiscoveredEntity],
        investigated_entities: list[DiscoveredEntity],
    ) -> list[EntityRelation]:
        """Build connection relationships.

        Args:
            all_entities: All discovered entities.
            investigated_entities: Entities that were investigated.

        Returns:
            List of entity relations.
        """
        connections: list[EntityRelation] = []

        investigated_ids = {e.entity_id for e in investigated_entities}

        for entity in all_entities:
            if entity.entity_id in investigated_ids:
                # Get relationship from metadata
                relationship = (
                    entity.metadata.get("relationship", "unknown") if entity.metadata else "unknown"
                )
                connections.append(
                    EntityRelation(
                        source_entity_id=uuid7(),  # Subject
                        target_entity_id=entity.entity_id,
                        relation_type=relationship,
                        strength=ConnectionStrength.MODERATE,
                        confidence=entity.confidence,
                    )
                )

        return connections

    def _create_subject_entity(self, d1_result: D1Result) -> DiscoveredEntity:
        """Create subject entity for connection analysis.

        Args:
            d1_result: D1 result.

        Returns:
            Subject as DiscoveredEntity.
        """
        subject_name = "Subject"
        if d1_result.knowledge_base and d1_result.knowledge_base.confirmed_names:
            subject_name = d1_result.knowledge_base.confirmed_names[0]

        return DiscoveredEntity(
            entity_id=uuid7(),
            entity_type=EntityType.PERSON,
            name=subject_name,
            discovery_degree=1,
            confidence=1.0,
            source_providers=["subject"],
            metadata={"relationship": "subject"},
        )


# =============================================================================
# D3 Handler (Enhanced - Task 7.8)
# =============================================================================


class D3Handler:
    """Handles D3 (extended network) comprehensive investigations.

    D3 investigations extend beyond direct connections to investigate
    entities connected to D2 entities (2+ hops from subject).

    Task 7.8 Enhanced Features:
    - Manual review checkpoint integration for critical findings
    - Extended source coverage tracking across multiple provider types
    - Automatic review point creation based on configurable thresholds
    - Checkpoint-based resume capability for long-running investigations
    """

    def __init__(
        self,
        d2_handler: D2Handler | None = None,
        connection_analyzer: ConnectionAnalyzer | None = None,
        checkpoint_manager: CheckpointManager | None = None,
        config: DegreeHandlerConfig | None = None,
    ) -> None:
        """Initialize D3 handler.

        Args:
            d2_handler: D2 handler for nested investigations.
            connection_analyzer: Connection risk analyzer.
            checkpoint_manager: Checkpoint manager for review points.
            config: Handler configuration.
        """
        self.d2_handler = d2_handler
        self.connection_analyzer = connection_analyzer or create_connection_analyzer()
        self.checkpoint_manager = checkpoint_manager or create_checkpoint_manager()
        self.config = config or DegreeHandlerConfig()

    async def execute_d3(
        self,
        d2_result: D2Result,
        locale: Locale,
        tier: ServiceTier,
        role_category: RoleCategory,
        available_providers: list[str],
        tenant_id: UUID | None = None,
        investigation_id: UUID | None = None,
        ctx: RequestContext | None = None,
    ) -> D3Result:
        """Execute D3 (extended network) comprehensive investigation.

        Args:
            d2_result: Result from D2 investigation.
            locale: Geographic locale.
            tier: Service tier.
            role_category: Job role category.
            available_providers: List of available provider IDs.
            tenant_id: Optional tenant ID.
            investigation_id: Optional investigation ID for checkpoints.
            ctx: Optional request context.

        Returns:
            D3Result with extended network findings, review points, and source coverage.
        """
        ctx = ctx or get_current_context_or_none()
        result = D3Result(d2_result=d2_result)
        result.investigation_id = investigation_id or uuid7()

        # Initialize source coverage tracking (Task 7.8)
        if self.config.d3_extended_sources:
            result.source_coverage = D3SourceCoverage(
                total_sources_queried=len(available_providers)
            )
            self._categorize_providers(available_providers, result.source_coverage)

        # Collect entities discovered during D2
        d2_discovered: list[DiscoveredEntity] = []
        for _entity in d2_result.investigated_entities:
            # In a full implementation, we would track entities
            # discovered during each entity's investigation
            pass

        # Prioritize extended entities
        prioritized = self._prioritize_extended_entities(
            d2_discovered,
            self.config.d3_max_entities,
        )

        result.extended_entities_skipped = len(d2_discovered) - len(prioritized)

        # Investigate extended entities with checkpointing
        entities_since_checkpoint = 0
        for entity in prioritized:
            entity_findings = await self._investigate_extended_entity(
                entity=entity,
                locale=locale,
                tier=tier,
                role_category=role_category,
                available_providers=available_providers,
                tenant_id=tenant_id,
            )
            result.extended_entity_findings[entity.entity_id] = entity_findings
            result.extended_entities.append(entity)

            # Check for review points (Task 7.8)
            if self.config.d3_enable_review_points:
                review_points = self._check_for_review_points(
                    entity=entity,
                    findings=entity_findings,
                    result=result,
                )
                result.review_points.extend(review_points)

            # Create checkpoint at intervals (Task 7.8)
            entities_since_checkpoint += 1
            if (
                entities_since_checkpoint >= self.config.d3_checkpoint_interval
                and result.investigation_id is not None
            ):
                checkpoint = await self._create_checkpoint(
                    result=result,
                    investigation_id=result.investigation_id,
                    current_phase="d3_entity_investigation",
                )
                if checkpoint:
                    result.checkpoint_ids.append(checkpoint.checkpoint_id)
                    result.last_checkpoint_id = checkpoint.checkpoint_id
                entities_since_checkpoint = 0

        result.extended_entities_investigated = len(result.extended_entities)

        # Build extended connections
        result.extended_connections = self._build_extended_connections(
            d2_result.investigated_entities,
            result.extended_entities,
        )

        # Analyze extended network risks
        if self.connection_analyzer and result.extended_entities:
            # Combine all entities for analysis
            all_entities = d2_result.investigated_entities + result.extended_entities
            all_relations = d2_result.connections + result.extended_connections

            result.extended_connection_analysis = self.connection_analyzer.analyze_connections(
                subject_entity=self._create_subject_entity(d2_result),
                discovered_entities=all_entities,
                relations=all_relations,
                degree=SearchDegree.D3,
            )

            if result.extended_connection_analysis:
                result.extended_risk_connections = (
                    result.extended_connection_analysis.risk_connections_found
                )
                result.total_network_risk = (
                    result.extended_connection_analysis.total_propagated_risk
                )

                # Check network-level review points (Task 7.8)
                if self.config.d3_enable_review_points:
                    network_reviews = self._check_network_review_points(result)
                    result.review_points.extend(network_reviews)

        # Calculate network metrics
        result.network_depth = self.config.d3_max_depth
        result.network_breadth = len(d2_result.investigated_entities) + len(
            result.extended_entities
        )

        # Finalize review point counts
        result.pending_reviews = sum(1 for rp in result.review_points if not rp.reviewed)
        result.reviews_completed = sum(1 for rp in result.review_points if rp.reviewed)

        # Calculate source coverage score
        if result.source_coverage:
            result.source_coverage.calculate_coverage_score()

        # Final checkpoint with review status
        if (
            self.config.d3_enable_review_points
            and result.pending_reviews > 0
            and result.investigation_id is not None
        ):
            checkpoint = await self._create_review_checkpoint(
                result=result,
                investigation_id=result.investigation_id,
            )
            if checkpoint:
                result.checkpoint_ids.append(checkpoint.checkpoint_id)
                result.last_checkpoint_id = checkpoint.checkpoint_id

        result.completed_at = datetime.now(UTC)
        return result

    def _categorize_providers(
        self,
        providers: list[str],
        coverage: D3SourceCoverage,
    ) -> None:
        """Categorize providers by source type.

        Args:
            providers: List of provider IDs.
            coverage: Source coverage to update.
        """
        for provider in providers:
            provider_lower = provider.lower()
            if any(x in provider_lower for x in ["identity", "idv"]):
                coverage.identity_sources_used.append(provider)
            elif any(x in provider_lower for x in ["employment", "work"]):
                coverage.employment_sources_used.append(provider)
            elif any(x in provider_lower for x in ["education", "degree"]):
                coverage.education_sources_used.append(provider)
            elif any(x in provider_lower for x in ["sanction", "ofac", "watchlist"]):
                coverage.sanctions_sources_used.append(provider)
            elif any(x in provider_lower for x in ["pep", "political"]):
                coverage.pep_sources_used.append(provider)
            elif any(x in provider_lower for x in ["adverse", "media", "news"]):
                coverage.adverse_media_sources_used.append(provider)
            elif any(x in provider_lower for x in ["corporate", "registry", "company"]):
                coverage.corporate_registry_sources_used.append(provider)
            elif any(x in provider_lower for x in ["court", "legal", "litigation"]):
                coverage.court_record_sources_used.append(provider)
            elif any(x in provider_lower for x in ["social", "linkedin", "twitter"]):
                coverage.social_media_sources_used.append(provider)

    def _check_for_review_points(
        self,
        entity: DiscoveredEntity,
        findings: list[Finding],
        result: D3Result,  # noqa: ARG002 - reserved for future threshold checks
    ) -> list[D3ReviewPoint]:
        """Check if entity or findings warrant a review point.

        Args:
            entity: The investigated entity.
            findings: Findings from investigation.
            result: Current D3 result (reserved for threshold checks).

        Returns:
            List of review points to add.
        """
        review_points: list[D3ReviewPoint] = []

        # Check entity risk level
        if hasattr(entity, "risk_level") and entity.risk_level in (
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        ):
            review_points.append(
                D3ReviewPoint(
                    review_type=D3ReviewPointType.HIGH_RISK_ENTITY,
                    entity_id=entity.entity_id,
                    entity_name=entity.name,
                    description=f"Entity {entity.name} has {entity.risk_level.value} risk",
                    severity="high" if entity.risk_level == RiskLevel.HIGH else "critical",
                )
            )

        # Check findings for sanctions/PEP hits
        for finding in findings:
            if hasattr(finding, "category"):
                if "sanction" in str(finding.category).lower():
                    if self.config.d3_review_on_sanctions_hit:
                        review_points.append(
                            D3ReviewPoint(
                                review_type=D3ReviewPointType.SANCTIONS_HIT,
                                entity_id=entity.entity_id,
                                entity_name=entity.name,
                                description=f"Potential sanctions match for {entity.name}",
                                severity="critical",
                            )
                        )
                elif "pep" in str(finding.category).lower():
                    if self.config.d3_review_on_pep_connection:
                        review_points.append(
                            D3ReviewPoint(
                                review_type=D3ReviewPointType.PEP_CONNECTION,
                                entity_id=entity.entity_id,
                                entity_name=entity.name,
                                description=f"PEP connection identified: {entity.name}",
                                severity="high",
                            )
                        )
                elif "adverse" in str(finding.category).lower():
                    review_points.append(
                        D3ReviewPoint(
                            review_type=D3ReviewPointType.ADVERSE_MEDIA,
                            entity_id=entity.entity_id,
                            entity_name=entity.name,
                            description=f"Adverse media found for {entity.name}",
                            severity="medium",
                        )
                    )

        return review_points

    def _check_network_review_points(self, result: D3Result) -> list[D3ReviewPoint]:
        """Check for network-level review points.

        Args:
            result: Current D3 result.

        Returns:
            List of network-level review points.
        """
        review_points: list[D3ReviewPoint] = []

        # Check total network risk
        if result.total_network_risk >= self.config.d3_review_risk_threshold:
            review_points.append(
                D3ReviewPoint(
                    review_type=D3ReviewPointType.NETWORK_CLUSTER,
                    description=(
                        f"Network risk ({result.total_network_risk:.2f}) exceeds "
                        f"threshold ({self.config.d3_review_risk_threshold:.2f})"
                    ),
                    severity="high",
                )
            )

        # Check network depth
        if result.network_depth >= self.config.d3_max_depth:
            review_points.append(
                D3ReviewPoint(
                    review_type=D3ReviewPointType.DEPTH_THRESHOLD,
                    description=(
                        f"Network investigation reached maximum depth ({result.network_depth})"
                    ),
                    severity="medium",
                )
            )

        return review_points

    async def _create_checkpoint(
        self,
        result: D3Result,
        investigation_id: UUID,
        current_phase: str,
    ) -> CheckpointData | None:
        """Create a checkpoint for the current state.

        Args:
            result: Current D3 result.
            investigation_id: Investigation ID.
            current_phase: Current phase name.

        Returns:
            Created checkpoint or None.
        """
        if not self.checkpoint_manager:
            return None

        return self.checkpoint_manager.create_checkpoint(
            investigation_id=investigation_id,
            current_phase=current_phase,
            sar_phase=SARPhase.SEARCH,  # Use SEARCH for active investigation
            active_types=[InformationType.NETWORK_D3],
            completed_types=[],
            type_states={
                "d3_state": {
                    "extended_entities_count": result.extended_entities_investigated,
                    "total_network_risk": result.total_network_risk,
                }
            },
            iteration_count=len(result.extended_entity_findings),
            queries_executed=0,
            findings_count=sum(
                len(findings) for findings in result.extended_entity_findings.values()
            ),
            confidence_scores={},
            reason=CheckpointReason.AUTO_SAVE,
        )

    async def _create_review_checkpoint(
        self,
        result: D3Result,
        investigation_id: UUID,
    ) -> CheckpointData | None:
        """Create a checkpoint that requires manual review.

        Args:
            result: Current D3 result.
            investigation_id: Investigation ID.

        Returns:
            Created review checkpoint or None.
        """
        if not self.checkpoint_manager:
            return None

        review_summary = ", ".join(f"{k}: {v}" for k, v in result.review_summary.items())

        # Use create_checkpoint with requires_review=True
        return self.checkpoint_manager.create_checkpoint(
            investigation_id=investigation_id,
            current_phase="d3_review_required",
            sar_phase=SARPhase.ASSESS,  # Use ASSESS phase for review
            active_types=[InformationType.NETWORK_D3],
            completed_types=[],
            type_states={
                "d3_state": {
                    "extended_entities_count": result.extended_entities_investigated,
                    "total_network_risk": result.total_network_risk,
                    "pending_reviews": result.pending_reviews,
                }
            },
            review_notes=(
                f"D3 investigation complete with {result.pending_reviews} pending reviews. "
                f"Summary: {review_summary}"
            ),
            requires_review=True,
            reason=CheckpointReason.REVIEW_REQUIRED,
        )

    def get_pending_reviews(self, result: D3Result) -> list[D3ReviewPoint]:
        """Get all pending review points from a D3 result.

        Args:
            result: D3 result to check.

        Returns:
            List of unreviewed review points.
        """
        return [rp for rp in result.review_points if not rp.reviewed]

    def mark_review_complete(
        self,
        result: D3Result,
        review_id: UUID,
        reviewer_notes: str = "",
        decision: str = "continue",
    ) -> bool:
        """Mark a review point as complete.

        Args:
            result: D3 result containing the review point.
            review_id: ID of the review point to mark.
            reviewer_notes: Notes from the reviewer.
            decision: Decision made (continue, escalate, terminate).

        Returns:
            True if review was found and marked, False otherwise.
        """
        for rp in result.review_points:
            if rp.review_id == review_id:
                rp.reviewed = True
                rp.reviewed_at = datetime.now(UTC)
                rp.reviewer_notes = reviewer_notes
                rp.decision = decision
                result.pending_reviews = sum(1 for r in result.review_points if not r.reviewed)
                result.reviews_completed = sum(1 for r in result.review_points if r.reviewed)
                return True
        return False

    def _prioritize_extended_entities(
        self,
        entities: list[DiscoveredEntity],
        max_count: int,
    ) -> list[DiscoveredEntity]:
        """Prioritize extended entities for investigation.

        Args:
            entities: Discovered entities.
            max_count: Maximum entities to return.

        Returns:
            Prioritized list of entities.
        """
        if not entities:
            return []

        # Use stricter filtering for D3
        scored: list[tuple[float, DiscoveredEntity]] = []
        for entity in entities:
            score = self._calculate_extended_priority(entity)
            if score >= self.config.d3_min_relevance:
                scored.append((score, entity))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entity for _, entity in scored[:max_count]]

    def _calculate_extended_priority(self, entity: DiscoveredEntity) -> float:
        """Calculate priority for extended entity.

        Args:
            entity: Discovered entity.

        Returns:
            Priority score (0.0-1.0).
        """
        # D3 prioritizes based on risk indicators
        score = 0.3  # Lower base for extended network

        # Higher weight on risk indicators
        if hasattr(entity, "risk_level"):
            risk_adjustments = {
                RiskLevel.CRITICAL: 0.5,
                RiskLevel.HIGH: 0.4,
                RiskLevel.MODERATE: 0.2,
                RiskLevel.LOW: 0.0,
            }
            score += risk_adjustments.get(entity.risk_level, 0.0)

        # Confidence still matters
        score += entity.confidence * 0.2

        return min(1.0, score)

    async def _investigate_extended_entity(
        self,
        entity: DiscoveredEntity,  # noqa: ARG002 - reserved for entity-specific checks
        locale: Locale,  # noqa: ARG002 - reserved for compliance filtering
        tier: ServiceTier,  # noqa: ARG002 - reserved for provider selection
        role_category: RoleCategory,  # noqa: ARG002 - reserved for depth adjustment
        available_providers: list[str],  # noqa: ARG002 - reserved for provider calls
        tenant_id: UUID | None = None,  # noqa: ARG002 - reserved for multi-tenant isolation
    ) -> list[Finding]:
        """Investigate an extended network entity.

        This method signature matches the D2Handler interface for consistency.
        Parameters are reserved for implementation when provider integration is complete.

        Args:
            entity: Entity to investigate.
            locale: Geographic locale (reserved for compliance filtering).
            tier: Service tier (reserved for provider selection).
            role_category: Job role category (reserved for depth adjustment).
            available_providers: Available provider IDs (reserved for provider calls).
            tenant_id: Optional tenant ID (reserved for multi-tenant isolation).

        Returns:
            List of findings for the entity.
        """
        # Very limited investigation for extended entities
        # Focus primarily on sanctions and watchlist checks
        findings: list[Finding] = []
        return findings

    def _build_extended_connections(
        self,
        d2_entities: list[DiscoveredEntity],
        d3_entities: list[DiscoveredEntity],
    ) -> list[EntityRelation]:
        """Build extended connection relationships.

        Args:
            d2_entities: D2 investigated entities.
            d3_entities: D3 investigated entities.

        Returns:
            List of entity relations.
        """
        connections: list[EntityRelation] = []

        # Create connections from D2 entities to D3 entities
        for d3_entity in d3_entities:
            # In a full implementation, we would track which D2 entity
            # led to discovering each D3 entity
            if d2_entities:
                connections.append(
                    EntityRelation(
                        source_entity_id=d2_entities[0].entity_id,  # Simplified
                        target_entity_id=d3_entity.entity_id,
                        relation_type="network_connection",
                        strength=ConnectionStrength.WEAK,
                        confidence=d3_entity.confidence * 0.8,  # Reduced confidence
                    )
                )

        return connections

    def _create_subject_entity(self, d2_result: D2Result) -> DiscoveredEntity:
        """Create subject entity for connection analysis.

        Args:
            d2_result: D2 result.

        Returns:
            Subject as DiscoveredEntity.
        """
        subject_name = "Subject"
        if d2_result.d1_result and d2_result.d1_result.knowledge_base:
            kb = d2_result.d1_result.knowledge_base
            if kb.confirmed_names:
                subject_name = kb.confirmed_names[0]

        return DiscoveredEntity(
            entity_id=uuid7(),
            entity_type=EntityType.PERSON,
            name=subject_name,
            discovery_degree=1,
            confidence=1.0,
            source_providers=["subject"],
            metadata={"relationship": "subject"},
        )


# =============================================================================
# Factory Functions
# =============================================================================


def create_d1_handler(
    sar_orchestrator: SARLoopOrchestrator | None = None,
    config: DegreeHandlerConfig | None = None,
) -> D1Handler:
    """Create D1 handler with default configuration.

    Args:
        sar_orchestrator: Optional SAR orchestrator.
        config: Optional configuration.

    Returns:
        Configured D1Handler.
    """
    return D1Handler(
        sar_orchestrator=sar_orchestrator,
        config=config or DegreeHandlerConfig(),
    )


def create_d2_handler(
    sar_orchestrator: SARLoopOrchestrator | None = None,
    connection_analyzer: ConnectionAnalyzer | None = None,
    config: DegreeHandlerConfig | None = None,
) -> D2Handler:
    """Create D2 handler with default configuration.

    Args:
        sar_orchestrator: Optional SAR orchestrator.
        connection_analyzer: Optional connection analyzer.
        config: Optional configuration.

    Returns:
        Configured D2Handler.
    """
    return D2Handler(
        sar_orchestrator=sar_orchestrator,
        connection_analyzer=connection_analyzer,
        config=config or DegreeHandlerConfig(),
    )


def create_d3_handler(
    d2_handler: D2Handler | None = None,
    connection_analyzer: ConnectionAnalyzer | None = None,
    checkpoint_manager: CheckpointManager | None = None,
    config: DegreeHandlerConfig | None = None,
) -> D3Handler:
    """Create D3 handler with default configuration.

    Args:
        d2_handler: Optional D2 handler.
        connection_analyzer: Optional connection analyzer.
        checkpoint_manager: Optional checkpoint manager for review points.
        config: Optional configuration.

    Returns:
        Configured D3Handler with enhanced features (Task 7.8).
    """
    return D3Handler(
        d2_handler=d2_handler,
        connection_analyzer=connection_analyzer,
        checkpoint_manager=checkpoint_manager,
        config=config or DegreeHandlerConfig(),
    )
