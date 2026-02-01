# Task 12.9: Production Monitoring and Alerting

**Priority**: P1
**Phase**: 12 - Production Readiness
**Estimated Effort**: 3 days
**Dependencies**: Task 1.11 (Structured Logging)

## Context

Implement comprehensive production monitoring and alerting with metrics collection, dashboards, and alert routing.

## Objectives

1. Metrics collection
2. Dashboard creation
3. Alert configuration
4. On-call rotation
5. Runbook integration

## Technical Approach

```python
# src/elile/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge

screening_duration = Histogram(
    'screening_duration_seconds',
    'Time to complete screening',
    ['tier', 'degree']
)

active_screenings = Gauge(
    'active_screenings',
    'Number of in-progress screenings',
    ['org_id']
)

api_requests = Counter(
    'api_requests_total',
    'Total API requests',
    ['endpoint', 'method', 'status']
)
```

## Implementation Checklist

- [ ] Set up metrics collection
- [ ] Create dashboards
- [ ] Configure alerts
- [ ] Write runbooks

## Success Criteria

- [ ] All key metrics tracked
- [ ] Alerts actionable
- [ ] <5 min MTTD
