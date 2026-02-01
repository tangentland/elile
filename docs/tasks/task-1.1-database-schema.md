# Task 1.1: Database Schema Foundation

## Overview

Create the core PostgreSQL database schema including tables for entities, profiles, cached data sources, and cross-screening indices. This task establishes the foundational data model that all other features depend on.

**Priority**: P0 (Critical)
**Estimated Effort**: 3-4 days
**Assignee**: [To be assigned]
**Status**: Not Started

## Dependencies

### Phase Dependencies
- None (first task in Phase 1)

### External Dependencies
- PostgreSQL 15+ installed and accessible
- SQLAlchemy 2.0+ installed
- Alembic 1.13+ installed for migrations

## Data Models

### Core SQLAlchemy Models

```python
# src/elile/models/base.py
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    """Base class for all database models."""
    pass

class TimestampMixin:
    """Mixin for created_at/updated_at timestamps."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
```

```python
# src/elile/models/entity.py
from enum import Enum
from uuid import UUID
from sqlalchemy import String, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin

class EntityType(str, Enum):
    INDIVIDUAL = "individual"
    ORGANIZATION = "organization"
    ADDRESS = "address"

class Entity(Base, TimestampMixin):
    """Core entity in the system (person, org, or address)."""
    __tablename__ = "entities"

    entity_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    entity_type: Mapped[EntityType] = mapped_column(String(50), nullable=False)

    # Canonical identifiers (SSN, EIN, etc.) - encrypted
    canonical_identifiers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Relationships
    profiles: Mapped[list["EntityProfile"]] = relationship(
        back_populates="entity",
        cascade="all, delete-orphan"
    )
    cached_sources: Mapped[list["CachedDataSource"]] = relationship(
        back_populates="entity",
        cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index('idx_entity_type', 'entity_type'),
        Index('idx_entity_created', 'created_at'),
    )

class EntityRelation(Base, TimestampMixin):
    """Relationship between two entities."""
    __tablename__ = "entity_relations"

    relation_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    from_entity_id: Mapped[UUID] = mapped_column(ForeignKey("entities.entity_id"), nullable=False)
    to_entity_id: Mapped[UUID] = mapped_column(ForeignKey("entities.entity_id"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(100), nullable=False)  # employer, household, business_partner
    confidence_score: Mapped[float] = mapped_column(nullable=False)  # 0.0 - 1.0
    discovered_in_screening: Mapped[UUID] = mapped_column(ForeignKey("entity_profiles.profile_id"), nullable=True)

    __table_args__ = (
        Index('idx_from_entity', 'from_entity_id'),
        Index('idx_to_entity', 'to_entity_id'),
        Index('idx_relation_type', 'relation_type'),
    )
```

```python
# src/elile/models/profile.py
from enum import Enum
from uuid import UUID
from sqlalchemy import String, JSON, Integer, Numeric, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin

class ProfileTrigger(str, Enum):
    SCREENING = "screening"
    MONITORING = "monitoring"
    MANUAL = "manual"

class EntityProfile(Base, TimestampMixin):
    """Versioned profile snapshot for an entity."""
    __tablename__ = "entity_profiles"

    profile_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    entity_id: Mapped[UUID] = mapped_column(ForeignKey("entities.entity_id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Trigger context
    trigger_type: Mapped[ProfileTrigger] = mapped_column(String(50), nullable=False)
    trigger_id: Mapped[UUID] = mapped_column(nullable=True)  # Screening or monitoring run ID

    # Snapshot data
    findings: Mapped[dict] = mapped_column(JSON, nullable=False)  # List of findings
    risk_score: Mapped[dict] = mapped_column(JSON, nullable=False)  # RiskScore object
    connections: Mapped[dict] = mapped_column(JSON, nullable=False)  # Connection graph
    connection_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Data sources used
    data_sources_used: Mapped[dict] = mapped_column(JSON, nullable=False)  # List of source refs
    stale_data_used: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # Flagged stale sources

    # Evolution tracking
    previous_version: Mapped[int] = mapped_column(Integer, nullable=True)
    delta: Mapped[dict] = mapped_column(JSON, nullable=True)  # ProfileDelta if comparing to previous
    evolution_signals: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # Detected patterns

    # Relationships
    entity: Mapped["Entity"] = relationship(back_populates="profiles")

    __table_args__ = (
        Index('idx_profile_entity', 'entity_id'),
        Index('idx_profile_version', 'entity_id', 'version', unique=True),
        Index('idx_profile_trigger', 'trigger_type', 'trigger_id'),
        Index('idx_profile_created', 'created_at'),
    )
```

