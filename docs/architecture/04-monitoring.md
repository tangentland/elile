# Ongoing Monitoring (Vigilance)

> **Prerequisites**: [01-design.md](01-design.md), [03-screening.md](03-screening.md)
>
> **See also**: [05-investigation.md](05-investigation.md) for risk analysis, [07-compliance.md](07-compliance.md) for compliance rules

## Vigilance Levels (Monitoring Frequency)

Controls *how often* re-screening occurs for ongoing monitoring.

| Level | Name | Frequency | Checks/Year | Use Case |
|-------|------|-----------|-------------|----------|
| **V0** | Pre-screen | One-time only | 1 | Contractors, low-risk roles |
| **V1** | Annual | Every 12 months | 1 | Standard regulated employees |
| **V2** | Monthly | Every 30 days | 12 | Elevated risk, trading, treasury |
| **V3** | Bi-monthly | Twice per month | 24 | Critical infrastructure, nuclear |

## Vigilance Monitoring Scope

```
┌─────────────────────────────────────────────────────────────────┐
│                  VIGILANCE MONITORING SCOPE                     │
├──────────┬─────────────┬────────────────────────────────────────┤
│ Level    │ Frequency   │ What's Monitored                       │
├──────────┼─────────────┼────────────────────────────────────────┤
│ V0       │ One-time    │ N/A - no ongoing monitoring            │
├──────────┼─────────────┼────────────────────────────────────────┤
│ V1       │ Annual      │ Full re-screen (same as initial)       │
├──────────┼─────────────┼────────────────────────────────────────┤
│ V2       │ Monthly     │ Criminal records, sanctions/PEP,       │
│          │             │ adverse media, regulatory actions,     │
│          │             │ civil litigation                       │
├──────────┼─────────────┼────────────────────────────────────────┤
│ V3       │ 2x/month    │ V2 checks + real-time sanctions alerts │
│          │             │ + continuous adverse media monitoring  │
│          │             │ + dark web monitoring (Enhanced only)  │
└──────────┴─────────────┴────────────────────────────────────────┘
```

## Vigilance Scheduler

Manages ongoing monitoring based on vigilance level.

```
┌─────────────────────────────────────────────────────────────────┐
│                    VIGILANCE SCHEDULER                           │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  SCHEDULE MANAGER                        │    │
│  │                                                          │    │
│  │  V0: No scheduling (one-time)                           │    │
│  │  V1: Annual cron (full re-screen)                       │    │
│  │  V2: Monthly cron (delta checks)                        │    │
│  │  V3: Bi-monthly cron + real-time hooks                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  DELTA DETECTOR                          │    │
│  │                                                          │    │
│  │  Compares current results to baseline:                  │    │
│  │  - New findings                                          │    │
│  │  - Changed findings                                      │    │
│  │  - Resolved findings                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  ALERT EVALUATOR                         │    │
│  │                                                          │    │
│  │  Determines if changes warrant alert:                   │    │
│  │  - Severity thresholds                                   │    │
│  │  - Change significance                                   │    │
│  │  - Role-based escalation rules                          │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Ongoing Monitoring Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    VIGILANCE SCHEDULER                           │
│                                                                  │
│   V1 (Annual)      V2 (Monthly)       V3 (Bi-monthly)          │
│       │                │                    │                   │
│       │                │                    │                   │
│       ▼                ▼                    ▼                   │
│   ┌───────┐        ┌───────┐           ┌───────┐               │
│   │ Full  │        │ Delta │           │ Delta │               │
│   │Re-scrn│        │ Check │           │ Check │               │
│   └───────┘        └───────┘           └───┬───┘               │
│                                             │                   │
│                                    ┌────────┴────────┐         │
│                                    ▼                 ▼         │
│                              ┌─────────┐      ┌──────────┐     │
│                              │Real-time│      │Continuous│     │
│                              │Sanctions│      │Adverse   │     │
│                              │ Alerts  │      │Media Mon.│     │
│                              └─────────┘      └──────────┘     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ Delta   │────►│  Alert  │────►│ Trigger │────►│  HRIS   │
│Detected │     │ Evaluate│     │ Review  │     │ Notify  │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
```

## Delta Detection

The delta detector compares the current monitoring check against the previous baseline to identify changes:

### Change Categories

