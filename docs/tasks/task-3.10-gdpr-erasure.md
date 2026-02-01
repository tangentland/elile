# Task 3.10: GDPR Right to Erasure

**Priority**: P1
**Phase**: 3 - Subject & Screening Engine
**Estimated Effort**: 2 days
**Dependencies**: Task 3.9 (Data Retention)

## Context

Implement GDPR Article 17 "Right to Erasure" allowing subjects to request deletion of personal data, with legal hold exemptions for ongoing investigations.

**Architecture Reference**: [07-compliance.md](../docs/architecture/07-compliance.md) - GDPR Compliance

## Objectives

1. Create erasure request workflow
2. Implement data anonymization
3. Support legal hold management
4. Generate erasure confirmation reports
5. Maintain audit trail of erasures

## Technical Approach

```python
# src/elile/compliance/erasure/service.py
class ErasureService:
    """Handle GDPR erasure requests."""

    def process_erasure_request(
        self,
        subject_id: str,
        request_type: str,  # full_erasure, anonymize, export
        requester_id: str
    ) -> ErasureOperation:
        """Process right to erasure request."""
        # Check for legal holds
        if self._has_legal_hold(subject_id):
            raise LegalHoldException("Subject has active legal hold")

        # Anonymize PII while preserving statistical data
        self._anonymize_subject_data(subject_id)

        # Log erasure operation
        audit_logger.log_erasure(subject_id, requester_id)
```

## Implementation Checklist

- [ ] Create erasure request API
- [ ] Implement anonymization logic
- [ ] Add legal hold checking
- [ ] Generate confirmation reports
- [ ] Test GDPR compliance

## Success Criteria

- [ ] Erasure completes within 30 days
- [ ] Legal holds block deletion
- [ ] Audit trail maintained
- [ ] Confirmation reports generated