```python
# src/elile/models/cache.py
from enum import Enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from sqlalchemy import String, LargeBinary, DateTime, Numeric, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin

class DataOrigin(str, Enum):
    PAID_EXTERNAL = "paid_external"
    CUSTOMER_PROVIDED = "customer_provided"

class FreshnessStatus(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    EXPIRED = "expired"

class CachedDataSource(Base, TimestampMixin):
    """Cached data from a provider for an entity."""
    __tablename__ = "cached_data_sources"

    cache_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    entity_id: Mapped[UUID] = mapped_column(ForeignKey("entities.entity_id"), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(100), nullable=False)
    check_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # Origin (determines sharing scope)
    data_origin: Mapped[DataOrigin] = mapped_column(String(50), nullable=False)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.tenant_id"), nullable=True)  # Set if customer_provided

    # Freshness tracking
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    freshness_status: Mapped[FreshnessStatus] = mapped_column(String(50), nullable=False)
    fresh_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stale_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Data (encrypted)
    raw_response: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # Encrypted
    normalized_data: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Cost tracking
    cost_incurred: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    cost_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # Relationships
    entity: Mapped["Entity"] = relationship(back_populates="cached_sources")

    __table_args__ = (
        Index('idx_cache_entity_check', 'entity_id', 'check_type'),
        Index('idx_cache_freshness', 'freshness_status', 'fresh_until'),
        Index('idx_cache_provider', 'provider_id'),
        Index('idx_cache_customer', 'customer_id'),  # For tenant isolation
        Index('idx_cache_origin', 'data_origin'),
    )
```

### Pydantic Schemas (for API validation)

```python
# src/elile/schemas/entity.py
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal

class EntityCreate(BaseModel):
    entity_type: Literal["individual", "organization", "address"]
    canonical_identifiers: dict[str, str] = Field(default_factory=dict)

class EntityResponse(BaseModel):
    entity_id: UUID
    entity_type: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # SQLAlchemy model compatibility

class EntityProfileResponse(BaseModel):
    profile_id: UUID
    entity_id: UUID
    version: int
    trigger_type: str
    risk_score: dict
    connection_count: int
    created_at: datetime

    class Config:
        from_attributes = True
```

## Interface Contracts

### Database Configuration

```python
# src/elile/config/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from .settings import settings

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    poolclass=NullPool if settings.ENVIRONMENT == "test" else None,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db() -> AsyncSession:
    """Dependency for FastAPI to inject database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
```

### Alembic Migration Template

```python
# migrations/versions/001_initial_schema.py
"""Initial database schema

Revision ID: 001
Revises:
Create Date: 2026-01-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create entities table
    op.create_table(
        'entities',
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('canonical_identifiers', postgresql.JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('idx_entity_type', 'entities', ['entity_type'])
    op.create_index('idx_entity_created', 'entities', ['created_at'])

    # Create entity_profiles table
    op.create_table(
        'entity_profiles',
        sa.Column('profile_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.Integer, nullable=False),
        sa.Column('trigger_type', sa.String(50), nullable=False),
        sa.Column('trigger_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('findings', postgresql.JSONB, nullable=False),
        sa.Column('risk_score', postgresql.JSONB, nullable=False),
        sa.Column('connections', postgresql.JSONB, nullable=False),
        sa.Column('connection_count', sa.Integer, nullable=False),
        sa.Column('data_sources_used', postgresql.JSONB, nullable=False),
        sa.Column('stale_data_used', postgresql.JSONB, nullable=False),
        sa.Column('previous_version', sa.Integer, nullable=True),
        sa.Column('delta', postgresql.JSONB, nullable=True),
        sa.Column('evolution_signals', postgresql.JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.entity_id'], ondelete='CASCADE'),
    )
    op.create_index('idx_profile_entity', 'entity_profiles', ['entity_id'])
    op.create_index('idx_profile_version', 'entity_profiles', ['entity_id', 'version'], unique=True)

    # Create cached_data_sources table
    op.create_table(
        'cached_data_sources',
        sa.Column('cache_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider_id', sa.String(100), nullable=False),
        sa.Column('check_type', sa.String(100), nullable=False),
        sa.Column('data_origin', sa.String(50), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('acquired_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('freshness_status', sa.String(50), nullable=False),
        sa.Column('fresh_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('stale_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('raw_response', sa.LargeBinary, nullable=False),
        sa.Column('normalized_data', postgresql.JSONB, nullable=False),
        sa.Column('cost_incurred', sa.Numeric(10, 2), nullable=False),
        sa.Column('cost_currency', sa.String(3), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.entity_id'], ondelete='CASCADE'),
    )
    op.create_index('idx_cache_entity_check', 'cached_data_sources', ['entity_id', 'check_type'])
    op.create_index('idx_cache_freshness', 'cached_data_sources', ['freshness_status', 'fresh_until'])

    # Create entity_relations table
    op.create_table(
        'entity_relations',
        sa.Column('relation_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('from_entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('to_entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('relation_type', sa.String(100), nullable=False),
        sa.Column('confidence_score', sa.Float, nullable=False),
        sa.Column('discovered_in_screening', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['from_entity_id'], ['entities.entity_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['to_entity_id'], ['entities.entity_id'], ondelete='CASCADE'),
    )
    op.create_index('idx_from_entity', 'entity_relations', ['from_entity_id'])
    op.create_index('idx_to_entity', 'entity_relations', ['to_entity_id'])

def downgrade() -> None:
    op.drop_table('entity_relations')
    op.drop_table('cached_data_sources')
    op.drop_table('entity_profiles')
    op.drop_table('entities')
```

