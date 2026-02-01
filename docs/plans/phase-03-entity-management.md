# Phase 3: Entity Management

## Overview

Phase 3 implements entity resolution (matching subjects to canonical entities), profile versioning with delta analysis, cache management with freshness policies, and data retention. This phase establishes the core data lifecycle management.

**Duration Estimate**: 2-3 weeks
**Team Size**: 2-3 developers
**Risk Level**: Medium (entity matching accuracy critical)

## Phase Goals

- ✓ Build entity resolution engine (exact + fuzzy matching)
- ✓ Implement profile versioning with delta computation
- ✓ Create cache management with freshness policies
- ✓ Build data retention and GDPR erasure capabilities

## Tasks

| Seq | Task Name | Priority | Status | Dependencies | Plan Document |
|-----|-----------|----------|--------|--------------|---------------|
| 3.1 | Entity Resolver (Exact Matching) | P0 | Not Started | 1.1, 1.6 | [task-3.1-entity-resolver-exact.md](../tasks/task-3.1-entity-resolver-exact.md) |
| 3.2 | Entity Resolver (Fuzzy Matching) | P0 | Not Started | 3.1 | [task-3.2-entity-resolver-fuzzy.md](../tasks/task-3.2-entity-resolver-fuzzy.md) |
| 3.3 | Entity Merge/Split Capability | P1 | Not Started | 3.1, 3.2 | [task-3.3-entity-merge-split.md](../tasks/task-3.3-entity-merge-split.md) |
| 3.4 | Profile Version Manager | P0 | Not Started | 1.1 | [task-3.4-profile-versioning.md](../tasks/task-3.4-profile-versioning.md) |
| 3.5 | Profile Delta Computation | P0 | Not Started | 3.4 | [task-3.5-profile-delta.md](../tasks/task-3.5-profile-delta.md) |
| 3.6 | Cache Manager (Core) | P0 | Not Started | 1.1, 1.10 | [task-3.6-cache-manager.md](../tasks/task-3.6-cache-manager.md) |
| 3.7 | Freshness Policy Engine | P0 | Not Started | 3.6 | [task-3.7-freshness-policies.md](../tasks/task-3.7-freshness-policies.md) |
| 3.8 | Stale Data Handler (Tier-Aware) | P0 | Not Started | 3.7, 2.1 | [task-3.8-stale-data-handler.md](../tasks/task-3.8-stale-data-handler.md) |
| 3.9 | Data Retention Manager | P1 | Not Started | 1.1, 2.5 | [task-3.9-data-retention.md](../tasks/task-3.9-data-retention.md) |
| 3.10 | GDPR Erasure Process | P1 | Not Started | 1.1, 2.10 | [task-3.10-gdpr-erasure.md](../tasks/task-3.10-gdpr-erasure.md) |
| 3.11 | Cross-Screening Index Builder | P1 | Not Started | 1.1 | [task-3.11-cross-screening-index.md](../tasks/task-3.11-cross-screening-index.md) |

## Key Data Models

### Entity Resolution
```python
class EntityMatchScore(BaseModel):
    entity_id: UUID
    match_score: float  # 0.0 - 1.0
    match_criteria: dict  # Which fields matched
    match_type: Literal["exact", "fuzzy"]

class EntityResolver:
    async def resolve_or_create(
        self,
        identifiers: dict[str, str],
        tenant_id: UUID,
        ctx: RequestContext
    ) -> Entity:
        """
        Find existing entity or create new one.
        Exact match: SSN, EIN, passport (deterministic)
        Fuzzy match: name + DOB + address (probabilistic)
        """
```

### Profile Delta
```python
class ProfileDelta(BaseModel):
    new_findings: list[Finding]
    resolved_findings: list[Finding]
    changed_findings: list[FindingChange]
    risk_score_change: float
    connection_count_change: int
    new_connections: list[EntityConnection]
    lost_connections: list[EntityConnection]
    evolution_signals: list[EvolutionSignal]
```

### Cache Freshness
```python
FRESHNESS_WINDOWS = {
    CheckType.SANCTIONS: timedelta(days=0),  # Always refresh
    CheckType.CRIMINAL: timedelta(days=7),
    CheckType.ADVERSE_MEDIA: timedelta(hours=24),
    CheckType.EMPLOYMENT: timedelta(days=90),
    CheckType.EDUCATION: timedelta(days=365),
}

STALE_WINDOWS = {
    CheckType.CRIMINAL: timedelta(days=30),
    CheckType.EMPLOYMENT: timedelta(days=180),
}
```

## Phase Acceptance Criteria

### Functional Requirements
- [x] Entity resolver finds exact matches (SSN, EIN)
- [x] Entity resolver scores fuzzy matches (>0.85 threshold)
- [x] Profile delta correctly identifies new/changed/resolved findings
- [x] Cache returns fresh data when available
- [x] Stale data policy varies by tier (Standard: use+flag, Enhanced: block+refresh)
- [x] GDPR erasure anonymizes subject data while preserving analytics

### Testing Requirements
- [x] Entity matching: 1000+ test cases with known matches/non-matches
- [x] Profile delta: Test all change types (new, resolved, changed)
- [x] Cache freshness: Time-based tests with mocked timestamps
- [x] GDPR erasure: Verify cascade through all tables

### Review Gates
- [x] Architecture review: Entity resolution algorithm
- [x] Legal review: GDPR erasure completeness
- [x] Performance review: Entity lookup optimization

---

*Phase Owner: [Assign team lead]*
*Last Updated: 2026-01-29*
