# Phase 10: Integration Layer

## Overview

Phase 10 implements the HRIS integration gateway for receiving hire events, consent grants, and publishing screening results back to HRIS platforms. This phase enables bidirectional integration with customer systems.

**Duration Estimate**: 3-4 weeks
**Team Size**: 2-3 developers
**Risk Level**: Medium (third-party integration complexity)

## Phase Goals

- ✓ Build HRIS webhook receiver
- ✓ Implement event processor for hire.initiated, consent.granted, etc.
- ✓ Create result publisher (status updates, alerts to HRIS)
- ✓ Build platform-specific adapters (Workday, SAP, etc.)

## Tasks

| Seq | Task Name | Priority | Status | Dependencies | Plan Document |
|-----|-----------|----------|--------|--------------|---------------|
| 10.1 | HRIS Integration Gateway (Core) | P0 | Not Started | 1.5 | [task-10.1-hris-gateway.md](../tasks/task-10.1-hris-gateway.md) |
| 10.2 | Webhook Receiver | P0 | Not Started | 10.1 | [task-10.2-webhook-receiver.md](../tasks/task-10.2-webhook-receiver.md) |
| 10.3 | Event Processor | P0 | Not Started | 10.2, Phase 7 | [task-10.3-event-processor.md](../tasks/task-10.3-event-processor.md) |
| 10.4 | Result Publisher | P0 | Not Started | 10.1 | [task-10.4-result-publisher.md](../tasks/task-10.4-result-publisher.md) |
| 10.5 | Webhook Retry Logic | P0 | Not Started | 10.4 | [task-10.5-webhook-retry.md](../tasks/task-10.5-webhook-retry.md) |
| 10.6 | Workday Adapter | P1 | Not Started | 10.1 | [task-10.6-workday-adapter.md](../tasks/task-10.6-workday-adapter.md) |
| 10.7 | SAP SuccessFactors Adapter | P2 | Not Started | 10.1 | [task-10.7-sap-adapter.md](../tasks/task-10.7-sap-adapter.md) |
| 10.8 | ADP Adapter | P2 | Not Started | 10.1 | [task-10.8-adp-adapter.md](../tasks/task-10.8-adp-adapter.md) |
| 10.9 | Generic Webhook Adapter | P1 | Not Started | 10.1 | [task-10.9-generic-adapter.md](../tasks/task-10.9-generic-adapter.md) |
| 10.10 | HRIS Configuration Manager | P1 | Not Started | 1.4, 10.1 | [task-10.10-hris-config.md](../tasks/task-10.10-hris-config.md) |

## Key Workflows

### HRIS Event Processing
```python
class HRISEvent(BaseModel):
    event_type: Literal[
        "hire.initiated",
        "consent.granted",
        "position.changed",
        "employee.terminated"
    ]
    tenant_id: UUID
    employee_id: str  # HRIS-specific ID
    event_data: dict
    received_at: datetime

class HRISEventProcessor:
    async def process_event(self, event: HRISEvent):
        """Process incoming HRIS webhook."""
        if event.event_type == "hire.initiated":
            await self.initiate_screening(event)
        elif event.event_type == "consent.granted":
            await self.start_screening(event)
        elif event.event_type == "position.changed":
            await self.reevaluate_monitoring(event)
        elif event.event_type == "employee.terminated":
            await self.stop_monitoring(event)

class HRISResultPublisher:
    async def publish_screening_complete(
        self,
        tenant_id: UUID,
        employee_id: str,
        result: ScreeningResult
    ):
        """Send screening result back to HRIS."""
        hris_adapter = await self.get_adapter(tenant_id)
        await hris_adapter.update_candidate_status(
            employee_id=employee_id,
            status="screening_complete",
            risk_level=result.profile.risk_score.overall,
            recommendation=result.recommendation
        )
```

### HRIS Adapters
```python
class HRISAdapter(ABC):
    """Abstract base for HRIS platform adapters."""

    @abstractmethod
    async def parse_webhook(self, payload: dict) -> HRISEvent:
        """Convert platform-specific webhook to standard event."""

    @abstractmethod
    async def update_candidate_status(
        self,
        employee_id: str,
        status: str,
        **kwargs
    ):
        """Update candidate status in HRIS."""

    @abstractmethod
    async def send_alert(
        self,
        employee_id: str,
        alert: Alert
    ):
        """Send monitoring alert to HRIS."""
```

## Phase Acceptance Criteria

### Functional Requirements
- [x] Webhook receiver validates signatures and processes events
- [x] hire.initiated event triggers screening workflow
- [x] consent.granted event starts data acquisition
- [x] Screening results published to HRIS via webhook
- [x] At least 1 platform adapter implemented (Workday or generic)
- [x] Retry logic handles webhook delivery failures

### Testing Requirements
- [x] Unit tests for event processing
- [x] Integration tests with mock HRIS webhooks
- [x] Webhook retry tests
- [x] End-to-end flow: hire event → screening → result webhook

### Review Gates
- [x] Security review: Webhook signature validation
- [x] Architecture review: Adapter pattern design

---

*Phase Owner: [Assign team lead]*
*Last Updated: 2026-01-29*
