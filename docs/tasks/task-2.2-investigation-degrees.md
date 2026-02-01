# Task 2.2: Investigation Degree Models

## Overview

Implement D1/D2/D3 investigation degree models defining search scope (subject only, direct connections, extended network). See [03-screening.md](../architecture/03-screening.md) for degree definitions.

**Priority**: P0 | **Effort**: 1 day | **Status**: Not Started

## Dependencies

- Task 1.1: Database Schema

## Implementation Checklist

- [ ] Create InvestigationDegree enum (D1/D2/D3)
- [ ] Define degree-specific search parameters
- [ ] Build DegreeConfig with depth limits
- [ ] Implement tier compatibility validation
- [ ] Write degree model tests

## Key Implementation

```python
# src/elile/models/investigation.py
from enum import Enum
from pydantic import BaseModel

class InvestigationDegree(str, Enum):
    D1 = "d1"  # Subject only
    D2 = "d2"  # Subject + direct connections (employers, addresses, associates)
    D3 = "d3"  # Subject + extended network (2nd degree) - Enhanced tier only

class DegreeConfig(BaseModel):
    """Configuration for investigation degree."""
    degree: InvestigationDegree
    max_depth: int  # Graph traversal depth
    include_connections: bool
    connection_types: list[str]
    cost_multiplier: float
    required_tier: ServiceTier | None

DEGREE_CONFIGS = {
    InvestigationDegree.D1: DegreeConfig(
        degree=InvestigationDegree.D1,
        max_depth=0,
        include_connections=False,
        connection_types=[],
        cost_multiplier=1.0,
        required_tier=None  # Available on all tiers
    ),
    InvestigationDegree.D2: DegreeConfig(
        degree=InvestigationDegree.D2,
        max_depth=1,
        include_connections=True,
        connection_types=["employer", "address", "household", "business_partner"],
        cost_multiplier=1.8,
        required_tier=None  # Available on all tiers
    ),
    InvestigationDegree.D3: DegreeConfig(
        degree=InvestigationDegree.D3,
        max_depth=2,
        include_connections=True,
        connection_types=["employer", "address", "household", "business_partner", "associate"],
        cost_multiplier=3.0,
        required_tier=ServiceTier.ENHANCED  # Enhanced only
    )
}

def validate_degree_tier_compatibility(
    degree: InvestigationDegree,
    tier: ServiceTier
) -> bool:
    """Check if degree is compatible with tier."""
    config = DEGREE_CONFIGS[degree]
    if config.required_tier and config.required_tier != tier:
        return False
    return True
```

## Testing Requirements

### Unit Tests
- Degree enum values correct
- D1 has max_depth=0, no connections
- D2 has max_depth=1, includes connections
- D3 requires Enhanced tier
- Validation rejects D3 + Standard tier

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] InvestigationDegree enum with D1/D2/D3
- [ ] DegreeConfig defines depth and connection types
- [ ] D3 requires Enhanced tier
- [ ] Validation function prevents invalid combinations
- [ ] Cost multipliers increase with degree
- [ ] Degree configs immutable

## Deliverables

- `src/elile/models/investigation.py`
- `tests/unit/test_investigation_degrees.py`

## References

- Architecture: [03-screening.md](../architecture/03-screening.md) - Investigation degrees
- Dependencies: Task 2.1 (service tiers)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
