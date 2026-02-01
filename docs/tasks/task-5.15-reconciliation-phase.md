# Task 5.15: SAR Reconciliation Phase Handler

**Priority**: P1
**Phase**: 5 - Investigation Engine
**Estimated Effort**: 3 days
**Dependencies**: Task 5.14 (Network Phase)

## Context

Implement Reconciliation phase for deduplicating findings, resolving conflicts, validating data consistency, and preparing final investigation report.

**Architecture Reference**: [05-investigation.md](../docs/architecture/05-investigation.md) - SAR Loop

## Objectives

1. Deduplicate findings across sources
2. Resolve data conflicts
3. Validate information consistency
4. Calculate confidence scores
5. Prepare findings for risk analysis

## Technical Approach

```python
# src/elile/investigation/phases/reconciliation.py
class ReconciliationPhaseHandler:
    """Handle Reconciliation phase."""

    async def execute(
        self,
        network: NetworkResult,
        all_findings: List[Finding]
    ) -> ReconciliationResult:
        """Reconcile and deduplicate findings."""
        # Deduplicate findings
        unique_findings = self._deduplicate(all_findings)

        # Resolve conflicts
        resolved = self._resolve_conflicts(unique_findings)

        # Calculate confidence scores
        scored = self._calculate_confidence(resolved)

        return ReconciliationResult(
            findings=scored,
            investigation_complete=True
        )
```

## Implementation Checklist

- [ ] Implement deduplication
- [ ] Add conflict resolution
- [ ] Create confidence scoring
- [ ] Test data consistency

## Success Criteria

- [ ] Dedup accuracy >95%
- [ ] Conflict resolution effective
- [ ] Confidence scores calibrated
