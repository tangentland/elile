# Task 4.1: Provider Gateway (Abstract Interface)

## Overview

Create abstract DataProvider interface and provider registry for all background check data sources. Establishes unified contract for provider implementations. See [06-data-sources.md](../architecture/06-data-sources.md) for provider architecture.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 1.1: Database Schema
- Task 2.8: Data Source Resolver

## Implementation Checklist

- [ ] Create abstract DataProvider base class
- [ ] Define ProviderResponse and NormalizedData models
- [ ] Build ProviderRegistry for discovery
- [ ] Implement provider health status tracking
- [ ] Add provider cost tracking interface
- [ ] Write provider interface tests

## Key Implementation

```python
# src/elile/providers/base.py
from abc import ABC, abstractmethod
from decimal import Decimal

class ProviderHealthStatus(BaseModel):
    """Health status of a provider."""
    provider_id: str
    available: bool
    last_check: datetime
    response_time_ms: float | None
    error_rate: float  # 0.0 - 1.0
    consecutive_failures: int

class ProviderResponse(BaseModel):
    """Raw response from provider."""
    provider_id: str
    check_type: str
    query_timestamp: datetime
    raw_data: dict
    records_found: int
    cost_incurred: Decimal
    response_time_ms: float
    metadata: dict = {}

class NormalizedRecord(BaseModel):
    """Standardized record format."""
    record_type: str
    severity: str | None
    description: str
    date: date | None
    source: str
    confidence: float
    raw_data: dict

class NormalizedData(BaseModel):
    """Normalized provider response."""
    check_type: str
    records: list[NormalizedRecord]
    confidence: float  # Overall confidence 0.0-1.0
    metadata: dict = {}

class DataProvider(ABC):
    """Abstract base for all data providers."""

    provider_id: str
    provider_name: str
    check_types: set[str]
    cost_per_query: Decimal
    rate_limit: int  # requests per minute
    timeout_seconds: int = 30

    @abstractmethod
    async def query(
        self,
        entity: Entity,
        check_type: str,
        ctx: RequestContext
    ) -> ProviderResponse:
        """
        Execute query against provider.

        Args:
            entity: Entity to query
            check_type: Type of check to perform
            ctx: Request context

        Returns:
            ProviderResponse with raw data

        Raises:
            ProviderError: If query fails
            RateLimitError: If rate limit exceeded
        """
        pass

    @abstractmethod
    def normalize_response(self, response: ProviderResponse) -> NormalizedData:
        """
        Convert provider-specific format to standard format.

        Args:
            response: Raw provider response

        Returns:
            NormalizedData in standard format
        """
        pass

    @abstractmethod
    async def health_check(self) -> ProviderHealthStatus:
        """Check if provider is available and responsive."""
        pass

# src/elile/providers/registry.py
class ProviderRegistry:
    """Registry of available data providers."""

    def __init__(self):
        self._providers: dict[str, DataProvider] = {}

    def register(self, provider: DataProvider):
        """Register a provider."""
        self._providers[provider.provider_id] = provider

    def get_provider(self, provider_id: str) -> DataProvider | None:
        """Get provider by ID."""
        return self._providers.get(provider_id)

    def get_providers_for_check(self, check_type: str) -> list[DataProvider]:
        """Get all providers that support a check type."""
        return [
            p for p in self._providers.values()
            if check_type in p.check_types
        ]

    async def health_check_all(self) -> dict[str, ProviderHealthStatus]:
        """Check health of all providers."""
        results = {}
        for provider_id, provider in self._providers.items():
            results[provider_id] = await provider.health_check()
        return results

# Global registry instance
provider_registry = ProviderRegistry()
```

## Testing Requirements

### Unit Tests
- Provider interface contract
- ProviderRegistry registration
- get_providers_for_check() filtering
- Health status model structure

### Integration Tests
- Multiple providers registered
- Provider lookup by ID
- Provider lookup by check_type

**Coverage Target**: 85%+

## Acceptance Criteria

- [ ] DataProvider abstract base class defined
- [ ] ProviderResponse and NormalizedData models complete
- [ ] ProviderRegistry supports registration and lookup
- [ ] health_check() interface defined
- [ ] normalize_response() interface defined
- [ ] Cost tracking interface included

## Deliverables

- `src/elile/providers/base.py`
- `src/elile/providers/registry.py`
- `tests/unit/test_provider_interface.py`

## References

- Architecture: [06-data-sources.md](../architecture/06-data-sources.md) - Provider architecture
- Dependencies: Task 1.1 (database), Task 2.8 (resolver)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
