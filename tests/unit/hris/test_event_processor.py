"""Unit tests for the HRIS Event Processor."""

from datetime import UTC, datetime
from uuid import UUID, uuid7

import pytest

from elile.agent.state import SearchDegree, ServiceTier, VigilanceLevel
from elile.compliance.types import Locale, RoleCategory
from elile.hris.event_processor import (
    HRISEventProcessor,
    InMemoryEventStore,
    ProcessingAction,
    ProcessingStatus,
    ProcessorConfig,
    create_event_processor,
)
from elile.hris.gateway import HRISEvent, HRISEventType, HRISPlatform
from elile.screening.types import ScreeningRequest

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tenant_id() -> UUID:
    """Test tenant ID."""
    return uuid7()


@pytest.fixture
def employee_id() -> str:
    """Test employee ID."""
    return "EMP-001"


@pytest.fixture
def event_store() -> InMemoryEventStore:
    """In-memory event store."""
    return InMemoryEventStore()


@pytest.fixture
def processor(event_store: InMemoryEventStore) -> HRISEventProcessor:
    """HRIS event processor with default config."""
    return HRISEventProcessor(event_store=event_store)


@pytest.fixture
def processor_config() -> ProcessorConfig:
    """Custom processor config."""
    return ProcessorConfig(
        default_service_tier=ServiceTier.ENHANCED,
        default_search_degree=SearchDegree.D2,
        default_vigilance_level=VigilanceLevel.V2,
        default_locale=Locale.US,
        default_role_category=RoleCategory.STANDARD,
    )


def create_hris_event(
    tenant_id: UUID,
    employee_id: str,
    event_type: HRISEventType,
    event_data: dict | None = None,
) -> HRISEvent:
    """Helper to create HRIS events."""
    return HRISEvent(
        event_id=uuid7(),
        tenant_id=tenant_id,
        employee_id=employee_id,
        event_type=event_type,
        platform=HRISPlatform.WORKDAY,
        raw_payload=event_data or {},
        event_data=event_data or {},
        received_at=datetime.now(UTC),
    )


# =============================================================================
# Factory Tests
# =============================================================================


class TestCreateEventProcessor:
    """Tests for create_event_processor factory function."""

    def test_create_with_defaults(self) -> None:
        """Should create processor with default configuration."""
        processor = create_event_processor()

        assert processor is not None
        assert processor.config is not None
        assert processor.config.default_service_tier == ServiceTier.STANDARD
        assert processor.config.auto_start_screening is True

    def test_create_with_custom_config(self, processor_config: ProcessorConfig) -> None:
        """Should create processor with custom configuration."""
        processor = create_event_processor(config=processor_config)

        assert processor.config.default_service_tier == ServiceTier.ENHANCED
        assert processor.config.default_search_degree == SearchDegree.D2

    def test_create_with_event_store(self, event_store: InMemoryEventStore) -> None:
        """Should create processor with custom event store."""
        processor = create_event_processor(event_store=event_store)

        assert processor._event_store is event_store


# =============================================================================
# Hire Initiated Event Tests
# =============================================================================


