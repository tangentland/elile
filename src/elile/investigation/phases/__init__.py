"""Investigation phase handlers.

This package provides phase handlers for the investigation process:
- foundation: Foundation phase (identity, employment, education) - Task 5.11
- records: Records phase (criminal, civil, financial, licenses, regulatory, sanctions) - Task 5.12
- intelligence: Intelligence phase (adverse media, digital footprint) - Task 5.13
- network: Network phase (D2/D3 connections) - Task 5.14
- reconciliation: Reconciliation phase (cross-source conflict resolution) - Task 5.15

See phase5_rework.md for implementation instructions.
"""

from elile.investigation.phases.network import (
    ConnectionStrength,
    DiscoveredEntity,
    EntityRelation,
    EntityType,
    NetworkConfig,
    NetworkPhaseHandler,
    NetworkPhaseResult,
    NetworkProfile,
    RelationType,
    RiskConnection,
    RiskLevel,
    create_network_phase_handler,
)

__all__ = [
    # Network phase (Task 5.14 - stub)
    "NetworkPhaseHandler",
    "create_network_phase_handler",
    "NetworkConfig",
    "NetworkPhaseResult",
    "NetworkProfile",
    "DiscoveredEntity",
    "EntityRelation",
    "RiskConnection",
    "EntityType",
    "RelationType",
    "RiskLevel",
    "ConnectionStrength",
]
