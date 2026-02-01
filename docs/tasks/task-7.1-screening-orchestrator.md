# Task 7.1: Screening Orchestrator

## Overview

Implement main screening orchestrator that coordinates the complete screening workflow from request validation through completion, integrating SAR loop, risk analysis, and report generation.

**Priority**: P0 | **Effort**: 3 days | **Status**: Not Started

## Dependencies

- Task 5.9: SAR Loop Orchestrator
- Task 6.7: Risk Aggregator
- Task 2.6: Compliance Engine

## Implementation

```python
# src/elile/screening/screening_orchestrator.py
class ScreeningOrchestrator:
    """Orchestrates complete screening workflow."""

    async def execute_screening(
        self,
        request: ScreeningRequest,
        ctx: RequestContext
    ) -> ScreeningResult:
        """Execute complete screening workflow."""

        # 1. Validate request
        await self._validate_request(request)

        # 2. Compliance check
        await self._check_compliance(request)

        # 3. Resolve data sources
        sources = await self._resolve_sources(request)

        # 4. Execute SAR loop
        sar_results = await self.sar_orchestrator.execute_all_types(
            request.knowledge_base,
            request.locale,
            request.tier,
            request.role_category,
            ctx
        )

        # 5. Analyze risk
        risk_assessment = await self.risk_aggregator.aggregate_risk(
            sar_results.findings,
            sar_results.patterns,
            sar_results.anomalies,
            sar_results.connections
        )

        # 6. Generate report
        report = await self.report_generator.generate(
            sar_results, risk_assessment, request.report_type
        )

        return ScreeningResult(
            screening_id=request.screening_id,
            status=ScreeningStatus.COMPLETE,
            risk_assessment=risk_assessment,
            report=report
        )
```

## Acceptance Criteria

- [ ] Orchestrates end-to-end screening
- [ ] Validates requests before execution
- [ ] Enforces compliance checks
- [ ] Integrates SAR loop, risk analysis, reporting
- [ ] Handles errors gracefully

## Deliverables

- `src/elile/screening/screening_orchestrator.py`
- `tests/integration/test_complete_screening.py`

## References

- Architecture: [05-investigation.md](../../docs/architecture/05-investigation.md) - Screening Engine

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
