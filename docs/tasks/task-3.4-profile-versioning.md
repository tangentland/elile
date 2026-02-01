# Task 3.4: Profile Version Manager

## Overview

Implement profile versioning system that creates new EntityProfile version for each screening, maintains version history, and supports profile comparison for delta analysis.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 1.1: Database Schema (EntityProfile model)

## Implementation Checklist

- [ ] Extend EntityProfile model with version number
- [ ] Implement profile creation with auto-increment version
- [ ] Build profile version history query
- [ ] Add latest profile retrieval
- [ ] Create profile snapshot functionality
- [ ] Write profile versioning tests

## Key Implementation

```python
# src/elile/services/profile_versioning.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

class ProfileVersionManager:
    """Manages entity profile versions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_profile_version(
        self,
        entity_id: UUID,
        risk_score: float,
        findings: list[Finding],
        entity_graph: dict,
        screening_id: UUID,
        ctx: RequestContext
    ) -> EntityProfile:
        """
        Create new profile version for entity.

        Version number auto-increments from previous version.
        """
        # Get latest version number
        latest_version = await self.get_latest_version_number(entity_id)
        new_version = (latest_version or 0) + 1

        profile = EntityProfile(
            entity_id=entity_id,
            version=new_version,
            risk_score=risk_score,
            findings_summary=self._summarize_findings(findings),
            entity_graph=entity_graph,
            created_by_screening=screening_id,
            created_at=datetime.utcnow()
        )

        self.db.add(profile)
        await self.db.flush()

        # Audit log
        await audit_logger.log_event(
            AuditEventType.PROFILE_CREATED,
            ctx,
            {
                "profile_id": str(profile.profile_id),
                "version": new_version,
                "screening_id": str(screening_id)
            },
            entity_id=entity_id
        )

        return profile

    async def get_latest_version_number(self, entity_id: UUID) -> int | None:
        """Get latest version number for entity."""
        query = select(func.max(EntityProfile.version)).where(
            EntityProfile.entity_id == entity_id
        )
        result = await self.db.execute(query)
        return result.scalar()

    async def get_latest_profile(self, entity_id: UUID) -> EntityProfile | None:
        """Get most recent profile for entity."""
        query = select(EntityProfile).where(
            EntityProfile.entity_id == entity_id
        ).order_by(EntityProfile.version.desc()).limit(1)

        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_profile_version(
        self,
        entity_id: UUID,
        version: int
    ) -> EntityProfile | None:
        """Get specific profile version."""
        query = select(EntityProfile).where(
            EntityProfile.entity_id == entity_id,
            EntityProfile.version == version
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_version_history(
        self,
        entity_id: UUID,
        limit: int = 10
    ) -> list[EntityProfile]:
        """Get profile version history (most recent first)."""
        query = select(EntityProfile).where(
            EntityProfile.entity_id == entity_id
        ).order_by(EntityProfile.version.desc()).limit(limit)

        result = await self.db.execute(query)
        return result.scalars().all()

    def _summarize_findings(self, findings: list[Finding]) -> dict:
        """Create summary of findings for profile."""
        return {
            "total_findings": len(findings),
            "by_category": self._count_by_category(findings),
            "by_severity": self._count_by_severity(findings)
        }
```

## Testing Requirements

### Unit Tests
- Version auto-increment logic
- Latest profile retrieval
- Version history query
- Profile creation with findings summary

### Integration Tests
- Create multiple profile versions
- Version numbers sequential
- Latest profile is correct
- Concurrent profile creation (locking)

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] Profile version auto-increments per entity
- [ ] get_latest_profile() returns most recent
- [ ] get_version_history() returns ordered list
- [ ] Profile includes findings summary
- [ ] Audit log for profile creation
- [ ] Concurrent safety (no duplicate versions)

## Deliverables

- `src/elile/services/profile_versioning.py`
- `tests/unit/test_profile_versioning.py`
- `tests/integration/test_profile_versions.py`

## References

- Architecture: [02-core-system.md](../architecture/02-core-system.md) - Profile versioning
- Dependencies: Task 1.1 (EntityProfile model)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
