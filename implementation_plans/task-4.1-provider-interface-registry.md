# Task 4.1: Provider Interface & Registry

## Overview
Create the data provider abstraction layer that allows consistent integration with multiple background check data sources (Sterling, Checkr, credit bureaus, court systems, etc.).

**Priority**: P0
**Status**: Complete
**Completed**: 2026-01-31
**Dependencies**: Phase 3 (Entity Management)

## Requirements

### Provider Interface
1. **DataProvider Protocol**: Contract for all providers
   - execute_check(): Execute a background check
   - health_check(): Verify provider availability
   - Provider metadata (ID, category, capabilities)

2. **Tier-Aware Routing**
   - CORE providers: Available in Standard tier
   - PREMIUM providers: Available only in Enhanced tier

3. **Cost Optimization**
   - CostTier enum for billing optimization
   - Sort providers by cost for selection

### Provider Registry
1. **Registration**: Add providers to central registry
2. **Lookup**: Find providers by check type, locale, tier
3. **Selection**: Get best provider for a check
4. **Fallback**: Get alternative providers

## Deliverables

### Types (`src/elile/providers/types.py`)
- DataSourceCategory enum (CORE, PREMIUM)
- CostTier enum (FREE, LOW, MEDIUM, HIGH, PREMIUM)
- ProviderStatus enum (HEALTHY, DEGRADED, UNHEALTHY, MAINTENANCE)
- ProviderHealth model
- ProviderResult model
- ProviderCapability model
- ProviderInfo model
- ProviderQuery model
- ProviderQueryCost model

### Protocol (`src/elile/providers/protocol.py`)
- DataProvider Protocol (interface contract)
- BaseDataProvider (base class for implementations)

### Registry (`src/elile/providers/registry.py`)
- ProviderRegistry class
- get_provider_registry() singleton accessor
- ProviderNotFoundError
- NoProviderAvailableError

## Files Created

| File | Purpose |
|------|---------|
| `src/elile/providers/__init__.py` | Package exports |
| `src/elile/providers/types.py` | Core types and enums |
| `src/elile/providers/protocol.py` | DataProvider Protocol |
| `src/elile/providers/registry.py` | ProviderRegistry class |
| `tests/unit/test_provider_registry.py` | Unit tests (48 tests) |

## Key Patterns

### Provider Registration
```python
registry = get_provider_registry()
registry.register(sterling_provider)
registry.register(checkr_provider)
```

### Provider Selection
```python
# Best provider for check
provider = registry.get_provider_for_check(
    check_type=CheckType.CRIMINAL_NATIONAL,
    locale=Locale.US,
    service_tier=ServiceTier.STANDARD,
)

# All providers for fallback
providers = registry.get_providers_for_check(
    check_type=CheckType.CRIMINAL_NATIONAL,
    healthy_only=True,
)
```

### Provider Implementation
```python
class SterlingProvider(BaseDataProvider):
    def __init__(self):
        super().__init__(ProviderInfo(
            provider_id="sterling",
            name="Sterling",
            category=DataSourceCategory.CORE,
            capabilities=[
                ProviderCapability(
                    check_type=CheckType.CRIMINAL_NATIONAL,
                    supported_locales=[Locale.US],
                    cost_tier=CostTier.MEDIUM,
                ),
            ],
        ))

    async def execute_check(self, check_type, subject, locale, **kwargs):
        # Provider-specific implementation
        ...

    async def health_check(self):
        # Check provider availability
        ...
```

## Test Results
- 48 unit tests passing
- Covers all public APIs
- Tests tier-aware selection
- Tests cost-optimized sorting
- Tests health-based filtering
