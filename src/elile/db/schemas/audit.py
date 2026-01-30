"""Pydantic schemas for audit event API validation."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AuditEventCreate(BaseModel):
    """Schema for creating audit events."""

    event_type: str
    severity: str = "info"
    tenant_id: UUID | None = None
    user_id: UUID | None = None
    correlation_id: UUID
    entity_id: UUID | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    event_data: dict[str, Any]
    ip_address: str | None = None
    user_agent: str | None = None


class AuditEventResponse(BaseModel):
    """Schema for audit event API responses."""

    audit_id: UUID
    event_type: str
    severity: str
    tenant_id: UUID | None
    user_id: UUID | None
    correlation_id: UUID
    entity_id: UUID | None
    resource_type: str | None
    resource_id: str | None
    event_data: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}  # Enable SQLAlchemy model compatibility


class AuditQueryRequest(BaseModel):
    """Schema for querying audit logs."""

    tenant_id: UUID | None = None
    event_type: str | None = None
    entity_id: UUID | None = None
    correlation_id: UUID | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    severity: str | None = None
    limit: int = Field(default=100, le=1000)
    offset: int = Field(default=0, ge=0)
