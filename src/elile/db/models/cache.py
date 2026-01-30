"""Cached data source models for Elile database."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid7

from sqlalchemy import DateTime, ForeignKey, Index, LargeBinary, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, PortableJSON, PortableUUID, TimestampMixin


class DataOrigin(str, Enum):
    """Origin of the data source.

    Determines sharing scope:
    - PAID_EXTERNAL: Data purchased from provider, can be shared across customers
    - CUSTOMER_PROVIDED: Data provided by customer, scoped to that customer only
    """

    PAID_EXTERNAL = "paid_external"
    CUSTOMER_PROVIDED = "customer_provided"


class FreshnessStatus(str, Enum):
    """Freshness status of cached data.

    - FRESH: Data is within freshness window, can be used without warnings
    - STALE: Data is past fresh window but still usable with staleness notice
    - EXPIRED: Data is too old to use, must be refreshed
    """

    FRESH = "fresh"
    STALE = "stale"
    EXPIRED = "expired"


class CachedDataSource(Base, TimestampMixin):
    """Cached data from a provider for an entity.

    Stores responses from background check providers to minimize API calls
    and reduce costs. Tracks freshness, origin, and cost information.
    """

    __tablename__ = "cached_data_sources"

    cache_id: Mapped[UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid7)
    entity_id: Mapped[UUID] = mapped_column(
        PortableUUID(), ForeignKey("entities.entity_id", ondelete="CASCADE"), nullable=False
    )
    provider_id: Mapped[str] = mapped_column(String(100), nullable=False)
    check_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # Origin (determines sharing scope)
    data_origin: Mapped[str] = mapped_column(String(50), nullable=False)
    # FK to tenants.tenant_id will be added via migration when tenants table exists
    customer_id: Mapped[UUID | None] = mapped_column(
        PortableUUID(),
        nullable=True,  # Set if customer_provided
    )

    # Freshness tracking
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    freshness_status: Mapped[str] = mapped_column(String(50), nullable=False)
    fresh_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stale_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Data (raw_response should be encrypted by application layer)
    raw_response: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # Encrypted
    normalized_data: Mapped[dict] = mapped_column(PortableJSON(), nullable=False)

    # Cost tracking
    cost_incurred: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    cost_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # Relationships
    entity: Mapped["Entity"] = relationship("Entity", back_populates="cached_sources")

    __table_args__ = (
        Index("idx_cache_entity_check", "entity_id", "check_type"),
        Index("idx_cache_freshness", "freshness_status", "fresh_until"),
        Index("idx_cache_provider", "provider_id"),
        Index("idx_cache_customer", "customer_id"),  # For tenant isolation
        Index("idx_cache_origin", "data_origin"),
    )

    def __repr__(self) -> str:
        return (
            f"<CachedDataSource(cache_id={self.cache_id}, "
            f"entity_id={self.entity_id}, provider={self.provider_id})>"
        )
