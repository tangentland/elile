# Task 3.3: Canonical Entity Management

## Overview
Implement canonical entity management for maintaining authoritative entity versions with identifier aggregation and relationship graph management.

**Priority**: P0
**Status**: Planned
**Dependencies**: Task 3.1, Task 3.2

## Requirements

### Canonical Entity Properties

- Single authoritative entity_id per person/organization
- Aggregates all identifiers discovered across screenings
- Maintains confidence scores per identifier
- Tracks identifier discovery history

### Identifier Management

- Identifiers are append-only (never deleted)
- Each identifier has confidence and discovery metadata
- Support for multiple identifier types

### Identifier Structure

```python
{
    "ssn": {
        "value": "123-45-6789",
        "confidence": 0.99,
        "discovered_at": "2026-01-15T10:00:00Z",
        "source": "credit_bureau"
    },
    "name_variants": [
        {"value": "John Smith", "confidence": 1.0},
        {"value": "Jon Smith", "confidence": 0.85}
    ],
    "passport": {
        "value": "N123456",
        "country": "US",
        "confidence": 0.95
    }
}
```

## Deliverables

### EntityManager Class

High-level entity operations:
- `create_entity(entity_type, identifiers)`: Create with dedup check
- `get_canonical(entity_id)`: Get authoritative entity
- `add_identifier(entity_id, id_type, value, confidence)`: Add identifier
- `get_identifiers(entity_id)`: Get all identifiers
- `add_relation(from_id, to_id, relation_type)`: Add relationship
- `get_relations(entity_id, direction)`: Get entity relationships

### IdentifierRecord Model

- `identifier_type`: SSN, EIN, passport, etc.
- `value`: The identifier value
- `confidence`: 0.0 - 1.0
- `discovered_at`: When found
- `source`: Where discovered

### RelationshipGraph

- `add_edge(from_id, to_id, relation_type, confidence)`: Add relation
- `get_neighbors(entity_id, depth)`: Get connected entities
- `get_path(from_id, to_id)`: Find connection path
- `to_networkx()`: Export for analysis

## Files to Create

| File | Purpose |
|------|---------|
| `src/elile/entity/manager.py` | EntityManager class |
| `src/elile/entity/identifiers.py` | Identifier management |
| `src/elile/entity/graph.py` | RelationshipGraph |
| `tests/unit/test_entity_manager.py` | Unit tests |

## Identifier Types

| Type | Format | Example |
|------|--------|---------|
| `ssn` | XXX-XX-XXXX | 123-45-6789 |
| `ein` | XX-XXXXXXX | 12-3456789 |
| `passport` | Varies by country | N12345678 |
| `drivers_license` | State + number | CA-D1234567 |
| `email` | Standard email | john@example.com |
| `phone` | E.164 format | +14155551234 |
| `name_variant` | String | Jon Smith |

## Integration Points

- EntityMatcher for resolution
- EntityDeduplicator for duplicate handling
- EntityRepository for persistence
- AuditLogger for tracking changes

## Test Cases

1. Create entity with identifiers
2. Add identifier increases confidence
3. Get all identifiers for entity
4. Add relationship between entities
5. Get neighbors at depth 1, 2, 3
6. Identifier history preserved
