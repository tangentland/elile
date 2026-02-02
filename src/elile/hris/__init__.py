"""HRIS Integration module for bidirectional HRIS platform communication.

This module provides:
- HRISGateway: Core gateway for managing HRIS connections and events
- HRISAdapter: Protocol for platform-specific adapters
- HRISEvent: Normalized event representation from HRIS platforms
- Event types and platform enums for HRIS integration

Example usage:
    from elile.hris import HRISGateway, create_hris_gateway, HRISEventType

    # Create gateway with default configuration
    gateway = create_hris_gateway(include_mock_adapter=True)

    # Register a connection for a tenant
    gateway.register_connection(connection)

    # Validate and parse inbound events
    validation = await gateway.validate_inbound_event(tenant_id, headers, payload)
    if validation.valid:
        event = await gateway.parse_inbound_event(tenant_id, event_type, parsed_payload)
"""

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

__all__ = [
    # Core gateway
    "HRISGateway",
    "GatewayConfig",
    "create_hris_gateway",
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
