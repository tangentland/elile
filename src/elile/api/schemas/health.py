"""Health check response schemas."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    """Health status indicators."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthResponse(BaseModel):
    """Basic health check response."""

    status: HealthStatus = Field(..., description="Overall health status")
    version: str = Field(..., description="Application version")
    timestamp: datetime = Field(..., description="Check timestamp")

    model_config = {"json_schema_extra": {"example": {
        "status": "healthy",
        "version": "0.1.0",
        "timestamp": "2026-01-30T12:00:00Z",
    }}}


class ComponentHealth(BaseModel):
    """Individual component health status."""

    status: HealthStatus
    message: str | None = None
    latency_ms: float | None = None


class HealthDetailResponse(HealthResponse):
    """Detailed health check response with component status."""

    database: ComponentHealth = Field(..., description="Database health")
    redis: ComponentHealth | None = Field(default=None, description="Redis health")
    details: dict[str, Any] | None = Field(
        default=None, description="Additional health details"
    )

    model_config = {"json_schema_extra": {"example": {
        "status": "healthy",
        "version": "0.1.0",
        "timestamp": "2026-01-30T12:00:00Z",
        "database": {"status": "healthy", "latency_ms": 1.5},
        "redis": {"status": "healthy", "latency_ms": 0.3},
        "details": {"active_connections": 5},
    }}}
