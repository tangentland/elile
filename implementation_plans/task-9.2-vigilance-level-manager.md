# Task 9.2: Vigilance Level Manager - Implementation Plan

## Overview

The Vigilance Level Manager determines and updates vigilance levels for monitored subjects based on role category and risk score. It integrates with the MonitoringScheduler to apply level changes and reschedule monitoring checks.

## Requirements

From [task-9.2-vigilance-level-manager.md](../docs/tasks/task-9.2-vigilance-level-manager.md):

1. Determine vigilance level based on role category and risk score
2. Update levels on position changes
3. Escalate for high-risk subjects
4. Reschedule checks after updates

## Files Created

| File | Purpose |
|------|---------|
| `src/elile/monitoring/vigilance_manager.py` | VigilanceManager class and related types |
| `tests/unit/test_vigilance_manager.py` | Comprehensive unit tests |

## Files Modified

| File | Changes |
|------|---------|
| `src/elile/monitoring/__init__.py` | Added exports for VigilanceManager and related types |

## Key Patterns

### Role-Based Default Vigilance Levels

```python
ROLE_DEFAULT_VIGILANCE: dict[RoleCategory, VigilanceLevel] = {
    # Critical roles - V3 (bi-monthly, 15 days)
    RoleCategory.GOVERNMENT: VigilanceLevel.V3,
    RoleCategory.SECURITY: VigilanceLevel.V3,
    # High-sensitivity roles - V2 (monthly, 30 days)
    RoleCategory.EXECUTIVE: VigilanceLevel.V2,
    RoleCategory.FINANCIAL: VigilanceLevel.V2,
    RoleCategory.HEALTHCARE: VigilanceLevel.V2,
    RoleCategory.EDUCATION: VigilanceLevel.V2,
    RoleCategory.TRANSPORTATION: VigilanceLevel.V2,
    # Standard roles - V1 (annual, 365 days)
    RoleCategory.STANDARD: VigilanceLevel.V1,
    RoleCategory.CONTRACTOR: VigilanceLevel.V1,
}
```

### Risk-Based Escalation Thresholds

```python
RISK_THRESHOLD_V3 = 75  # Critical risk - escalate to V3
RISK_THRESHOLD_V2 = 50  # High risk - at least V2
```

### VigilanceManager API

```python
manager = create_vigilance_manager(scheduler=scheduler)

# Determine level for new subject
decision = manager.determine_vigilance_level(
    role_category=RoleCategory.EXECUTIVE,
    risk_score=80,
    current_level=None,
    tenant_id=tenant_id,
)
# decision.recommended_level == VigilanceLevel.V3 (risk > 75)

# Evaluate position change
decision = manager.evaluate_position_change(
    monitoring_config=config,
    new_role_category=RoleCategory.GOVERNMENT,
    risk_score=current_risk,
)

# Apply decision
update = await manager.apply_decision(decision, config_id)
```

### Tenant-Specific Mappings

```python
# Override defaults for specific tenant
manager.set_tenant_mapping(
    tenant_id=tenant_id,
    role_category=RoleCategory.CONTRACTOR,
    vigilance_level=VigilanceLevel.V2,  # Elevated from V1
    risk_threshold_override=40,  # Lower threshold
)
```

## Implementation Details

### Classes and Types

1. **VigilanceManager** - Main class for vigilance level management
   - `determine_vigilance_level()` - Calculate appropriate level
   - `evaluate_for_escalation()` - Check if escalation needed based on risk
   - `evaluate_position_change()` - Handle job role changes
   - `update_vigilance()` - Apply level change through scheduler
   - `validate_downgrade()` - Check if downgrade is permitted

2. **VigilanceDecision** - Dataclass capturing decision details
   - Recommended level, previous level
   - Role factors, risk factors
   - Full audit trail

3. **VigilanceUpdate** - Dataclass capturing update results
   - Success/failure status
   - Rescheduling information
   - Immediate check trigger status

4. **VigilanceChangeReason** - Enum for change reasons
   - INITIAL_ASSIGNMENT, ROLE_CHANGE, RISK_ESCALATION, MANUAL_OVERRIDE, etc.

5. **ManagerConfig** - Configuration options
   - Risk thresholds (V2, V3)
   - Auto-escalation settings
   - Check triggering behavior

6. **SchedulerProtocol** - Interface for scheduler integration
   - Allows loose coupling with MonitoringScheduler

### Key Design Decisions

1. **Role-Based Defaults**: Higher-risk roles (government, security) get more frequent monitoring by default

2. **Risk Never Downgrades Automatically**: Risk escalation can upgrade vigilance, but downgrading requires explicit action and validation

3. **Tenant Customization**: Organizations can customize role mappings and risk thresholds per tenant

4. **Scheduler Protocol**: Uses Protocol for loose coupling - VigilanceManager doesn't depend directly on MonitoringScheduler

5. **Decision Audit Trail**: All decisions are captured with full context for compliance and debugging

## Test Results

```
72 tests passed
- Role default mapping tests (10)
- Get role default tests (4)
- Tenant mapping tests (3)
- Vigilance level determination tests (5)
- Risk-based escalation tests (9)
- Position change tests (4)
- Escalation evaluation tests (5)
- Downgrade validation tests (6)
- Lifecycle event creation tests (6)
- Decision history tests (5)
- Data class tests (4)
- Manager config tests (2)
- Async update tests (6)
- Factory function tests (3)
```

## Dependencies

- Task 2.3: Vigilance Levels (provides VigilanceLevel enum)
- Task 9.1: Monitoring Scheduler (provides MonitoringConfig, lifecycle event handling)

## Future Integration Points

1. **Screening Orchestrator**: Call `evaluate_for_escalation()` after screenings complete
2. **HRIS Gateway**: Use lifecycle event helpers when processing HRIS events
3. **HR Dashboard**: Expose decision history for audit/review
4. **Monitoring Scheduler**: Integration via SchedulerProtocol

---

*Completed: 2026-02-02*
*Tag: phase9/task-9.2*
