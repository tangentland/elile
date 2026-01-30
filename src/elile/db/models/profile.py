"""Entity profile models for Elile database."""

from enum import Enum
from uuid import UUID, uuid7

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, PortableJSON, PortableUUID, TimestampMixin


class ProfileTrigger(str, Enum):
    """Type of trigger that created this profile snapshot."""

    SCREENING = "screening"
    MONITORING = "monitoring"
    MANUAL = "manual"


class EntityProfile(Base, TimestampMixin):
    """Versioned profile snapshot for an entity.

    Each profile represents a point-in-time view of an entity's risk assessment,
    including findings, connections, and risk scores. Profiles are versioned to
    track evolution over time and support comparison between investigations.
    """

    __tablename__ = "entity_profiles"

    profile_id: Mapped[UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid7)
    entity_id: Mapped[UUID] = mapped_column(
        PortableUUID(), ForeignKey("entities.entity_id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Trigger context - what created this profile
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_id: Mapped[UUID | None] = mapped_column(
        PortableUUID(), nullable=True
    )  # Screening or monitoring run ID

    # Snapshot data - findings from this investigation
    findings: Mapped[dict] = mapped_column(
        PortableJSON(), nullable=False
    )  # List of Finding objects as dicts
    risk_score: Mapped[dict] = mapped_column(PortableJSON(), nullable=False)  # RiskScore object as dict
    connections: Mapped[dict] = mapped_column(PortableJSON(), nullable=False)  # Connection graph as dict
    connection_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Data sources used in this profile
    data_sources_used: Mapped[dict] = mapped_column(
        PortableJSON(), nullable=False
    )  # List of data source references
    stale_data_used: Mapped[dict] = mapped_column(
        PortableJSON(), nullable=False, default=dict
    )  # Flagged stale sources

    # Evolution tracking - comparison to previous versions
    previous_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delta: Mapped[dict | None] = mapped_column(
        PortableJSON(), nullable=True
    )  # ProfileDelta if comparing to previous
    evolution_signals: Mapped[dict] = mapped_column(
        PortableJSON(), nullable=False, default=dict
    )  # Detected evolution patterns

    # Relationships
    entity: Mapped["Entity"] = relationship("Entity", back_populates="profiles")

    __table_args__ = (
        Index("idx_profile_entity", "entity_id"),
        Index("idx_profile_version", "entity_id", "version", unique=True),
        Index("idx_profile_trigger", "trigger_type", "trigger_id"),
        Index("idx_profile_created", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<EntityProfile(id={self.profile_id}, entity_id={self.entity_id}, "
            f"version={self.version})>"
        )