class TestHireInitiatedEvent:
    """Tests for hire.initiated event handling."""

    @pytest.mark.asyncio
    async def test_handle_hire_creates_pending_screening(
        self,
        processor: HRISEventProcessor,
        tenant_id: UUID,
        employee_id: str,
    ) -> None:
        """Should create a pending screening request."""
        event = create_hris_event(
            tenant_id=tenant_id,
            employee_id=employee_id,
            event_type=HRISEventType.HIRE_INITIATED,
            event_data={
                "full_name": "John Doe",
                "date_of_birth": "1990-01-15",
                "email": "john.doe@example.com",
            },
        )

        result = await processor.process_event(event)

        assert result.status == ProcessingStatus.SUCCESS
        assert result.action == ProcessingAction.SCREENING_INITIATED
        assert result.screening_id is not None
        assert result.details["status"] == "pending_consent"

    @pytest.mark.asyncio
    async def test_hire_extracts_subject_identifiers(
        self,
        processor: HRISEventProcessor,
        event_store: InMemoryEventStore,
        tenant_id: UUID,
        employee_id: str,
    ) -> None:
        """Should extract subject identifiers from event data."""
        event = create_hris_event(
            tenant_id=tenant_id,
            employee_id=employee_id,
            event_type=HRISEventType.HIRE_INITIATED,
            event_data={
                "firstName": "Jane",
                "lastName": "Smith",
                "dateOfBirth": "1985-03-20",
                "work_email": "jane.smith@company.com",
            },
        )

        await processor.process_event(event)

        # Verify pending screening has correct subject
        pending = await event_store.get_pending_screening(tenant_id, employee_id)
        assert pending is not None
        assert pending.subject.full_name == "Jane Smith"
        assert pending.subject.email == "jane.smith@company.com"

    @pytest.mark.asyncio
    async def test_hire_uses_default_config_values(
        self,
        processor: HRISEventProcessor,
        event_store: InMemoryEventStore,
        tenant_id: UUID,
        employee_id: str,
    ) -> None:
        """Should use default config values when not specified in event."""
        event = create_hris_event(
            tenant_id=tenant_id,
            employee_id=employee_id,
            event_type=HRISEventType.HIRE_INITIATED,
            event_data={"full_name": "Test User"},
        )

        await processor.process_event(event)

        pending = await event_store.get_pending_screening(tenant_id, employee_id)
        assert pending is not None
        assert pending.service_tier == ServiceTier.STANDARD
        assert pending.search_degree == SearchDegree.D1
        assert pending.vigilance_level == VigilanceLevel.V1

    @pytest.mark.asyncio
    async def test_hire_extracts_custom_config_from_event(
        self,
        processor: HRISEventProcessor,
        event_store: InMemoryEventStore,
        tenant_id: UUID,
        employee_id: str,
    ) -> None:
        """Should extract custom configuration from event data."""
        event = create_hris_event(
            tenant_id=tenant_id,
            employee_id=employee_id,
            event_type=HRISEventType.HIRE_INITIATED,
            event_data={
                "full_name": "Executive Hire",
                "service_tier": "enhanced",
                "search_degree": "D2",
                "vigilance_level": "V2",
                "role_category": "executive",
            },
        )

        await processor.process_event(event)

        pending = await event_store.get_pending_screening(tenant_id, employee_id)
        assert pending is not None
        assert pending.service_tier == ServiceTier.ENHANCED
        assert pending.search_degree == SearchDegree.D2
        assert pending.vigilance_level == VigilanceLevel.V2
        assert pending.role_category == RoleCategory.EXECUTIVE

    @pytest.mark.asyncio
    async def test_hire_infers_role_from_job_title(
        self,
        processor: HRISEventProcessor,
        event_store: InMemoryEventStore,
        tenant_id: UUID,
        employee_id: str,
    ) -> None:
        """Should infer role category from job title."""
        event = create_hris_event(
            tenant_id=tenant_id,
            employee_id=employee_id,
            event_type=HRISEventType.HIRE_INITIATED,
            event_data={
                "full_name": "John Finance",
                "job_title": "Senior Finance Manager",
            },
        )

        await processor.process_event(event)

        pending = await event_store.get_pending_screening(tenant_id, employee_id)
        assert pending is not None
        assert pending.role_category == RoleCategory.FINANCIAL


# =============================================================================
# Consent Granted Event Tests
# =============================================================================


