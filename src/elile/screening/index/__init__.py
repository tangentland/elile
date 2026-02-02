"""Cross-screening entity index module.

This module provides functionality for indexing and querying entity connections
across screening operations, enabling network analysis and relationship mapping.

Usage:
    from elile.screening.index import (
        CrossScreeningIndex,
        get_cross_screening_index,
        SubjectConnection,
        ConnectionType,
    )

    # Get singleton index
    index = get_cross_screening_index()

    # Index a screening's connections
    await index.index_screening_connections(
        screening_id=screening_id,
        subject_id=subject_id,
        entities=discovered_entities,
    )

    # Find connected subjects
    result = await index.find_connected_subjects(
        subject_id=subject_id,
        max_degree=2,
    )
    for connection in result.connections:
        print(f"{connection.target_subject_id}: {connection.connection_type}")

Network Graph:
    # Build a network graph for visualization
    graph = await index.get_network_graph(
        subject_id=subject_id,
        max_depth=2,
    )
    print(f"Nodes: {graph.node_count}, Edges: {graph.edge_count}")

Relationship Strength:
    # Calculate relationship strength between two subjects
    strength = await index.calculate_relationship_strength(
        subject_id_a=subject_a,
        subject_id_b=subject_b,
    )
"""

from elile.screening.index.index import (
    CrossScreeningIndex,
    IndexConfig,
    IndexStatistics,
    create_index,
    get_cross_screening_index,
)
from elile.screening.index.types import (
    ConnectionStrength,
    ConnectionType,
    CrossScreeningIndexError,
    CrossScreeningResult,
    EntityReference,
    IndexingError,
    NetworkEdge,
    NetworkGraph,
    NetworkNode,
    ScreeningEntity,
    ScreeningNotIndexedError,
    SubjectConnection,
    SubjectNotFoundError,
)

__all__ = [
    # Main class
    "CrossScreeningIndex",
    # Factory functions
    "create_index",
    "get_cross_screening_index",
    # Configuration
    "IndexConfig",
    "IndexStatistics",
    # Types
    "ConnectionStrength",
    "ConnectionType",
    "CrossScreeningResult",
    "EntityReference",
    "NetworkEdge",
    "NetworkGraph",
    "NetworkNode",
    "ScreeningEntity",
    "SubjectConnection",
    # Exceptions
    "CrossScreeningIndexError",
    "IndexingError",
    "ScreeningNotIndexedError",
    "SubjectNotFoundError",
]
