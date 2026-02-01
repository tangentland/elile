# Task 8.6: FCRA Disclosure Report Generator

**Priority**: P1
**Phase**: 8 - Reporting Engine
**Estimated Effort**: 2 days
**Dependencies**: Task 8.1 (Report Generation)

## Context

Generate FCRA-compliant disclosure reports for adverse action notifications to candidates with legally required content and formatting.

## Objectives

1. FCRA-compliant formatting
2. Include required disclosures
3. Adverse action process support
4. Multi-language support
5. Delivery tracking

## Technical Approach

```python
# src/elile/reporting/generators/disclosure.py
class FCRADisclosureGenerator:
    def generate(self, screening: Screening) -> DisclosureReport:
        # FCRA required elements
        # Summary of rights
        # Adverse findings
        # Dispute process
        pass
```

## Implementation Checklist

- [ ] Implement FCRA generator
- [ ] Add required disclosures
- [ ] Test compliance

## Success Criteria

- [ ] FCRA compliant
- [ ] All required elements present
