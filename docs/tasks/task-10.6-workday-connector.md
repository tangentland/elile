# Task 10.6: Workday Connector

**Priority**: P1
**Phase**: 10 - External Integrations
**Estimated Effort**: 3 days
**Dependencies**: Task 10.5 (HRIS Gateway)

## Context

Implement Workday-specific connector for employee data sync, consent management, and screening result delivery.

## Objectives

1. Workday API integration
2. Employee data mapping
3. Consent workflow
4. Result delivery
5. Webhook handling

## Technical Approach

```python
# src/elile/integrations/hris/connectors/workday.py
class WorkdayConnector(HRISConnector):
    async def get_employee(self, employee_id: str) -> Employee:
        # Call Workday API
        # Transform to internal model
        pass

    async def submit_consent_request(
        self,
        employee_id: str,
        request: ConsentRequest
    ) -> str:
        # Create Workday task
        pass
```

## Implementation Checklist

- [ ] Implement Workday API client
- [ ] Add data mapping
- [ ] Test integration

## Success Criteria

- [ ] Full CRUD operations
- [ ] Consent workflow works
