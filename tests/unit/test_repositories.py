"""Unit tests for database repositories."""
# ruff: noqa: ARG002  # Fixtures used for database setup side effects

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid7

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from elile.db.models.cache import CachedDataSource, DataOrigin, FreshnessStatus
from elile.db.models.entity import Entity, EntityType
from elile.db.models.profile import EntityProfile, ProfileTrigger
from elile.db.repositories import (
    CacheRepository,
    EntityRepository,
    ProfileRepository,
)


class TestEntityRepository:
    """Tests for EntityRepository."""

    @pytest_asyncio.fixture
    async def repo(self, db_session: AsyncSession) -> EntityRepository:
        """Create entity repository."""
        return EntityRepository(db_session)

    @pytest_asyncio.fixture
    async def test_entity(self, db_session: AsyncSession) -> Entity:
        """Create a test entity."""
        entity = Entity(
            entity_id=uuid7(),
            entity_type=EntityType.INDIVIDUAL.value,
            canonical_identifiers={"ssn_hash": "abc123"},
        )
        db_session.add(entity)
        await db_session.commit()
        await db_session.refresh(entity)
        return entity

    @pytest.mark.asyncio
    async def test_get_entity(
        self,
        repo: EntityRepository,
        test_entity: Entity,
    ):
        """Test getting entity by ID."""
        result = await repo.get(test_entity.entity_id)
        assert result is not None
        assert result.entity_id == test_entity.entity_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_entity(self, repo: EntityRepository):
        """Test getting nonexistent entity returns None."""
        result = await repo.get(uuid7())
        assert result is None

    @pytest.mark.asyncio
    async def test_create_entity(
        self,
        repo: EntityRepository,
    ):
        """Test creating entity."""
        entity = Entity(
            entity_id=uuid7(),
            entity_type=EntityType.ORGANIZATION.value,
            canonical_identifiers={"ein": "12-3456789"},
        )
        result = await repo.create(entity)
        assert result.entity_id == entity.entity_id
        assert result.entity_type == EntityType.ORGANIZATION.value

    @pytest.mark.asyncio
    async def test_delete_entity(
        self,
        repo: EntityRepository,
        test_entity: Entity,
    ):
        """Test deleting entity."""
        await repo.delete(test_entity)
        result = await repo.get(test_entity.entity_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_list_entities(
        self,
        repo: EntityRepository,
        db_session: AsyncSession,
    ):
        """Test listing entities with pagination."""
        for _ in range(5):
            entity = Entity(
                entity_id=uuid7(),
                entity_type=EntityType.INDIVIDUAL.value,
                canonical_identifiers={},
            )
            db_session.add(entity)
        await db_session.commit()

        results = await repo.list(limit=3)
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_get_by_type(
        self,
        repo: EntityRepository,
        test_entity: Entity,
    ):
        """Test getting entities by type."""
        results = await repo.get_by_type(EntityType.INDIVIDUAL)
        assert len(results) >= 1
        assert all(e.entity_type == EntityType.INDIVIDUAL.value for e in results)

    @pytest.mark.asyncio
    async def test_get_individuals(
        self,
        repo: EntityRepository,
        test_entity: Entity,
    ):
        """Test getting individual entities."""
        results = await repo.get_individuals()
        assert len(results) >= 1
        assert all(e.entity_type == EntityType.INDIVIDUAL.value for e in results)

    @pytest.mark.asyncio
    async def test_count_by_type(
        self,
        repo: EntityRepository,
        test_entity: Entity,
    ):
        """Test counting entities by type."""
        count = await repo.count_by_type(EntityType.INDIVIDUAL)
        assert count >= 1


class TestProfileRepository:
    """Tests for ProfileRepository."""

    @pytest_asyncio.fixture
    async def repo(self, db_session: AsyncSession) -> ProfileRepository:
        """Create profile repository."""
        return ProfileRepository(db_session)

    @pytest_asyncio.fixture
    async def test_entity(self, db_session: AsyncSession) -> Entity:
        """Create a test entity."""
        entity = Entity(
            entity_id=uuid7(),
            entity_type=EntityType.INDIVIDUAL.value,
            canonical_identifiers={},
        )
        db_session.add(entity)
        await db_session.commit()
        await db_session.refresh(entity)
        return entity

    @pytest_asyncio.fixture
    async def test_profile(
        self,
        db_session: AsyncSession,
        test_entity: Entity,
    ) -> EntityProfile:
        """Create a test profile."""
        profile = EntityProfile(
            profile_id=uuid7(),
            entity_id=test_entity.entity_id,
            version=1,
            trigger_type=ProfileTrigger.SCREENING.value,
            trigger_id=uuid7(),
            findings={"items": []},
            risk_score={"overall": 0.5},
            connections={"nodes": [], "edges": []},
            connection_count=0,
            data_sources_used=[],
            stale_data_used=[],
            evolution_signals={},
        )
        db_session.add(profile)
        await db_session.commit()
        await db_session.refresh(profile)
        return profile

    @pytest.mark.asyncio
    async def test_get_profile(
        self,
        repo: ProfileRepository,
        test_profile: EntityProfile,
    ):
        """Test getting profile by ID."""
        result = await repo.get(test_profile.profile_id)
        assert result is not None
        assert result.profile_id == test_profile.profile_id

    @pytest.mark.asyncio
    async def test_get_latest_profile(
        self,
        repo: ProfileRepository,
        test_entity: Entity,
        test_profile: EntityProfile,
        db_session: AsyncSession,
    ):
        """Test getting latest profile for entity."""
        # Create a newer version
        profile2 = EntityProfile(
            profile_id=uuid7(),
            entity_id=test_entity.entity_id,
            version=2,
            trigger_type=ProfileTrigger.MONITORING.value,
            findings={"items": []},
            risk_score={"overall": 0.6},
            connections={"nodes": [], "edges": []},
            connection_count=0,
            data_sources_used=[],
            stale_data_used=[],
            evolution_signals={},
        )
        db_session.add(profile2)
        await db_session.commit()

        latest = await repo.get_latest(test_entity.entity_id)
        assert latest is not None
        assert latest.version == 2

    @pytest.mark.asyncio
    async def test_get_by_version(
        self,
        repo: ProfileRepository,
        test_entity: Entity,
        test_profile: EntityProfile,
    ):
        """Test getting profile by version."""
        result = await repo.get_by_version(test_entity.entity_id, 1)
        assert result is not None
        assert result.version == 1

    @pytest.mark.asyncio
    async def test_get_next_version(
        self,
        repo: ProfileRepository,
        test_entity: Entity,
        test_profile: EntityProfile,
    ):
        """Test getting next version number."""
        next_version = await repo.get_next_version(test_entity.entity_id)
        assert next_version == 2

    @pytest.mark.asyncio
    async def test_get_screening_profiles(
        self,
        repo: ProfileRepository,
        test_profile: EntityProfile,
    ):
        """Test getting screening profiles."""
        results = await repo.get_screening_profiles()
        assert len(results) >= 1
        assert all(p.trigger_type == ProfileTrigger.SCREENING.value for p in results)

    @pytest.mark.asyncio
    async def test_get_by_trigger(
        self,
        repo: ProfileRepository,
        test_profile: EntityProfile,
    ):
        """Test getting profiles by trigger type."""
        results = await repo.get_by_trigger(ProfileTrigger.SCREENING)
        assert len(results) >= 1


class TestCacheRepository:
    """Tests for CacheRepository."""

    @pytest_asyncio.fixture
    async def repo(self, db_session: AsyncSession) -> CacheRepository:
        """Create cache repository."""
        return CacheRepository(db_session)

    @pytest_asyncio.fixture
    async def test_entity(self, db_session: AsyncSession) -> Entity:
        """Create a test entity."""
        entity = Entity(
            entity_id=uuid7(),
            entity_type=EntityType.INDIVIDUAL.value,
            canonical_identifiers={},
        )
        db_session.add(entity)
        await db_session.commit()
        await db_session.refresh(entity)
        return entity

    @pytest_asyncio.fixture
    async def test_cache_entry(
        self,
        db_session: AsyncSession,
        test_entity: Entity,
    ) -> CachedDataSource:
        """Create a test cache entry."""
        now = datetime.now(UTC)
        entry = CachedDataSource(
            cache_id=uuid7(),
            entity_id=test_entity.entity_id,
            provider_id="test_provider",
            check_type="identity_verification",
            data_origin=DataOrigin.PAID_EXTERNAL.value,
            raw_response=b"encrypted test data",
            normalized_data={"verified": True},
            freshness_status=FreshnessStatus.FRESH.value,
            acquired_at=now,
            fresh_until=now + timedelta(days=7),
            stale_until=now + timedelta(days=30),
            cost_incurred=Decimal("1.50"),
            cost_currency="USD",
        )
        db_session.add(entry)
        await db_session.commit()
        await db_session.refresh(entry)
        return entry

    @pytest.mark.asyncio
    async def test_get_cache_entry(
        self,
        repo: CacheRepository,
        test_cache_entry: CachedDataSource,
    ):
        """Test getting cache entry by ID."""
        result = await repo.get(test_cache_entry.cache_id)
        assert result is not None
        assert result.cache_id == test_cache_entry.cache_id

    @pytest.mark.asyncio
    async def test_get_by_check_type(
        self,
        repo: CacheRepository,
        test_entity: Entity,
        test_cache_entry: CachedDataSource,
    ):
        """Test getting cache entry by check type."""
        result = await repo.get_by_check_type(
            test_entity.entity_id,
            "identity_verification",
        )
        assert result is not None
        assert result.check_type == "identity_verification"

    @pytest.mark.asyncio
    async def test_get_for_entity(
        self,
        repo: CacheRepository,
        test_entity: Entity,
        test_cache_entry: CachedDataSource,
    ):
        """Test getting cache entries for entity."""
        results = await repo.get_for_entity(test_entity.entity_id)
        assert len(results) >= 1
        assert all(e.entity_id == test_entity.entity_id for e in results)

    @pytest.mark.asyncio
    async def test_mark_stale(
        self,
        repo: CacheRepository,
        test_cache_entry: CachedDataSource,
    ):
        """Test marking cache entry as stale."""
        await repo.mark_stale(test_cache_entry.cache_id)
        result = await repo.get(test_cache_entry.cache_id)
        assert result.freshness_status == FreshnessStatus.STALE.value

    @pytest.mark.asyncio
    async def test_count_by_freshness(
        self,
        repo: CacheRepository,
        test_cache_entry: CachedDataSource,
    ):
        """Test counting entries by freshness."""
        counts = await repo.count_by_freshness()
        assert counts[FreshnessStatus.FRESH] >= 1

    @pytest.mark.asyncio
    async def test_delete_for_entity(
        self,
        repo: CacheRepository,
        test_entity: Entity,
        test_cache_entry: CachedDataSource,
    ):
        """Test deleting cache entries for entity."""
        deleted = await repo.delete_for_entity(test_entity.entity_id)
        assert deleted >= 1

        results = await repo.get_for_entity(test_entity.entity_id)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_fresh_entry(
        self,
        repo: CacheRepository,
        test_entity: Entity,
        test_cache_entry: CachedDataSource,
    ):
        """Test getting fresh cache entry."""
        result = await repo.get_fresh_entry(
            test_entity.entity_id,
            "test_provider",
            "identity_verification",
        )
        assert result is not None
        assert result.freshness_status == FreshnessStatus.FRESH.value

    @pytest.mark.asyncio
    async def test_get_by_provider(
        self,
        repo: CacheRepository,
        test_cache_entry: CachedDataSource,
    ):
        """Test getting cache entries by provider."""
        results = await repo.get_by_provider("test_provider")
        assert len(results) >= 1
        assert all(e.provider_id == "test_provider" for e in results)

    @pytest.mark.asyncio
    async def test_mark_expired(
        self,
        repo: CacheRepository,
        test_cache_entry: CachedDataSource,
    ):
        """Test marking cache entry as expired."""
        await repo.mark_expired(test_cache_entry.cache_id)
        result = await repo.get(test_cache_entry.cache_id)
        assert result.freshness_status == FreshnessStatus.EXPIRED.value
