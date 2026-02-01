# Task 5.14: SAR Network Phase Handler

**Priority**: P1
**Phase**: 5 - Investigation Engine
**Estimated Effort**: 3 days
**Dependencies**: Task 5.13 (Intelligence Phase)

## Context

Implement Network phase for relationship mapping, entity connection analysis, and investigation of associates and affiliated entities.

**Architecture Reference**: [05-investigation.md](../docs/architecture/05-investigation.md) - SAR Loop

## Objectives

1. Extract entity relationships
2. Build network graph
3. Analyze connection strength
4. Identify high-risk associations
5. Support network visualization

## Technical Approach

```python
# src/elile/investigation/phases/network.py
class NetworkPhaseHandler:
    """Handle Network analysis phase."""

    async def execute(
        self,
        intelligence: IntelligenceResult
    ) -> NetworkResult:
        """Build and analyze entity network."""
        # Extract entities from all sources
        entities = self._extract_entities(intelligence)

        # Build relationship graph
        graph = self._build_network_graph(entities)

        # Analyze connections
        risk_connections = self._identify_risk_connections(graph)

        return NetworkResult(
            entity_graph=graph,
            risk_connections=risk_connections,
            next_phase="reconciliation"
        )
```

## Implementation Checklist

- [ ] Implement entity extraction
- [ ] Build network graph
- [ ] Add connection scoring
- [ ] Create visualization data

## Success Criteria

- [ ] Network graph accurate
- [ ] Risk scoring effective
- [ ] Visualization supported
