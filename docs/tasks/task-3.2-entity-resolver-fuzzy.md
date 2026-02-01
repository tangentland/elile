# Task 3.2: Entity Resolver (Fuzzy Matching)

## Overview

Implement probabilistic entity resolution using fuzzy matching on name + DOB + address when exact identifiers unavailable. Uses similarity scoring with configurable threshold (0.85).

**Priority**: P0 | **Effort**: 3 days | **Status**: Not Started

## Dependencies

- Task 3.1: Entity Resolver (Exact)
- External: python-Levenshtein or rapidfuzz

## Implementation Checklist

- [ ] Add fuzzy matching to EntityResolver
- [ ] Implement name similarity (Levenshtein/Jaro-Winkler)
- [ ] Build DOB and address matching
- [ ] Create composite scoring algorithm
- [ ] Add configurable match threshold
- [ ] Write fuzzy matching tests with known cases

## Key Implementation

```python
# src/elile/services/entity_resolution.py (extend)
from rapidfuzz import fuzz
from datetime import date

class EntityResolver:
    FUZZY_MATCH_THRESHOLD = 0.85  # 85% similarity required

    async def resolve_fuzzy(
        self,
        name: str,
        dob: date | None = None,
        address: str | None = None,
        tenant_id: UUID | None = None
    ) -> list[EntityMatchScore]:
        """
        Find entities using fuzzy matching.

        Scoring:
        - Name: 50% weight (Jaro-Winkler)
        - DOB: 30% weight (exact or None)
        - Address: 20% weight (fuzzy)

        Returns:
            List of EntityMatchScore sorted by score (desc)
        """
        from sqlalchemy import select

        # Get all entities (or filter by tenant)
        query = select(Entity).where(Entity.entity_type == EntityType.INDIVIDUAL)
        if tenant_id:
            query = query.where(Entity.tenant_id == tenant_id)

        result = await self.db.execute(query)
        entities = result.scalars().all()

        matches = []
        for entity in entities:
            score = self._calculate_fuzzy_score(
                entity,
                name=name,
                dob=dob,
                address=address
            )

            if score >= self.FUZZY_MATCH_THRESHOLD:
                matches.append(EntityMatchScore(
                    entity_id=entity.entity_id,
                    match_score=score,
                    match_criteria={
                        "name": name,
                        "dob": dob.isoformat() if dob else None,
                        "address": address
                    },
                    match_type="fuzzy"
                ))

        # Sort by score descending
        matches.sort(key=lambda m: m.match_score, reverse=True)
        return matches

    def _calculate_fuzzy_score(
        self,
        entity: Entity,
        name: str,
        dob: date | None,
        address: str | None
    ) -> float:
        """Calculate composite fuzzy match score."""
        total_score = 0.0
        total_weight = 0.0

        # Name similarity (50% weight)
        if name and hasattr(entity, 'name'):  # Assume name stored in profile
            name_score = fuzz.ratio(name.lower(), entity.name.lower()) / 100.0
            total_score += name_score * 0.5
            total_weight += 0.5

        # DOB match (30% weight)
        if dob and hasattr(entity, 'dob'):
            dob_score = 1.0 if entity.dob == dob else 0.0
            total_score += dob_score * 0.3
            total_weight += 0.3

        # Address similarity (20% weight)
        if address and hasattr(entity, 'address'):
            addr_score = fuzz.partial_ratio(address.lower(), entity.address.lower()) / 100.0
            total_score += addr_score * 0.2
            total_weight += 0.2

        # Normalize by actual weight used
        return total_score / total_weight if total_weight > 0 else 0.0
```

## Testing Requirements

### Unit Tests
- Name similarity calculation
- DOB exact match vs mismatch
- Address fuzzy matching
- Composite score calculation
- Threshold filtering (>=0.85)

### Integration Tests
- Fuzzy match finds similar entities
- Fuzzy match with 1000+ entities (performance)
- No false positives below threshold

**Coverage Target**: 85%+

## Acceptance Criteria

- [ ] Fuzzy matching on name + DOB + address
- [ ] Match score >= 0.85 required
- [ ] Results sorted by score descending
- [ ] Composite scoring uses weighted factors
- [ ] Performance acceptable (<1s for 10k entities)
- [ ] Integration with exact matching (try exact first)

## Deliverables

- `src/elile/services/entity_resolution.py` (extend)
- `tests/unit/test_entity_resolver_fuzzy.py`
- `tests/data/fuzzy_match_cases.json` (test data)

## References

- Architecture: [02-core-system.md](../architecture/02-core-system.md) - Entity resolution
- Dependencies: Task 3.1 (exact matching)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
