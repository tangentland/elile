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
| 7.1 | Screening Request Model & Orchestrator | P0 | ✅ Complete | Phase 2, 3, 5, 6 | [task-7.1-screening-orchestrator.md](../tasks/task-7.1-screening-orchestrator.md) |
| 7.2 | Degree D1 Handler | P0 | ✅ Complete | 7.1 | [task-7.2-degree-d1-handler.md](../tasks/task-7.2-degree-d1-handler.md) |
| 7.3 | Degree D2/D3 Handlers | P0 | ✅ Complete | 7.2 | [task-7.3-degree-d2-handler.md](../tasks/task-7.3-degree-d2-handler.md) |
| 7.4 | Tier Router | P0 | ✅ Complete | 2.1 | [task-7.4-tier-router.md](../tasks/task-7.4-tier-router.md) |
| 7.5 | Screening State Manager | P0 | ✅ Complete | 7.1 | [task-7.5-screening-state-manager.md](../tasks/task-7.5-screening-state-manager.md) |
| 7.6 | Result Compiler | P0 | ✅ Complete | 5.9, 6.7 | [task-7.6-result-compiler.md](../tasks/task-7.6-result-compiler.md) |
| 7.7 | Screening API Endpoints | P0 | ✅ Complete | 7.2, 1.5 | [task-7.7-screening-api-endpoints.md](../tasks/task-7.7-screening-api-endpoints.md) |
| 7.8 | D3 Handler Enhancements | P1 | ✅ Complete | 7.3 | [task-7.8-degree-d3-handler.md](../tasks/task-7.8-degree-d3-handler.md) |
| 7.9 | Screening Queue | P1 | ✅ Complete | 1.10 | [task-7.9-screening-queue.md](../tasks/task-7.9-screening-queue.md) |
| 7.10 | Cost Estimator | P1 | ✅ Complete | 7.4 | [task-7.10-cost-estimator.md](../tasks/task-7.10-cost-estimator.md) |
| 7.11 | Progress Tracker | P1 | ✅ Complete | 7.5 | [task-7.11-progress-tracker.md](../tasks/task-7.11-progress-tracker.md) |

**P0 Tasks Complete: 7/7** | **P1 Tasks Complete: 4/4** ✅

*Note: Tasks 7.8-7.11 are P1 (enhancements). Basic D3 handling is included in Task 7.3.*

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
*Last Updated: 2026-02-02*