## Implementation Steps

### Step 1: Set up SQLAlchemy Base Models (1 day)
1. Create `src/elile/models/base.py` with `Base` and `TimestampMixin`
2. Create `src/elile/models/__init__.py` to export all models
3. Write unit tests for base model behavior

### Step 2: Implement Entity Models (1 day)
1. Create `src/elile/models/entity.py` with `Entity` and `EntityRelation`
2. Add proper indexes and foreign key constraints
3. Write unit tests for entity creation and relationships

### Step 3: Implement Profile Models (1 day)
1. Create `src/elile/models/profile.py` with `EntityProfile`
2. Add version tracking and delta computation logic
3. Write unit tests for profile versioning

### Step 4: Implement Cache Models (1 day)
1. Create `src/elile/models/cache.py` with `CachedDataSource`
2. Add freshness status tracking
3. Write unit tests for cache behavior

### Step 5: Create Alembic Migration (0.5 days)
1. Initialize Alembic: `alembic init migrations`
2. Configure `migrations/env.py` to use async engine
3. Create initial migration: `alembic revision --autogenerate -m "Initial schema"`
4. Review and adjust migration file
5. Test migration: `alembic upgrade head`
6. Test rollback: `alembic downgrade -1`

### Step 6: Database Configuration (0.5 days)
1. Create `src/elile/config/database.py` with async engine setup
2. Implement `get_db()` dependency for FastAPI
3. Add connection pooling configuration

### Step 7: Integration Testing (1 day)
1. Write integration tests for database operations
2. Test concurrent access patterns
3. Test foreign key cascades
4. Performance test: 10,000 entity inserts

## Testing Requirements

### Unit Tests (80%+ coverage)

```python
# tests/unit/test_entity_model.py
import pytest
from uuid import uuid4
from src.elile.models.entity import Entity, EntityType

def test_entity_creation():
    entity = Entity(
        entity_id=uuid4(),
        entity_type=EntityType.INDIVIDUAL,
        canonical_identifiers={"ssn": "encrypted_value"}
    )
    assert entity.entity_type == EntityType.INDIVIDUAL
    assert "ssn" in entity.canonical_identifiers

def test_entity_timestamps():
    entity = Entity(entity_type=EntityType.INDIVIDUAL)
    assert entity.created_at is not None
    assert entity.updated_at is not None
```

### Integration Tests

```python
# tests/integration/test_database.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.elile.models.entity import Entity, EntityType
from src.elile.models.profile import EntityProfile, ProfileTrigger

@pytest.mark.asyncio
async def test_create_entity_with_profile(db_session: AsyncSession):
    # Create entity
    entity = Entity(entity_type=EntityType.INDIVIDUAL)
    db_session.add(entity)
    await db_session.flush()

    # Create profile
    profile = EntityProfile(
        entity_id=entity.entity_id,
        version=1,
        trigger_type=ProfileTrigger.SCREENING,
        findings=[],
        risk_score={"overall": 0.1},
        connections=[],
        connection_count=0,
        data_sources_used=[],
        stale_data_used=[]
    )
    db_session.add(profile)
    await db_session.commit()

    # Verify relationship
    assert len(entity.profiles) == 1
    assert entity.profiles[0].version == 1

@pytest.mark.asyncio
async def test_cascade_delete(db_session: AsyncSession):
    # Create entity with profile
    entity = Entity(entity_type=EntityType.INDIVIDUAL)
    profile = EntityProfile(
        entity=entity,
        version=1,
        trigger_type=ProfileTrigger.SCREENING,
        findings=[],
        risk_score={},
        connections=[],
        connection_count=0,
        data_sources_used=[],
        stale_data_used=[]
    )
    db_session.add(entity)
    await db_session.commit()

    # Delete entity
    await db_session.delete(entity)
    await db_session.commit()

    # Verify profile deleted (cascade)
    result = await db_session.get(EntityProfile, profile.profile_id)
    assert result is None
```