class TestConsentGrantedEvent:
    """Tests for consent.granted event handling."""

    @pytest.mark.asyncio
    async def test_consent_starts_screening(
        self,
        processor: HRISEventProcessor,
        event_store: InMemoryEventStore,  # noqa: ARG002
        tenant_id: UUID,
        employee_id: str,
    ) -> None:
        """Should start screening when consent is granted."""
        # First create pending screening
        hire_event = create_hris_event(
            tenant_id=tenant_id,
            employee_id=employee_id,
            event_type=HRISEventType.HIRE_INITIATED,
            event_data={"full_name": "John Doe"},
        )
        hire_result = await processor.process_event(hire_event)

        # Now grant consent
        consent_event = create_hris_event(
            tenant_id=tenant_id,
            employee_id=employee_id,
            event_type=HRISEventType.CONSENT_GRANTED,
            event_data={"consent_token": "consent-abc123"},
        )
        consent_result = await processor.process_event(consent_event)

        assert consent_result.status == ProcessingStatus.SUCCESS
        assert consent_result.action == ProcessingAction.SCREENING_STARTED
        assert consent_result.screening_id == hire_result.screening_id
        assert consent_result.details["consent_token"] == "consent-abc123"

    @pytest.mark.asyncio
    async def test_consent_removes_pending_screening(
        self,
        processor: HRISEventProcessor,
        event_store: InMemoryEventStore,
        tenant_id: UUID,
        employee_id: str,
    ) -> None:
        """Should remove pending screening after consent."""
        # Create pending screening
        hire_event = create_hris_event(
            tenant_id=tenant_id,
            employee_id=employee_id,
            event_type=HRISEventType.HIRE_INITIATED,
            event_data={"full_name": "John Doe"},
        )
        await processor.process_event(hire_event)

        # Verify pending exists
        assert await event_store.get_pending_screening(tenant_id, employee_id) is not None

        # Grant consent
        consent_event = create_hris_event(
            tenant_id=tenant_id,
            employee_id=employee_id,
            event_type=HRISEventType.CONSENT_GRANTED,
        )
        await processor.process_event(consent_event)

        # Verify pending removed
        assert await event_store.get_pending_screening(tenant_id, employee_id) is None

    @pytest.mark.asyncio
    async def test_consent_without_pending_is_skipped(
        self,
        processor: HRISEventProcessor,
        tenant_id: UUID,
        employee_id: str,
    ) -> None:
        """Should skip if no pending screening exists."""
        consent_event = create_hris_event(
            tenant_id=tenant_id,
            employee_id=employee_id,
            event_type=HRISEventType.CONSENT_GRANTED,
        )

        result = await processor.process_event(consent_event)

        assert result.status == ProcessingStatus.SKIPPED
        assert result.action == ProcessingAction.NO_ACTION
        assert "No pending screening" in result.details["reason"]

    @pytest.mark.asyncio
    async def test_consent_uses_event_consent_reference(
        self,
        processor: HRISEventProcessor,
        event_store: InMemoryEventStore,  # noqa: ARG002
        tenant_id: UUID,
        employee_id: str,
    ) -> None:
        """Should use consent_reference from event if available."""
        # Create pending screening
        hire_event = create_hris_event(
            tenant_id=tenant_id,
            employee_id=employee_id,
            event_type=HRISEventType.HIRE_INITIATED,
            event_data={"full_name": "John Doe"},
        )
        await processor.process_event(hire_event)

        # Create consent event with consent_reference
        consent_event = HRISEvent(
            event_id=uuid7(),
            tenant_id=tenant_id,
            employee_id=employee_id,
            event_type=HRISEventType.CONSENT_GRANTED,
            platform=HRISPlatform.WORKDAY,
            raw_payload={},
            event_data={},
            consent_reference="ref-xyz789",
            received_at=datetime.now(UTC),
        )

        result = await processor.process_event(consent_event)

        assert result.details["consent_token"] == "ref-xyz789"


# =============================================================================
# Position Changed Event Tests
# =============================================================================


class TestPositionChangedEvent:
    """Tests for position.changed event handling."""

    @pytest.mark.asyncio
    async def test_position_change_creates_lifecycle_event(
        self,
        processor: HRISEventProcessor,
        event_store: InMemoryEventStore,
        tenant_id: UUID,
        employee_id: str,
    ) -> None:
        """Should create lifecycle event for position change."""
        # First create a subject mapping
        subject_id = uuid7()
        await event_store.save_employee_mapping(tenant_id, employee_id, subject_id)

        event = create_hris_event(
            tenant_id=tenant_id,
            employee_id=employee_id,
            event_type=HRISEventType.POSITION_CHANGED,
            event_data={
                "previous_title": "Software Engineer",
                "new_title": "Director of Engineering",
                "role_category": "executive",
            },
        )

        result = await processor.process_event(event)

        assert result.status == ProcessingStatus.SUCCESS
        assert result.action == ProcessingAction.LIFECYCLE_EVENT_CREATED
        assert result.subject_id == subject_id
        assert result.details["new_role_category"] == "executive"

    @pytest.mark.asyncio
    async def test_position_change_without_mapping_is_skipped(
        self,
        processor: HRISEventProcessor,
        tenant_id: UUID,
        employee_id: str,
    ) -> None:
        """Should skip if no subject mapping exists."""
        event = create_hris_event(
            tenant_id=tenant_id,
            employee_id=employee_id,
            event_type=HRISEventType.POSITION_CHANGED,
            event_data={"new_title": "Manager"},
        )

        result = await processor.process_event(event)

        assert result.status == ProcessingStatus.SKIPPED
        assert "No subject mapping" in result.details["reason"]


