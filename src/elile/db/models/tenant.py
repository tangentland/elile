"""Tenant model for multi-tenancy support."""

from datetime import datetime
from uuid import UUID, uuid7

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, PortableUUID


class Tenant(Base):
    """Tenant (customer organization) in the system.

    Each tenant represents a customer organization using the platform.
    All data is isolated by tenant_id for multi-tenant security.
    """

    __tablename__ = "tenants"

    tenant_id: Mapped[UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Tenant(id={self.tenant_id}, name={self.name})>"