### Edge Cases

1. **Duplicate entity prevention**: Test unique constraints
2. **Version conflicts**: Test concurrent profile creation for same entity
3. **Null foreign keys**: Test optional relationships
4. **Large JSON fields**: Test profile with 1000+ findings
5. **Cascade deletes**: Verify all child records deleted

## Acceptance Criteria

### Functional Requirements
- [ ] All 4 core tables created (entities, entity_profiles, cached_data_sources, entity_relations)
- [ ] Proper foreign key constraints with CASCADE delete
- [ ] Indexes on frequently queried columns (entity_id, check_type, freshness_status)
- [ ] Enum types properly mapped (EntityType, FreshnessStatus, etc.)
- [ ] Timestamp columns auto-populate on insert/update
- [ ] JSON columns support nested structures
- [ ] Alembic migrations work forward and backward

### Data Integrity
- [ ] Cannot create profile for non-existent entity (FK constraint)
- [ ] Cannot create duplicate entity_id (PK constraint)
- [ ] Profile version increments correctly
- [ ] Deleting entity cascades to profiles and cache

### Performance
- [ ] Can insert 10,000 entities in <10 seconds
- [ ] Entity lookup by entity_id in <5ms
- [ ] Profile version lookup uses index (EXPLAIN shows index scan)
- [ ] Cache queries filtered by entity_id + check_type use composite index

### Testing
- [ ] Unit test coverage ≥80%
- [ ] All integration tests passing
- [ ] Migration tested on fresh database
- [ ] Rollback migration tested

### Documentation
- [ ] ERD diagram created showing all relationships
- [ ] All models have docstrings
- [ ] Migration includes descriptive comment
- [ ] README updated with database setup instructions

## Review Sign-offs

- [ ] **Code Review**: Senior developer reviews models and migration
- [ ] **Architecture Review**: Schema design validated against 02-core-system.md
- [ ] **Security Review**: No sensitive data stored unencrypted (except encrypted fields)

## Deliverables

1. **Source Files**:
   - `src/elile/models/base.py`
   - `src/elile/models/entity.py`
   - `src/elile/models/profile.py`
   - `src/elile/models/cache.py`
   - `src/elile/config/database.py`
   - `migrations/versions/001_initial_schema.py`

2. **Test Files**:
   - `tests/unit/test_entity_model.py`
   - `tests/unit/test_profile_model.py`
   - `tests/integration/test_database.py`

3. **Documentation**:
   - ERD diagram (PNG/SVG)
   - Database setup guide (README.md section)

## Verification Steps

After implementation, verify:

```bash
# 1. Run migrations
alembic upgrade head

# 2. Verify tables created
psql -d elile_dev -c "\dt"
# Should show: entities, entity_profiles, cached_data_sources, entity_relations

# 3. Verify indexes
psql -d elile_dev -c "\d entities"
# Should show indexes: idx_entity_type, idx_entity_created

# 4. Run tests
pytest tests/unit/test_entity_model.py -v
pytest tests/integration/test_database.py -v

# 5. Check coverage
pytest --cov=src/elile/models --cov-report=term-missing
# Should show ≥80% coverage
```

## Notes

- **Encryption**: The `canonical_identifiers` and `raw_response` fields store encrypted data. Task 1.6 (Encryption Utilities) must implement encrypt/decrypt functions.
- **Tenant Isolation**: The `customer_id` field in `cached_data_sources` is used by Task 1.4 (Multi-Tenancy) for tenant filtering.
- **Audit Trail**: Entity creation/modification events are logged by Task 1.2 (Audit Logging).

---

*Task Owner: [To be assigned]*
*Created: 2026-01-29*
*Last Updated: 2026-01-29*
