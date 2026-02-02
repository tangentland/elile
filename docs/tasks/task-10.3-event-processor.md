# Task 10.3: Event Processor

## Overview

Implement the HRIS Event Processor that routes received HRIS events to appropriate handlers within the Elile system. The processor handles lifecycle events from HRIS platforms and triggers corresponding actions in the screening and monitoring subsystems.

## Priority

**P0 - Critical**

This task is essential for processing incoming HRIS events and initiating the screening workflow.

## Dependencies

- Task 10.1: HRIS Integration Gateway (Core) - provides HRISEvent model
- Task 10.2: Webhook Receiver - receives events to process
- Phase 7: Screening Service - for initiating screenings

## Implementation Details

### Event Handlers

The processor handles the following event types:

1. **hire.initiated** - Creates a pending screening request awaiting consent
2. **consent.granted** - Starts the screening with the consent token
3. **position.changed** - Creates lifecycle event for vigilance reevaluation
4. **employee.terminated** - Terminates monitoring for the employee
5. **rehire.initiated** - Processes rehire with new/existing subject mapping

### Key Components

- `HRISEventProcessor` - Main processor class that routes events
- `ProcessorConfig` - Configuration for defaults and processing options
- `ProcessingResult` - Result of event processing
- `ProcessingStatus` - Status enum (success, failed, skipped, pending, queued)
- `ProcessingAction` - Action taken (screening_initiated, screening_started, etc.)
- `InMemoryEventStore` - Store for pending screenings and employee mappings
- Service protocols for screening, monitoring, vigilance integration

### Configuration Options

- `default_service_tier` - Default service tier for new screenings
- `default_search_degree` - Default search degree (D1/D2/D3)
- `default_vigilance_level` - Default vigilance level for monitoring
- `auto_start_screening` - Whether to auto-start when consent granted
- `auto_terminate_on_termination` - Whether to auto-terminate monitoring

## Acceptance Criteria

- [x] Handler for hire.initiated creates pending screening request
- [x] Handler for consent.granted starts screening with consent token
- [x] Handler for position.changed creates lifecycle event
- [x] Handler for employee.terminated terminates monitoring
- [x] Handler for rehire.initiated processes rehire scenario
- [x] Proper error handling with failed status
- [x] Audit logging for all events processed
- [x] Processing statistics tracking
- [x] Integration with webhook receiver endpoint
- [x] Comprehensive unit tests (25 tests)

## Files Created/Modified

### Created
- `src/elile/hris/event_processor.py` - Main event processor implementation

### Modified
- `src/elile/hris/__init__.py` - Added exports for event processor
- `src/elile/api/routers/v1/hris_webhook.py` - Integrated event processor
- `src/elile/api/schemas/hris_webhook.py` - Added processing_result to response

## Testing

25 unit tests covering:
- Factory function tests
- Hire initiated event handling
- Consent granted event handling
- Position changed event handling
- Employee terminated event handling
- Rehire initiated event handling
- Unknown/outbound event handling
- Statistics tracking
- In-memory event store operations
- Error handling

## Status

**Complete** - 2026-02-01
