# Task 12.19: Operations Playbook

**Priority**: P2
**Phase**: 12 - Production Readiness
**Estimated Effort**: 4 days
**Dependencies**: Task 12.9 (Monitoring), Task 12.17 (Incident Response)

## Context

Create comprehensive operations playbook covering common scenarios, troubleshooting procedures, maintenance tasks, and escalation paths.

## Objectives

1. Common scenario runbooks
2. Troubleshooting guides
3. Maintenance procedures
4. Escalation matrix
5. On-call guidelines

## Technical Approach

```markdown
# docs/operations/playbook.md

## Runbooks

### High CPU Usage

**Symptoms:**
- CPU utilization >80% sustained
- Slow API response times
- Queue backlog growing

**Investigation:**
1. Check recent deployments
2. Review application metrics
3. Analyze slow query log
4. Check for stuck processes

**Resolution:**
1. Scale up workers if needed
2. Optimize slow queries
3. Add caching where applicable

### Database Connection Exhaustion

**Symptoms:**
- "Too many connections" errors
- Connection timeout errors
- Database CPU at 100%

**Investigation:**
1. Check active connections: `SELECT * FROM pg_stat_activity`
2. Review connection pool settings
3. Look for long-running queries

**Resolution:**
1. Kill idle connections
2. Increase connection pool size
3. Optimize queries
4. Scale database if needed

### Failed Screenings

**Symptoms:**
- Screening stuck in "in_progress"
- Provider API errors
- Timeout errors

**Investigation:**
1. Check screening logs
2. Review provider status
3. Check circuit breaker state

**Resolution:**
1. Retry screening
2. Switch to backup provider
3. Manually complete if needed
```

## Implementation Checklist

- [ ] Document common scenarios
- [ ] Create troubleshooting guides
- [ ] Write maintenance procedures
- [ ] Define escalation paths
- [ ] Document on-call process

## Success Criteria

- [ ] Complete scenario coverage
- [ ] Clear procedures
- [ ] Tested runbooks
- [ ] Team trained

## Documentation Structure

```
operations/
├── runbooks/
│   ├── high-cpu.md
│   ├── database-issues.md
│   ├── provider-failures.md
│   └── monitoring-alerts.md
├── maintenance/
│   ├── database-maintenance.md
│   ├── cache-cleanup.md
│   └── log-rotation.md
├── troubleshooting/
│   ├── api-errors.md
│   ├── screening-failures.md
│   └── performance-issues.md
└── on-call/
    ├── escalation-matrix.md
    ├── shift-handoff.md
    └── incident-response.md
```

## Key Metrics to Monitor

- API response time (p50, p95, p99)
- Error rate by endpoint
- Screening completion rate
- Provider API latency
- Database connection pool usage
- Cache hit rate
- Queue depth
- Active screening count

## Common Issues and Solutions

| Issue | Symptoms | Solution |
|-------|----------|----------|
| Slow API | High latency | Check DB queries, add caching |
| Failed screenings | Timeouts | Retry logic, circuit breaker |
| Memory leak | Increasing memory | Restart workers, fix leak |
| High costs | Provider overuse | Optimize queries, use cache |

## Escalation Matrix

| Severity | Response Time | Escalation Path |
|----------|--------------|-----------------|
| P0 (Critical) | 15 minutes | On-call → Manager → CTO |
| P1 (High) | 1 hour | On-call → Team Lead |
| P2 (Medium) | 4 hours | On-call engineer |
| P3 (Low) | Next business day | Team backlog |

## Maintenance Windows

- Database backups: Daily at 2 AM UTC
- Log rotation: Weekly on Sundays
- Provider credential rotation: Quarterly
- Security patches: As needed (emergency or monthly)
- Database maintenance: Monthly on first Sunday

## Tools and Access

- Monitoring: Datadog/Grafana
- Logs: ELK Stack
- Database: PostgreSQL admin access
- Cache: Redis CLI
- Cloud: AWS Console
- CI/CD: GitHub Actions
- Alerting: PagerDuty

## Success Criteria

- [ ] All common scenarios documented
- [ ] Runbooks tested in production
- [ ] Team trained on procedures
- [ ] On-call rotation functional
- [ ] Escalation paths clear
- [ ] MTTD <5 minutes
- [ ] MTTR <30 minutes for P1 issues

## Future Enhancements

- Automated remediation for common issues
- Self-healing infrastructure
- Predictive alerting
- Automated runbook execution
