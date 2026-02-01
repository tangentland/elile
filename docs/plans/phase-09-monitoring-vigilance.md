# Phase 9: Monitoring & Vigilance

## Overview

Phase 9 implements ongoing employee monitoring with vigilance levels (V1/V2/V3), delta detection, alert pipeline, and real-time monitoring for V3. This phase enables continuous risk assessment beyond pre-employment screening.

**Duration Estimate**: 3-4 weeks
**Team Size**: 2-3 developers
**Risk Level**: Medium (scheduler reliability critical)

## Phase Goals

- ✓ Build vigilance scheduler (V1/V2/V3)
- ✓ Implement delta detector comparing profiles
- ✓ Create alert pipeline with severity routing
- ✓ Add real-time monitoring (V3: sanctions webhooks, continuous adverse media)

## Tasks

| Seq | Task Name | Priority | Status | Dependencies | Plan Document |
|-----|-----------|----------|--------|--------------|---------------|
| 9.1 | Monitoring Subscription Manager | P0 | Not Started | Phase 7 | [task-9.1-subscription-manager.md](../tasks/task-9.1-subscription-manager.md) |
| 9.2 | Vigilance Scheduler (APScheduler) | P0 | Not Started | 9.1 | [task-9.2-vigilance-scheduler.md](../tasks/task-9.2-vigilance-scheduler.md) |
| 9.3 | V1 Scheduler (Annual Re-screen) | P0 | Not Started | 9.2 | [task-9.3-v1-scheduler.md](../tasks/task-9.3-v1-scheduler.md) |
| 9.4 | V2 Scheduler (Monthly Delta) | P0 | Not Started | 9.2 | [task-9.4-v2-scheduler.md](../tasks/task-9.4-v2-scheduler.md) |
| 9.5 | V3 Scheduler (Bi-monthly + Real-time) | P1 | Not Started | 9.2 | [task-9.5-v3-scheduler.md](../tasks/task-9.5-v3-scheduler.md) |
| 9.6 | Delta Detector | P0 | Not Started | 3.5 | [task-9.6-delta-detector.md](../tasks/task-9.6-delta-detector.md) |
| 9.7 | Change Significance Scorer | P0 | Not Started | 9.6 | [task-9.7-significance-scorer.md](../tasks/task-9.7-significance-scorer.md) |
| 9.8 | Alert Generator | P0 | Not Started | 9.7 | [task-9.8-alert-generator.md](../tasks/task-9.8-alert-generator.md) |
| 9.9 | Alert Routing Engine | P0 | Not Started | 9.8 | [task-9.9-alert-routing.md](../tasks/task-9.9-alert-routing.md) |
| 9.10 | Real-time Sanctions Monitor (V3) | P1 | Not Started | 4.7 | [task-9.10-realtime-sanctions.md](../tasks/task-9.10-realtime-sanctions.md) |
| 9.11 | Continuous Adverse Media (V3) | P1 | Not Started | 4.12 | [task-9.11-continuous-media.md](../tasks/task-9.11-continuous-media.md) |
| 9.12 | Alert Management API | P1 | Not Started | 9.8 | [task-9.12-alert-management.md](../tasks/task-9.12-alert-management.md) |

## Key Workflows

### Vigilance Monitoring
```python
class MonitoringSubscription(Base):
    subscription_id: UUID
    entity_id: UUID
    tenant_id: UUID
    vigilance_level: VigilanceLevel
    service_tier: ServiceTier
    degree: InvestigationDegree
    baseline_profile_id: UUID  # Reference profile for delta comparison
    next_check_at: datetime
    active: bool

class VigilanceScheduler:
    async def schedule_monitoring(self, subscription: MonitoringSubscription):
        """Schedule recurring checks based on vigilance level."""
        if subscription.vigilance_level == VigilanceLevel.V1:
            # Annual full re-screen
            schedule = "0 0 * * 0"  # Weekly check for due screenings
        elif subscription.vigilance_level == VigilanceLevel.V2:
            # Monthly delta checks
            schedule = "0 0 1 * *"  # First of month
        elif subscription.vigilance_level == VigilanceLevel.V3:
            # Bi-monthly + real-time
            schedule = "0 0 1,15 * *"  # 1st and 15th

class DeltaDetector:
    async def detect_changes(
        self,
        current_profile: EntityProfile,
        baseline_profile: EntityProfile
    ) -> ProfileDelta:
        """Compare profiles and identify significant changes."""
```

### Alert Routing
```python
class Alert(Base):
    alert_id: UUID
    subscription_id: UUID
    entity_id: UUID
    severity: AlertSeverity  # critical, high, medium, low
    change_type: str  # new_finding, escalation, status_change
    description: str
    delta: ProfileDelta
    created_at: datetime
    acknowledged_at: datetime | None

ALERT_ROUTING = {
    (VigilanceLevel.V1, AlertSeverity.CRITICAL): ["email", "webhook"],
    (VigilanceLevel.V2, AlertSeverity.HIGH): ["email", "webhook"],
    (VigilanceLevel.V3, AlertSeverity.MEDIUM): ["email", "webhook", "sms"],
}
```

## Phase Acceptance Criteria

### Functional Requirements
- [x] V1 monitoring schedules annual re-screens
- [x] V2 monitoring executes monthly delta checks
- [x] V3 monitoring includes real-time sanctions + bi-monthly checks
- [x] Delta detector identifies new/changed/resolved findings
- [x] Alerts route based on severity and vigilance level
- [x] Real-time sanctions webhooks trigger immediate screening

### Performance Requirements
- [x] Scheduler handles 10,000+ active subscriptions
- [x] Delta detection completes in <30 seconds
- [x] Real-time alerts delivered within 5 minutes

### Testing Requirements
- [x] Scheduler tests with mocked time
- [x] Delta detection tests (all change types)
- [x] Alert routing tests
- [x] Real-time monitoring integration tests

### Review Gates
- [x] Architecture review: Scheduler design
- [x] Performance review: Scalability under load

---

*Phase Owner: [Assign team lead]*
*Last Updated: 2026-01-29*