# =============================================================================
# Employee Terminated Event Tests
# =============================================================================


class TestEmployeeTerminatedEvent:
    """Tests for employee.terminated event handling."""

    @pytest.mark.asyncio
    async def test_termination_creates_lifecycle_event(
        self,
        processor: HRISEventProcessor,
        event_store: InMemoryEventStore,
        tenant_id: UUID,
        employee_id: str,
    ) -> None:
        """Should create termination lifecycle event."""
        subject_id = uuid7()
        await event_store.save_employee_mapping(tenant_id, employee_id, subject_id)

        event = create_hris_event(
            tenant_id=tenant_id,
            employee_id=employee_id,
            event_type=HRISEventType.EMPLOYEE_TERMINATED,
            event_data={"termination_reason": "resignation"},
        )

        result = await processor.process_event(event)

        assert result.status == ProcessingStatus.SUCCESS
        assert result.action == ProcessingAction.MONITORING_TERMINATED
        assert result.subject_id == subject_id

    @pytest.mark.asyncio
    async def test_termination_without_mapping_is_skipped(
        self,
        processor: HRISEventProcessor,
        tenant_id: UUID,
        employee_id: str,
    ) -> None:
        """Should skip if no subject mapping exists."""
        event = create_hris_event(
            tenant_id=tenant_id,
            employee_id=employee_id,
            event_type=HRISEventType.EMPLOYEE_TERMINATED,
        )

        result = await processor.process_event(event)

        assert result.status == ProcessingStatus.SKIPPED


# =============================================================================
# Rehire Initiated Event Tests
# =============================================================================


class TestRehireInitiatedEvent:
    """Tests for rehire.initiated event handling."""

    @pytest.mark.asyncio
    async def test_rehire_creates_pending_screening(
        self,
        processor: HRISEventProcessor,
        event_store: InMemoryEventStore,  # noqa: ARG002
        tenant_id: UUID,
        employee_id: str,
    ) -> None:
        """Should create pending screening for rehire."""
        event = create_hris_event(
            tenant_id=tenant_id,
            employee_id=employee_id,
            event_type=HRISEventType.REHIRE_INITIATED,
            event_data={
                "full_name": "Former Employee",
                "role_category": "financial",
            },
        )

        result = await processor.process_event(event)

        assert result.status == ProcessingStatus.SUCCESS
        assert result.action == ProcessingAction.REHIRE_PROCESSED
        assert result.screening_id is not None
        assert result.details["is_rehire"] is True

    @pytest.mark.asyncio
    async def test_rehire_with_existing_subject(
        self,
        processor: HRISEventProcessor,
        event_store: InMemoryEventStore,
        tenant_id: UUID,
        employee_id: str,
    ) -> None:
        """Should recognize existing subject on rehire."""
        # Create existing subject mapping
        subject_id = uuid7()
        await event_store.save_employee_mapping(tenant_id, employee_id, subject_id)

        event = create_hris_event(
            tenant_id=tenant_id,
            employee_id=employee_id,
            event_type=HRISEventType.REHIRE_INITIATED,
            event_data={"full_name": "Returning Employee"},
        )

        result = await processor.process_event(event)

        assert result.status == ProcessingStatus.SUCCESS
        assert result.subject_id == subject_id
        assert result.details["existing_subject"] is True


# =============================================================================
# Unknown/Outbound Event Tests
# =============================================================================


class TestOtherEvents:
    """Tests for other event types."""

    @pytest.mark.asyncio
    async def test_outbound_events_are_skipped(
        self,
        processor: HRISEventProcessor,
        tenant_id: UUID,
        employee_id: str,
    ) -> None:
        """Should skip outbound event types."""
        event = create_hris_event(
            tenant_id=tenant_id,
            employee_id=employee_id,
            event_type=HRISEventType.SCREENING_COMPLETE,  # Outbound event
        )

        result = await processor.process_event(event)

        assert result.status == ProcessingStatus.SKIPPED
        assert result.action == ProcessingAction.NO_ACTION


# =============================================================================
# Statistics Tests
# =============================================================================


