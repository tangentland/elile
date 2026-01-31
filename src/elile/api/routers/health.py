"""Health check endpoints."""

import time
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from elile.api.schemas.health import (
    ComponentHealth,
    HealthDetailResponse,
    HealthResponse,
    HealthStatus,
)
from elile.db.dependencies import get_db

router = APIRouter(tags=["health"])

# Application version - should come from package metadata in production
APP_VERSION = "0.1.0"


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Basic health check",
    description="Returns basic liveness status. No authentication required.",
)
async def health_check() -> HealthResponse:
    """Basic liveness check endpoint.

    Returns 200 if the application is running, regardless of
    dependency health. Use /health/ready for full readiness check.
    """
    return HealthResponse(
        status=HealthStatus.HEALTHY,
        version=APP_VERSION,
        timestamp=datetime.now(UTC),
    )


@router.get(
    "/health/db",
    response_model=HealthDetailResponse,
    summary="Database health check",
    description="Checks database connectivity. No authentication required.",
)
async def health_db(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HealthDetailResponse:
    """Database connectivity check.

    Executes a simple query to verify database connection.
    Returns detailed status including latency.
    """
    # Check database
    db_health = await _check_database(db)

    # Determine overall status
    overall_status = db_health.status

    return HealthDetailResponse(
        status=overall_status,
        version=APP_VERSION,
        timestamp=datetime.now(UTC),
        database=db_health,
        redis=None,
        details=None,
    )


@router.get(
    "/health/ready",
    response_model=HealthDetailResponse,
    summary="Full readiness check",
    description="Checks all dependencies for readiness. No authentication required.",
)
async def health_ready(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HealthDetailResponse:
    """Full readiness check endpoint.

    Verifies all dependencies are healthy and the application
    is ready to accept traffic. Use this for Kubernetes readiness probes.
    """
    # Check all components
    db_health = await _check_database(db)
    redis_health = await _check_redis()

    # Determine overall status
    overall_status = _aggregate_health([db_health, redis_health])

    # Gather additional details
    details = {
        "checks_performed": ["database", "redis"],
    }

    return HealthDetailResponse(
        status=overall_status,
        version=APP_VERSION,
        timestamp=datetime.now(UTC),
        database=db_health,
        redis=redis_health,
        details=details,
    )


async def _check_database(db: AsyncSession) -> ComponentHealth:
    """Check database connectivity.

    Args:
        db: Database session

    Returns:
        ComponentHealth with database status
    """
    start = time.perf_counter()
    try:
        # Execute simple query
        await db.execute(text("SELECT 1"))
        latency_ms = (time.perf_counter() - start) * 1000

        return ComponentHealth(
            status=HealthStatus.HEALTHY,
            message="Database connection successful",
            latency_ms=round(latency_ms, 2),
        )
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            message=f"Database connection failed: {str(e)[:100]}",
            latency_ms=round(latency_ms, 2),
        )


async def _check_redis() -> ComponentHealth:
    """Check Redis connectivity.

    Returns:
        ComponentHealth with Redis status, or None if Redis not configured
    """
    try:
        from elile.config.settings import get_settings
        settings = get_settings()

        if not settings.REDIS_URL:
            return ComponentHealth(
                status=HealthStatus.HEALTHY,
                message="Redis not configured (optional)",
                latency_ms=None,
            )

        # TODO: Implement actual Redis check when Redis is set up
        # For now, return healthy if URL is configured
        return ComponentHealth(
            status=HealthStatus.HEALTHY,
            message="Redis configured (check not implemented)",
            latency_ms=None,
        )
    except Exception as e:
        return ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            message=f"Redis check failed: {str(e)[:100]}",
            latency_ms=None,
        )


def _aggregate_health(components: list[ComponentHealth | None]) -> HealthStatus:
    """Aggregate component health into overall status.

    Args:
        components: List of component health statuses

    Returns:
        Overall health status:
        - UNHEALTHY if any required component is unhealthy
        - DEGRADED if any component is degraded
        - HEALTHY otherwise
    """
    statuses = [c.status for c in components if c is not None]

    if any(s == HealthStatus.UNHEALTHY for s in statuses):
        return HealthStatus.UNHEALTHY

    if any(s == HealthStatus.DEGRADED for s in statuses):
        return HealthStatus.DEGRADED

    return HealthStatus.HEALTHY
