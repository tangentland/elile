"""Type definitions for cross-screening entity index.

This module defines the core types for tracking entity connections across
screening operations, including relationship strength scoring and temporal tracking.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from elile.entity.types import RelationType


class ConnectionType(str, Enum):
    """Type of cross-screening connection."""

    # Direct connections discovered during screening
    EMPLOYER = "employer"  # Shared employer
    COLLEAGUE = "colleague"  # Worked at same organization
    BUSINESS_PARTNER = "business_partner"  # Business partnership
    DIRECTOR = "director"  # Shared directorship
    ADDRESS = "address"  # Shared address/residence
    FAMILY = "family"  # Family relationship
    ASSOCIATE = "associate"  # General association

    # Indirect connections
    SHARED_FINDING = "shared_finding"  # Appear in same finding
    SHARED_SOURCE = "shared_source"  # Found in same data source
    NETWORK_NEIGHBOR = "network_neighbor"  # Connected through network graph


class ConnectionStrength(str, Enum):
    """Strength/quality of a connection."""

    WEAK = "weak"  # Low confidence or indirect
    MODERATE = "moderate"  # Medium confidence
    STRONG = "strong"  # High confidence, direct evidence
    VERIFIED = "verified"  # Confirmed through multiple sources


class SubjectConnection(BaseModel):
    """A connection between two subjects discovered across screenings.

    Attributes:
        connection_id: Unique identifier for this connection.
        source_subject_id: The subject from which the connection was discovered.
        target_subject_id: The connected subject.
        connection_type: Type of relationship.
        strength: Confidence/strength of the connection.
        confidence_score: Numeric confidence score 0.0-1.0.
        degree: Number of hops from the original subject.
        discovered_at: When the connection was first discovered.
        last_seen_at: When the connection was last confirmed.
        screening_ids: Screening operations that established this connection.
        evidence: Supporting evidence for the connection.
        metadata: Additional connection metadata.
    """

    connection_id: UUID
    source_subject_id: UUID
    target_subject_id: UUID
    connection_type: ConnectionType
    strength: ConnectionStrength = ConnectionStrength.MODERATE
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.5)
    degree: int = Field(ge=1, le=10, default=1)  # 1 = direct, 2+ = via intermediaries
    discovered_at: datetime
    last_seen_at: datetime
    screening_ids: list[UUID] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_direct(self) -> bool:
        """Check if this is a direct (degree 1) connection."""
        return self.degree == 1

    def to_relation_type(self) -> RelationType | None:
        """Convert to entity RelationType if applicable."""
        mapping = {
            ConnectionType.EMPLOYER: RelationType.EMPLOYER,
            ConnectionType.COLLEAGUE: RelationType.COLLEAGUE,
            ConnectionType.BUSINESS_PARTNER: RelationType.BUSINESS_PARTNER,
            ConnectionType.DIRECTOR: RelationType.DIRECTOR,
            ConnectionType.FAMILY: RelationType.FAMILY,
            ConnectionType.ASSOCIATE: RelationType.ASSOCIATE,
        }
        return mapping.get(self.connection_type)


class EntityReference(BaseModel):
    """Reference to an entity discovered during screening.

    Attributes:
        entity_id: Unique entity identifier.
        entity_type: Type of entity (person, organization, address).
        name: Display name for the entity.
        screening_id: Screening where this entity was discovered.
        discovered_at: When the entity was first discovered.
        confidence_score: Confidence in entity identification.
        identifiers: Known identifiers (SSN, EIN, etc.).
    """

    entity_id: UUID
    entity_type: str  # "person", "organization", "address"
    name: str
    screening_id: UUID
    discovered_at: datetime
    confidence_score: float = Field(ge=0.0, le=1.0, default=1.0)
    identifiers: dict[str, str] = Field(default_factory=dict)


class ScreeningEntity(BaseModel):
    """An entity and its relationships discovered in a screening.

    This represents an entity found during a screening operation along with
    all the connections it has to other entities.

    Attributes:
        screening_id: The screening where this entity was found.
        entity_id: The entity's unique identifier.
        subject_id: The screening subject this entity relates to.
        entity_type: Type of entity (person, organization, address).
        name: Display name.
        role: Role in relation to the subject (employer, associate, etc.).
        connections: Other entities this entity connects to.
        findings_count: Number of findings involving this entity.
        metadata: Additional entity metadata.
    """

    screening_id: UUID
    entity_id: UUID
    subject_id: UUID
    entity_type: str
    name: str
    role: str | None = None
    connections: list[UUID] = Field(default_factory=list)
    findings_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class CrossScreeningResult(BaseModel):
    """Result of a cross-screening search operation.

    Attributes:
        query_subject_id: The subject being queried.
        connections: All discovered connections.
        total_connections: Total number of connections found.
        direct_connections: Number of direct (degree 1) connections.
        max_degree: Maximum degree of connections included.
        query_time_ms: Time taken for the query in milliseconds.
    """

    query_subject_id: UUID
    connections: list[SubjectConnection] = Field(default_factory=list)
    total_connections: int = 0
    direct_connections: int = 0
    max_degree: int = 0
    query_time_ms: float = 0.0

    def get_by_degree(self, degree: int) -> list[SubjectConnection]:
        """Get connections at a specific degree."""
        return [c for c in self.connections if c.degree == degree]

    def get_by_type(self, conn_type: ConnectionType) -> list[SubjectConnection]:
        """Get connections of a specific type."""
        return [c for c in self.connections if c.connection_type == conn_type]


class NetworkNode(BaseModel):
    """A node in the cross-screening network graph.

    Attributes:
        subject_id: Subject identifier.
        name: Display name.
        screenings_count: Number of screenings involving this subject.
        connections_count: Number of known connections.
        risk_score: Aggregate risk score from screenings.
        metadata: Additional node metadata.
    """

    subject_id: UUID
    name: str
    screenings_count: int = 0
    connections_count: int = 0
    risk_score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class NetworkEdge(BaseModel):
    """An edge in the cross-screening network graph.

    Attributes:
        source_id: Source subject ID.
        target_id: Target subject ID.
        connection_type: Type of connection.
        weight: Edge weight (relationship strength).
        screenings: Screening IDs that established this edge.
        metadata: Additional edge metadata.
    """

    source_id: UUID
    target_id: UUID
    connection_type: ConnectionType
    weight: float = Field(ge=0.0, le=1.0, default=0.5)
    screenings: list[UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NetworkGraph(BaseModel):
    """A subgraph of the cross-screening network.

    Attributes:
        nodes: All nodes in the subgraph.
        edges: All edges in the subgraph.
        center_subject_id: The central subject (if applicable).
        max_depth: Maximum depth from center.
    """

    nodes: list[NetworkNode] = Field(default_factory=list)
    edges: list[NetworkEdge] = Field(default_factory=list)
    center_subject_id: UUID | None = None
    max_depth: int = 0

    @property
    def node_count(self) -> int:
        """Get the number of nodes."""
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        """Get the number of edges."""
        return len(self.edges)

    def get_node(self, subject_id: UUID) -> NetworkNode | None:
        """Get a node by subject ID."""
        for node in self.nodes:
            if node.subject_id == subject_id:
                return node
        return None

    def get_neighbors(self, subject_id: UUID) -> list[UUID]:
        """Get all neighbors of a node."""
        neighbors = set()
        for edge in self.edges:
            if edge.source_id == subject_id:
                neighbors.add(edge.target_id)
            elif edge.target_id == subject_id:
                neighbors.add(edge.source_id)
        return list(neighbors)


# =============================================================================
# Exceptions
# =============================================================================


class CrossScreeningIndexError(Exception):
    """Base exception for cross-screening index errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class SubjectNotFoundError(CrossScreeningIndexError):
    """Raised when a subject is not found in the index."""

    def __init__(self, subject_id: UUID) -> None:
        super().__init__(
            f"Subject {subject_id} not found in cross-screening index",
            details={"subject_id": str(subject_id)},
        )
        self.subject_id = subject_id


class ScreeningNotIndexedError(CrossScreeningIndexError):
    """Raised when a screening has not been indexed."""

    def __init__(self, screening_id: UUID) -> None:
        super().__init__(
            f"Screening {screening_id} has not been indexed",
            details={"screening_id": str(screening_id)},
        )
        self.screening_id = screening_id


class IndexingError(CrossScreeningIndexError):
    """Raised when indexing fails."""

    def __init__(self, screening_id: UUID, reason: str) -> None:
        super().__init__(
            f"Failed to index screening {screening_id}: {reason}",
            details={"screening_id": str(screening_id), "reason": reason},
        )
        self.screening_id = screening_id
        self.reason = reason