class TestStatistics:
    """Tests for event processing statistics."""

    @pytest.mark.asyncio
    async def test_get_statistics(
        self,
        processor: HRISEventProcessor,
        tenant_id: UUID,
        employee_id: str,  # noqa: ARG002
    ) -> None:
        """Should track processing statistics."""
        # Process several events
        for i in range(3):
            event = create_hris_event(
                tenant_id=tenant_id,
                employee_id=f"EMP-{i}",
                event_type=HRISEventType.HIRE_INITIATED,
                event_data={"full_name": f"Employee {i}"},
            )
            await processor.process_event(event)

        stats = processor.get_statistics()

        assert stats["total_processed"] == 3
        assert stats["events_processed"][HRISEventType.HIRE_INITIATED] == 3


# =============================================================================
# InMemoryEventStore Tests
# =============================================================================


class TestInMemoryEventStore:
    """Tests for the in-memory event store."""

    @pytest.mark.asyncio
    async def test_save_and_get_pending_screening(
        self,
        event_store: InMemoryEventStore,
        tenant_id: UUID,
    ) -> None:
        """Should save and retrieve pending screenings."""
        from elile.entity.types import SubjectIdentifiers
        from elile.screening.types import ScreeningRequest

        request = ScreeningRequest(
            tenant_id=tenant_id,
            subject=SubjectIdentifiers(full_name="Test User"),
            locale=Locale.US,
            consent_token="",
        )

        await event_store.save_pending_screening(tenant_id, "EMP-001", request)
        retrieved = await event_store.get_pending_screening(tenant_id, "EMP-001")

        assert retrieved is not None
        assert retrieved.screening_id == request.screening_id

    @pytest.mark.asyncio
    async def test_remove_pending_screening(
        self,
        event_store: InMemoryEventStore,
        tenant_id: UUID,
    ) -> None:
        """Should remove pending screenings."""
        from elile.entity.types import SubjectIdentifiers
        from elile.screening.types import ScreeningRequest

        request = ScreeningRequest(
            tenant_id=tenant_id,
            subject=SubjectIdentifiers(full_name="Test User"),
            locale=Locale.US,
            consent_token="",
        )

        await event_store.save_pending_screening(tenant_id, "EMP-001", request)
        removed = await event_store.remove_pending_screening(tenant_id, "EMP-001")

        assert removed is True
        assert await event_store.get_pending_screening(tenant_id, "EMP-001") is None

    @pytest.mark.asyncio
    async def test_employee_mapping(
        self,
        event_store: InMemoryEventStore,
        tenant_id: UUID,
    ) -> None:
        """Should save and retrieve employee mappings."""
        subject_id = uuid7()

        await event_store.save_employee_mapping(tenant_id, "EMP-001", subject_id)
        retrieved = await event_store.get_subject_id_by_employee_id(tenant_id, "EMP-001")

        assert retrieved == subject_id


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in event processing."""

    @pytest.mark.asyncio
    async def test_processing_error_is_captured(
        self,
        tenant_id: UUID,
        employee_id: str,
    ) -> None:
        """Should capture errors and return failed status."""
        # Create processor with a broken event store
        class BrokenStore(InMemoryEventStore):
            async def save_pending_screening(
                self,
                tenant_id: UUID,  # noqa: ARG002
                employee_id: str,  # noqa: ARG002
                request: ScreeningRequest,  # noqa: ARG002
            ) -> None:
                raise RuntimeError("Database connection failed")

        processor = HRISEventProcessor(event_store=BrokenStore())

        event = create_hris_event(
            tenant_id=tenant_id,
            employee_id=employee_id,
            event_type=HRISEventType.HIRE_INITIATED,
            event_data={"full_name": "Test User"},
        )

        result = await processor.process_event(event)

        assert result.status == ProcessingStatus.FAILED
        assert "Database connection failed" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_processing_time_is_tracked(
        self,
        processor: HRISEventProcessor,
        tenant_id: UUID,
        employee_id: str,
    ) -> None:
        """Should track processing time in milliseconds."""
        event = create_hris_event(
            tenant_id=tenant_id,
            employee_id=employee_id,
            event_type=HRISEventType.HIRE_INITIATED,
            event_data={"full_name": "Test User"},
        )

        result = await processor.process_event(event)

        assert result.processing_time_ms >= 0
        assert result.processed_at is not None
