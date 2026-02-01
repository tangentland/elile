# Task 5.12: SAR Records Phase Handler

**Priority**: P1
**Phase**: 5 - Investigation Engine
**Estimated Effort**: 3 days
**Dependencies**: Task 5.11 (Foundation Phase)

## Context

Implement Records phase focused on collecting structured records from official sources (court records, regulatory filings, government databases).

**Architecture Reference**: [05-investigation.md](../docs/architecture/05-investigation.md) - SAR Loop

## Objectives

1. Query official record databases
2. Collect criminal, civil, financial records
3. Extract structured data from records
4. Verify record authenticity
5. Cross-reference findings

## Technical Approach

```python
# src/elile/investigation/phases/records.py
class RecordsPhaseHandler:
    """Handle Records phase of investigation."""

    async def execute(
        self,
        foundation: FoundationResult,
        compliance_rules: ComplianceRules
    ) -> RecordsResult:
        """Execute records collection phase."""
        # Select record sources based on compliance
        sources = self._select_record_sources(compliance_rules)

        # Query each source
        criminal = await self._query_criminal_records(foundation)
        civil = await self._query_civil_records(foundation)
        financial = await self._query_financial_records(foundation)

        # Extract and structure data
        records = self._extract_structured_data([criminal, civil, financial])

        return RecordsResult(records=records, next_phase="intelligence")
```

## Implementation Checklist

- [ ] Implement record source queries
- [ ] Add data extraction
- [ ] Create record validation
- [ ] Test compliance filtering

## Success Criteria

- [ ] All allowed sources queried
- [ ] Record extraction accurate
- [ ] Compliance rules enforced
