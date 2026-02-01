# Task 10.5: HRIS Integration Gateway

**Priority**: P1
**Phase**: 10 - External Integrations
**Estimated Effort**: 3 days
**Dependencies**: Task 10.1 (API Framework)

## Context

Create unified gateway for HRIS system integrations supporting consent collection, employee lifecycle events, and bidirectional data sync.

## Objectives

1. Unified HRIS interface
2. Multi-platform support
3. Consent workflow integration
4. Employee event webhooks
5. Data synchronization

## Technical Approach

```python
# src/elile/integrations/hris/gateway.py
class HRISGateway:
    def __init__(self, provider: str):
        self.connector = self._get_connector(provider)

    async def sync_employee(self, employee_id: str) -> Employee:
        # Fetch from HRIS
        # Map to internal model
        # Create/update subject
        pass

    async def request_consent(
        self,
        employee_id: str,
        screening_type: str
    ) -> ConsentRequest:
        # Create consent request in HRIS
        # Track status
        pass
```

## Implementation Checklist

- [ ] Create gateway interface
- [ ] Add connector abstraction
- [ ] Implement sync logic
- [ ] Test multi-platform

## Success Criteria

- [ ] Multiple HRIS supported
- [ ] Reliable sync
