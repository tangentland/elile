"""Provider response caching service for Elile.

This module provides caching functionality for data provider responses,
implementing cache-aside pattern with configurable freshness periods
and tenant-aware isolation.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from elile.core.encryption import Encryptor
from elile.core.logging import get_logger
from elile.db.models.cache import CachedDataSource, DataOrigin, FreshnessStatus
from elile.db.repositories.cache import CacheRepository

from .types import ProviderResult

logger = get_logger(__name__)


class CacheFreshnessConfig(BaseModel):
    """Configuration for cache freshness periods.

    Defines how long cached data remains fresh and when it becomes stale/expired.
    Different check types may have different freshness requirements.
    """

    fresh_duration: timedelta = Field(
        default=timedelta(days=7),
        description="How long data remains fresh (no warnings)",
    )
    stale_duration: timedelta = Field(
        default=timedelta(days=30),
        description="Additional time data is usable with staleness notice",
    )

    @property
    def total_usable_duration(self) -> timedelta:
        """Total time data can be used (fresh + stale)."""
        return self.fresh_duration + self.stale_duration


# Default freshness configs by check type category
DEFAULT_FRESHNESS_CONFIGS: dict[str, CacheFreshnessConfig] = {
    # Criminal records - refresh frequently due to legal importance
    "criminal": CacheFreshnessConfig(
        fresh_duration=timedelta(days=7),
        stale_duration=timedelta(days=14),
    ),
    # Credit reports - refresh monthly per FCRA
    "credit": CacheFreshnessConfig(
        fresh_duration=timedelta(days=30),
        stale_duration=timedelta(days=30),
    ),
    # Employment verification - relatively stable
    "employment": CacheFreshnessConfig(
        fresh_duration=timedelta(days=30),
        stale_duration=timedelta(days=60),
    ),
    # Education verification - very stable
    "education": CacheFreshnessConfig(
        fresh_duration=timedelta(days=90),
        stale_duration=timedelta(days=180),
    ),
    # Identity/biographical - moderately stable
    "identity": CacheFreshnessConfig(
        fresh_duration=timedelta(days=30),
        stale_duration=timedelta(days=60),
    ),
    # Default for unknown types
    "default": CacheFreshnessConfig(
        fresh_duration=timedelta(days=7),
        stale_duration=timedelta(days=30),
    ),
}


@dataclass
class CacheEntry:
    """Represents a cached provider response."""

    cache_id: UUID
    entity_id: UUID
    provider_id: str
    check_type: str
    freshness: FreshnessStatus
    acquired_at: datetime
    fresh_until: datetime
    stale_until: datetime
    normalized_data: dict[str, Any]
    cost_incurred: Decimal
    cost_currency: str
    data_origin: DataOrigin
    tenant_id: UUID | None = None

    @property
    def is_usable(self) -> bool:
        """Check if cache entry is still usable."""
        return self.freshness in (FreshnessStatus.FRESH, FreshnessStatus.STALE)

    @property
    def is_fresh(self) -> bool:
        """Check if cache entry is fresh."""
        return self.freshness == FreshnessStatus.FRESH

    @property
    def age(self) -> timedelta:
        """Get age of the cached data."""
        return datetime.now(UTC) - self.acquired_at


@dataclass
class CacheLookupResult:
    """Result of a cache lookup operation."""

    hit: bool
    entry: CacheEntry | None = None
    freshness: FreshnessStatus | None = None

    @property
    def is_fresh_hit(self) -> bool:
        """Check if this is a fresh cache hit."""
        return self.hit and self.entry is not None and self.entry.is_fresh

    @property
    def is_stale_hit(self) -> bool:
        """Check if this is a stale cache hit."""
        return (
            self.hit
            and self.entry is not None
            and self.entry.freshness == FreshnessStatus.STALE
        )


@dataclass
class CacheStats:
    """Statistics for cache operations."""

    lookups: int = 0
    hits: int = 0
    fresh_hits: int = 0
    stale_hits: int = 0
    misses: int = 0
    stores: int = 0
    invalidations: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.lookups == 0:
            return 0.0
        return self.hits / self.lookups

    @property
    def fresh_hit_rate(self) -> float:
        """Calculate fresh hit rate."""
        if self.lookups == 0:
            return 0.0
        return self.fresh_hits / self.lookups


class ProviderCacheService:
    """Service for caching provider responses.

    Provides cache-aside pattern for provider requests with:
    - Configurable freshness periods per check type
    - Tenant-aware isolation
    - Encryption of sensitive raw response data
    - Statistics tracking

    Usage:
        cache = ProviderCacheService(session)

        # Try cache first
        result = await cache.get(entity_id, provider_id, check_type)
        if result.hit and result.entry.is_usable:
            return result.entry.normalized_data

        # Cache miss - fetch from provider
        provider_result = await provider.execute_check(...)

        # Store in cache
        await cache.store(entity_id, provider_result)
    """

    def __init__(
        self,
        session: AsyncSession,
        encryptor: Encryptor | None = None,
        freshness_configs: dict[str, CacheFreshnessConfig] | None = None,
    ):
        """Initialize cache service.

        Args:
            session: Database session for repository operations.
            encryptor: Encryptor for raw response data (creates default if None).
            freshness_configs: Custom freshness configs by check type category.
        """
        self._session = session
        self._repository = CacheRepository(session)
        self._encryptor = encryptor or Encryptor()
        self._freshness_configs = freshness_configs or DEFAULT_FRESHNESS_CONFIGS
        self._stats = CacheStats()

    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats

    def _get_freshness_config(self, check_type: str) -> CacheFreshnessConfig:
        """Get freshness config for a check type.

        Args:
            check_type: The check type to get config for.

        Returns:
            CacheFreshnessConfig for the check type category.
        """
        # Map check type to category based on prefix/content
        check_lower = check_type.lower()

        if "criminal" in check_lower:
            return self._freshness_configs.get("criminal", DEFAULT_FRESHNESS_CONFIGS["criminal"])
        elif "credit" in check_lower:
            return self._freshness_configs.get("credit", DEFAULT_FRESHNESS_CONFIGS["credit"])
        elif "employment" in check_lower or "work" in check_lower:
            return self._freshness_configs.get(
                "employment", DEFAULT_FRESHNESS_CONFIGS["employment"]
            )
        elif "education" in check_lower or "degree" in check_lower:
            return self._freshness_configs.get("education", DEFAULT_FRESHNESS_CONFIGS["education"])
        elif "identity" in check_lower or "ssn" in check_lower:
            return self._freshness_configs.get("identity", DEFAULT_FRESHNESS_CONFIGS["identity"])
        else:
            return self._freshness_configs.get("default", DEFAULT_FRESHNESS_CONFIGS["default"])

    def _compute_freshness_status(
        self,
        acquired_at: datetime,
        fresh_until: datetime,
        stale_until: datetime,
    ) -> FreshnessStatus:
        """Compute current freshness status based on timestamps.

        Args:
            acquired_at: When data was acquired.
            fresh_until: When data becomes stale.
            stale_until: When data becomes expired.

        Returns:
            Current FreshnessStatus.
        """
        now = datetime.now(UTC)

        if now < fresh_until:
            return FreshnessStatus.FRESH
        elif now < stale_until:
            return FreshnessStatus.STALE
        else:
            return FreshnessStatus.EXPIRED

    def _model_to_entry(self, model: CachedDataSource) -> CacheEntry:
        """Convert database model to CacheEntry.

        Args:
            model: CachedDataSource database model.

        Returns:
            CacheEntry dataclass.
        """
        # Compute current freshness status
        freshness = self._compute_freshness_status(
            model.acquired_at,
            model.fresh_until,
            model.stale_until,
        )

        return CacheEntry(
            cache_id=model.cache_id,
            entity_id=model.entity_id,
            provider_id=model.provider_id,
            check_type=model.check_type,
            freshness=freshness,
            acquired_at=model.acquired_at,
            fresh_until=model.fresh_until,
            stale_until=model.stale_until,
            normalized_data=model.normalized_data,
            cost_incurred=model.cost_incurred,
            cost_currency=model.cost_currency,
            data_origin=DataOrigin(model.data_origin),
            tenant_id=model.customer_id,
        )

    async def get(
        self,
        entity_id: UUID,
        provider_id: str,
        check_type: str,
        *,
        tenant_id: UUID | None = None,
        include_stale: bool = True,
    ) -> CacheLookupResult:
        """Look up cached provider response.

        Args:
            entity_id: Entity the data is for.
            provider_id: Provider that produced the data.
            check_type: Type of background check.
            tenant_id: Optional tenant for isolation.
            include_stale: Whether to return stale entries.

        Returns:
            CacheLookupResult with hit status and entry if found.
        """
        self._stats.lookups += 1

        # Try to find a fresh entry first
        cached = await self._repository.get_fresh_entry(
            entity_id=entity_id,
            provider_id=provider_id,
            check_type=check_type,
        )

        if cached is not None:
            # Verify tenant isolation for customer-provided data
            if (
                cached.data_origin == DataOrigin.CUSTOMER_PROVIDED.value
                and tenant_id is not None
                and cached.customer_id != tenant_id
            ):
                # Different tenant, treat as miss
                self._stats.misses += 1
                logger.debug(
                    "cache_miss_tenant_mismatch",
                    entity_id=str(entity_id),
                    provider_id=provider_id,
                    check_type=check_type,
                )
                return CacheLookupResult(hit=False)

            entry = self._model_to_entry(cached)

            if entry.is_fresh:
                self._stats.hits += 1
                self._stats.fresh_hits += 1
                logger.debug(
                    "cache_hit_fresh",
                    entity_id=str(entity_id),
                    provider_id=provider_id,
                    check_type=check_type,
                    age_hours=entry.age.total_seconds() / 3600,
                )
                return CacheLookupResult(hit=True, entry=entry, freshness=FreshnessStatus.FRESH)

        # Try to find any usable entry if include_stale
        if include_stale:
            entries = await self._repository.get_for_entity(
                entity_id=entity_id,
                provider_id=provider_id,
                fresh_only=False,
            )

            for model in entries:
                # Verify tenant isolation
                if (
                    model.data_origin == DataOrigin.CUSTOMER_PROVIDED.value
                    and tenant_id is not None
                    and model.customer_id != tenant_id
                ):
                    continue

                entry = self._model_to_entry(model)

                if entry.freshness == FreshnessStatus.STALE:
                    self._stats.hits += 1
                    self._stats.stale_hits += 1
                    logger.debug(
                        "cache_hit_stale",
                        entity_id=str(entity_id),
                        provider_id=provider_id,
                        check_type=check_type,
                        age_days=entry.age.days,
                    )
                    return CacheLookupResult(hit=True, entry=entry, freshness=FreshnessStatus.STALE)

        self._stats.misses += 1
        logger.debug(
            "cache_miss",
            entity_id=str(entity_id),
            provider_id=provider_id,
            check_type=check_type,
        )
        return CacheLookupResult(hit=False)

    async def store(
        self,
        entity_id: UUID,
        result: ProviderResult,
        *,
        tenant_id: UUID | None = None,
        data_origin: DataOrigin = DataOrigin.PAID_EXTERNAL,
        raw_response: bytes | str | None = None,
        commit: bool = True,
    ) -> CacheEntry:
        """Store provider response in cache.

        Args:
            entity_id: Entity the data is for.
            result: Provider result to cache.
            tenant_id: Tenant for isolation (required for CUSTOMER_PROVIDED).
            data_origin: Origin of the data (determines sharing scope).
            raw_response: Raw response bytes to encrypt and store.
            commit: Whether to commit the transaction.

        Returns:
            Created CacheEntry.
        """
        now = datetime.now(UTC)
        config = self._get_freshness_config(result.check_type)

        # Calculate freshness timestamps
        fresh_until = now + config.fresh_duration
        stale_until = now + config.total_usable_duration

        # Encrypt raw response if provided
        if raw_response is not None:
            if isinstance(raw_response, str):
                raw_response = raw_response.encode("utf-8")
            encrypted_response = self._encryptor.encrypt(raw_response)
        else:
            # Store empty encrypted blob if no raw response
            encrypted_response = self._encryptor.encrypt(b"")

        # Create cache entry (store check_type as string value)
        check_type_str = (
            result.check_type.value
            if hasattr(result.check_type, "value")
            else str(result.check_type)
        )
        cached = CachedDataSource(
            entity_id=entity_id,
            provider_id=result.provider_id,
            check_type=check_type_str,
            data_origin=data_origin.value,
            customer_id=tenant_id if data_origin == DataOrigin.CUSTOMER_PROVIDED else None,
            acquired_at=now,
            freshness_status=FreshnessStatus.FRESH.value,
            fresh_until=fresh_until,
            stale_until=stale_until,
            raw_response=encrypted_response,
            normalized_data=result.normalized_data or {},
            cost_incurred=result.cost_incurred,
            cost_currency="USD",
        )

        self._session.add(cached)

        if commit:
            await self._session.commit()
            await self._session.refresh(cached)

        self._stats.stores += 1
        logger.info(
            "cache_stored",
            entity_id=str(entity_id),
            provider_id=result.provider_id,
            check_type=check_type_str,
            fresh_until=fresh_until.isoformat(),
            cost_usd=float(cached.cost_incurred),
        )

        return self._model_to_entry(cached)

    async def invalidate(
        self,
        entity_id: UUID,
        provider_id: str | None = None,
        check_type: str | None = None,
        *,
        commit: bool = True,
    ) -> int:
        """Invalidate cached entries for an entity.

        Args:
            entity_id: Entity to invalidate cache for.
            provider_id: Optional provider filter.
            check_type: Optional check type filter.
            commit: Whether to commit.

        Returns:
            Number of entries invalidated.
        """
        # Get entries to invalidate
        entries = await self._repository.get_for_entity(
            entity_id=entity_id,
            provider_id=provider_id,
        )

        count = 0
        for entry in entries:
            if check_type is not None and entry.check_type != check_type:
                continue

            await self._repository.mark_expired(entry.cache_id, commit=False)
            count += 1

        if commit and count > 0:
            await self._session.commit()

        self._stats.invalidations += count
        logger.info(
            "cache_invalidated",
            entity_id=str(entity_id),
            provider_id=provider_id,
            check_type=check_type,
            count=count,
        )

        return count

    async def get_or_fetch(
        self,
        entity_id: UUID,
        provider_id: str,
        check_type: "CheckType",
        locale: "Locale",
        fetch_fn,
        *,
        tenant_id: UUID | None = None,
        include_stale: bool = False,
        store_result: bool = True,
        data_origin: DataOrigin = DataOrigin.PAID_EXTERNAL,
    ) -> tuple[ProviderResult, bool]:
        """Get from cache or fetch from provider.

        Implements cache-aside pattern: check cache first, fetch on miss,
        optionally store result in cache.

        Args:
            entity_id: Entity the data is for.
            provider_id: Provider to fetch from.
            check_type: Type of background check.
            locale: Locale for the check.
            fetch_fn: Async function to fetch data if cache miss.
            tenant_id: Tenant for isolation.
            include_stale: Whether to accept stale cache hits.
            store_result: Whether to store fetch result in cache.
            data_origin: Origin of data if storing.

        Returns:
            Tuple of (ProviderResult, was_cached).
        """
        from elile.compliance.types import CheckType, Locale

        # Try cache first
        check_type_str = check_type.value if isinstance(check_type, CheckType) else check_type
        lookup = await self.get(
            entity_id=entity_id,
            provider_id=provider_id,
            check_type=check_type_str,
            tenant_id=tenant_id,
            include_stale=include_stale,
        )

        if lookup.hit and lookup.entry is not None and lookup.entry.is_usable:
            # Convert stored check_type string back to enum
            stored_check_type = CheckType(lookup.entry.check_type)

            # Return cached data as ProviderResult
            cached_result = ProviderResult(
                provider_id=lookup.entry.provider_id,
                check_type=stored_check_type,
                locale=locale,  # Use provided locale
                success=True,
                normalized_data=lookup.entry.normalized_data,
                cost_incurred=lookup.entry.cost_incurred,
            )
            return cached_result, True

        # Cache miss - fetch from provider
        result = await fetch_fn()

        # Store in cache if successful
        if store_result and result.success:
            await self.store(
                entity_id=entity_id,
                result=result,
                tenant_id=tenant_id,
                data_origin=data_origin,
            )

        return result, False

    async def update_freshness(self, *, commit: bool = True) -> tuple[int, int]:
        """Update freshness status for all cached entries.

        Should be run periodically to mark entries as stale/expired.

        Args:
            commit: Whether to commit.

        Returns:
            Tuple of (stale_count, expired_count).
        """
        stale_count, expired_count = await self._repository.update_freshness_batch(commit=commit)

        logger.info(
            "cache_freshness_updated",
            stale_count=stale_count,
            expired_count=expired_count,
        )

        return stale_count, expired_count

    async def cleanup_expired(
        self,
        older_than: timedelta = timedelta(days=90),
        *,
        commit: bool = True,
    ) -> int:
        """Delete old expired cache entries.

        Args:
            older_than: Only delete entries older than this.
            commit: Whether to commit.

        Returns:
            Number of entries deleted.
        """
        deleted = await self._repository.delete_expired(older_than=older_than, commit=commit)

        logger.info(
            "cache_cleanup_completed",
            deleted_count=deleted,
            older_than_days=older_than.days,
        )

        return deleted

    async def get_stats_by_freshness(
        self,
        tenant_id: UUID | None = None,
    ) -> dict[FreshnessStatus, int]:
        """Get cache entry counts by freshness status.

        Args:
            tenant_id: Optional tenant filter.

        Returns:
            Dictionary mapping FreshnessStatus to count.
        """
        return await self._repository.count_by_freshness(tenant_id=tenant_id)

    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self._stats = CacheStats()
