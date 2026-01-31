"""Pydantic schemas for tenant API validation."""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# Slug validation pattern: lowercase alphanumeric with hyphens, 3-100 chars
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")


class TenantCreate(BaseModel):
    """Schema for creating a new tenant."""

    name: str = Field(..., min_length=1, max_length=255, description="Tenant display name")
    slug: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="URL-safe identifier (lowercase alphanumeric with hyphens)",
    )

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Validate slug format: lowercase alphanumeric with hyphens."""
        v = v.lower().strip()
        if not SLUG_PATTERN.match(v):
            raise ValueError(
                "Slug must be lowercase alphanumeric with hyphens, "
                "cannot start or end with hyphen"
            )
        if "--" in v:
            raise ValueError("Slug cannot contain consecutive hyphens")
        return v


class TenantUpdate(BaseModel):
    """Schema for updating an existing tenant."""

    name: str | None = Field(None, min_length=1, max_length=255, description="Tenant display name")
    slug: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="URL-safe identifier (lowercase alphanumeric with hyphens)",
    )

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        """Validate slug format if provided."""
        if v is None:
            return v
        v = v.lower().strip()
        if not SLUG_PATTERN.match(v):
            raise ValueError(
                "Slug must be lowercase alphanumeric with hyphens, "
                "cannot start or end with hyphen"
            )
        if "--" in v:
            raise ValueError("Slug cannot contain consecutive hyphens")
        return v


class TenantResponse(BaseModel):
    """Schema for tenant API responses."""

    tenant_id: UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
