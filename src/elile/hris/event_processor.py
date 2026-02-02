"""HRIS Event Processor for routing events to appropriate handlers.

This module processes incoming HRIS events and routes them to the appropriate
subsystems (screening, monitoring, vigilance management).
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol
from uuid import UUID, uuid7

import structlog
from pydantic import BaseModel, Field

from elile.agent.state import SearchDegree, ServiceTier, VigilanceLevel
from elile.compliance.types import Locale, RoleCategory
from elile.entity.types import SubjectIdentifiers
from elile.hris.gateway import (
    HRISEvent,
    HRISEventType,
)
from elile.monitoring.types import (
    LifecycleEvent,
    LifecycleEventType,
    MonitoringStatus,
)
from elile.screening.types import (
    ScreeningPriority,
    ScreeningRequest,
    ScreeningStatus,
)

logger = structlog.get_logger()


# =============================================================================
# Enums and Types
# =============================================================================


class ProcessingStatus(str, Enum):
    """Status of event processing."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"
    QUEUED = "queued"


class ProcessingAction(str, Enum):
    """Action taken by the event processor."""

    SCREENING_INITIATED = "screening_initiated"
    SCREENING_STARTED = "screening_started"
    MONITORING_TERMINATED = "monitoring_terminated"
    VIGILANCE_UPDATED = "vigilance_updated"
    LIFECYCLE_EVENT_CREATED = "lifecycle_event_created"
    REHIRE_PROCESSED = "rehire_processed"
    NO_ACTION = "no_action"


# =============================================================================
# Processing Results
# =============================================================================


@dataclass
class ProcessingResult:
    """Result of processing an HRIS event.

    Contains the status, actions taken, and any related entity IDs.
    """

    result_id: UUID = field(default_factory=uuid7)
    event_id: UUID = field(default_factory=uuid7)
    event_type: HRISEventType = HRISEventType.HIRE_INITIATED

    # Status
    status: ProcessingStatus = ProcessingStatus.SUCCESS
    action: ProcessingAction = ProcessingAction.NO_ACTION
    error_message: str | None = None

    # Related entities
    screening_id: UUID | None = None
    monitoring_config_id: UUID | None = None
    subject_id: UUID | None = None

    # Timing
    processed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    processing_time_ms: int = 0

    # Audit
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "result_id": str(self.result_id),
            "event_id": str(self.event_id),
            "event_type": self.event_type.value,
            "status": self.status.value,
            "action": self.action.value,
            "error_message": self.error_message,
            "screening_id": str(self.screening_id) if self.screening_id else None,
            "monitoring_config_id": (
                str(self.monitoring_config_id) if self.monitoring_config_id else None
            ),
            "subject_id": str(self.subject_id) if self.subject_id else None,
            "processed_at": self.processed_at.isoformat(),
            "processing_time_ms": self.processing_time_ms,
            "details": self.details,
        }


# =============================================================================
# Configuration
# =============================================================================


class ProcessorConfig(BaseModel):
    """Configuration for the HRIS event processor."""

    # Screening defaults
    default_service_tier: ServiceTier = ServiceTier.STANDARD
    default_search_degree: SearchDegree = SearchDegree.D1
    default_vigilance_level: VigilanceLevel = VigilanceLevel.V1
    default_locale: Locale = Locale.US
    default_role_category: RoleCategory = RoleCategory.STANDARD

    # Processing options
    auto_start_screening: bool = Field(
        default=True,
        description="Automatically start screening when consent is granted",
    )
    auto_terminate_on_termination: bool = Field(
        default=True,
        description="Automatically terminate monitoring when employee is terminated",
    )
    require_consent_for_screening: bool = Field(
        default=True,
        description="Require consent.granted event before starting screening",
    )

    # Queue settings
    enable_async_processing: bool = Field(
        default=False,
        description="Queue events for async processing instead of immediate",
    )

    # Retry settings
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay_seconds: int = Field(default=60, ge=10, le=600)


