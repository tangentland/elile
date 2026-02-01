# Task 3.1: Entity Resolver (Exact Matching)

## Overview

Implement deterministic entity resolution using exact matching on canonical identifiers (SSN, EIN, passport). Creates or returns existing entity based on unique identifiers.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 1.1: Database Schema (Entity model)
- Task 1.6: Encryption (for SSN/identifiers)

## Implementation Checklist

- [ ] Create EntityResolver service with exact matching
- [ ] Implement identifier normalization (remove dashes, spaces)
- [ ] Build entity lookup by canonical identifiers
- [ ] Add entity creation with deduplication
- [ ] Create match confidence scoring
- [ ] Write entity resolution tests

## Key Implementation

```python
# src/elile/services/entity_resolution.py
from dataclasses import dataclass

@dataclass
class EntityMatchScore:
    """Entity match result with confidence."""
    entity_id: UUID
    match_score: float  # 0.0 - 1.0 (1.0 for exact match)
    match_criteria: dict[str, Any]  # Which fields matched
    match_type: Literal["exact", "fuzzy"]

class EntityResolver:
    """Resolve entities using exact and fuzzy matching."""

    def __init__(self, db: AsyncSession, encryption_service: EncryptionService):
        self.db = db
        self.encryption = encryption_service

    def normalize_identifier(self, identifier: str, id_type: str) -> str:
        """Normalize identifier for matching."""
        # Remove common formatting
        normalized = identifier.replace("-", "").replace(" ", "").strip().upper()

        if id_type == "ssn":
            # SSN: 9 digits only
            return "".join(c for c in normalized if c.isdigit())
        elif id_type == "ein":
            # EIN: 9 digits only
            return "".join(c for c in normalized if c.isdigit())
        elif id_type == "passport":
            # Passport: alphanumeric
            return normalized

        return normalized

    async def resolve_exact(
        self,
        identifiers: dict[str, str],
        tenant_id: UUID,
        ctx: RequestContext
    ) -> EntityMatchScore | None:
        """
        Find entity by exact match on canonical identifiers.

        Args:
            identifiers: Dict of id_type -> value (e.g., {"ssn": "123-45-6789"})
            tenant_id: Tenant ID for multi-tenant isolation
            ctx: Request context

        Returns:
            EntityMatchScore if found, None otherwise
        """
        from sqlalchemy import select, or_

        # Normalize identifiers
        normalized = {
            id_type: self.normalize_identifier(value, id_type)
            for id_type, value in identifiers.items()
        }

        # Build query for canonical identifier match
        conditions = []
        for id_type, value in normalized.items():
            # Encrypt value for comparison
            encrypted = self.encryption.encrypt(value)
            conditions.append(
                Entity.canonical_identifiers[id_type].astext == encrypted
            )

        if not conditions:
            return None

        query = select(Entity).where(
            Entity.tenant_id == tenant_id,  # Multi-tenant isolation
            or_(*conditions)
        )

        result = await self.db.execute(query)
        entity = result.scalars().first()

        if entity:
            # Determine which identifiers matched
            matched_fields = {}
            for id_type, value in normalized.items():
                stored_value = entity.canonical_identifiers.get(id_type)
                if stored_value == self.encryption.encrypt(value):
                    matched_fields[id_type] = value

            return EntityMatchScore(
                entity_id=entity.entity_id,
                match_score=1.0,  # Exact match
                match_criteria={"matched_identifiers": matched_fields},
                match_type="exact"
            )

        return None

    async def resolve_or_create(
        self,
        identifiers: dict[str, str],
        entity_type: EntityType,
        tenant_id: UUID,
        ctx: RequestContext
    ) -> Entity:
        """
        Find existing entity or create new one.

        Args:
            identifiers: Canonical identifiers (SSN, EIN, etc.)
            entity_type: INDIVIDUAL or ORGANIZATION
            tenant_id: Tenant ID
            ctx: Request context

        Returns:
            Existing or newly created Entity
        """
        # Try exact match first
        match = await self.resolve_exact(identifiers, tenant_id, ctx)
        if match:
            entity = await self.db.get(Entity, match.entity_id)
            return entity

        # No match - create new entity
        normalized = {
            id_type: self.normalize_identifier(value, id_type)
            for id_type, value in identifiers.items()
        }

        # Encrypt canonical identifiers
        encrypted_identifiers = {
            id_type: self.encryption.encrypt(value)
            for id_type, value in normalized.items()
        }

        entity = Entity(
            entity_type=entity_type,
            tenant_id=tenant_id,
            canonical_identifiers=encrypted_identifiers
        )

        self.db.add(entity)
        await self.db.flush()

        # Audit log
        await audit_logger.log_event(
            AuditEventType.ENTITY_CREATED,
            ctx,
            {"entity_type": entity_type, "match_type": "new"},
            entity_id=entity.entity_id
        )

        return entity
```

## Testing Requirements

### Unit Tests
- Identifier normalization (SSN with/without dashes)
- Exact match on SSN
- Exact match on EIN
- Multi-tenant isolation (no cross-tenant matches)
- Create new entity when no match

### Integration Tests
- resolve_or_create with existing entity
- resolve_or_create with new entity
- Concurrent entity resolution (race conditions)

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] EntityResolver resolves by SSN, EIN, passport
- [ ] Identifier normalization handles formatting
- [ ] Exact matches return score=1.0
- [ ] resolve_or_create returns existing entity if found
- [ ] New entities created with encrypted identifiers
- [ ] Multi-tenant isolation enforced
- [ ] Audit log for entity creation

## Deliverables

- `src/elile/services/entity_resolution.py`
- `tests/unit/test_entity_resolver_exact.py`
- `tests/integration/test_entity_resolution.py`

## References

- Architecture: [02-core-system.md](../architecture/02-core-system.md) - Entity resolution
- Dependencies: Task 1.1 (Entity model), Task 1.6 (encryption)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
