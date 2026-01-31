# Task 3.2: Entity Deduplication Pipeline

## Overview
Implement deduplication logic to prevent duplicate entities across the platform, with merge operations for identified duplicates.

**Priority**: P0
**Status**: Planned
**Dependencies**: Task 3.1

## Requirements

### Deduplication Scope

1. **Cross-Screening**: Same individual screened multiple times → one entity
2. **Identifier Enrichment**: New identifiers discovered → check for matches
3. **Tenant Isolation**: Customer data scoped per tenant

### Deduplication Process

1. **Before-Write Check**
   - On entity creation: exact match on canonical identifiers
   - If match found: return existing entity, don't create

2. **Enrichment Trigger**
   - When canonical_identifiers updated with new values
   - Re-run exact match with new identifiers
   - If match found: merge entities

3. **Merge Strategy**
   - Keep older entity (lower UUIDv7 timestamp)
   - Update all relationships to point to canonical entity
   - Preserve identifier history
   - Create audit trail of merge

## Deliverables

### EntityDeduplicator Class

- `check_duplicate(identifiers)`: Pre-creation check
- `merge_entities(source_id, target_id)`: Merge two entities
- `on_identifier_added(entity_id, identifier)`: Enrichment hook
- `find_potential_duplicates(entity_id)`: Scan for duplicates

### MergeResult Model

- `canonical_entity_id`: Surviving entity
- `merged_entity_id`: Absorbed entity
- `relationships_updated`: Count of updated relations
- `profiles_migrated`: Count of migrated profiles

### DuplicateCandidate Model

- `entity_id`: Potential duplicate
- `match_confidence`: Similarity score
- `matching_identifiers`: List of matched identifiers

## Files to Create

| File | Purpose |
|------|---------|
| `src/elile/entity/deduplication.py` | EntityDeduplicator class |
| `tests/unit/test_deduplication.py` | Unit tests |
| `tests/integration/test_entity_merge.py` | Integration tests |

## Merge Algorithm

```python
async def merge_entities(
    self,
    source_id: UUID,
    target_id: UUID,
    reason: str = "duplicate_detected",
) -> MergeResult:
    # 1. Determine canonical (older by UUIDv7)
    source = await self._repo.get(source_id)
    target = await self._repo.get(target_id)
    canonical = source if source.entity_id < target.entity_id else target
    duplicate = target if canonical == source else source

    # 2. Merge identifiers
    merged_ids = {**canonical.canonical_identifiers, **duplicate.canonical_identifiers}
    await self._repo.update(canonical.entity_id, canonical_identifiers=merged_ids)

    # 3. Update relationships
    rel_count = await self._update_relationships(duplicate.entity_id, canonical.entity_id)

    # 4. Migrate profiles
    profile_count = await self._migrate_profiles(duplicate.entity_id, canonical.entity_id)

    # 5. Mark duplicate as merged
    await self._mark_merged(duplicate.entity_id, canonical.entity_id)

    # 6. Audit log
    await self._audit.log_event(
        event_type=AuditEventType.ENTITY_MERGED,
        entity_id=canonical.entity_id,
        event_data={"merged_from": str(duplicate.entity_id), "reason": reason},
    )

    return MergeResult(
        canonical_entity_id=canonical.entity_id,
        merged_entity_id=duplicate.entity_id,
        relationships_updated=rel_count,
        profiles_migrated=profile_count,
    )
```

## Integration Points

- EntityMatcher for duplicate detection
- EntityRepository for database operations
- AuditLogger for merge audit trail
- RequestContext for tenant scoping

## Test Cases

1. Create entity with existing SSN → return existing
2. Add SSN to entity matching another → merge triggered
3. Merge updates all relationships correctly
4. Merge preserves all identifiers
5. Merge creates proper audit trail
6. Tenant-scoped deduplication doesn't cross tenants