# =============================================================================
# Service Protocols
# =============================================================================


class ScreeningServiceProtocol(Protocol):
    """Protocol for the screening service interface."""

    async def initiate_screening(
        self,
        request: ScreeningRequest,
    ) -> UUID:
        """Initiate a new screening and return the screening ID."""
        ...

    async def get_screening_status(
        self,
        screening_id: UUID,
    ) -> ScreeningStatus | None:
        """Get the status of a screening."""
        ...


class MonitoringServiceProtocol(Protocol):
    """Protocol for the monitoring service interface."""

    async def terminate_monitoring(
        self,
        config_id: UUID,
        reason: str | None = None,
    ) -> bool:
        """Terminate monitoring for a subject."""
        ...

    async def get_config_by_subject(
        self,
        subject_id: UUID,
        tenant_id: UUID,
    ) -> Any | None:
        """Get monitoring config by subject."""
        ...

    async def handle_lifecycle_event(
        self,
        event: LifecycleEvent,
    ) -> Any | None:
        """Handle a lifecycle event."""
        ...


class VigilanceServiceProtocol(Protocol):
    """Protocol for the vigilance management interface."""

    async def evaluate_position_change(
        self,
        subject_id: UUID,
        tenant_id: UUID,
        new_role_category: RoleCategory,
    ) -> VigilanceLevel:
        """Evaluate vigilance level after position change."""
        ...


# =============================================================================
# Event Store
# =============================================================================


class EventStore(Protocol):
    """Protocol for event persistence."""

    async def save_pending_screening(
        self,
        tenant_id: UUID,
        employee_id: str,
        request: ScreeningRequest,
    ) -> None:
        """Save a pending screening request awaiting consent."""
        ...

    async def get_pending_screening(
        self,
        tenant_id: UUID,
        employee_id: str,
    ) -> ScreeningRequest | None:
        """Get a pending screening request."""
        ...

    async def remove_pending_screening(
        self,
        tenant_id: UUID,
        employee_id: str,
    ) -> bool:
        """Remove a pending screening request."""
        ...

    async def get_subject_id_by_employee_id(
        self,
        tenant_id: UUID,
        employee_id: str,
    ) -> UUID | None:
        """Get subject ID from HRIS employee ID mapping."""
        ...

    async def save_employee_mapping(
        self,
        tenant_id: UUID,
        employee_id: str,
        subject_id: UUID,
    ) -> None:
        """Save mapping between HRIS employee ID and internal subject ID."""
        ...


class InMemoryEventStore:
    """In-memory implementation of EventStore for testing."""

    def __init__(self) -> None:
        self._pending_screenings: dict[str, ScreeningRequest] = {}
        self._employee_mappings: dict[str, UUID] = {}

    def _key(self, tenant_id: UUID, employee_id: str) -> str:
        return f"{tenant_id}:{employee_id}"

    async def save_pending_screening(
        self,
        tenant_id: UUID,
        employee_id: str,
        request: ScreeningRequest,
    ) -> None:
        self._pending_screenings[self._key(tenant_id, employee_id)] = request

    async def get_pending_screening(
        self,
        tenant_id: UUID,
        employee_id: str,
    ) -> ScreeningRequest | None:
        return self._pending_screenings.get(self._key(tenant_id, employee_id))

    async def remove_pending_screening(
        self,
        tenant_id: UUID,
        employee_id: str,
    ) -> bool:
        key = self._key(tenant_id, employee_id)
        if key in self._pending_screenings:
            del self._pending_screenings[key]
            return True
        return False

    async def get_subject_id_by_employee_id(
        self,
        tenant_id: UUID,
        employee_id: str,
    ) -> UUID | None:
        return self._employee_mappings.get(self._key(tenant_id, employee_id))

    async def save_employee_mapping(
        self,
        tenant_id: UUID,
        employee_id: str,
        subject_id: UUID,
    ) -> None:
        self._employee_mappings[self._key(tenant_id, employee_id)] = subject_id


