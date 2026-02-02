# Task 9.1: Monitoring Scheduler - Implementation Plan

## Overview

Implemented a monitoring scheduler for ongoing employee vigilance based on vigilance levels (V1/V2/V3). The scheduler manages periodic monitoring checks and handles employee lifecycle events.

## Requirements

1. Schedule monitoring based on vigilance level:
   - V1 = Annual (365 days)
   - V2 = Monthly (30 days)
   - V3 = Bi-monthly (15 days)
   - V0 = No monitoring (one-time only)

2. Execute scheduled checks at appropriate intervals
3. Handle lifecycle events (termination, leave, promotion, transfer)
4. Generate alerts based on severity thresholds
5. Support pause/resume/terminate operations

## Files Created/Modified

### New Files
- `src/elile/monitoring/__init__.py` - Module exports
- `src/elile/monitoring/types.py` - Types and data models
- `src/elile/monitoring/scheduler.py` - MonitoringScheduler class
- `tests/unit/test_monitoring_scheduler.py` - Unit tests (70 tests)

### Key Types
- **MonitoringConfig** - Configuration for monitoring a subject
- **MonitoringCheck** - Record of a monitoring check execution
- **ProfileDelta** - Detected change between checks
- **MonitoringAlert** - Alert generated from deltas
- **LifecycleEvent** - Employee lifecycle event
- **ScheduleResult** - Result of scheduling operation

### Key Classes
- **MonitoringScheduler** - Main scheduler class
- **SchedulerConfig** - Scheduler configuration
- **MonitoringStore** - Storage protocol
- **InMemoryMonitoringStore** - In-memory implementation for testing

## Key Patterns Used

### Vigilance Level Intervals
```python
VIGILANCE_INTERVALS = {
    VigilanceLevel.V1: timedelta(days=365),  # Annual
    VigilanceLevel.V2: timedelta(days=30),   # Monthly
    VigilanceLevel.V3: timedelta(days=15),   # Bi-monthly
}
```

### Alert Thresholds by Vigilance Level
```python
AUTO_ALERT_THRESHOLDS = {
    VigilanceLevel.V1: DeltaSeverity.CRITICAL,  # Only critical
    VigilanceLevel.V2: DeltaSeverity.HIGH,      # High and above
    VigilanceLevel.V3: DeltaSeverity.MEDIUM,    # Medium and above
}
```

### Lifecycle Event Handling
- Termination → Stops monitoring
- Leave of absence → Pauses monitoring
- Return from leave → Resumes monitoring
- Promotion/Position change → Updates role/vigilance
- Transfer → Updates locale
- Vigilance upgrade/downgrade → Updates interval

## Test Results

All 70 tests passing:
- TestVigilanceIntervals (5 tests)
- TestScheduleMonitoring (10 tests)
- TestExecuteScheduledChecks (5 tests)
- TestLifecycleEvents (10 tests)
- TestPauseResumeTerminate (7 tests)
- TestUpdateVigilanceLevel (3 tests)
- TestTriggerImmediateCheck (2 tests)
- TestGetMonitoringStatus (2 tests)
- TestAlertGeneration (4 tests)
- TestAlertThresholds (6 tests)
- TestMonitoringConfigValidation (3 tests)
- TestMonitoringCheck (5 tests)
- TestProfileDelta (1 test)
- TestLifecycleEvent (2 tests)
- TestFactoryFunction (3 tests)
- TestInMemoryStore (5 tests)

## Integration Points

- Uses `VigilanceLevel` from `elile.agent.state`
- Uses `ServiceTier`, `SearchDegree` from `elile.agent.state`
- Uses `Locale`, `RoleCategory` from `elile.compliance.types`

## Future Work

- Task 9.2: Vigilance Level Manager (depends on this task)
- Task 9.3: Delta Detector (depends on this task)
- Task 9.4: Alert Generator (depends on 9.3)
- Integration with actual screening orchestrator for delta detection
- Persistent storage implementation (database backend)

## Acceptance Criteria Met

- [x] V0 returns error for ongoing monitoring
- [x] V1/V2/V3 schedule at correct intervals
- [x] Execute scheduled checks
- [x] Update next_check_date after execution
- [x] Handle lifecycle events
- [x] Pause/resume/terminate operations
- [x] Alert generation with severity thresholds
- [x] 70 unit tests passing
- [x] Type checking passes (mypy)
- [x] Linting passes (ruff)
- [x] Formatting applied (black)
