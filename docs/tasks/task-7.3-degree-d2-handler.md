# Task 7.3: Degree D2 Handler

## Overview

Implement D2 (network expansion) handler that investigates direct connections discovered during subject investigation, with entity queue management and connection mapping.

**Priority**: P0 | **Effort**: 3 days | **Status**: Not Started

## Dependencies

- Task 7.2: D1 Handler
- Task 6.6: Connection Analyzer

## Implementation

```python
# src/elile/screening/degree_handlers.py
class D2Handler:
    """Handles D2 (direct network) investigations."""

    async def execute_d2(
        self,
        subject: SubjectInfo,
        discovered_entities: list[Entity],
        max_entities: int,
        ctx: RequestContext
    ) -> D2Result:
        """Execute D2 network expansion."""

        # Prioritize entities for investigation
        entity_queue = self._prioritize_entities(
            discovered_entities, max_entities
        )

        # Investigate each entity
        entity_findings = {}
        for entity in entity_queue:
            findings = await self._investigate_entity(entity, ctx)
            entity_findings[entity.entity_id] = findings

        # Build connection graph
        connections = self.connection_analyzer.analyze_connections(
            subject, entity_queue, SearchDegree.D2
        )

        return D2Result(
            entity_findings=entity_findings,
            connections=connections
        )

    def _prioritize_entities(
        self,
        entities: list[Entity],
        max_count: int
    ) -> list[Entity]:
        """Prioritize entities for investigation."""
        # Sort by relevance, take top N
        pass
```

## Acceptance Criteria

- [ ] Investigates direct connections (D2)
- [ ] Prioritizes entities (top N)
- [ ] Builds connection graph
- [ ] Respects max entity limits

## Deliverables

- `src/elile/screening/degree_handlers.py` (extend)
- `tests/unit/test_d2_handler.py`

## References

- Architecture: [03-screening.md](../../docs/architecture/03-screening.md) - D2

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
