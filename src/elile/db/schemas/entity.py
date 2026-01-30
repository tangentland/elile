"""Pydantic schemas for entity models."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class EntityCreate(BaseModel):
    """Schema for creating a new entity."""

    entity_type: Literal["individual", "organization", "address"]
    canonical_identifiers: dict[str, str] = Field(default_factory=dict)


class EntityResponse(BaseModel):
    """Schema for entity API responses."""

    entity_id: UUID
    entity_type: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}  # Enable SQLAlchemy model compatibility


class EntityProfileResponse(BaseModel):
    """Schema for entity profile API responses."""

    profile_id: UUID
    entity_id: UUID
    version: int
    trigger_type: str
    risk_score: dict
    connection_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
