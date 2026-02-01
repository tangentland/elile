"""Connection Analyzer for network risk assessment.

This module provides the ConnectionAnalyzer that:
1. Builds connection graphs from discovered entities and relations
2. Analyzes network topology (centrality, clustering)
3. Calculates risk propagation through network edges
4. Identifies risky connections (sanctions, PEP, shell companies)
5. Generates visualization data for graph rendering
"""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.agent.state import SearchDegree
from elile.core.logging import get_logger
from elile.investigation.phases.network import (
    ConnectionStrength,
    DiscoveredEntity,
    EntityRelation,
    EntityType,
    NetworkProfile,
    RelationType,
    RiskConnection,
    RiskLevel,
)

logger = get_logger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class ConnectionRiskType(str, Enum):
    """Types of connection-based risks."""

    # Regulatory risks
    SANCTIONS_CONNECTION = "sanctions_connection"
    PEP_CONNECTION = "pep_connection"
    WATCHLIST_CONNECTION = "watchlist_connection"

    # Structural risks
    SHELL_COMPANY = "shell_company"
    CIRCULAR_OWNERSHIP = "circular_ownership"
    OPAQUE_STRUCTURE = "opaque_structure"

    # Behavioral risks
    FREQUENT_ENTITY_CHANGES = "frequent_entity_changes"
    RAPID_NETWORK_GROWTH = "rapid_network_growth"
    UNUSUAL_CONCENTRATION = "unusual_concentration"

    # Association risks
    CRIMINAL_ASSOCIATION = "criminal_association"
    FRAUD_ASSOCIATION = "fraud_association"
    HIGH_RISK_INDUSTRY = "high_risk_industry"
    ADVERSE_MEDIA_ASSOCIATION = "adverse_media_association"


# Risk decay factor per hop (risk decreases as distance increases)
RISK_DECAY_PER_HOP: dict[RiskLevel, float] = {
    RiskLevel.CRITICAL: 0.7,  # 70% retained per hop for critical
    RiskLevel.HIGH: 0.6,  # 60% retained per hop for high
    RiskLevel.MODERATE: 0.5,  # 50% retained per hop for moderate
    RiskLevel.LOW: 0.3,  # 30% retained per hop for low
    RiskLevel.NONE: 0.0,
}

# Connection strength multipliers for risk propagation
STRENGTH_MULTIPLIER: dict[ConnectionStrength, float] = {
    ConnectionStrength.DIRECT: 1.0,  # Full propagation for direct connections
    ConnectionStrength.STRONG: 0.9,  # 90% for strong
    ConnectionStrength.MODERATE: 0.7,  # 70% for moderate
    ConnectionStrength.WEAK: 0.4,  # 40% for weak
}

# Relation type risk factors (some relationships carry more risk)
RELATION_RISK_FACTOR: dict[RelationType, float] = {
    RelationType.FAMILY: 0.8,  # Family ties carry significant risk
    RelationType.BUSINESS: 0.9,  # Business relationships carry high risk
    RelationType.OWNERSHIP: 1.0,  # Ownership is highest risk
    RelationType.FINANCIAL: 0.95,  # Financial ties very high
    RelationType.EMPLOYMENT: 0.6,  # Employment moderate
    RelationType.LEGAL: 0.8,  # Legal relationships significant
    RelationType.SOCIAL: 0.3,  # Social ties lowest
    RelationType.PROFESSIONAL: 0.5,  # Professional moderate
    RelationType.EDUCATIONAL: 0.2,  # Educational lowest
    RelationType.POLITICAL: 0.9,  # Political very high (PEP exposure)
    RelationType.OTHER: 0.4,  # Unknown moderate
}

# Risk thresholds
PROPAGATED_RISK_THRESHOLDS: dict[RiskLevel, float] = {
    RiskLevel.CRITICAL: 0.8,
    RiskLevel.HIGH: 0.6,
    RiskLevel.MODERATE: 0.4,
    RiskLevel.LOW: 0.2,
    RiskLevel.NONE: 0.0,
}


# =============================================================================
# Models
# =============================================================================


@dataclass
class ConnectionNode:
    """A node in the connection graph representing an entity."""

    node_id: UUID = field(default_factory=uuid7)
    entity_id: UUID | None = None
    entity: DiscoveredEntity | None = None
    is_subject: bool = False
    depth: int = 0  # 0=subject, 1=D1 (direct connections), 2=D2, 3=D3

    # Risk attributes
    intrinsic_risk: float = 0.0  # Entity's own risk level (0.0-1.0)
    propagated_risk: float = 0.0  # Risk propagated from connections
    total_risk: float = 0.0  # Combined risk score
    risk_level: RiskLevel = RiskLevel.NONE
    risk_factors: list[str] = field(default_factory=list)

    # Network metrics
    degree_centrality: float = 0.0  # Number of direct connections / max possible
    betweenness_centrality: float = 0.0  # How often on shortest paths
    connection_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "node_id": str(self.node_id),
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "is_subject": self.is_subject,
            "depth": self.depth,
            "intrinsic_risk": self.intrinsic_risk,
            "propagated_risk": self.propagated_risk,
            "total_risk": self.total_risk,
            "risk_level": self.risk_level.value,
            "risk_factors": self.risk_factors,
            "degree_centrality": self.degree_centrality,
            "betweenness_centrality": self.betweenness_centrality,
            "connection_count": self.connection_count,
        }


