# Task 6.10: Configurable Risk Thresholds

**Priority**: P1
**Phase**: 6 - Risk Analysis Engine
**Estimated Effort**: 2 days
**Dependencies**: Task 6.1 (Risk Scoring)

## Context

Implement configurable risk thresholds per organization, role type, and jurisdiction to support customized risk tolerance levels.

**Architecture Reference**: [06-data-sources.md](../docs/architecture/06-data-sources.md)

## Objectives

1. Define threshold configuration model
2. Support org-level customization
3. Role-based threshold adjustment
4. Threshold breach alerting
5. Historical threshold tracking

## Technical Approach

```python
# src/elile/risk/thresholds.py
class RiskThresholdConfig(BaseModel):
    org_id: str
    role_type: Optional[str]
    thresholds: Dict[RiskLevel, int] = {
        RiskLevel.LOW: 30,
        RiskLevel.MEDIUM: 60,
        RiskLevel.HIGH: 80,
        RiskLevel.CRITICAL: 95
    }
```

## Implementation Checklist

- [ ] Create threshold models
- [ ] Add configuration API
- [ ] Implement breach detection
- [ ] Test customization

## Success Criteria

- [ ] Thresholds configurable
- [ ] Breach alerts work