| Category | Examples | Severity Mapping |
|----------|----------|------------------|
| **New Finding** | New arrest, new lawsuit, new sanctions match | Based on finding severity |
| **Escalation** | Civil → Criminal, misdemeanor → felony | High |
| **Status Change** | Pending → Convicted, Filed → Dismissed | Variable |
| **Resolution** | Judgment satisfied, license reinstated | Low (positive) |
| **Network Change** | New high-risk connection (D2/D3) | Based on connection risk |

### Alert Severity Thresholds

| Vigilance Level | Auto-Alert Threshold | Human Review Threshold |
|-----------------|---------------------|------------------------|
| V1 (Annual) | Critical only | High and above |
| V2 (Monthly) | High and above | Medium and above |
| V3 (Bi-monthly) | Medium and above | Low and above |

## Real-Time Monitoring (V3)

V3 vigilance includes real-time hooks for critical checks:

### Sanctions Real-Time

- Webhook subscription to sanctions providers
- Immediate notification on SDN list updates
- Automatic re-check of monitored population
- Priority alert routing

### Continuous Adverse Media

- Daily media monitoring for V3 subjects
- AI-powered relevance filtering
- Sentiment analysis for severity
- Automated false-positive reduction

### Dark Web Monitoring (Enhanced Only)

- Credential leak detection
- PII exposure alerts
- Forum mention monitoring
- Threat intelligence correlation

## Monitoring Lifecycle Events

The vigilance scheduler responds to lifecycle events from HRIS:

| Event | Action |
|-------|--------|
| **Position Change** | Re-evaluate vigilance level based on new role |
| **Promotion to Critical Role** | Escalate to higher vigilance |
| **Transfer** | Update locale, re-apply compliance rules |
| **Leave of Absence** | Pause monitoring (configurable) |
| **Termination** | Stop monitoring, trigger retention policy |
| **Rehire** | Resume monitoring with new baseline |

## Monitoring Configuration

```python
class MonitoringConfig(BaseModel):
    """Configuration for ongoing monitoring."""

    subject_id: UUID
    vigilance_level: VigilanceLevel
    service_tier: ServiceTier
    degrees: SearchDegree

    # Schedule
    start_date: date
    next_check_date: date | None

    # Baseline
    baseline_profile_id: UUID

    # Alert routing
    alert_recipients: list[str]
    escalation_path: list[str]

    # Real-time hooks (V3)
    sanctions_realtime: bool = False
    adverse_media_continuous: bool = False
    dark_web_monitoring: bool = False


class MonitoringCheck(BaseModel):
    """Record of a monitoring check execution."""

    check_id: UUID
    monitoring_config_id: UUID
    check_type: str  # "scheduled" | "triggered" | "realtime"

    # Timing
    scheduled_at: datetime
    started_at: datetime
    completed_at: datetime | None

    # Results
    status: str  # "completed" | "failed" | "partial"
    deltas_detected: list[ProfileDelta]
    alerts_generated: list[Alert]

    # Profile
    new_profile_id: UUID | None  # Created if deltas found
```

## Alert Management

```
┌─────────────────────────────────────────────────────────────────┐
│                      ALERT PIPELINE                              │
│                                                                  │
│  Monitoring Check                                                │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────┐                                            │
│  │ Delta Detected  │                                            │
│  └────────┬────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐     ┌───────────────┐                     │
│  │ Evaluate        │────►│ Below         │── (no alert)        │
│  │ Severity        │     │ Threshold?    │                     │
│  └─────────────────┘     └───────┬───────┘                     │
│                                  │ Above                        │
│                                  ▼                              │
│                          ┌───────────────┐                     │
│                          │ Create Alert  │                     │
│                          └───────┬───────┘                     │
│                                  │                              │
│              ┌───────────────────┼───────────────────┐         │
│              ▼                   ▼                   ▼         │
│       ┌───────────┐       ┌───────────┐       ┌───────────┐   │
│       │  Email    │       │  Webhook  │       │    SMS    │   │
│       │ Notify    │       │   HRIS    │       │  Urgent   │   │
│       └───────────┘       └───────────┘       └───────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Monitoring Metrics

Key metrics tracked for monitoring operations:

| Metric | Description | Target |
|--------|-------------|--------|
| Check completion rate | % of scheduled checks completed on time | >99.5% |
| Alert latency | Time from detection to notification | <15 min |
| False positive rate | Alerts dismissed without action | <10% |
| Coverage | % of active employees with monitoring | 100% |
| Delta detection accuracy | Verified changes vs. detected | >99% |

---

*See [05-investigation.md](05-investigation.md) for risk analysis and evolution signals*
*See [11-interfaces.md](11-interfaces.md) for Monitoring Console UI*
