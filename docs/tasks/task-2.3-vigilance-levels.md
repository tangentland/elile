# Task 2.3: Vigilance Level Models

## Overview

Define V0/V1/V2/V3 vigilance levels for ongoing monitoring frequency (one-time, annual, monthly, bi-monthly + real-time). See [04-monitoring.md](../architecture/04-monitoring.md) for vigilance definitions.

**Priority**: P0 | **Effort**: 1 day | **Status**: Not Started

## Dependencies

- Task 1.1: Database Schema

## Implementation Checklist

- [ ] Create VigilanceLevel enum (V0/V1/V2/V3)
- [ ] Define vigilance-specific monitoring configs
- [ ] Build VigilanceConfig with schedules
- [ ] Implement monitoring check types per level
- [ ] Write vigilance model tests

## Key Implementation

```python
# src/elile/models/vigilance.py
from enum import Enum
from pydantic import BaseModel
from datetime import timedelta

class VigilanceLevel(str, Enum):
    V0 = "v0"  # Pre-screen only (no ongoing monitoring)
    V1 = "v1"  # Annual full re-screen
    V2 = "v2"  # Monthly delta checks
    V3 = "v3"  # Bi-monthly delta + real-time sanctions/adverse media

class VigilanceConfig(BaseModel):
    """Configuration for vigilance level."""
    level: VigilanceLevel
    monitoring_enabled: bool
    check_frequency: timedelta | None
    real_time_checks: list[str]  # Check types for real-time monitoring
    cost_multiplier: float
    description: str

VIGILANCE_CONFIGS = {
    VigilanceLevel.V0: VigilanceConfig(
        level=VigilanceLevel.V0,
        monitoring_enabled=False,
        check_frequency=None,
        real_time_checks=[],
        cost_multiplier=1.0,
        description="Pre-employment screening only"
    ),
    VigilanceLevel.V1: VigilanceConfig(
        level=VigilanceLevel.V1,
        monitoring_enabled=True,
        check_frequency=timedelta(days=365),
        real_time_checks=[],
        cost_multiplier=1.2,
        description="Annual full re-screening"
    ),
    VigilanceLevel.V2: VigilanceConfig(
        level=VigilanceLevel.V2,
        monitoring_enabled=True,
        check_frequency=timedelta(days=30),
        real_time_checks=[],
        cost_multiplier=1.5,
        description="Monthly delta checks"
    ),
    VigilanceLevel.V3: VigilanceConfig(
        level=VigilanceLevel.V3,
        monitoring_enabled=True,
        check_frequency=timedelta(days=15),
        real_time_checks=["sanctions", "adverse_media"],
        cost_multiplier=2.0,
        description="Bi-monthly delta + real-time critical alerts"
    )
}

def get_vigilance_config(level: VigilanceLevel) -> VigilanceConfig:
    """Get configuration for vigilance level."""
    return VIGILANCE_CONFIGS[level]
```

## Testing Requirements

### Unit Tests
- Vigilance enum values correct
- V0 has monitoring_enabled=False
- V1/V2/V3 have monitoring_enabled=True
- V3 includes real-time checks
- Check frequencies increase with level

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] VigilanceLevel enum with V0/V1/V2/V3
- [ ] VigilanceConfig includes frequency and real-time checks
- [ ] V0 disables monitoring
- [ ] V3 enables real-time sanctions/adverse media
- [ ] Cost multipliers increase with vigilance
- [ ] Vigilance configs immutable

## Deliverables

- `src/elile/models/vigilance.py`
- `tests/unit/test_vigilance_levels.py`

## References

- Architecture: [04-monitoring.md](../architecture/04-monitoring.md) - Vigilance levels
- Future: Phase 9 (monitoring implementation)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
