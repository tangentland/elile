"""Network Phase Handler for relationship mapping and entity connection analysis.

This module provides:
- NetworkPhaseHandler: Handles D2/D3 network analysis phase
- NetworkProfile: Combined network analysis results
- DiscoveredEntity: Entity discovered in network analysis
- EntityRelation: Relationship between entities
- RiskConnection: Risky connection with recommendations
- EntityType, RelationType, RiskLevel, ConnectionStrength: Enums

The Network phase analyzes relationships and connections for D2 (direct)
and D3 (extended) investigation degrees, building entity graphs and
identifying risk-relevant associations.

Architecture Reference: docs/architecture/05-investigation.md
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.core.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Enums
# =============================================================================


class EntityType(str, Enum):
    """Types of entities discovered in network analysis."""

    PERSON = "person"
    INDIVIDUAL = "person"  # Alias for backwards compatibility
    COMPANY = "company"
    ORGANIZATION = "organization"
    TRUST = "trust"
    GOVERNMENT_ENTITY = "government_entity"
    SHELL_COMPANY = "shell_company"
    UNKNOWN = "unknown"


class RelationType(str, Enum):
    """Types of relationships between entities."""

    # Primary relationship categories (used for risk weighting)
    FAMILY = "family"
    BUSINESS = "business"
    OWNERSHIP = "ownership"
    FINANCIAL = "financial"
    EMPLOYMENT = "employment"
    LEGAL = "legal"
    SOCIAL = "social"
    PROFESSIONAL = "professional"
    EDUCATIONAL = "educational"
    POLITICAL = "political"
    OTHER = "other"

    # Detailed business relationships
    EMPLOYER = "employer"
    EMPLOYEE = "employee"
    BUSINESS_PARTNER = "business_partner"
    INVESTOR = "investor"
    BOARD_MEMBER = "board_member"
    SHAREHOLDER = "shareholder"
    BENEFICIAL_OWNER = "beneficial_owner"

    # Detailed personal relationships
    SPOUSE = "spouse"
    ASSOCIATE = "associate"
    FRIEND = "friend"

    # Legal/regulatory
    LEGAL_REPRESENTATIVE = "legal_representative"
    REGISTERED_AGENT = "registered_agent"
    POWER_OF_ATTORNEY = "power_of_attorney"

    # Other
    CO_SIGNATORY = "co_signatory"
    COUNTERPARTY = "counterparty"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    """Risk levels for network connections."""

    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class ConnectionStrength(str, Enum):
    """Strength of connection between entities."""

    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    DIRECT = "direct"


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class DiscoveredEntity:
    """An entity discovered during network analysis.

    Represents a person, company, or organization found through
    relationship analysis that may be relevant to the investigation.

    Attributes:
        entity_id: Unique identifier for this entity.
        entity_type: Type of entity (person, company, etc.).
        name: Name or identifier of the entity.
        aliases: Known aliases or alternate names.
        jurisdiction: Primary jurisdiction of the entity.
        discovery_degree: Degree at which entity was discovered (D2, D3).
        source_providers: Providers that contributed to discovery.
        confidence: Confidence in entity identification (0.0-1.0).
        risk_indicators: Risk indicators associated with entity.
        is_sanctioned: Whether entity appears on sanctions lists.
        is_pep: Whether entity is a Politically Exposed Person.
        discovered_at: When the entity was discovered.
        metadata: Additional entity metadata.
    """

    entity_id: UUID = field(default_factory=uuid7)
    entity_type: EntityType = EntityType.UNKNOWN
    name: str = ""
    aliases: list[str] = field(default_factory=list)
    jurisdiction: str | None = None

    # Discovery context
    discovery_degree: int = 2  # D2 = 2, D3 = 3
    source_providers: list[str] = field(default_factory=list)
    confidence: float = 0.5

    # Risk indicators
    risk_indicators: list[str] = field(default_factory=list)
    is_sanctioned: bool = False
    is_pep: bool = False

    # Timing
    discovered_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Additional data
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def discovery_depth(self) -> int:
        """Alias for discovery_degree (backwards compatibility)."""
        return self.discovery_degree

    @property
    def risk_level(self) -> "RiskLevel":
        """Compute risk level from indicators (backwards compatibility)."""
        if self.is_sanctioned:
            return RiskLevel.CRITICAL
        if self.is_pep:
            return RiskLevel.HIGH
        if self.entity_type == EntityType.SHELL_COMPANY:
            return RiskLevel.HIGH
        if self.risk_indicators:
            # Check for high-risk indicators
            indicators_lower = [r.lower() for r in self.risk_indicators]
            if any("sanction" in i for i in indicators_lower):
                return RiskLevel.CRITICAL
            if any("pep" in i or "criminal" in i for i in indicators_lower):
                return RiskLevel.HIGH
            if any("shell" in i or "offshore" in i for i in indicators_lower):
                return RiskLevel.MODERATE
            return RiskLevel.LOW
        return RiskLevel.NONE

    @property
    def risk_factors(self) -> list[str]:
        """Alias for risk_indicators (backwards compatibility)."""
        return self.risk_indicators

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_id": str(self.entity_id),
            "entity_type": self.entity_type.value,
            "name": self.name,
            "aliases": self.aliases,
            "jurisdiction": self.jurisdiction,
            "discovery_degree": self.discovery_degree,
            "source_providers": self.source_providers,
            "confidence": self.confidence,
            "risk_indicators": self.risk_indicators,
            "is_sanctioned": self.is_sanctioned,
            "is_pep": self.is_pep,
            "discovered_at": self.discovered_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class EntityRelation:
    """A relationship between two entities.

    Represents a connection between entities discovered during
    network analysis, with relationship type and strength.

    Attributes:
        relation_id: Unique identifier for this relation.
        source_entity_id: ID of the source entity.
        target_entity_id: ID of the target entity.
        relation_type: Type of relationship.
        strength: Strength of the connection.
        bidirectional: Whether relation applies in both directions.
        start_date: When relationship began (if known).
        end_date: When relationship ended (None if ongoing).
        confidence: Confidence in relation (0.0-1.0).
        evidence: Evidence supporting the relation.
        source_provider: Provider that identified this relation.
        discovered_at: When the relation was discovered.
    """

    relation_id: UUID = field(default_factory=uuid7)
    source_entity_id: UUID | None = None
    target_entity_id: UUID | None = None
    relation_type: RelationType = RelationType.UNKNOWN
    strength: ConnectionStrength = ConnectionStrength.MODERATE

    # Relationship details
    bidirectional: bool = False
    start_date: datetime | None = None
    end_date: datetime | None = None

    # Quality metrics
    confidence: float = 0.5
    evidence: list[str] = field(default_factory=list)
    source_provider: str = ""

    # Timing
    discovered_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_current(self) -> bool:
        """Whether the relationship is currently active."""
        return self.end_date is None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "relation_id": str(self.relation_id),
            "source_entity_id": str(self.source_entity_id) if self.source_entity_id else None,
            "target_entity_id": str(self.target_entity_id) if self.target_entity_id else None,
            "relation_type": self.relation_type.value,
            "strength": self.strength.value,
            "bidirectional": self.bidirectional,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "is_current": self.is_current,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "source_provider": self.source_provider,
            "discovered_at": self.discovered_at.isoformat(),
        }


@dataclass
class RiskConnection:
    """A risky connection identified in network analysis.

    Represents a connection that poses potential risk, including
    the risk type, level, and recommended actions.

    Attributes:
        connection_id: Unique identifier for this risk connection.
        source_entity_id: ID of the primary entity (usually subject).
        target_entity_id: ID of the connected risky entity.
        risk_level: Overall risk level of this connection.
        risk_types: Types of risks identified.
        path_length: Degrees of separation (1 = direct, 2 = one hop, etc.).
        connection_path: Entity IDs in the connection path.
        risk_factors: Specific risk factors identified.
        recommendations: Recommended actions.
        requires_review: Whether manual review is required.
        confidence: Confidence in risk assessment (0.0-1.0).
        identified_at: When the risk was identified.
        entity: The risky entity (backwards compat).
        relation: The relation to the entity (backwards compat).
        risk_category: Category of risk (backwards compat).
        risk_description: Human-readable description (backwards compat).
        recommended_action: Single recommended action (backwards compat).
    """

    connection_id: UUID = field(default_factory=uuid7)
    source_entity_id: UUID | None = None
    target_entity_id: UUID | None = None

    # Risk assessment
    risk_level: RiskLevel = RiskLevel.MODERATE
    risk_types: list[str] = field(default_factory=list)

    # Connection details
    path_length: int = 1
    connection_path: list[UUID] = field(default_factory=list)

    # Analysis results
    risk_factors: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    requires_review: bool = False

    # Quality
    confidence: float = 0.5

    # Timing
    identified_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Backwards compatibility fields (used by connection_analyzer)
    entity: "DiscoveredEntity | None" = None
    relation: "EntityRelation | None" = None
    risk_category: str = ""
    risk_description: str = ""
    recommended_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "connection_id": str(self.connection_id),
            "source_entity_id": str(self.source_entity_id) if self.source_entity_id else None,
            "target_entity_id": str(self.target_entity_id) if self.target_entity_id else None,
            "risk_level": self.risk_level.value,
            "risk_types": self.risk_types,
            "path_length": self.path_length,
            "connection_path": [str(e) for e in self.connection_path],
            "risk_factors": self.risk_factors,
            "recommendations": self.recommendations,
            "requires_review": self.requires_review,
            "confidence": self.confidence,
            "identified_at": self.identified_at.isoformat(),
        }


@dataclass
class NetworkProfile:
    """Complete network analysis results.

    Contains all discovered entities, relationships, and risk
    connections from D2/D3 network analysis.

    Attributes:
        profile_id: Unique identifier for this profile.
        subject_entity_id: ID of the investigation subject.
        entities: Discovered entities.
        relations: Discovered relationships.
        risk_connections: Identified risky connections.
        d2_complete: Whether D2 analysis is complete.
        d3_complete: Whether D3 analysis is complete.
        entity_count: Total entities discovered.
        relation_count: Total relations discovered.
        high_risk_count: Number of high/critical risk connections.
        analyzed_at: When analysis was completed.
        analysis_duration_ms: Duration of analysis in milliseconds.
    """

    profile_id: UUID = field(default_factory=uuid7)
    subject_entity_id: UUID | None = None

    # Discovered data
    entities: list[DiscoveredEntity] = field(default_factory=list)
    relations: list[EntityRelation] = field(default_factory=list)
    risk_connections: list[RiskConnection] = field(default_factory=list)

    # Completion status
    d2_complete: bool = False
    d3_complete: bool = False

    # Statistics
    entity_count: int = 0
    relation_count: int = 0
    high_risk_count: int = 0

    # Timing
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    analysis_duration_ms: float = 0.0

    def __post_init__(self) -> None:
        """Update counts after initialization."""
        self.entity_count = len(self.entities)
        self.relation_count = len(self.relations)
        self.high_risk_count = sum(
            1 for rc in self.risk_connections if rc.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        )

    @property
    def entity_id(self) -> UUID | None:
        """Alias for subject_entity_id (backwards compatibility)."""
        return self.subject_entity_id

    @property
    def d2_entities(self) -> list[DiscoveredEntity]:
        """Get D2 (depth 2) entities."""
        return [e for e in self.entities if e.discovery_degree == 2]

    @property
    def d3_entities(self) -> list[DiscoveredEntity]:
        """Get D3 (depth 3) entities."""
        return [e for e in self.entities if e.discovery_degree == 3]

    def get_entity(self, entity_id: UUID) -> DiscoveredEntity | None:
        """Get entity by ID."""
        for entity in self.entities:
            if entity.entity_id == entity_id:
                return entity
        return None

    def get_relations_for_entity(self, entity_id: UUID) -> list[EntityRelation]:
        """Get all relations involving an entity."""
        return [
            r
            for r in self.relations
            if r.source_entity_id == entity_id or r.target_entity_id == entity_id
        ]

    def get_risk_connections_for_entity(self, entity_id: UUID) -> list[RiskConnection]:
        """Get risk connections involving an entity."""
        return [
            rc
            for rc in self.risk_connections
            if rc.source_entity_id == entity_id
            or rc.target_entity_id == entity_id
            or entity_id in rc.connection_path
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "profile_id": str(self.profile_id),
            "subject_entity_id": str(self.subject_entity_id) if self.subject_entity_id else None,
            "entities": [e.to_dict() for e in self.entities],
            "relations": [r.to_dict() for r in self.relations],
            "risk_connections": [rc.to_dict() for rc in self.risk_connections],
            "d2_complete": self.d2_complete,
            "d3_complete": self.d3_complete,
            "entity_count": self.entity_count,
            "relation_count": self.relation_count,
            "high_risk_count": self.high_risk_count,
            "analyzed_at": self.analyzed_at.isoformat(),
            "analysis_duration_ms": self.analysis_duration_ms,
        }


# =============================================================================
# Configuration
# =============================================================================


class NetworkConfig(BaseModel):
    """Configuration for NetworkPhaseHandler."""

    # Entity limits
    max_entities_per_degree: int = Field(
        default=20, ge=1, le=100, description="Max entities per degree level"
    )
    max_total_entities: int = Field(
        default=100, ge=10, le=500, description="Max total entities to analyze"
    )

    # Depth settings
    enable_d2: bool = Field(default=True, description="Enable D2 (direct) analysis")
    enable_d3: bool = Field(default=False, description="Enable D3 (extended) analysis")

    # Risk thresholds
    min_risk_confidence: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Min confidence to flag risk"
    )
    auto_flag_sanctions: bool = Field(
        default=True, description="Auto-flag sanctioned entities"
    )
    auto_flag_pep: bool = Field(default=True, description="Auto-flag PEP connections")

    # Analysis settings
    include_historical: bool = Field(
        default=True, description="Include historical relationships"
    )
    historical_lookback_years: int = Field(
        default=7, ge=1, le=20, description="Years to look back for history"
    )


@dataclass
class NetworkPhaseResult:
    """Result from NetworkPhaseHandler execution.

    Contains the network profile and execution metadata.
    """

    result_id: UUID = field(default_factory=uuid7)
    profile: NetworkProfile = field(default_factory=NetworkProfile)

    # Execution metadata
    success: bool = True
    error_message: str | None = None
    warnings: list[str] = field(default_factory=list)

    # Statistics
    entities_analyzed: int = 0
    relations_found: int = 0
    risks_identified: int = 0

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "result_id": str(self.result_id),
            "profile": self.profile.to_dict(),
            "success": self.success,
            "error_message": self.error_message,
            "warnings": self.warnings,
            "entities_analyzed": self.entities_analyzed,
            "relations_found": self.relations_found,
            "risks_identified": self.risks_identified,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
        }


# =============================================================================
# Phase Handler
# =============================================================================


class NetworkPhaseHandler:
    """Handles the Network analysis phase of investigation.

    The Network phase analyzes relationships and connections for D2 (direct)
    and D3 (extended) investigation degrees, building entity graphs and
    identifying risk-relevant associations.

    This phase:
    1. Extracts entities from all gathered intelligence
    2. Builds relationship graph between entities
    3. Analyzes connection strength and patterns
    4. Identifies risky associations (sanctions, PEP, shell companies)
    5. Generates visualization data for graph rendering

    Note: Full implementation in Task 5.14.
    This is a stub providing the interface.

    Example:
        ```python
        handler = NetworkPhaseHandler()
        result = await handler.execute(
            subject_entity_id=subject_id,
            intelligence_data=gathered_data,
            degree=SearchDegree.D2,
        )
        for rc in result.profile.risk_connections:
            print(f"Risk: {rc.risk_level} - {rc.risk_types}")
        ```
    """

    def __init__(
        self,
        config: NetworkConfig | None = None,
    ):
        """Initialize the network phase handler.

        Args:
            config: Handler configuration.
        """
        self.config = config or NetworkConfig()

    async def execute(
        self,
        subject_entity_id: UUID,
        intelligence_data: dict[str, Any] | None = None,
        degree: int = 2,  # 2 = D2, 3 = D3
    ) -> NetworkPhaseResult:
        """Execute network analysis phase.

        This is a stub implementation. Full analysis will be
        implemented in Task 5.14.

        Args:
            subject_entity_id: ID of the investigation subject.
            intelligence_data: Gathered intelligence data.
            degree: Investigation degree (2 = D2, 3 = D3).

        Returns:
            NetworkPhaseResult with analysis results.
        """
        start_time = datetime.now(UTC)

        logger.info(
            "Network phase execution (stub)",
            subject_entity_id=str(subject_entity_id),
            degree=degree,
        )

        # Stub implementation - return empty profile
        # Full implementation in Task 5.14
        profile = NetworkProfile(
            subject_entity_id=subject_entity_id,
            d2_complete=degree >= 2,
            d3_complete=degree >= 3,
        )

        end_time = datetime.now(UTC)
        duration_ms = (end_time - start_time).total_seconds() * 1000

        return NetworkPhaseResult(
            profile=profile,
            success=True,
            entities_analyzed=0,
            relations_found=0,
            risks_identified=0,
            started_at=start_time,
            completed_at=end_time,
            duration_ms=duration_ms,
        )

    def _extract_entities(
        self,
        intelligence_data: dict[str, Any] | None,
    ) -> list[DiscoveredEntity]:
        """Extract entities from intelligence data.

        Args:
            intelligence_data: Gathered intelligence.

        Returns:
            List of discovered entities.
        """
        # Stub - will be implemented in Task 5.14
        return []

    def _build_relations(
        self,
        entities: list[DiscoveredEntity],
        intelligence_data: dict[str, Any] | None,
    ) -> list[EntityRelation]:
        """Build relations between entities.

        Args:
            entities: Discovered entities.
            intelligence_data: Gathered intelligence.

        Returns:
            List of entity relations.
        """
        # Stub - will be implemented in Task 5.14
        return []

    def _identify_risk_connections(
        self,
        entities: list[DiscoveredEntity],
        relations: list[EntityRelation],
        subject_entity_id: UUID,
    ) -> list[RiskConnection]:
        """Identify risky connections in the network.

        Args:
            entities: Discovered entities.
            relations: Entity relations.
            subject_entity_id: Subject entity ID.

        Returns:
            List of identified risk connections.
        """
        # Stub - will be implemented in Task 5.14
        risk_connections = []

        # Auto-flag sanctioned entities
        if self.config.auto_flag_sanctions:
            for entity in entities:
                if entity.is_sanctioned:
                    risk_connections.append(
                        RiskConnection(
                            source_entity_id=subject_entity_id,
                            target_entity_id=entity.entity_id,
                            risk_level=RiskLevel.CRITICAL,
                            risk_types=["sanctions_connection"],
                            risk_factors=["Entity appears on sanctions list"],
                            recommendations=["Immediate escalation required"],
                            requires_review=True,
                            confidence=0.95,
                        )
                    )

        # Auto-flag PEP connections
        if self.config.auto_flag_pep:
            for entity in entities:
                if entity.is_pep:
                    risk_connections.append(
                        RiskConnection(
                            source_entity_id=subject_entity_id,
                            target_entity_id=entity.entity_id,
                            risk_level=RiskLevel.HIGH,
                            risk_types=["pep_connection"],
                            risk_factors=["Connection to Politically Exposed Person"],
                            recommendations=["Enhanced due diligence required"],
                            requires_review=True,
                            confidence=0.9,
                        )
                    )

        return risk_connections


def create_network_phase_handler(
    config: NetworkConfig | None = None,
) -> NetworkPhaseHandler:
    """Create a network phase handler.

    Args:
        config: Optional handler configuration.

    Returns:
        Configured NetworkPhaseHandler.
    """
    return NetworkPhaseHandler(config=config)
