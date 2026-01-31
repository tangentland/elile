"""Integration tests for database operations."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid7

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from elile.db.models.cache import CachedDataSource, DataOrigin, FreshnessStatus
from elile.db.models.entity import Entity, EntityRelation, EntityType
from elile.db.models.profile import EntityProfile, ProfileTrigger


@pytest.mark.asyncio
async def test_create_entity(db_session: AsyncSession):
    """Test creating an entity in the database."""
    entity = Entity(entity_type=EntityType.INDIVIDUAL, canonical_identifiers={"ssn": "encrypted"})
    db_session.add(entity)
    await db_session.commit()

    # Verify entity was created
    result = await db_session.get(Entity, entity.entity_id)
    assert result is not None
    assert result.entity_type == EntityType.INDIVIDUAL
    assert result.created_at is not None


@pytest.mark.asyncio
async def test_create_entity_with_profile(db_session: AsyncSession):
    """Test creating an entity with a profile."""
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
        stale_data_used={},
    )
    db_session.add(profile)
    await db_session.commit()

    # Verify relationship using explicit query
    stmt = select(EntityProfile).where(EntityProfile.entity_id == entity.entity_id)
    result = await db_session.execute(stmt)
    profiles = result.scalars().all()
    assert len(profiles) == 1
    assert profiles[0].version == 1


@pytest.mark.asyncio
async def test_cascade_delete(db_session: AsyncSession):
    """Test cascade delete of entity deletes profiles."""
    # Create entity with profile
    entity = Entity(entity_type=EntityType.INDIVIDUAL)
    db_session.add(entity)
    await db_session.flush()

    profile = EntityProfile(
        entity_id=entity.entity_id,
        version=1,
        trigger_type=ProfileTrigger.SCREENING,
        findings=[],
        risk_score={},
        connections=[],
        connection_count=0,
        data_sources_used=[],
        stale_data_used={},
    )
    db_session.add(profile)
    await db_session.commit()

    profile_id = profile.profile_id

    # Delete entity
    await db_session.delete(entity)
    await db_session.commit()

    # Verify profile deleted (cascade)
    result = await db_session.get(EntityProfile, profile_id)
    assert result is None


@pytest.mark.asyncio
async def test_entity_relations(db_session: AsyncSession):
    """Test creating relationships between entities."""
    # Create two entities
    entity1 = Entity(entity_type=EntityType.INDIVIDUAL)
    entity2 = Entity(entity_type=EntityType.ORGANIZATION)
    db_session.add_all([entity1, entity2])
    await db_session.flush()

    # Create relation
    relation = EntityRelation(
        from_entity_id=entity1.entity_id,
        to_entity_id=entity2.entity_id,
        relation_type="employer",
        confidence_score=0.95,
    )
    db_session.add(relation)
    await db_session.commit()

    # Verify relation
    result = await db_session.get(EntityRelation, relation.relation_id)
    assert result is not None
    assert result.relation_type == "employer"
    assert result.confidence_score == 0.95


@pytest.mark.asyncio
async def test_cached_data_source(db_session: AsyncSession):
    """Test creating and querying cached data sources."""
    # Create entity
    entity = Entity(entity_type=EntityType.INDIVIDUAL)
    db_session.add(entity)
    await db_session.flush()

    # Create cached data
    now = datetime.now(timezone.utc)
    cache = CachedDataSource(
        entity_id=entity.entity_id,
        provider_id="sterling",
        check_type="criminal_record",
        data_origin=DataOrigin.PAID_EXTERNAL,
        acquired_at=now,
        freshness_status=FreshnessStatus.FRESH,
        fresh_until=now + timedelta(days=30),
        stale_until=now + timedelta(days=90),
        raw_response=b"encrypted_data",
        normalized_data={"status": "clear"},
        cost_incurred=Decimal("25.00"),
        cost_currency="USD",
    )
    db_session.add(cache)
    await db_session.commit()

    # Query by entity_id and check_type
    stmt = select(CachedDataSource).where(
        CachedDataSource.entity_id == entity.entity_id,
        CachedDataSource.check_type == "criminal_record",
    )
    result = await db_session.execute(stmt)
    cached = result.scalar_one_or_none()

    assert cached is not None
    assert cached.provider_id == "sterling"
    assert cached.freshness_status == FreshnessStatus.FRESH


@pytest.mark.asyncio
async def test_profile_versioning(db_session: AsyncSession):
    """Test creating multiple versions of entity profiles."""
    # Create entity
    entity = Entity(entity_type=EntityType.INDIVIDUAL)
    db_session.add(entity)
    await db_session.flush()

    # Create version 1
    profile_v1 = EntityProfile(
        entity_id=entity.entity_id,
        version=1,
        trigger_type=ProfileTrigger.SCREENING,
        findings=[],
        risk_score={"overall": 0.1},
        connections=[],
        connection_count=0,
        data_sources_used=[],
        stale_data_used={},
    )
    db_session.add(profile_v1)
    await db_session.flush()

    # Create version 2
    profile_v2 = EntityProfile(
        entity_id=entity.entity_id,
        version=2,
        trigger_type=ProfileTrigger.MONITORING,
        findings=[{"type": "new_finding"}],
        risk_score={"overall": 0.3},
        connections=[],
        connection_count=0,
        data_sources_used=[],
        stale_data_used={},
        previous_version=1,
        delta={"risk_increase": 0.2},
    )
    db_session.add(profile_v2)
    await db_session.commit()

    # Query all versions
    stmt = (
        select(EntityProfile)
        .where(EntityProfile.entity_id == entity.entity_id)
        .order_by(EntityProfile.version)
    )
    result = await db_session.execute(stmt)
    profiles = result.scalars().all()

    assert len(profiles) == 2
    assert profiles[0].version == 1
    assert profiles[1].version == 2
    assert profiles[1].previous_version == 1


@pytest.mark.asyncio
async def test_bulk_entity_insert(db_session: AsyncSession):
    """Test inserting multiple entities efficiently."""
    # Use a unique entity type marker for test isolation
    test_marker = "bulk_test_individual"
    entities = [Entity(entity_type=test_marker) for _ in range(100)]
    db_session.add_all(entities)
    await db_session.commit()

    # Count only the entities we created (isolate from other tests by type)
    stmt = select(Entity).where(Entity.entity_type == test_marker)
    result = await db_session.execute(stmt)
    our_entities = result.scalars().all()

    assert len(our_entities) == 100
