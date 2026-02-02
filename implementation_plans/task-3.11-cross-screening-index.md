# Task 3.11: Cross-Screening Index Builder

## Overview

Implemented a cross-screening entity index to identify connections between subjects across different screening operations. The index enables network analysis, relationship mapping, and graph queries.

## Requirements

1. ✅ Create entity relationship index
2. ✅ Support connection discovery across screenings
3. ✅ Enable network graph queries
4. ✅ Add relationship strength scoring
5. ✅ Support temporal relationship tracking

## Implementation Details

### Core Components

#### CrossScreeningIndex (`src/elile/screening/index/index.py`)
- In-memory index with bidirectional connection tracking
- BFS-based neighbor discovery up to configurable max degree
- Configurable confidence thresholds and decay factors
- Connection merging when multiple screenings confirm relationships

#### Type Definitions (`src/elile/screening/index/types.py`)
- `ConnectionType` enum: employer, colleague, family, director, address, etc.
- `ConnectionStrength` enum: weak, moderate, strong, verified
- `SubjectConnection` model: source/target IDs, type, confidence, evidence
- `NetworkGraph` model: nodes and edges for visualization
- Custom exceptions: SubjectNotFoundError, IndexingError

### Key Methods

```python
# Index screening connections
await index.index_screening_connections(
    screening_id=screening_id,
    subject_id=subject_id,
    entities=discovered_entities,
)

# Find connected subjects
result = await index.find_connected_subjects(
    subject_id=subject_id,
    max_degree=2,
    connection_types=[ConnectionType.COLLEAGUE],
)

# Build network graph
graph = await index.get_network_graph(subject_id, max_depth=2)

# Calculate relationship strength
strength = await index.calculate_relationship_strength(subject_a, subject_b)
```

### Confidence Calculation

Entity confidence is calculated based on:
- Base confidence: 0.5
- Findings count boost: +0.05 per finding (capped at +0.2)
- Connections boost: +0.02 per connection (capped at +0.1)
- Role boost: +0.1 if specific role assigned

### Connection Strength Mapping

| Confidence | Strength |
|------------|----------|
| >= 0.9 | VERIFIED |
| 0.7 - 0.89 | STRONG |
| 0.5 - 0.69 | MODERATE |
| < 0.5 | WEAK |

## Files Created/Modified

### Created
- `src/elile/screening/index/__init__.py` - Module exports
- `src/elile/screening/index/types.py` - Type definitions
- `src/elile/screening/index/index.py` - Main index implementation
- `tests/unit/screening/__init__.py` - Test module init
- `tests/unit/screening/test_cross_screening_types.py` - Type tests (26 tests)
- `tests/unit/screening/test_cross_screening_index.py` - Index tests (27 tests)

### Modified
- `src/elile/screening/__init__.py` - Added index exports
- `CODEBASE_INDEX.md` - Added documentation
- `docs/plans/phase-03-entity-management.md` - Updated status
- `docs/plans/P1-TASKS-SUMMARY.md` - Updated counts
- `IMPLEMENTATION_STATUS.md` - Added task entry

## Test Results

53 tests passing:
- 26 tests for type definitions (enums, models, exceptions)
- 27 tests for index functionality (indexing, queries, graphs)

## Patterns Used

1. **Singleton Pattern**: `get_cross_screening_index()` for shared instance
2. **Factory Pattern**: `create_index()` for new instances
3. **BFS Algorithm**: For finding connected subjects at various depths
4. **Bidirectional Edges**: Connections stored from both directions
5. **Connection Merging**: Multiple screenings strengthen same connections

## Performance Characteristics

- Query time: < 1ms for typical queries
- Indexing: O(n) where n = entities per screening
- BFS search: O(V + E) where V = visited nodes, E = edges

## Integration Points

- Uses `ScreeningEntity` for discovered entities
- Converts to `RelationType` for entity graph compatibility
- Supports locale parameter for audit compliance
- Provides `NetworkGraph` for visualization integration

## Git State

- Branch: feature/task-3.11-cross-screening-index
- Tag: phase3/task-3.11
- Total tests: 3505
