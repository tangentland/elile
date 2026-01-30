"""Entity models for Elile database."""

from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class EntityType(str, Enum):
    """Type of entity in the system."""

    INDIVIDUAL = "individual"
    ORGANIZATION = "organization"
    ADDRESS = "address"


class Entity(Base, TimestampMixin):
    """Core entity in the system (person, organization, or address).

    Entities are the fundamental objects being investigated. Each entity
    has a canonical form and may have multiple profiles representing
    different points in time or investigation contexts.
    """

    __tablename__ = "entities"

    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Canonical identifiers (SSN, EIN, etc.) - should be encrypted by application layer
    canonical_identifiers: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Relationships
    profiles: Mapped[list["EntityProfile"]] = relationship(
        "EntityProfile", back_populates="entity", cascade="all, delete-orphan"
    )
    cached_sources: Mapped[list["CachedDataSource"]] = relationship(
        "CachedDataSource", back_populates="entity", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_entity_type", "entity_type"),
        Index("idx_entity_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Entity(id={self.entity_id}, type={self.entity_type})>"


class EntityRelation(Base, TimestampMixin):
    """Relationship between two entities.

    Tracks discovered connections between entities such as:
    - Employment relationships
    - Household members
    - Business partnerships
    - Family connections
    """

    __tablename__ = "entity_relations"

    relation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    from_entity_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("entities.entity_id", ondelete="CASCADE"), nullable=False
    )
    to_entity_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("entities.entity_id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # employer, household, business_partner
    confidence_score: Mapped[float] = mapped_column(
        Float, nullable=False
    )  # 0.0 - 1.0 confidence in this relation
    discovered_in_screening: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("entity_profiles.profile_id"), nullable=True
    )

    __table_args__ = (
        Index("idx_from_entity", "from_entity_id"),
        Index("idx_to_entity", "to_entity_id"),
        Index("idx_relation_type", "relation_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<EntityRelation(from={self.from_entity_id}, "
            f"to={self.to_entity_id}, type={self.relation_type})>"
        )
