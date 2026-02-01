# Task 6.6: Connection Analyzer

## Overview

Implement connection analyzer that maps relationships between entities, analyzes network graphs, and assesses risk propagation through connections for D2/D3 investigations.

**Priority**: P0 | **Effort**: 3 days | **Status**: Not Started

## Dependencies

- Task 3.1-3.2: Entity Resolution
- Task 2.2: Investigation Degrees

## Implementation

```python
# src/elile/risk/connection_analyzer.py
class ConnectionAnalyzer:
    """Analyzes entity connections and network risk."""

    def analyze_connections(
        self,
        subject_entity: Entity,
        discovered_entities: list[Entity],
        degree: SearchDegree
    ) -> list[EntityConnection]:
        """Build and analyze connection graph."""

        connections = []

        if degree == SearchDegree.D1:
            # No network analysis for D1
            return []

        # Build D2 connections (direct)
        if degree >= SearchDegree.D2:
            connections.extend(
                self._build_direct_connections(subject_entity, discovered_entities)
            )

        # Build D3 connections (extended)
        if degree == SearchDegree.D3:
            connections.extend(
                self._build_extended_connections(discovered_entities)
            )

        # Analyze risk propagation
        self._analyze_risk_propagation(connections)

        return connections

    def _build_direct_connections(
        self,
        subject: Entity,
        entities: list[Entity]
    ) -> list[EntityConnection]:
        """Build direct (D2) connections."""
        pass

    def _analyze_risk_propagation(self, connections: list[EntityConnection]) -> None:
        """Calculate risk propagation through network."""
        pass
```

## Acceptance Criteria

- [ ] Maps D2 direct connections
- [ ] Maps D3 extended network
- [ ] Calculates risk propagation
- [ ] Identifies risky connections
- [ ] Graph visualization data

## Deliverables

- `src/elile/risk/connection_analyzer.py`
- `tests/unit/test_connection_analyzer.py`

## References

- Architecture: [05-investigation.md](../../docs/architecture/05-investigation.md) - Connection Mapper

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
