# Task 2.4: Service Configuration Validator

## Overview

Build validator for service configuration combinations (tier + degree + vigilance) to enforce business rules like "D3 requires Enhanced tier". Prevents invalid screening configurations.

**Priority**: P0 | **Effort**: 1 day | **Status**: Not Started

## Dependencies

- Task 2.1: Service Tiers
- Task 2.2: Investigation Degrees
- Task 2.3: Vigilance Levels

## Implementation Checklist

- [ ] Create ServiceConfig model combining tier/degree/vigilance
- [ ] Implement validation rules for combinations
- [ ] Add cost calculation based on multipliers
- [ ] Build human review level integration
- [ ] Write comprehensive validation tests

## Key Implementation

```python
# src/elile/models/config.py
from pydantic import BaseModel, field_validator, model_validator

class HumanReviewLevel(str, Enum):
    NONE = "none"           # Automated only
    FINDINGS = "findings"   # Review any findings
    ALL = "all"             # Review all screenings

class ServiceConfig(BaseModel):
    """Complete service configuration with validation."""
    tier: ServiceTier
    degree: InvestigationDegree
    vigilance: VigilanceLevel
    human_review: HumanReviewLevel = HumanReviewLevel.FINDINGS

    @model_validator(mode='after')
    def validate_combination(self):
        """Validate tier + degree + vigilance combination."""
        # D3 requires Enhanced tier
        if self.degree == InvestigationDegree.D3 and self.tier != ServiceTier.ENHANCED:
            raise ValueError("D3 investigation degree requires Enhanced service tier")

        # Enhanced tier with V0 is unusual (warn in logs, don't error)
        if self.tier == ServiceTier.ENHANCED and self.vigilance == VigilanceLevel.V0:
            logger.warning("Enhanced tier with V0 vigilance - consider V2+ for ROI")

        return self

    def calculate_cost_multiplier(self) -> float:
        """Calculate total cost multiplier from all factors."""
        tier_config = get_tier_config(self.tier)
        degree_config = DEGREE_CONFIGS[self.degree]
        vigilance_config = get_vigilance_config(self.vigilance)

        return (
            tier_config.cost_multiplier *
            degree_config.cost_multiplier *
            vigilance_config.cost_multiplier
        )

    def get_enabled_features(self) -> dict[str, bool]:
        """Get all enabled features for this configuration."""
        tier_config = get_tier_config(self.tier)
        return {
            **tier_config.features,
            "human_review": self.human_review != HumanReviewLevel.NONE,
            "ongoing_monitoring": self.vigilance != VigilanceLevel.V0
        }
```

## Testing Requirements

### Unit Tests
- Valid combinations accepted
- D3 + Standard raises ValueError
- Cost multiplier calculation correct
- Feature flags set correctly

### Integration Tests
- ServiceConfig serialization/deserialization
- Validation errors include helpful messages

**Coverage Target**: 95%+ (business logic critical)

## Acceptance Criteria

- [ ] ServiceConfig validates tier + degree + vigilance
- [ ] D3 + Standard tier raises validation error
- [ ] Cost multiplier calculation works
- [ ] Enabled features returned correctly
- [ ] Validation errors are descriptive
- [ ] All valid combinations accepted

## Deliverables

- `src/elile/models/config.py`
- `tests/unit/test_service_config.py`

## References

- Architecture: [03-screening.md](../architecture/03-screening.md) - Service configuration
- Dependencies: Tasks 2.1, 2.2, 2.3

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
