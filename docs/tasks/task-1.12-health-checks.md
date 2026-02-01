# Task 1.12: Health Check System

**Priority**: P1
**Phase**: 1 - Foundation
**Estimated Effort**: 1 day
**Dependencies**: Task 1.3 (API Framework), Task 1.10 (Redis Cache)

## Context

Implement comprehensive health check endpoints for monitoring system availability, dependency status, and readiness for production traffic. Critical for Kubernetes liveness/readiness probes and observability.

**Architecture Reference**: [10-platform.md](../docs/architecture/10-platform.md) - Deployment
**Related**: [02-core-system.md](../docs/architecture/02-core-system.md) - System Architecture

## Objectives

1. Create health check endpoints for liveness and readiness
2. Implement dependency health checks (database, Redis, external APIs)
3. Add health check aggregation and status reporting
4. Support graceful degradation mode
5. Provide health metrics for monitoring

## Technical Approach

### Health Check Models

```python
# src/elile/health/models.py
from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel
from datetime import datetime

class HealthStatus(str, Enum):
    """Health check status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

class ComponentHealth(BaseModel):
    """Individual component health."""
    name: str
    status: HealthStatus
    message: Optional[str] = None
    latency_ms: Optional[float] = None
    last_check: datetime
    details: Dict[str, any] = {}

class SystemHealth(BaseModel):
    """Overall system health."""
    status: HealthStatus
    version: str
    uptime_seconds: float
    timestamp: datetime
    components: Dict[str, ComponentHealth]
```

### Health Checker Base

```python
# src/elile/health/checker.py
import time
from abc import ABC, abstractmethod
from datetime import datetime
from elile.health.models import ComponentHealth, HealthStatus

class HealthChecker(ABC):
    """Base class for health checkers."""

    def __init__(self, name: str, timeout: float = 5.0):
        self.name = name
        self.timeout = timeout

    @abstractmethod
    async def check(self) -> ComponentHealth:
        """Perform health check."""
        pass

    async def execute(self) -> ComponentHealth:
        """Execute health check with timing."""
        start = time.time()
        try:
            result = await self.check()
            result.latency_ms = (time.time() - start) * 1000
            result.last_check = datetime.utcnow()
            return result
        except Exception as e:
            return ComponentHealth(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                latency_ms=(time.time() - start) * 1000,
                last_check=datetime.utcnow()
            )
```

### Database Health Check

```python
# src/elile/health/checks/database.py
from sqlalchemy import text
from elile.health.checker import HealthChecker
from elile.health.models import ComponentHealth, HealthStatus
from elile.storage.database import get_session

class DatabaseHealthChecker(HealthChecker):
    """Database connectivity health check."""

    def __init__(self):
        super().__init__("database", timeout=3.0)

    async def check(self) -> ComponentHealth:
        """Check database connectivity."""
        try:
            session = next(get_session())
            result = session.execute(text("SELECT 1"))
            row = result.fetchone()

            if row and row[0] == 1:
                return ComponentHealth(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message="Database connection successful",
                    last_check=datetime.utcnow()
                )
            else:
                return ComponentHealth(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message="Unexpected database response",
                    last_check=datetime.utcnow()
                )

        except Exception as e:
            return ComponentHealth(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Database error: {str(e)}",
                last_check=datetime.utcnow()
            )
```

### Redis Health Check

```python
# src/elile/health/checks/redis.py
from elile.health.checker import HealthChecker
from elile.health.models import ComponentHealth, HealthStatus
from elile.cache.redis_client import redis_client

class RedisHealthChecker(HealthChecker):
    """Redis connectivity health check."""

    def __init__(self):
        super().__init__("redis", timeout=2.0)

    async def check(self) -> ComponentHealth:
        """Check Redis connectivity."""
        try:
            # Ping Redis
            if redis_client.client.ping():
                # Get cache info
                info = redis_client.client.info("stats")

                return ComponentHealth(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message="Redis connection successful",
                    last_check=datetime.utcnow(),
                    details={
                        "total_commands": info.get("total_commands_processed", 0),
                        "connected_clients": info.get("connected_clients", 0)
                    }
                )
            else:
                return ComponentHealth(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message="Redis ping failed",
                    last_check=datetime.utcnow()
                )

        except Exception as e:
            return ComponentHealth(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Redis error: {str(e)}",
                last_check=datetime.utcnow()
            )
```

### External API Health Check

```python
# src/elile/health/checks/external_api.py
import httpx
from elile.health.checker import HealthChecker
from elile.health.models import ComponentHealth, HealthStatus

class ExternalAPIHealthChecker(HealthChecker):
    """External API health check."""

    def __init__(self, name: str, url: str, timeout: float = 5.0):
        super().__init__(name, timeout)
        self.url = url

    async def check(self) -> ComponentHealth:
        """Check external API availability."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.url)

                if response.status_code == 200:
                    return ComponentHealth(
                        name=self.name,
                        status=HealthStatus.HEALTHY,
                        message=f"API returned {response.status_code}",
                        last_check=datetime.utcnow()
                    )
                else:
                    return ComponentHealth(
                        name=self.name,
                        status=HealthStatus.DEGRADED,
                        message=f"API returned {response.status_code}",
                        last_check=datetime.utcnow()
                    )

        except Exception as e:
            return ComponentHealth(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"API error: {str(e)}",
                last_check=datetime.utcnow()
            )
```

