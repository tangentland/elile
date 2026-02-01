# Task 3.11: Cross-Screening Index

**Priority**: P1
**Phase**: 3 - Subject & Screening Engine
**Estimated Effort**: 2 days
**Dependencies**: Task 3.1 (Subject Management), Task 1.10 (Redis Cache)

## Context

Implement cross-screening entity index to identify connections between subjects across different screening operations. Enables network analysis and relationship mapping.

**Architecture Reference**: [05-investigation.md](../docs/architecture/05-investigation.md) - Network Analysis

## Objectives

1. Create entity relationship index
2. Support connection discovery across screenings
3. Enable network graph queries
4. Add relationship strength scoring
5. Support temporal relationship tracking

## Technical Approach

```python
# src/elile/screening/index/cross_screening_index.py
class CrossScreeningIndex:
    """Index for cross-screening entity relationships."""

    def index_screening_connections(
        self,
        screening_id: str
    ) -> None:
        """Index all entities found in screening."""
        # Extract entities from findings
        # Create bidirectional edges
        # Calculate relationship scores
        pass

    def find_connected_subjects(
        self,
        subject_id: str,
        max_degree: int = 2
    ) -> List[SubjectConnection]:
        """Find subjects connected to target."""
        pass
```

## Implementation Checklist

- [ ] Design graph index schema
- [ ] Implement entity extraction
- [ ] Add relationship scoring
- [ ] Create query interface
- [ ] Test connection discovery

## Success Criteria

- [ ] Index updates in real-time
- [ ] Query returns results <1s
- [ ] Relationship scores accurate
- [ ] Network visualization supported
