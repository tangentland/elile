"""HRIS Integration module for bidirectional HRIS platform communication.

This module provides:
- HRISGateway: Core gateway for managing HRIS connections and events
- HRISEventProcessor: Routes HRIS events to appropriate handlers
- HRISResultPublisher: Publishes screening results and alerts to HRIS platforms
- HRISAdapter: Protocol for platform-specific adapters
- HRISEvent: Normalized event representation from HRIS platforms
- Event types and platform enums for HRIS integration

Example usage:
    from elile.hris import (
        HRISGateway,
        HRISEventProcessor,
        HRISResultPublisher,
        create_hris_gateway,
        create_event_processor,
        create_result_publisher,
        HRISEventType,
    )

    # Create gateway with default configuration
    gateway = create_hris_gateway(include_mock_adapter=True)

    # Create event processor
    processor = create_event_processor()

    # Create result publisher
    publisher = create_result_publisher(gateway=gateway)

    # Register a connection for a tenant
    gateway.register_connection(connection)

    # Validate and parse inbound events
    validation = await gateway.validate_inbound_event(tenant_id, headers, payload)
    if validation.valid:
        event = await gateway.parse_inbound_event(tenant_id, event_type, parsed_payload)

        # Process the event
        result = await processor.process_event(event)

    # Publish screening result back to HRIS
    publish_result = await publisher.publish_screening_complete(
        screening_id=screening_id,
        employee_id="EMP-001",
        tenant_id=tenant_id,
        result=screening_result,
    )
"""

from elile.hris.event_processor import (
    EventStore,
    HRISEventProcessor,
    InMemoryEventStore,
    ProcessingAction,
    ProcessingResult,
    ProcessingStatus,
    ProcessorConfig,
    create_event_processor,
)
from elile.hris.gateway import (
    AlertUpdate,
    BaseHRISAdapter,
    EmployeeInfo,
    GatewayConfig,
    HRISAdapter,
    HRISConnection,
    HRISConnectionStatus,
    HRISEvent,
    HRISEventType,
    HRISGateway,
    HRISPlatform,
    MockHRISAdapter,
    ScreeningUpdate,
    WebhookValidationResult,
    create_hris_gateway,
)
from elile.hris.result_publisher import (
    DeliveryRecord,
    HRISResultPublisher,
    PublishEventType,
    PublisherConfig,
    PublishResult,
    PublishStatus,
    create_result_publisher,
)

__all__ = [
    # Core gateway
    "HRISGateway",
    "GatewayConfig",
    "create_hris_gateway",
    # Event processor
    "HRISEventProcessor",
    "ProcessorConfig",
    "ProcessingResult",
    "ProcessingStatus",
    "ProcessingAction",
    "EventStore",
    "InMemoryEventStore",
    "create_event_processor",
    # Result publisher
    "HRISResultPublisher",
    "PublisherConfig",
    "PublishResult",
    "PublishStatus",
    "PublishEventType",
    "DeliveryRecord",
    "create_result_publisher",
    # Adapter protocol and base class
    "HRISAdapter",
    "BaseHRISAdapter",
    "MockHRISAdapter",
    # Event types
    "HRISEvent",
    "HRISEventType",
    # Connection management
    "HRISConnection",
    "HRISConnectionStatus",
    "HRISPlatform",
    # Data transfer objects
    "ScreeningUpdate",
    "AlertUpdate",
    "EmployeeInfo",
    "WebhookValidationResult",
]