@dataclass
class ConnectionEdge:
    """An edge in the connection graph representing a relationship."""

    edge_id: UUID = field(default_factory=uuid7)
    source_node_id: UUID | None = None
    target_node_id: UUID | None = None
    relation: EntityRelation | None = None

    # Edge attributes
    relation_type: RelationType = RelationType.OTHER
    strength: ConnectionStrength = ConnectionStrength.MODERATE
    is_current: bool = True

    # Risk attributes
    edge_risk_factor: float = 0.5  # Risk transmission factor
    carries_propagated_risk: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "edge_id": str(self.edge_id),
            "source_node_id": str(self.source_node_id) if self.source_node_id else None,
            "target_node_id": str(self.target_node_id) if self.target_node_id else None,
            "relation_type": self.relation_type.value,
            "strength": self.strength.value,
            "is_current": self.is_current,
            "edge_risk_factor": self.edge_risk_factor,
            "carries_propagated_risk": self.carries_propagated_risk,
        }


@dataclass
class RiskPropagationPath:
    """A path through which risk propagates to the subject."""

    path_id: UUID = field(default_factory=uuid7)
    source_node_id: UUID | None = None
    source_risk_level: RiskLevel = RiskLevel.NONE
    hops: list[UUID] = field(default_factory=list)  # Node IDs in path
    path_length: int = 0
    propagated_risk_score: float = 0.0  # Final risk reaching subject
    decay_factor: float = 1.0  # Total decay applied
    risk_type: ConnectionRiskType | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path_id": str(self.path_id),
            "source_node_id": str(self.source_node_id) if self.source_node_id else None,
            "source_risk_level": self.source_risk_level.value,
            "hops": [str(h) for h in self.hops],
            "path_length": self.path_length,
            "propagated_risk_score": self.propagated_risk_score,
            "decay_factor": self.decay_factor,
            "risk_type": self.risk_type.value if self.risk_type else None,
            "description": self.description,
        }


