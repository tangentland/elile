# Task 3.1: Entity Resolution Engine

## Overview
Implement the entity resolution engine that determines whether incoming subject identifiers match existing entities or require creating new ones.

**Priority**: P0
**Status**: Planned
**Dependencies**: Phase 1, Phase 2

## Requirements

### Three-Stage Matching Process

1. **Exact Match** (Priority 1)
   - Match on canonical identifiers: SSN, EIN, passport, national ID
   - If match found → use existing entity immediately
   - Highest confidence (1.0)

2. **Fuzzy Match** (Priority 2)
   - Multi-field similarity: full name + date of birth + address
   - Scoring threshold: 0.70 - 0.95 confidence
   - Uses string similarity algorithms (Levenshtein, Jaro-Winkler)
   - Handles variants: maiden names, spelling variations

3. **Tier-Based Resolution**
   - **Standard Tier**:
     - Confidence > 0.85 → auto-match
     - Confidence < 0.85 → create new entity
   - **Enhanced Tier**:
     - Confidence 0.70-0.95 → queue for analyst review
     - Analyst can validate, merge, or create new

## Deliverables

### EntityMatcher Class

Core matching logic:
- `match_exact(identifiers)`: Exact identifier lookup
- `match_fuzzy(name, dob, address)`: Similarity scoring
- `resolve(subject_info, tier)`: Full resolution logic
- `calculate_similarity(a, b)`: String similarity

### MatchResult Model

Resolution outcome:
- `entity_id`: Matched entity or None
- `match_type`: EXACT, FUZZY, NEW
- `confidence`: 0.0 - 1.0
- `requires_review`: Boolean for Enhanced tier
- `matched_fields`: Which fields matched

### ResolutionDecision Enum

- MATCH_EXISTING: Use existing entity
- CREATE_NEW: Create new entity
- PENDING_REVIEW: Queue for analyst (Enhanced only)

## Files to Create

| File | Purpose |
|------|---------|
| `src/elile/entity/__init__.py` | Package initialization |
| `src/elile/entity/matcher.py` | EntityMatcher class |
| `src/elile/entity/types.py` | MatchResult, enums |
| `tests/unit/test_entity_matcher.py` | Unit tests |

## Algorithm Details

### Exact Match
```python
async def match_exact(self, identifiers: dict) -> Entity | None:
    for id_type, value in identifiers.items():
        if id_type in ("ssn", "ein", "passport"):
            # Query entities with matching canonical_identifiers
            entity = await self._find_by_identifier(id_type, value)
            if entity:
                return entity
    return None
```

### Fuzzy Match
```python
def calculate_similarity(self, subject: SubjectInfo, entity: Entity) -> float:
    scores = []
    # Name similarity (Jaro-Winkler)
    name_score = jaro_winkler(subject.full_name, entity.name)
    scores.append(name_score * 0.4)  # 40% weight

    # DOB match (exact or None)
    if subject.dob and entity.dob:
        dob_score = 1.0 if subject.dob == entity.dob else 0.0
        scores.append(dob_score * 0.35)  # 35% weight

    # Address similarity
    if subject.address and entity.address:
        addr_score = address_similarity(subject.address, entity.address)
        scores.append(addr_score * 0.25)  # 25% weight

    return sum(scores)
```

## Integration Points

- RequestContext for tenant isolation
- AuditLogger for resolution decisions
- ComplianceEngine for locale rules
- EntityRepository for database access

## Test Cases

1. Exact SSN match → return existing entity
2. No identifiers match → create new entity
3. Fuzzy match > 0.85 Standard → auto-match
4. Fuzzy match 0.70-0.85 Enhanced → pending review
5. Name-only match → low confidence, create new