# =============================================================================
# HRIS Event Processor
# =============================================================================


class HRISEventProcessor:
    """Processes HRIS events and routes them to appropriate handlers.

    The processor handles:
    - hire.initiated: Creates a pending screening request
    - consent.granted: Starts the screening with the pending request
    - position.changed: Creates lifecycle event for vigilance reevaluation
    - employee.terminated: Terminates monitoring
    - rehire.initiated: Resumes monitoring for a rehired employee

    Example:
        processor = HRISEventProcessor(
            screening_service=screening_orchestrator,
            monitoring_service=monitoring_scheduler,
            vigilance_service=vigilance_manager,
        )

        result = await processor.process_event(hris_event)
        if result.status == ProcessingStatus.SUCCESS:
            print(f"Event processed: {result.action.value}")
    """

    def __init__(
        self,
        config: ProcessorConfig | None = None,
        screening_service: ScreeningServiceProtocol | None = None,
        monitoring_service: MonitoringServiceProtocol | None = None,
        vigilance_service: VigilanceServiceProtocol | None = None,
        event_store: EventStore | None = None,
    ) -> None:
        """Initialize the event processor.

        Args:
            config: Processor configuration.
            screening_service: Service for initiating screenings.
            monitoring_service: Service for managing monitoring.
            vigilance_service: Service for vigilance level management.
            event_store: Store for pending events and mappings.
        """
        self.config = config or ProcessorConfig()
        self._screening_service = screening_service
        self._monitoring_service = monitoring_service
        self._vigilance_service = vigilance_service
        self._event_store = event_store or InMemoryEventStore()
        self._processed_count: dict[HRISEventType, int] = {}

    async def process_event(self, event: HRISEvent) -> ProcessingResult:
        """Process an HRIS event.

        Routes the event to the appropriate handler based on event type.

        Args:
            event: The HRIS event to process.

        Returns:
            ProcessingResult with status and details.
        """
        start_time = datetime.now(UTC)

        result = ProcessingResult(
            event_id=event.event_id,
            event_type=event.event_type,
        )

        logger.info(
            "Processing HRIS event",
            event_id=str(event.event_id),
            event_type=event.event_type.value,
            tenant_id=str(event.tenant_id),
            employee_id=event.employee_id,
        )

        try:
            match event.event_type:
                case HRISEventType.HIRE_INITIATED:
                    result = await self._handle_hire_initiated(event, result)

                case HRISEventType.CONSENT_GRANTED:
                    result = await self._handle_consent_granted(event, result)

                case HRISEventType.POSITION_CHANGED:
                    result = await self._handle_position_changed(event, result)

                case HRISEventType.EMPLOYEE_TERMINATED:
                    result = await self._handle_employee_terminated(event, result)

                case HRISEventType.REHIRE_INITIATED:
                    result = await self._handle_rehire_initiated(event, result)

                case _:
                    # Outbound events or unknown types are skipped
                    result.status = ProcessingStatus.SKIPPED
                    result.action = ProcessingAction.NO_ACTION
                    result.details["reason"] = f"Event type {event.event_type.value} not handled"

            # Update statistics
            self._processed_count[event.event_type] = (
                self._processed_count.get(event.event_type, 0) + 1
            )

        except Exception as e:
            result.status = ProcessingStatus.FAILED
            result.error_message = str(e)
            logger.exception(
                "Failed to process HRIS event",
                event_id=str(event.event_id),
                event_type=event.event_type.value,
            )

        # Calculate processing time
        end_time = datetime.now(UTC)
        result.processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
        result.processed_at = end_time

        logger.info(
            "AUDIT: hris_event_processed",
            audit_event_type="hris.event_processed",
            event_id=str(event.event_id),
            event_type=event.event_type.value,
            tenant_id=str(event.tenant_id),
            employee_id=event.employee_id,
            status=result.status.value,
            action=result.action.value,
            processing_time_ms=result.processing_time_ms,
        )

        return result

    async def _handle_hire_initiated(
        self,
        event: HRISEvent,
        result: ProcessingResult,
    ) -> ProcessingResult:
        """Handle a hire.initiated event.

        Creates a pending screening request that will be started when
        consent is granted.

        Args:
            event: The hire initiated event.
            result: The result to populate.

        Returns:
            Updated processing result.
        """
        # Extract subject info from event data
        subject = self._extract_subject_identifiers(event)

        # Determine service configuration from event data
        service_tier = self._extract_service_tier(event)
        search_degree = self._extract_search_degree(event)
        vigilance_level = self._extract_vigilance_level(event)
        role_category = self._extract_role_category(event)
        locale = self._extract_locale(event)

        # Create screening request (pending consent)
        screening_request = ScreeningRequest(
            tenant_id=event.tenant_id,
            subject=subject,
            locale=locale,
            service_tier=service_tier,
            search_degree=search_degree,
            vigilance_level=vigilance_level,
            role_category=role_category,
            consent_token="",  # Will be filled when consent is granted
            priority=self._extract_priority(event),
            metadata={
                "hris_event_id": str(event.event_id),
                "hris_employee_id": event.employee_id,
                "hire_initiated_at": event.received_at.isoformat(),
            },
        )

        # Store pending screening
        await self._event_store.save_pending_screening(
            tenant_id=event.tenant_id,
            employee_id=event.employee_id,
            request=screening_request,
        )

        # Create subject ID mapping if we have one
        if screening_request.subject.full_name:
            subject_id = uuid7()
            await self._event_store.save_employee_mapping(
                tenant_id=event.tenant_id,
                employee_id=event.employee_id,
                subject_id=subject_id,
            )
            result.subject_id = subject_id

        result.screening_id = screening_request.screening_id
        result.status = ProcessingStatus.SUCCESS
        result.action = ProcessingAction.SCREENING_INITIATED
        result.details = {
            "screening_id": str(screening_request.screening_id),
            "status": "pending_consent",
            "service_tier": service_tier.value,
            "search_degree": search_degree.value,
            "vigilance_level": vigilance_level.value,
            "role_category": role_category.value,
        }

        logger.info(
            "Screening initiated (pending consent)",
            screening_id=str(screening_request.screening_id),
            tenant_id=str(event.tenant_id),
            employee_id=event.employee_id,
        )

        return result

    async def _handle_consent_granted(
        self,
        event: HRISEvent,
        result: ProcessingResult,
    ) -> ProcessingResult:
        """Handle a consent.granted event.

        Starts the screening with the previously created pending request.

        Args:
            event: The consent granted event.
            result: The result to populate.

        Returns:
            Updated processing result.
        """
        # Get pending screening
        pending_request = await self._event_store.get_pending_screening(
            tenant_id=event.tenant_id,
            employee_id=event.employee_id,
        )

        if pending_request is None:
            # No pending screening - might have been started via API
            result.status = ProcessingStatus.SKIPPED
            result.action = ProcessingAction.NO_ACTION
            result.details = {
                "reason": "No pending screening found for employee",
                "employee_id": event.employee_id,
            }
            logger.warning(
                "Consent granted but no pending screening found",
                tenant_id=str(event.tenant_id),
                employee_id=event.employee_id,
            )
            return result

        # Extract consent token from event
        consent_token = (
            event.consent_reference
            or event.event_data.get("consent_token")
            or event.event_data.get("consent_reference")
            or f"consent-{event.event_id}"
        )

        # Create new request with consent token using model_copy
        screening_request = pending_request.model_copy(
            update={
                "consent_token": consent_token,
                "metadata": {
                    **pending_request.metadata,
                    "consent_granted_at": event.received_at.isoformat(),
                    "consent_event_id": str(event.event_id),
                },
            }
        )

        # Start screening if service is available
        if self._screening_service is not None and self.config.auto_start_screening:
            try:
                screening_id = await self._screening_service.initiate_screening(
                    screening_request
                )
                result.screening_id = screening_id
                result.action = ProcessingAction.SCREENING_STARTED
                result.details["screening_status"] = "started"
            except Exception as e:
                logger.error(
                    "Failed to start screening",
                    screening_id=str(screening_request.screening_id),
                    error=str(e),
                )
                result.screening_id = screening_request.screening_id
                result.action = ProcessingAction.SCREENING_STARTED
                result.details["screening_status"] = "queued"
                result.details["error"] = str(e)
        else:
            result.screening_id = screening_request.screening_id
            result.action = ProcessingAction.SCREENING_STARTED
            result.details["screening_status"] = "queued"

        # Remove pending screening
        await self._event_store.remove_pending_screening(
            tenant_id=event.tenant_id,
            employee_id=event.employee_id,
        )

        result.status = ProcessingStatus.SUCCESS
        result.details["consent_token"] = consent_token

        logger.info(
            "Screening started after consent",
            screening_id=str(screening_request.screening_id),
            tenant_id=str(event.tenant_id),
            employee_id=event.employee_id,
        )

        return result

    async def _handle_position_changed(
        self,
        event: HRISEvent,
        result: ProcessingResult,
    ) -> ProcessingResult:
        """Handle a position.changed event.

        Creates a lifecycle event for vigilance reevaluation.

        Args:
            event: The position changed event.
            result: The result to populate.

        Returns:
            Updated processing result.
        """
        # Get subject ID from mapping
        subject_id = await self._event_store.get_subject_id_by_employee_id(
            tenant_id=event.tenant_id,
            employee_id=event.employee_id,
        )

        if subject_id is None:
            result.status = ProcessingStatus.SKIPPED
            result.action = ProcessingAction.NO_ACTION
            result.details = {
                "reason": "No subject mapping found for employee",
                "employee_id": event.employee_id,
            }
            logger.warning(
                "Position changed but no subject mapping found",
                tenant_id=str(event.tenant_id),
                employee_id=event.employee_id,
            )
            return result

        # Extract new role information
        new_role_category = self._extract_role_category(event)
        new_locale = self._extract_locale(event)
        position_info = event.position_info or event.event_data.get("position", {})

        # Create lifecycle event
        lifecycle_event = LifecycleEvent(
            subject_id=subject_id,
            tenant_id=event.tenant_id,
            event_type=LifecycleEventType.POSITION_CHANGE,
            description=self._build_position_change_description(event),
            new_role_category=new_role_category,
            new_locale=new_locale if new_locale != self.config.default_locale else None,
            metadata={
                "hris_event_id": str(event.event_id),
                "employee_id": event.employee_id,
                "position_info": position_info,
            },
        )

        # Handle lifecycle event if monitoring service available
        if self._monitoring_service is not None:
            try:
                config = await self._monitoring_service.handle_lifecycle_event(lifecycle_event)
                if config is not None:
                    result.monitoring_config_id = config.config_id
                    result.details["new_vigilance_level"] = config.vigilance_level.value
            except Exception as e:
                logger.error(
                    "Failed to handle lifecycle event",
                    event_id=str(lifecycle_event.event_id),
                    error=str(e),
                )
                result.details["error"] = str(e)

        result.subject_id = subject_id
        result.status = ProcessingStatus.SUCCESS
        result.action = ProcessingAction.LIFECYCLE_EVENT_CREATED
        result.details["lifecycle_event_id"] = str(lifecycle_event.event_id)
        result.details["new_role_category"] = new_role_category.value

        logger.info(
            "Position change lifecycle event created",
            subject_id=str(subject_id),
            tenant_id=str(event.tenant_id),
            employee_id=event.employee_id,
            new_role_category=new_role_category.value,
        )

        return result

    async def _handle_employee_terminated(
        self,
        event: HRISEvent,
        result: ProcessingResult,
    ) -> ProcessingResult:
        """Handle an employee.terminated event.

        Terminates monitoring for the employee.

        Args:
            event: The termination event.
            result: The result to populate.

        Returns:
            Updated processing result.
        """
        # Get subject ID from mapping
        subject_id = await self._event_store.get_subject_id_by_employee_id(
            tenant_id=event.tenant_id,
            employee_id=event.employee_id,
        )

        if subject_id is None:
            result.status = ProcessingStatus.SKIPPED
            result.action = ProcessingAction.NO_ACTION
            result.details = {
                "reason": "No subject mapping found for employee",
                "employee_id": event.employee_id,
            }
            logger.warning(
                "Termination received but no subject mapping found",
                tenant_id=str(event.tenant_id),
                employee_id=event.employee_id,
            )
            return result

        # Create termination lifecycle event
        lifecycle_event = LifecycleEvent(
            subject_id=subject_id,
            tenant_id=event.tenant_id,
            event_type=LifecycleEventType.TERMINATION,
            description=self._build_termination_description(event),
            metadata={
                "hris_event_id": str(event.event_id),
                "employee_id": event.employee_id,
                "termination_data": event.event_data,
            },
        )

        # Handle lifecycle event if monitoring service available
        if self._monitoring_service is not None and self.config.auto_terminate_on_termination:
            try:
                config = await self._monitoring_service.handle_lifecycle_event(lifecycle_event)
                if config is not None:
                    result.monitoring_config_id = config.config_id
                    result.details["monitoring_status"] = MonitoringStatus.TERMINATED.value
            except Exception as e:
                logger.error(
                    "Failed to terminate monitoring",
                    subject_id=str(subject_id),
                    error=str(e),
                )
                result.details["error"] = str(e)

        result.subject_id = subject_id
        result.status = ProcessingStatus.SUCCESS
        result.action = ProcessingAction.MONITORING_TERMINATED
        result.details["lifecycle_event_id"] = str(lifecycle_event.event_id)

        logger.info(
            "Employee terminated - monitoring stopped",
            subject_id=str(subject_id),
            tenant_id=str(event.tenant_id),
            employee_id=event.employee_id,
        )

        return result

    async def _handle_rehire_initiated(
        self,
        event: HRISEvent,
        result: ProcessingResult,
    ) -> ProcessingResult:
        """Handle a rehire.initiated event.

        Processes a rehire by creating a new screening request and
        potentially resuming monitoring.

        Args:
            event: The rehire event.
            result: The result to populate.

        Returns:
            Updated processing result.
        """
        # Check if we have an existing subject mapping
        subject_id = await self._event_store.get_subject_id_by_employee_id(
            tenant_id=event.tenant_id,
            employee_id=event.employee_id,
        )

        # Extract subject info from event
        subject = self._extract_subject_identifiers(event)
        service_tier = self._extract_service_tier(event)
        search_degree = self._extract_search_degree(event)
        vigilance_level = self._extract_vigilance_level(event)
        role_category = self._extract_role_category(event)
        locale = self._extract_locale(event)

        # Create pending screening for rehire
        screening_request = ScreeningRequest(
            tenant_id=event.tenant_id,
            subject=subject,
            locale=locale,
            service_tier=service_tier,
            search_degree=search_degree,
            vigilance_level=vigilance_level,
            role_category=role_category,
            consent_token="",  # Requires new consent
            priority=self._extract_priority(event),
            metadata={
                "hris_event_id": str(event.event_id),
                "hris_employee_id": event.employee_id,
                "is_rehire": True,
                "rehire_initiated_at": event.received_at.isoformat(),
            },
        )

        # Store pending screening
        await self._event_store.save_pending_screening(
            tenant_id=event.tenant_id,
            employee_id=event.employee_id,
            request=screening_request,
        )

        # Create rehire lifecycle event if we have a subject
        if subject_id is not None and self._monitoring_service is not None:
            lifecycle_event = LifecycleEvent(
                subject_id=subject_id,
                tenant_id=event.tenant_id,
                event_type=LifecycleEventType.REHIRE,
                description=f"Rehire initiated for {subject.full_name or event.employee_id}",
                new_role_category=role_category,
                new_locale=locale if locale != self.config.default_locale else None,
                new_vigilance_level=vigilance_level,
                metadata={
                    "hris_event_id": str(event.event_id),
                    "employee_id": event.employee_id,
                },
            )
            try:
                config = await self._monitoring_service.handle_lifecycle_event(lifecycle_event)
                if config is not None:
                    result.monitoring_config_id = config.config_id
            except Exception as e:
                logger.error(
                    "Failed to process rehire lifecycle event",
                    subject_id=str(subject_id),
                    error=str(e),
                )
                result.details["lifecycle_error"] = str(e)

        result.subject_id = subject_id
        result.screening_id = screening_request.screening_id
        result.status = ProcessingStatus.SUCCESS
        result.action = ProcessingAction.REHIRE_PROCESSED
        result.details = {
            "screening_id": str(screening_request.screening_id),
            "is_rehire": True,
            "existing_subject": subject_id is not None,
            "status": "pending_consent",
        }

        logger.info(
            "Rehire processed - pending consent",
            screening_id=str(screening_request.screening_id),
            tenant_id=str(event.tenant_id),
            employee_id=event.employee_id,
            existing_subject=subject_id is not None,
        )

        return result

    # =============================================================================
    # Helper Methods
    # =============================================================================

    def _extract_subject_identifiers(self, event: HRISEvent) -> SubjectIdentifiers:
        """Extract subject identifiers from HRIS event data."""
        data = event.event_data

        # Try various field name conventions
        full_name = (
            data.get("full_name")
            or data.get("fullName")
            or data.get("name")
            or f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
            or f"{data.get('firstName', '')} {data.get('lastName', '')}".strip()
        )

        dob_str = data.get("date_of_birth") or data.get("dateOfBirth") or data.get("dob")
        date_of_birth = None
        if dob_str:
            try:
                from datetime import date

                if isinstance(dob_str, str):
                    date_of_birth = date.fromisoformat(dob_str)
                elif isinstance(dob_str, date):
                    date_of_birth = dob_str
            except ValueError:
                pass

        # Build kwargs with only non-None values to avoid overriding defaults
        kwargs: dict[str, Any] = {}

        if full_name:
            kwargs["full_name"] = full_name
        if date_of_birth:
            kwargs["date_of_birth"] = date_of_birth

        email = data.get("email") or data.get("work_email") or data.get("workEmail")
        if email:
            kwargs["email"] = email

        phone = data.get("phone") or data.get("work_phone") or data.get("workPhone")
        if phone:
            kwargs["phone"] = phone

        address = data.get("address") or data.get("street_address")
        if address:
            kwargs["street_address"] = address

        city = data.get("city")
        if city:
            kwargs["city"] = city

        state = data.get("state") or data.get("province")
        if state:
            kwargs["state"] = state

        country = data.get("country")
        if country:
            kwargs["country"] = country

        return SubjectIdentifiers(**kwargs)

    def _extract_service_tier(self, event: HRISEvent) -> ServiceTier:
        """Extract service tier from event data."""
        tier_str = (
            event.event_data.get("service_tier")
            or event.event_data.get("serviceTier")
            or event.event_data.get("tier")
        )
        if tier_str:
            try:
                return ServiceTier(tier_str.lower())
            except ValueError:
                pass
        return self.config.default_service_tier

    def _extract_search_degree(self, event: HRISEvent) -> SearchDegree:
        """Extract search degree from event data."""
        degree_str = (
            event.event_data.get("search_degree")
            or event.event_data.get("searchDegree")
            or event.event_data.get("degree")
        )
        if degree_str:
            try:
                # Normalize to lowercase for enum value matching
                return SearchDegree(degree_str.lower())
            except ValueError:
                pass
        return self.config.default_search_degree

    def _extract_vigilance_level(self, event: HRISEvent) -> VigilanceLevel:
        """Extract vigilance level from event data."""
        level_str = (
            event.event_data.get("vigilance_level")
            or event.event_data.get("vigilanceLevel")
            or event.event_data.get("monitoring_level")
        )
        if level_str:
            try:
                # Normalize to lowercase for enum value matching
                return VigilanceLevel(level_str.lower())
            except ValueError:
                pass
        return self.config.default_vigilance_level

    def _extract_role_category(self, event: HRISEvent) -> RoleCategory:
        """Extract role category from event data."""
        role_str = (
            event.event_data.get("role_category")
            or event.event_data.get("roleCategory")
            or event.event_data.get("job_category")
            or event.event_data.get("jobCategory")
        )
        if role_str:
            try:
                return RoleCategory(role_str.lower())
            except ValueError:
                pass

        # Try to infer from job title
        job_title = (
            event.event_data.get("job_title")
            or event.event_data.get("jobTitle")
            or event.event_data.get("title")
            or ""
        ).lower()

        # Basic title-based inference
        if any(word in job_title for word in ["executive", "director", "vp", "chief", "president"]):
            return RoleCategory.EXECUTIVE
        if any(word in job_title for word in ["finance", "accountant", "controller", "treasury"]):
            return RoleCategory.FINANCIAL
        if any(word in job_title for word in ["security", "guard", "protection"]):
            return RoleCategory.SECURITY
        if any(word in job_title for word in ["government", "federal", "public"]):
            return RoleCategory.GOVERNMENT
        if any(word in job_title for word in ["doctor", "nurse", "medical", "healthcare", "health"]):
            return RoleCategory.HEALTHCARE

        return self.config.default_role_category

    def _extract_locale(self, event: HRISEvent) -> Locale:
        """Extract locale from event data."""
        locale_str = (
            event.event_data.get("locale")
            or event.event_data.get("country")
            or event.event_data.get("work_country")
        )
        if locale_str:
            try:
                return Locale(locale_str.upper())
            except ValueError:
                pass
        return self.config.default_locale

    def _extract_priority(self, event: HRISEvent) -> ScreeningPriority:
        """Extract screening priority from event data."""
        priority_str = (
            event.event_data.get("priority")
            or event.event_data.get("screening_priority")
        )
        if priority_str:
            try:
                return ScreeningPriority(priority_str.lower())
            except ValueError:
                pass
        return ScreeningPriority.NORMAL

    def _build_position_change_description(self, event: HRISEvent) -> str:
        """Build a description for a position change event."""
        data = event.event_data
        old_title = data.get("previous_title") or data.get("old_title") or "previous role"
        new_title = data.get("new_title") or data.get("title") or data.get("job_title") or "new role"
        return f"Position changed from {old_title} to {new_title}"

    def _build_termination_description(self, event: HRISEvent) -> str:
        """Build a description for a termination event."""
        data = event.event_data
        reason = data.get("termination_reason") or data.get("reason") or "not specified"
        return f"Employment terminated - reason: {reason}"

    def get_statistics(self) -> dict[str, Any]:
        """Get event processing statistics.

        Returns:
            Dictionary with processing counts by event type.
        """
        return {
            "events_processed": dict(self._processed_count),
            "total_processed": sum(self._processed_count.values()),
        }


# =============================================================================
# Factory Function
# =============================================================================


def create_event_processor(
    config: ProcessorConfig | None = None,
    screening_service: ScreeningServiceProtocol | None = None,
    monitoring_service: MonitoringServiceProtocol | None = None,
    vigilance_service: VigilanceServiceProtocol | None = None,
    event_store: EventStore | None = None,
) -> HRISEventProcessor:
    """Create an HRIS event processor.

    Args:
        config: Processor configuration.
        screening_service: Service for initiating screenings.
        monitoring_service: Service for managing monitoring.
        vigilance_service: Service for vigilance level management.
        event_store: Store for pending events and mappings.

    Returns:
        Configured HRISEventProcessor instance.
    """
    return HRISEventProcessor(
        config=config,
        screening_service=screening_service,
        monitoring_service=monitoring_service,
        vigilance_service=vigilance_service,
        event_store=event_store,
    )
