# Phase 7: Screening Service

## Overview

Phase 7 implements the end-to-end screening workflow that orchestrates all previous phases. This is the core service that executes screenings from request to report generation.

**Duration Estimate**: 3-4 weeks
**Team Size**: 2-3 developers
**Risk Level**: Medium (integration complexity)

## Phase Goals

- ✓ Build complete screening request handler
- ✓ Orchestrate all phases (compliance → data acquisition → investigation → risk analysis → reporting)
- ✓ Implement basic report generation (3 core report types)
- ✓ Create screening status tracking

## Tasks

| Seq | Task Name | Priority | Status | Dependencies | Plan Document |
|-----|-----------|----------|--------|--------------|---------------|
| 7.1 | Screening Request Model | P0 | Not Started | Phase 2, 3 | [task-7.1-screening-request.md](../tasks/task-7.1-screening-request.md) |
| 7.2 | Screening Orchestrator | P0 | Not Started | Phase 5, 6 | [task-7.2-screening-orchestrator.md](../tasks/task-7.2-screening-orchestrator.md) |
| 7.3 | Data Acquisition Coordinator | P0 | Not Started | Phase 4, 3.6 | [task-7.3-data-acquisition.md](../tasks/task-7.3-data-acquisition.md) |
| 7.4 | Screening Status Tracker | P0 | Not Started | 1.1 | [task-7.4-status-tracker.md](../tasks/task-7.4-status-tracker.md) |
| 7.5 | Basic Report Generator (Summary) | P0 | Not Started | 6.1 | [task-7.5-report-gen-summary.md](../tasks/task-7.5-report-gen-summary.md) |
| 7.6 | Basic Report Generator (Audit) | P0 | Not Started | 1.2, 2.6 | [task-7.6-report-gen-audit.md](../tasks/task-7.6-report-gen-audit.md) |
| 7.7 | Basic Report Generator (Disclosure) | P0 | Not Started | 2.9 | [task-7.7-report-gen-disclosure.md](../tasks/task-7.7-report-gen-disclosure.md) |
| 7.8 | Screening API Endpoints | P0 | Not Started | 7.2, 1.5 | [task-7.8-screening-api.md](../tasks/task-7.8-screening-api.md) |
| 7.9 | Async Job Queue Integration | P0 | Not Started | 1.10 | [task-7.9-job-queue.md](../tasks/task-7.9-job-queue.md) |
| 7.10 | Error Recovery & Retry | P1 | Not Started | 7.2 | [task-7.10-error-recovery.md](../tasks/task-7.10-error-recovery.md) |
| 7.11 | Screening Result Persistence | P0 | Not Started | 1.1, 3.4 | [task-7.11-result-persistence.md](../tasks/task-7.11-result-persistence.md) |

## Key Workflows

### Screening Orchestration
```python
class ScreeningService:
    async def execute_screening(
        self,
        request: ScreeningRequest
    ) -> ScreeningResult:
        """
        Complete screening workflow:
        1. Validate & create audit context
        2. Compliance gating
        3. Entity resolution
        4. Data acquisition
        5. Investigation (SAR loop)
        6. Risk analysis
        7. Profile creation
        8. Report generation
        9. Audit closure
        """

class ScreeningRequest(BaseModel):
    subject: SubjectIdentifiers
    locale: str
    service_tier: ServiceTier
    degree: InvestigationDegree
    vigilance: VigilanceLevel
    consent_token: str
    tenant_id: UUID

class ScreeningResult(BaseModel):
    screening_id: UUID
    profile: EntityProfile
    reports: dict[str, bytes]  # report_type -> PDF bytes
    audit_id: UUID
    total_cost: Decimal
    status: ScreeningStatus
```

## Phase Acceptance Criteria

### Functional Requirements
- [x] Complete D1 screening executes end-to-end
- [x] Complete D2 screening with connection discovery
- [x] Compliance rules enforced before data acquisition
- [x] Profile created with correct version number
- [x] 3 basic reports generated (summary, audit, disclosure)
- [x] Screening status tracked through all phases

### Performance Requirements
- [x] D1 screening completes in <10 minutes (mock providers)
- [x] Can handle 10 concurrent screenings
- [x] Job queue processes failed screenings with retry

### Testing Requirements
- [x] End-to-end integration tests (all tiers and degrees)
- [x] Error handling tests (provider failure, budget exceeded)
- [x] Concurrent screening tests

### Review Gates
- [x] Architecture review: Orchestration design
- [x] Security review: Request validation
- [x] Performance review: Bottleneck identification

---

*Phase Owner: [Assign team lead]*
*Last Updated: 2026-01-29*