### Health Service

```python
# src/elile/health/service.py
import time
from typing import List, Dict
from datetime import datetime
from elile.health.checker import HealthChecker
from elile.health.models import SystemHealth, HealthStatus, ComponentHealth
from elile.health.checks.database import DatabaseHealthChecker
from elile.health.checks.redis import RedisHealthChecker
from elile.config.settings import settings

class HealthService:
    """Aggregate health check service."""

    def __init__(self):
        self.start_time = time.time()
        self.checkers: List[HealthChecker] = []

        # Register default checkers
        self.register_checker(DatabaseHealthChecker())
        self.register_checker(RedisHealthChecker())

    def register_checker(self, checker: HealthChecker) -> None:
        """Register a health checker."""
        self.checkers.append(checker)

    async def check_all(self) -> SystemHealth:
        """Run all health checks."""
        components: Dict[str, ComponentHealth] = {}

        # Execute all checks in parallel
        import asyncio
        results = await asyncio.gather(
            *[checker.execute() for checker in self.checkers],
            return_exceptions=True
        )

        # Aggregate results
        for result in results:
            if isinstance(result, ComponentHealth):
                components[result.name] = result
            else:
                # Handle exceptions
                components["unknown"] = ComponentHealth(
                    name="unknown",
                    status=HealthStatus.UNHEALTHY,
                    message=str(result),
                    last_check=datetime.utcnow()
                )

        # Determine overall status
        overall_status = self._determine_overall_status(components)

        return SystemHealth(
            status=overall_status,
            version=settings.version,
            uptime_seconds=time.time() - self.start_time,
            timestamp=datetime.utcnow(),
            components=components
        )

    def _determine_overall_status(
        self,
        components: Dict[str, ComponentHealth]
    ) -> HealthStatus:
        """Determine overall system health."""
        if not components:
            return HealthStatus.UNHEALTHY

        # Any unhealthy critical component = unhealthy
        critical_components = ["database"]
        for name in critical_components:
            if name in components and components[name].status == HealthStatus.UNHEALTHY:
                return HealthStatus.UNHEALTHY

        # Any degraded component = degraded
        if any(c.status == HealthStatus.DEGRADED for c in components.values()):
            return HealthStatus.DEGRADED

        # All healthy
        return HealthStatus.HEALTHY

# Global health service
health_service = HealthService()
```

### Health Endpoints

```python
# src/elile/api/routes/health.py
from fastapi import APIRouter, Response, status
from elile.health.service import health_service
from elile.health.models import SystemHealth, HealthStatus

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/live")
async def liveness() -> dict:
    """Liveness probe - is the application running?"""
    return {"status": "alive"}

@router.get("/ready")
async def readiness(response: Response) -> SystemHealth:
    """Readiness probe - is the application ready for traffic?"""
    health = await health_service.check_all()

    # Set appropriate HTTP status
    if health.status == HealthStatus.UNHEALTHY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif health.status == HealthStatus.DEGRADED:
        response.status_code = status.HTTP_200_OK
    else:
        response.status_code = status.HTTP_200_OK

    return health

@router.get("/status")
async def detailed_status() -> SystemHealth:
    """Detailed health status."""
    return await health_service.check_all()
```

## Implementation Checklist

### Core Infrastructure
- [ ] Create health check models
- [ ] Implement HealthChecker base class
- [ ] Create HealthService aggregator
- [ ] Add health check endpoints
- [ ] Configure Kubernetes probes

### Health Checkers
- [ ] Implement database health check
- [ ] Implement Redis health check
- [ ] Add external API health checks
- [ ] Create disk space checker
- [ ] Add memory usage checker

### Monitoring Integration
- [ ] Export health metrics
- [ ] Add health check logging
- [ ] Create health dashboards
- [ ] Configure alerting rules
- [ ] Add health trends tracking

### Testing
- [ ] Test liveness endpoint
- [ ] Test readiness endpoint
- [ ] Test unhealthy scenarios
- [ ] Test degraded mode
- [ ] Verify Kubernetes integration

## Testing Strategy

```python
# tests/health/test_health_service.py
import pytest
from elile.health.service import health_service
from elile.health.models import HealthStatus

@pytest.mark.asyncio
async def test_healthy_system():
    """Test healthy system status."""
    health = await health_service.check_all()
    assert health.status == HealthStatus.HEALTHY
    assert "database" in health.components
    assert "redis" in health.components

@pytest.mark.asyncio
async def test_unhealthy_database():
    """Test unhealthy database detection."""
    # Mock database failure
    # Verify overall status is unhealthy
    pass

@pytest.mark.asyncio
async def test_degraded_mode():
    """Test degraded mode when non-critical component fails."""
    # Mock non-critical component failure
    # Verify status is degraded, not unhealthy
    pass
```

## Success Criteria

- [ ] Liveness endpoint responds in <100ms
- [ ] Readiness endpoint checks all dependencies
- [ ] Health checks detect failures within 5 seconds
- [ ] Kubernetes probes configured correctly
- [ ] Health metrics exported to monitoring
- [ ] Degraded mode allows partial operation

## Documentation

- Document health check endpoints
- Create Kubernetes probe configuration guide
- Add troubleshooting guide for unhealthy states
- Document health check intervals and timeouts

## Future Enhancements

- Add application-specific health metrics
- Implement circuit breaker integration
- Create health prediction based on trends
- Add automated remediation triggers
