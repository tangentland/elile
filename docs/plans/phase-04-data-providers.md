# Phase 4: Data Provider Integration

## Overview

Phase 4 implements the provider gateway abstraction, mock providers for testing, and integrations with real background check data providers. This phase enables actual data acquisition from external sources.

**Duration Estimate**: 4-6 weeks
**Team Size**: 3-4 developers
**Risk Level**: High (third-party API dependencies, cost control)

## Phase Goals

- ✓ Build provider gateway with unified interface
- ✓ Implement rate limiting and retry logic
- ✓ Create mock providers for development/testing
- ✓ Integrate core providers (T1: sanctions, criminal, employment, credit)
- ✓ Implement cost tracking and budget enforcement

## Tasks

| Seq | Task Name | Priority | Status | Dependencies | Plan Document |
|-----|-----------|----------|--------|--------------|---------------|
| 4.1 | Provider Gateway (Abstract Interface) | P0 | Not Started | 1.1, 2.8 | [task-4.1-provider-gateway.md](../tasks/task-4.1-provider-gateway.md) |
| 4.2 | Provider Health Monitor | P0 | Not Started | 4.1 | [task-4.2-provider-health.md](../tasks/task-4.2-provider-health.md) |
| 4.3 | Rate Limiter | P0 | Not Started | 1.10 | [task-4.3-rate-limiter.md](../tasks/task-4.3-rate-limiter.md) |
| 4.4 | Retry Logic (Exponential Backoff) | P0 | Not Started | 4.1 | [task-4.4-retry-logic.md](../tasks/task-4.4-retry-logic.md) |
| 4.5 | Cost Tracker | P0 | Not Started | 1.1, 1.3 | [task-4.5-cost-tracker.md](../tasks/task-4.5-cost-tracker.md) |
| 4.6 | Mock Provider Framework | P0 | Not Started | 4.1 | [task-4.6-mock-providers.md](../tasks/task-4.6-mock-providers.md) |
| 4.7 | Sanctions Provider (World-Check/OFAC) | P0 | Not Started | 4.1 | [task-4.7-sanctions-provider.md](../tasks/task-4.7-sanctions-provider.md) |
| 4.8 | Criminal Records Provider (PACER/State Courts) | P0 | Not Started | 4.1 | [task-4.8-criminal-provider.md](../tasks/task-4.8-criminal-provider.md) |
| 4.9 | Employment Verification (The Work Number) | P0 | Not Started | 4.1 | [task-4.9-employment-provider.md](../tasks/task-4.9-employment-provider.md) |
| 4.10 | Credit Bureau Provider (Experian/Equifax) | P0 | Not Started | 4.1, 2.6 | [task-4.10-credit-provider.md](../tasks/task-4.10-credit-provider.md) |
| 4.11 | Education Verification (Clearinghouse) | P1 | Not Started | 4.1 | [task-4.11-education-provider.md](../tasks/task-4.11-education-provider.md) |
| 4.12 | Adverse Media Provider (LexisNexis/Factiva) | P1 | Not Started | 4.1 | [task-4.12-adverse-media-provider.md](../tasks/task-4.12-adverse-media-provider.md) |
| 4.13 | Regulatory/License Provider (FINRA/State Boards) | P1 | Not Started | 4.1 | [task-4.13-regulatory-provider.md](../tasks/task-4.13-regulatory-provider.md) |
| 4.14 | Provider Response Normalizer | P0 | Not Started | 4.1 | [task-4.14-response-normalizer.md](../tasks/task-4.14-response-normalizer.md) |
| 4.15 | Provider Failover Logic | P1 | Not Started | 4.2 | [task-4.15-provider-failover.md](../tasks/task-4.15-provider-failover.md) |
| 4.16 | LLM Synthesis Provider | P1 | Not Started | 4.1, 4.6, 5.10 | [task-4.16-llm-synthesis-provider.md](../tasks/task-4.16-llm-synthesis-provider.md) |

## Key Interfaces

### Provider Gateway
```python
class DataProvider(ABC):
    """Abstract base for all data providers."""

    provider_id: str
    check_types: set[CheckType]
    cost_per_query: Decimal
    rate_limit: int  # requests per minute

    @abstractmethod
    async def query(self, entity: Entity, check_type: CheckType) -> ProviderResponse:
        """Execute query against provider."""

    @abstractmethod
    def normalize_response(self, raw: dict) -> NormalizedData:
        """Convert provider-specific format to standard format."""

    @abstractmethod
    async def health_check(self) -> ProviderHealthStatus:
        """Check if provider is available."""
```

### Provider Response
```python
class ProviderResponse(BaseModel):
    provider_id: str
    check_type: CheckType
    query_timestamp: datetime
    raw_data: dict
    records_found: int
    cost_incurred: Decimal
    metadata: dict  # Provider-specific metadata

class NormalizedData(BaseModel):
    """Standardized format across all providers."""
    check_type: CheckType
    records: list[NormalizedRecord]
    confidence: float
    metadata: dict
```

## Phase Acceptance Criteria

### Functional Requirements
- [x] Provider gateway supports all core check types
- [x] Rate limiting enforced per provider
- [x] Retry logic handles transient failures (3 retries with backoff)
- [x] Cost tracking updates request context
- [x] Mock providers return realistic test data
- [x] At least 4 real providers integrated (sanctions, criminal, employment, credit)

### Performance Requirements
- [x] Provider query timeout: 30 seconds
- [x] Concurrent queries: 10+ providers in parallel
- [x] Rate limiting accurate to ±5%

### Testing Requirements
- [x] Unit tests for each provider
- [x] Integration tests with mock providers
- [x] Error handling tests (timeout, 500 errors, rate limit)
- [x] Cost tracking validation

### Review Gates
- [x] Security review: API key management
- [x] Legal review: Provider contract compliance
- [x] Architecture review: Provider abstraction design

---

*Phase Owner: [Assign team lead]*
*Last Updated: 2026-01-29*