@dataclass
class ConnectionGraph:
    """The complete connection graph for analysis."""

    graph_id: UUID = field(default_factory=uuid7)
    subject_node_id: UUID | None = None
    nodes: dict[UUID, ConnectionNode] = field(default_factory=dict)
    edges: list[ConnectionEdge] = field(default_factory=list)

    # Adjacency representation
    adjacency: dict[UUID, list[UUID]] = field(default_factory=dict)

    # Metrics
    total_nodes: int = 0
    total_edges: int = 0
    max_depth: int = 0
    density: float = 0.0  # Actual edges / possible edges
    avg_degree: float = 0.0  # Average connections per node
    is_connected: bool = True

    # Risk paths
    risk_paths: list[RiskPropagationPath] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (for visualization)."""
        return {
            "graph_id": str(self.graph_id),
            "subject_node_id": str(self.subject_node_id) if self.subject_node_id else None,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges],
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "max_depth": self.max_depth,
            "density": self.density,
            "avg_degree": self.avg_degree,
            "is_connected": self.is_connected,
            "risk_paths": [p.to_dict() for p in self.risk_paths],
        }

    def get_node_by_entity(self, entity_id: UUID) -> ConnectionNode | None:
        """Get node by entity ID."""
        for node in self.nodes.values():
            if node.entity_id == entity_id:
                return node
        return None


@dataclass
class ConnectionAnalysisResult:
    """Result of connection analysis."""

    analysis_id: UUID = field(default_factory=uuid7)
    subject_entity_id: UUID | None = None
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Graph data
    graph: ConnectionGraph | None = None

    # Risk assessment
    connections_analyzed: int = 0
    risk_connections_found: list[RiskConnection] = field(default_factory=list)
    propagation_paths: list[RiskPropagationPath] = field(default_factory=list)
    total_propagated_risk: float = 0.0
    highest_connection_risk: RiskLevel = RiskLevel.NONE
    risk_factors: list[str] = field(default_factory=list)

    # By degree
    d2_risk_score: float = 0.0  # Risk from D2 connections
    d3_risk_score: float = 0.0  # Risk from D3 connections

    # Summary
    summary: str = ""
    recommended_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "analysis_id": str(self.analysis_id),
            "subject_entity_id": str(self.subject_entity_id)
            if self.subject_entity_id
            else None,
            "analyzed_at": self.analyzed_at.isoformat(),
            "connections_analyzed": self.connections_analyzed,
            "risk_connections_found": [r.to_dict() for r in self.risk_connections_found],
            "propagation_paths": [p.to_dict() for p in self.propagation_paths],
            "total_propagated_risk": self.total_propagated_risk,
            "highest_connection_risk": self.highest_connection_risk.value,
            "risk_factors": self.risk_factors,
            "d2_risk_score": self.d2_risk_score,
            "d3_risk_score": self.d3_risk_score,
            "summary": self.summary,
            "recommended_actions": self.recommended_actions,
            "graph": self.graph.to_dict() if self.graph else None,
        }


class AnalyzerConfig(BaseModel):
    """Configuration for connection analyzer."""

    # Graph building
    max_d2_entities: int = Field(default=100, ge=1, description="Max D2 entities to include")
    max_d3_entities: int = Field(default=500, ge=1, description="Max D3 entities to include")

    # Risk propagation
    enable_risk_propagation: bool = Field(
        default=True, description="Enable risk propagation calculation"
    )
    max_propagation_depth: int = Field(
        default=3, ge=1, le=5, description="Max hops for risk propagation"
    )
    min_propagated_risk: float = Field(
        default=0.1, ge=0.0, le=1.0, description="Minimum propagated risk to report"
    )

    # Risk thresholds
    high_risk_threshold: float = Field(
        default=0.6, ge=0.0, le=1.0, description="Threshold for high risk connections"
    )
    critical_risk_threshold: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Threshold for critical risk connections"
    )

    # Network metrics
    calculate_centrality: bool = Field(
        default=True, description="Calculate centrality metrics"
    )

    # Current relationships weighting
    current_relationship_weight: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Weight for current relationships"
    )
    past_relationship_weight: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Weight for past relationships"
    )


# =============================================================================
# Connection Analyzer
# =============================================================================


class ConnectionAnalyzer:
    """Analyzes entity connections and network risk.

    The ConnectionAnalyzer builds network graphs from discovered entities
    and relationships, calculates risk propagation through the network,
    and identifies risky connections for D2/D3 investigations.

    Example:
        ```python
        analyzer = ConnectionAnalyzer()

        result = analyzer.analyze_connections(
            subject_entity=subject,
            discovered_entities=entities,
            relations=relations,
            degree=SearchDegree.D2,
        )

        print(f"Total propagated risk: {result.total_propagated_risk:.2f}")
        print(f"Risk connections: {len(result.risk_connections_found)}")

        # Get visualization data
        graph_data = result.graph.to_dict()
        ```
    """

    def __init__(self, config: AnalyzerConfig | None = None):
        """Initialize the connection analyzer.

        Args:
            config: Analyzer configuration.
        """
        self.config = config or AnalyzerConfig()

    def analyze_connections(
        self,
        subject_entity: DiscoveredEntity | None,
        discovered_entities: list[DiscoveredEntity],
        relations: list[EntityRelation],
        degree: SearchDegree,
        network_profile: NetworkProfile | None = None,
    ) -> ConnectionAnalysisResult:
        """Analyze entity connections and assess network risk.

        Args:
            subject_entity: The subject entity (or None to auto-create).
            discovered_entities: List of discovered entities.
            relations: List of entity relations.
            degree: Search degree (D1, D2, D3).
            network_profile: Optional network profile for additional context.

        Returns:
            ConnectionAnalysisResult with graph and risk assessment.
        """
        result = ConnectionAnalysisResult(
            subject_entity_id=subject_entity.entity_id if subject_entity else None,
        )

        logger.info(
            "Starting connection analysis",
            degree=degree.value,
            entities=len(discovered_entities),
            relations=len(relations),
        )

        # No analysis for D1 (subject only)
        if degree == SearchDegree.D1:
            result.summary = "No network analysis for D1 (subject only)"
            return result

        # Build the connection graph
        graph = self._build_graph(
            subject_entity=subject_entity,
            discovered_entities=discovered_entities,
            relations=relations,
            degree=degree,
            network_profile=network_profile,
        )
        result.graph = graph
        result.connections_analyzed = graph.total_edges

        # Calculate network metrics
        if self.config.calculate_centrality:
            self._calculate_centrality_metrics(graph)

        # Analyze intrinsic entity risks
        self._analyze_entity_risks(graph)

        # Calculate risk propagation
        if self.config.enable_risk_propagation:
            propagation_paths = self._calculate_risk_propagation(graph, degree)
            result.propagation_paths = propagation_paths
            graph.risk_paths = propagation_paths

            # Sum propagated risk to subject
            result.total_propagated_risk = self._sum_propagated_risk(
                graph, propagation_paths
            )

            # Calculate risk by degree
            result.d2_risk_score = self._calculate_risk_by_depth(graph, 2)
            result.d3_risk_score = self._calculate_risk_by_depth(graph, 3)

        # Identify risk connections
        risk_connections = self._identify_risk_connections(graph, degree)
        result.risk_connections_found = risk_connections

        # Determine highest risk level
        result.highest_connection_risk = self._get_highest_risk_level(graph)

        # Collect risk factors
        result.risk_factors = self._collect_risk_factors(graph, risk_connections)

        # Generate summary and recommendations
        result.summary = self._generate_summary(result, degree)
        result.recommended_actions = self._generate_recommendations(result)

        logger.info(
            "Connection analysis complete",
            nodes=graph.total_nodes,
            edges=graph.total_edges,
            risk_connections=len(risk_connections),
            propagated_risk=result.total_propagated_risk,
        )

        return result

    def analyze_from_network_profile(
        self,
        network_profile: NetworkProfile,
        degree: SearchDegree,
    ) -> ConnectionAnalysisResult:
        """Analyze connections from a NetworkProfile.

        Convenience method that extracts entities and relations from
        a NetworkProfile.

        Args:
            network_profile: Network profile from investigation.
            degree: Search degree (D2 or D3).

        Returns:
            ConnectionAnalysisResult with graph and risk assessment.
        """
        # Combine D2 and D3 entities
        all_entities = network_profile.d2_entities + network_profile.d3_entities

        # Create subject entity placeholder
        subject = DiscoveredEntity(
            entity_id=network_profile.entity_id,
            name="Subject",
            discovery_degree=1,
            entity_type=EntityType.INDIVIDUAL,
        )

        return self.analyze_connections(
            subject_entity=subject,
            discovered_entities=all_entities,
            relations=network_profile.relations,
            degree=degree,
            network_profile=network_profile,
        )

    def get_visualization_data(
        self,
        result: ConnectionAnalysisResult,
    ) -> dict[str, Any]:
        """Get graph visualization data in a standard format.

        Returns data suitable for visualization libraries like vis.js,
        d3.js, or cytoscape.

        Args:
            result: Connection analysis result.

        Returns:
            Dictionary with nodes and edges for visualization.
        """
        if not result.graph:
            return {"nodes": [], "edges": [], "metadata": {}}

        graph = result.graph

        # Build node list with visualization attributes
        nodes = []
        for node in graph.nodes.values():
            node_data = {
                "id": str(node.node_id),
                "label": node.entity.name if node.entity else "Subject",
                "type": node.entity.entity_type.value if node.entity else "individual",
                "depth": node.depth,
                "risk_level": node.risk_level.value,
                "risk_score": node.total_risk,
                "is_subject": node.is_subject,
                "size": 30 if node.is_subject else max(10, node.connection_count * 5),
                "color": self._get_node_color(node.risk_level),
            }
            nodes.append(node_data)

        # Build edge list
        edges = []
        for edge in graph.edges:
            edge_data = {
                "id": str(edge.edge_id),
                "source": str(edge.source_node_id),
                "target": str(edge.target_node_id),
                "type": edge.relation_type.value,
                "strength": edge.strength.value,
                "width": self._get_edge_width(edge.strength),
                "color": self._get_edge_color(edge.edge_risk_factor),
                "dashes": not edge.is_current,  # Dashed for past relationships
            }
            edges.append(edge_data)

        # Metadata
        metadata = {
            "total_nodes": graph.total_nodes,
            "total_edges": graph.total_edges,
            "max_depth": graph.max_depth,
            "density": graph.density,
            "propagated_risk": result.total_propagated_risk,
            "risk_paths": len(result.propagation_paths),
        }

        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": metadata,
        }

    def _build_graph(
        self,
        subject_entity: DiscoveredEntity | None,
        discovered_entities: list[DiscoveredEntity],
        relations: list[EntityRelation],
        degree: SearchDegree,
        network_profile: NetworkProfile | None,  # noqa: ARG002
    ) -> ConnectionGraph:
        """Build the connection graph from entities and relations.

        Args:
            subject_entity: Subject entity.
            discovered_entities: Discovered entities.
            relations: Entity relations.
            degree: Search degree.
            network_profile: Optional network profile.

        Returns:
            Constructed ConnectionGraph.
        """
        graph = ConnectionGraph()

        # Create subject node
        subject_node = ConnectionNode(
            entity_id=subject_entity.entity_id if subject_entity else uuid7(),
            entity=subject_entity,
            is_subject=True,
            depth=0,
        )
        graph.nodes[subject_node.node_id] = subject_node
        graph.subject_node_id = subject_node.node_id
        graph.adjacency[subject_node.node_id] = []

        # Entity ID to node ID mapping
        entity_to_node: dict[UUID, UUID] = {}
        if subject_entity:
            entity_to_node[subject_entity.entity_id] = subject_node.node_id

        # Add discovered entity nodes
        for entity in discovered_entities:
            # Respect limits
            if entity.discovery_degree == 2 and len(
                [n for n in graph.nodes.values() if n.depth == 2]
            ) >= self.config.max_d2_entities:
                continue
            if entity.discovery_degree == 3 and len(
                [n for n in graph.nodes.values() if n.depth == 3]
            ) >= self.config.max_d3_entities:
                continue

            # Skip D3 if not requested
            if entity.discovery_degree == 3 and degree != SearchDegree.D3:
                continue

            node = ConnectionNode(
                entity_id=entity.entity_id,
                entity=entity,
                is_subject=False,
                depth=entity.discovery_degree,
                intrinsic_risk=self._entity_risk_to_score(entity.risk_level),
                risk_level=entity.risk_level,
                risk_factors=list(entity.risk_factors),
            )
            graph.nodes[node.node_id] = node
            graph.adjacency[node.node_id] = []
            entity_to_node[entity.entity_id] = node.node_id

        # Add edges from relations
        for relation in relations:
            source_id = relation.source_entity_id
            target_id = relation.target_entity_id

            if source_id is None or target_id is None:
                continue

            # Find or skip if entities not in graph
            source_node_id = entity_to_node.get(source_id)
            target_node_id = entity_to_node.get(target_id)

            if source_node_id is None or target_node_id is None:
                continue

            # Calculate edge risk factor
            edge_risk = self._calculate_edge_risk_factor(relation)

            # Apply current/past weighting
            if relation.is_current:
                edge_risk *= self.config.current_relationship_weight
            else:
                edge_risk *= self.config.past_relationship_weight

            edge = ConnectionEdge(
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                relation=relation,
                relation_type=relation.relation_type,
                strength=relation.strength,
                is_current=relation.is_current,
                edge_risk_factor=edge_risk,
            )
            graph.edges.append(edge)

            # Update adjacency
            graph.adjacency[source_node_id].append(target_node_id)
            graph.adjacency[target_node_id].append(source_node_id)

            # Update connection counts
            graph.nodes[source_node_id].connection_count += 1
            graph.nodes[target_node_id].connection_count += 1

        # Calculate graph metrics
        graph.total_nodes = len(graph.nodes)
        graph.total_edges = len(graph.edges)
        graph.max_depth = max((n.depth for n in graph.nodes.values()), default=0)

        # Calculate density
        if graph.total_nodes > 1:
            max_edges = graph.total_nodes * (graph.total_nodes - 1) / 2
            graph.density = graph.total_edges / max_edges if max_edges > 0 else 0
        else:
            graph.density = 0

        # Calculate average degree
        if graph.total_nodes > 0:
            total_connections = sum(n.connection_count for n in graph.nodes.values())
            graph.avg_degree = total_connections / graph.total_nodes
        else:
            graph.avg_degree = 0

        return graph

    def _calculate_centrality_metrics(self, graph: ConnectionGraph) -> None:
        """Calculate centrality metrics for all nodes.

        Args:
            graph: Connection graph to analyze.
        """
        if graph.total_nodes == 0:
            return

        max_possible = graph.total_nodes - 1 if graph.total_nodes > 1 else 1

        # Degree centrality
        for node in graph.nodes.values():
            node.degree_centrality = node.connection_count / max_possible

        # Betweenness centrality (simplified - count paths through each node)
        if graph.total_nodes > 2:
            self._calculate_betweenness(graph)

    def _calculate_betweenness(self, graph: ConnectionGraph) -> None:
        """Calculate betweenness centrality using BFS.

        Args:
            graph: Connection graph.
        """
        # Count paths through each node
        path_counts: dict[UUID, int] = defaultdict(int)

        node_ids = list(graph.nodes.keys())
        for i, source in enumerate(node_ids):
            for target in node_ids[i + 1 :]:
                # BFS to find shortest path
                path = self._find_path(graph, source, target)
                # Count intermediate nodes
                for node_id in path[1:-1]:  # Exclude source and target
                    path_counts[node_id] += 1

        # Normalize
        max_paths = len(node_ids) * (len(node_ids) - 1) / 2 if len(node_ids) > 1 else 1
        for node_id, count in path_counts.items():
            if node_id in graph.nodes:
                graph.nodes[node_id].betweenness_centrality = count / max_paths

    def _find_path(self, graph: ConnectionGraph, source: UUID, target: UUID) -> list[UUID]:
        """Find shortest path between two nodes using BFS.

        Args:
            graph: Connection graph.
            source: Source node ID.
            target: Target node ID.

        Returns:
            List of node IDs in path (empty if no path).
        """
        if source == target:
            return [source]

        queue = deque([(source, [source])])
        visited = {source}

        while queue:
            current, path = queue.popleft()

            for neighbor in graph.adjacency.get(current, []):
                if neighbor == target:
                    return path + [neighbor]

                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return []

    def _analyze_entity_risks(self, graph: ConnectionGraph) -> None:
        """Analyze intrinsic risks of entities in the graph.

        Args:
            graph: Connection graph.
        """
        for node in graph.nodes.values():
            if node.entity:
                # Convert risk level to score
                node.intrinsic_risk = self._entity_risk_to_score(node.entity.risk_level)
                node.risk_level = node.entity.risk_level
                node.risk_factors = list(node.entity.risk_factors)

                # Check for specific risk indicators
                risk_factors = node.entity.risk_factors
                if any("sanction" in rf.lower() for rf in risk_factors):
                    node.intrinsic_risk = max(node.intrinsic_risk, 0.95)
                    node.risk_level = RiskLevel.CRITICAL
                if any("pep" in rf.lower() for rf in risk_factors):
                    node.intrinsic_risk = max(node.intrinsic_risk, 0.8)
                    if node.risk_level != RiskLevel.CRITICAL:
                        node.risk_level = RiskLevel.HIGH
                if any("shell" in rf.lower() or "offshore" in rf.lower() for rf in risk_factors):
                    node.intrinsic_risk = max(node.intrinsic_risk, 0.7)
                    if node.risk_level not in (RiskLevel.CRITICAL, RiskLevel.HIGH):
                        node.risk_level = RiskLevel.MODERATE

    def _calculate_risk_propagation(
        self,
        graph: ConnectionGraph,
        degree: SearchDegree,
    ) -> list[RiskPropagationPath]:
        """Calculate how risk propagates through the network to the subject.

        Risk propagates from high-risk entities through relationships,
        decaying with distance and relationship strength.

        Args:
            graph: Connection graph.
            degree: Search degree.

        Returns:
            List of risk propagation paths.
        """
        propagation_paths: list[RiskPropagationPath] = []

        if not graph.subject_node_id:
            return propagation_paths

        subject_node = graph.nodes.get(graph.subject_node_id)
        if not subject_node:
            return propagation_paths

        max_depth = 2 if degree == SearchDegree.D2 else 3
        max_depth = min(max_depth, self.config.max_propagation_depth)

        # Find all risky nodes (intrinsic risk > threshold)
        risky_nodes = [
            n for n in graph.nodes.values()
            if n.intrinsic_risk >= self.config.min_propagated_risk and not n.is_subject
        ]

        for risky_node in risky_nodes:
            # Find path from risky node to subject
            path_nodes = self._find_path(graph, risky_node.node_id, graph.subject_node_id)

            if not path_nodes or len(path_nodes) > max_depth + 1:
                continue

            # Calculate propagated risk along path
            current_risk = risky_node.intrinsic_risk
            total_decay = 1.0

            for i in range(len(path_nodes) - 1):
                source = path_nodes[i]
                target = path_nodes[i + 1]

                # Find edge between nodes
                edge = self._find_edge(graph, source, target)
                if not edge:
                    continue

                # Apply decay
                decay = RISK_DECAY_PER_HOP.get(risky_node.risk_level, 0.5)
                decay *= edge.edge_risk_factor
                total_decay *= decay
                current_risk *= decay

            # Only report if above threshold
            if current_risk >= self.config.min_propagated_risk:
                risk_type = self._determine_risk_type(risky_node)
                propagation_path = RiskPropagationPath(
                    source_node_id=risky_node.node_id,
                    source_risk_level=risky_node.risk_level,
                    hops=path_nodes,
                    path_length=len(path_nodes) - 1,
                    propagated_risk_score=current_risk,
                    decay_factor=total_decay,
                    risk_type=risk_type,
                    description=self._format_propagation_description(
                        risky_node, path_nodes, current_risk, graph
                    ),
                )
                propagation_paths.append(propagation_path)

        # Sort by propagated risk (highest first)
        propagation_paths.sort(key=lambda p: p.propagated_risk_score, reverse=True)

        return propagation_paths

    def _find_edge(
        self,
        graph: ConnectionGraph,
        source: UUID,
        target: UUID,
    ) -> ConnectionEdge | None:
        """Find edge between two nodes.

        Args:
            graph: Connection graph.
            source: Source node ID.
            target: Target node ID.

        Returns:
            Edge if found, None otherwise.
        """
        for edge in graph.edges:
            if (edge.source_node_id == source and edge.target_node_id == target) or (
                edge.source_node_id == target and edge.target_node_id == source
            ):
                return edge
        return None

    def _determine_risk_type(self, node: ConnectionNode) -> ConnectionRiskType | None:
        """Determine the type of connection risk from a node.

        Args:
            node: Connection node.

        Returns:
            Risk type if identifiable.
        """
        if not node.risk_factors:
            return None

        risk_factors_lower = [rf.lower() for rf in node.risk_factors]

        if any("sanction" in rf for rf in risk_factors_lower):
            return ConnectionRiskType.SANCTIONS_CONNECTION
        if any("pep" in rf for rf in risk_factors_lower):
            return ConnectionRiskType.PEP_CONNECTION
        if any("watchlist" in rf for rf in risk_factors_lower):
            return ConnectionRiskType.WATCHLIST_CONNECTION
        if any("shell" in rf for rf in risk_factors_lower):
            return ConnectionRiskType.SHELL_COMPANY
        if any("criminal" in rf for rf in risk_factors_lower):
            return ConnectionRiskType.CRIMINAL_ASSOCIATION
        if any("fraud" in rf for rf in risk_factors_lower):
            return ConnectionRiskType.FRAUD_ASSOCIATION
        if any("adverse" in rf or "media" in rf for rf in risk_factors_lower):
            return ConnectionRiskType.ADVERSE_MEDIA_ASSOCIATION

        return None

    def _format_propagation_description(
        self,
        source_node: ConnectionNode,
        path: list[UUID],
        propagated_risk: float,
        graph: ConnectionGraph,  # noqa: ARG002
    ) -> str:
        """Format a description for a propagation path.

        Args:
            source_node: Source of risk.
            path: Node IDs in path.
            propagated_risk: Final propagated risk.
            graph: Connection graph.

        Returns:
            Human-readable description.
        """
        source_name = source_node.entity.name if source_node.entity else "Unknown"
        hops = len(path) - 1

        risk_type = ""
        if source_node.risk_factors:
            risk_type = f" ({', '.join(source_node.risk_factors[:2])})"

        return (
            f"Risk propagates from {source_name}{risk_type} "
            f"through {hops} hop(s) with {propagated_risk:.1%} reaching subject"
        )

    def _sum_propagated_risk(
        self,
        graph: ConnectionGraph,  # noqa: ARG002
        paths: list[RiskPropagationPath],
    ) -> float:
        """Sum propagated risk from all paths (with diminishing returns).

        Args:
            graph: Connection graph.
            paths: Risk propagation paths.

        Returns:
            Total propagated risk score (0.0-1.0).
        """
        if not paths:
            return 0.0

        # Sum with diminishing returns (not simple addition)
        # Use formula: 1 - product(1 - risk_i)
        remaining_clean = 1.0
        for path in paths:
            remaining_clean *= (1 - path.propagated_risk_score)

        return min(1.0, 1 - remaining_clean)

    def _calculate_risk_by_depth(self, graph: ConnectionGraph, depth: int) -> float:
        """Calculate total risk from connections at a specific depth.

        Args:
            graph: Connection graph.
            depth: Depth level (2 for D2, 3 for D3).

        Returns:
            Risk score from that depth.
        """
        nodes_at_depth = [n for n in graph.nodes.values() if n.depth == depth]
        if not nodes_at_depth:
            return 0.0

        # Average of total risks at that depth
        total_risk = sum(n.total_risk for n in nodes_at_depth)
        return total_risk / len(nodes_at_depth)

    def _identify_risk_connections(
        self,
        graph: ConnectionGraph,
        degree: SearchDegree,
    ) -> list[RiskConnection]:
        """Identify high-risk connections in the network.

        Args:
            graph: Connection graph.
            degree: Search degree.

        Returns:
            List of identified risk connections.
        """
        risk_connections: list[RiskConnection] = []

        for node in graph.nodes.values():
            if node.is_subject:
                continue

            # Skip D3 if not requested
            if node.depth > 2 and degree != SearchDegree.D3:
                continue

            # Check if this is a risk connection
            if node.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                # Find the relation to this entity
                relation = self._find_relation_to_node(graph, node)

                risk_type = self._determine_risk_type(node)
                risk_category = risk_type.value if risk_type else "high_risk_connection"

                risk_conn = RiskConnection(
                    entity=node.entity,
                    relation=relation,
                    risk_level=node.risk_level,
                    risk_category=risk_category,
                    risk_description=self._format_risk_description(node, risk_type),
                    recommended_action=self._get_recommended_action(node.risk_level),
                    confidence=node.entity.confidence if node.entity else 0.5,
                )
                risk_connections.append(risk_conn)

            # Also check nodes with high propagated risk
            elif node.total_risk >= self.config.high_risk_threshold:
                relation = self._find_relation_to_node(graph, node)

                risk_conn = RiskConnection(
                    entity=node.entity,
                    relation=relation,
                    risk_level=RiskLevel.MODERATE,
                    risk_category="propagated_risk",
                    risk_description=f"Entity has elevated risk score ({node.total_risk:.1%}) from network position",
                    recommended_action="review",
                    confidence=node.entity.confidence if node.entity else 0.5,
                )
                risk_connections.append(risk_conn)

        return risk_connections

    def _find_relation_to_node(
        self,
        graph: ConnectionGraph,
        node: ConnectionNode,
    ) -> EntityRelation | None:
        """Find the relation that connects to a node.

        Args:
            graph: Connection graph.
            node: Target node.

        Returns:
            EntityRelation if found.
        """
        for edge in graph.edges:
            if edge.source_node_id == node.node_id or edge.target_node_id == node.node_id:
                return edge.relation
        return None

    def _format_risk_description(
        self,
        node: ConnectionNode,
        risk_type: ConnectionRiskType | None,
    ) -> str:
        """Format risk description for a node.

        Args:
            node: Connection node.
            risk_type: Type of risk.

        Returns:
            Human-readable risk description.
        """
        entity_name = node.entity.name if node.entity else "Unknown entity"

        if risk_type == ConnectionRiskType.SANCTIONS_CONNECTION:
            return f"{entity_name} appears on sanctions list"
        elif risk_type == ConnectionRiskType.PEP_CONNECTION:
            return f"{entity_name} is a Politically Exposed Person (PEP)"
        elif risk_type == ConnectionRiskType.SHELL_COMPANY:
            return f"{entity_name} identified as potential shell company"
        elif risk_type == ConnectionRiskType.CRIMINAL_ASSOCIATION:
            return f"{entity_name} has criminal record or associations"
        elif risk_type == ConnectionRiskType.FRAUD_ASSOCIATION:
            return f"{entity_name} linked to fraud activity"
        else:
            factors = ", ".join(node.risk_factors[:3]) if node.risk_factors else "unspecified"
            return f"{entity_name} flagged as high risk ({factors})"

    def _get_recommended_action(self, risk_level: RiskLevel) -> str:
        """Get recommended action based on risk level.

        Args:
            risk_level: Risk level.

        Returns:
            Recommended action string.
        """
        if risk_level == RiskLevel.CRITICAL:
            return "escalate_immediately"
        elif risk_level == RiskLevel.HIGH:
            return "enhanced_due_diligence"
        elif risk_level == RiskLevel.MODERATE:
            return "review"
        else:
            return "monitor"

    def _get_highest_risk_level(self, graph: ConnectionGraph) -> RiskLevel:
        """Get the highest risk level in the graph.

        Args:
            graph: Connection graph.

        Returns:
            Highest RiskLevel.
        """
        risk_order = [
            RiskLevel.NONE,
            RiskLevel.LOW,
            RiskLevel.MODERATE,
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        ]

        highest = RiskLevel.NONE
        for node in graph.nodes.values():
            if not node.is_subject and risk_order.index(node.risk_level) > risk_order.index(highest):
                highest = node.risk_level

        return highest

    def _collect_risk_factors(
        self,
        graph: ConnectionGraph,
        risk_connections: list[RiskConnection],
    ) -> list[str]:
        """Collect all unique risk factors from the analysis.

        Args:
            graph: Connection graph.
            risk_connections: Identified risk connections.

        Returns:
            List of unique risk factors.
        """
        factors: set[str] = set()

        # From nodes
        for node in graph.nodes.values():
            factors.update(node.risk_factors)

        # From risk connections
        for conn in risk_connections:
            if conn.risk_category:
                factors.add(conn.risk_category)

        return sorted(factors)

    def _generate_summary(
        self,
        result: ConnectionAnalysisResult,
        degree: SearchDegree,
    ) -> str:
        """Generate analysis summary.

        Args:
            result: Analysis result.
            degree: Search degree.

        Returns:
            Summary string.
        """
        if not result.graph:
            return "No network analysis performed"

        graph = result.graph
        parts = []

        # Network overview
        parts.append(
            f"Analyzed {graph.total_nodes} entities with {graph.total_edges} relationships"
        )

        # Risk connections
        if result.risk_connections_found:
            critical = sum(1 for c in result.risk_connections_found if c.risk_level == RiskLevel.CRITICAL)
            high = sum(1 for c in result.risk_connections_found if c.risk_level == RiskLevel.HIGH)

            if critical > 0:
                parts.append(f"{critical} CRITICAL risk connection(s) identified")
            if high > 0:
                parts.append(f"{high} HIGH risk connection(s) identified")
        else:
            parts.append("No high-risk connections identified")

        # Propagated risk
        if result.total_propagated_risk > 0:
            parts.append(
                f"Total propagated risk to subject: {result.total_propagated_risk:.1%}"
            )

        # Degree breakdown
        if degree == SearchDegree.D3 and result.d3_risk_score > 0:
            parts.append(
                f"D3 network contributes {result.d3_risk_score:.1%} additional risk"
            )

        return ". ".join(parts)

    def _generate_recommendations(
        self,
        result: ConnectionAnalysisResult,
    ) -> list[str]:
        """Generate recommended actions based on analysis.

        Args:
            result: Analysis result.

        Returns:
            List of recommended actions.
        """
        recommendations: list[str] = []

        # Critical connections
        critical = [
            c for c in result.risk_connections_found
            if c.risk_level == RiskLevel.CRITICAL
        ]
        if critical:
            recommendations.append(
                "IMMEDIATE: Review critical risk connections with compliance team"
            )

        # High risk connections
        high = [
            c for c in result.risk_connections_found
            if c.risk_level == RiskLevel.HIGH
        ]
        if high:
            recommendations.append(
                "Conduct enhanced due diligence on high-risk associated entities"
            )

        # Sanctions
        if any(c.risk_category == "sanctions_connection" for c in result.risk_connections_found):
            recommendations.append(
                "Verify sanctions screening results and document compliance decision"
            )

        # PEP
        if any(c.risk_category == "pep_connection" for c in result.risk_connections_found):
            recommendations.append(
                "Apply enhanced PEP screening procedures and senior management approval"
            )

        # High propagated risk
        if result.total_propagated_risk > 0.5:
            recommendations.append(
                "Network risk assessment indicates elevated exposure - consider additional verification"
            )

        # Default if no specific issues
        if not recommendations:
            recommendations.append("Standard monitoring procedures apply")

        return recommendations

    def _calculate_edge_risk_factor(self, relation: EntityRelation) -> float:
        """Calculate the risk transmission factor for an edge.

        Args:
            relation: Entity relation.

        Returns:
            Risk factor (0.0-1.0).
        """
        # Start with relation type factor
        base_factor = RELATION_RISK_FACTOR.get(relation.relation_type, 0.5)

        # Apply strength multiplier
        strength_mult = STRENGTH_MULTIPLIER.get(relation.strength, 0.7)

        return base_factor * strength_mult

    def _entity_risk_to_score(self, risk_level: RiskLevel) -> float:
        """Convert risk level to numeric score.

        Args:
            risk_level: Risk level enum.

        Returns:
            Score (0.0-1.0).
        """
        scores = {
            RiskLevel.NONE: 0.0,
            RiskLevel.LOW: 0.25,
            RiskLevel.MODERATE: 0.5,
            RiskLevel.HIGH: 0.75,
            RiskLevel.CRITICAL: 0.95,
        }
        return scores.get(risk_level, 0.0)

    def _get_node_color(self, risk_level: RiskLevel) -> str:
        """Get visualization color for a risk level.

        Args:
            risk_level: Risk level.

        Returns:
            Hex color code.
        """
        colors = {
            RiskLevel.NONE: "#90EE90",  # Light green
            RiskLevel.LOW: "#98FB98",  # Pale green
            RiskLevel.MODERATE: "#FFD700",  # Gold
            RiskLevel.HIGH: "#FFA500",  # Orange
            RiskLevel.CRITICAL: "#FF4500",  # Red-orange
        }
        return colors.get(risk_level, "#808080")

    def _get_edge_width(self, strength: ConnectionStrength) -> int:
        """Get visualization width for connection strength.

        Args:
            strength: Connection strength.

        Returns:
            Width in pixels.
        """
        widths = {
            ConnectionStrength.WEAK: 1,
            ConnectionStrength.MODERATE: 2,
            ConnectionStrength.STRONG: 3,
            ConnectionStrength.DIRECT: 4,
        }
        return widths.get(strength, 2)

    def _get_edge_color(self, risk_factor: float) -> str:
        """Get visualization color for edge risk factor.

        Args:
            risk_factor: Risk transmission factor.

        Returns:
            Hex color code.
        """
        if risk_factor >= 0.8:
            return "#FF6B6B"  # Red
        elif risk_factor >= 0.6:
            return "#FFB347"  # Orange
        elif risk_factor >= 0.4:
            return "#FFE66D"  # Yellow
        else:
            return "#C0C0C0"  # Gray


def create_connection_analyzer(
    config: AnalyzerConfig | None = None,
) -> ConnectionAnalyzer:
    """Create a connection analyzer.

    Args:
        config: Optional analyzer configuration.

    Returns:
        Configured ConnectionAnalyzer.
    """
    return ConnectionAnalyzer(config=config)
