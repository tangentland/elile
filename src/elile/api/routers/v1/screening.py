"""Screening API endpoints.

This module provides REST API endpoints for screening operations:
- POST /v1/screenings - Initiate a new screening
- GET /v1/screenings/{screening_id} - Get screening status/results
- DELETE /v1/screenings/{screening_id} - Cancel a screening
"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from elile.api.dependencies import get_request_context
from elile.api.schemas.errors import APIError, ErrorCode
from elile.api.schemas.screening import (
    ScreeningCancelResponse,
    ScreeningCreateRequest,
    ScreeningListResponse,
    ScreeningResponse,
    screening_response_from_result,
)
from elile.core.context import RequestContext
from elile.entity.types import SubjectIdentifiers
from elile.screening import (
    ScreeningOrchestrator,
    ScreeningRequest,
    ScreeningResult,
    ScreeningStateManager,
    ScreeningStatus,
    create_screening_orchestrator,
    create_state_manager,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/screenings", tags=["screening"])


# =============================================================================
# Dependencies
# =============================================================================


def get_orchestrator() -> ScreeningOrchestrator:
    """Get the screening orchestrator instance.

    In production, this would be configured with proper dependencies.
    """
    return create_screening_orchestrator()


def get_state_manager() -> ScreeningStateManager:
    """Get the screening state manager instance.

    In production, this would use a persistent store (Redis/database).
    """
    # Use a module-level singleton for in-memory state
    # In production, this would be a distributed store
    return _get_global_state_manager()


# Simple in-memory singleton for state manager
_state_manager: ScreeningStateManager | None = None


def _get_global_state_manager() -> ScreeningStateManager:
    """Get or create global state manager singleton."""
    global _state_manager
    if _state_manager is None:
        _state_manager = create_state_manager()
    return _state_manager


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/",
    response_model=ScreeningResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Initiate a new screening",
    description="""
    Start a new background screening investigation.

    The screening will be processed asynchronously. Use the returned
    screening_id to poll for status updates.

    **Required fields:**
    - subject.full_name: Subject's full legal name
    - consent_token: Proof of subject consent

    **Service Tiers:**
    - standard: Core data sources, automated analysis
    - enhanced: Premium data sources, analyst review

    **Search Degrees:**
    - D1: Subject-only investigation
    - D2: First-degree connections
    - D3: Extended network (requires Enhanced tier)
    """,
    responses={
        202: {"description": "Screening initiated successfully"},
        400: {"model": APIError, "description": "Invalid request"},
        403: {"model": APIError, "description": "Compliance blocked"},
        422: {"model": APIError, "description": "Validation error"},
    },
)
async def initiate_screening(
    request: ScreeningCreateRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    orchestrator: Annotated[ScreeningOrchestrator, Depends(get_orchestrator)],
    state_manager: Annotated[ScreeningStateManager, Depends(get_state_manager)],
) -> ScreeningResponse:
    """Initiate a new background screening.

    This endpoint accepts a screening request and begins asynchronous processing.
    The screening ID can be used to check status and retrieve results.

    Args:
        request: Screening creation request.
        ctx: Request context with tenant and actor info.
        orchestrator: Screening orchestrator.
        state_manager: State manager for tracking.

    Returns:
        ScreeningResponse with screening_id and initial status.

    Raises:
        HTTPException: On validation or compliance errors.
    """
    request_time = datetime.now(UTC)

    logger.info(
        "Initiating screening",
        tenant_id=str(ctx.tenant_id),
        subject_name=request.subject.full_name,
        locale=request.locale.value,
        tier=request.service_tier.value,
    )

    # Convert API request to domain model
    subject = SubjectIdentifiers(
        full_name=request.subject.full_name,
        first_name=request.subject.first_name,
        last_name=request.subject.last_name,
        middle_name=request.subject.middle_name,
        date_of_birth=_parse_date(request.subject.date_of_birth),
        ssn=request.subject.ssn,
        email=request.subject.email,
        phone=request.subject.phone,
        street_address=(
            request.subject.current_address.street_address
            if request.subject.current_address
            else None
        ),
        city=request.subject.current_address.city if request.subject.current_address else None,
        state=request.subject.current_address.state if request.subject.current_address else None,
        postal_code=(
            request.subject.current_address.postal_code if request.subject.current_address else None
        ),
    )

    screening_request = ScreeningRequest(
        tenant_id=ctx.tenant_id,
        subject=subject,
        locale=request.locale,
        service_tier=request.service_tier,
        search_degree=request.search_degree,
        vigilance_level=request.vigilance_level,
        role_category=request.role_category,
        consent_token=request.consent_token,
        report_types=request.report_types,
        priority=request.priority,
        requested_by=ctx.actor_id,
        metadata=request.metadata,
    )

    # Create initial state
    await state_manager.create_state(screening_request.screening_id, ctx.tenant_id)

    try:
        # Execute screening (synchronous for now, async background task in production)
        result = await orchestrator.execute_screening(screening_request, ctx)

        # Update state with result
        if result.status == ScreeningStatus.COMPLETE:
            await state_manager.complete_screening(screening_request.screening_id, result)
        elif result.status in [ScreeningStatus.FAILED, ScreeningStatus.COMPLIANCE_BLOCKED]:
            state = await state_manager.load_state(screening_request.screening_id)
            if state:
                state.status = result.status
                await state_manager.save_state(screening_request.screening_id, state)

        # Store result for later retrieval
        _store_result(screening_request.screening_id, result)

        logger.info(
            "Screening completed",
            screening_id=str(screening_request.screening_id),
            status=result.status.value,
            risk_score=result.risk_score,
        )

        return screening_response_from_result(result, request_time)

    except Exception as e:
        logger.error(
            "Screening failed",
            screening_id=str(screening_request.screening_id),
            error=str(e),
        )

        # Update state with failure
        state = await state_manager.load_state(screening_request.screening_id)
        if state:
            state.status = ScreeningStatus.FAILED
            await state_manager.save_state(screening_request.screening_id, state)

        # Still return the result (with failed status)
        result = ScreeningResult(
            screening_id=screening_request.screening_id,
            tenant_id=ctx.tenant_id,
            status=ScreeningStatus.FAILED,
            error_message=str(e),
            error_code="EXECUTION_ERROR",
            started_at=request_time,
            completed_at=datetime.now(UTC),
        )

        return screening_response_from_result(result, request_time)


@router.get(
    "/{screening_id}",
    response_model=ScreeningResponse,
    summary="Get screening status and results",
    description="""
    Retrieve the current status and results of a screening.

    Poll this endpoint to check screening progress and retrieve
    results once complete.
    """,
    responses={
        200: {"description": "Screening details"},
        404: {"model": APIError, "description": "Screening not found"},
    },
)
async def get_screening(
    screening_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    state_manager: Annotated[ScreeningStateManager, Depends(get_state_manager)],
) -> ScreeningResponse:
    """Get screening status and results.

    Args:
        screening_id: The screening identifier.
        ctx: Request context with tenant info.
        state_manager: State manager for retrieval.

    Returns:
        ScreeningResponse with current status and results.

    Raises:
        HTTPException: If screening not found or unauthorized.
    """
    logger.debug(
        "Getting screening",
        screening_id=str(screening_id),
        tenant_id=str(ctx.tenant_id),
    )

    # Check if screening exists in state
    state = await state_manager.load_state(screening_id)

    if state is None:
        # Check stored results
        result = _get_stored_result(screening_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error_code": ErrorCode.NOT_FOUND.value,
                    "message": f"Screening not found: {screening_id}",
                    "request_id": str(ctx.request_id),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

        # Verify tenant access
        if result.tenant_id and result.tenant_id != ctx.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": ErrorCode.FORBIDDEN.value,
                    "message": "Access denied to this screening",
                    "request_id": str(ctx.request_id),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

        return screening_response_from_result(result)

    # Verify tenant access from state
    if state.tenant_id != ctx.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": ErrorCode.FORBIDDEN.value,
                "message": "Access denied to this screening",
                "request_id": str(ctx.request_id),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    # Get stored result if available
    result = _get_stored_result(screening_id)
    if result:
        return screening_response_from_result(result)

    # Return state-based response (for in-progress screenings)
    return ScreeningResponse(
        screening_id=screening_id,
        status=state.status,
        created_at=state.created_at,
        updated_at=state.updated_at,
        progress_percent=int(state.progress_percent),
        current_phase=state.current_phase.value if state.current_phase else None,
    )


@router.delete(
    "/{screening_id}",
    response_model=ScreeningCancelResponse,
    summary="Cancel a screening",
    description="""
    Cancel a screening that is in progress.

    Screenings that are already complete or failed cannot be cancelled.
    """,
    responses={
        200: {"description": "Screening cancelled"},
        404: {"model": APIError, "description": "Screening not found"},
        409: {"model": APIError, "description": "Screening cannot be cancelled"},
    },
)
async def cancel_screening(
    screening_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    state_manager: Annotated[ScreeningStateManager, Depends(get_state_manager)],
) -> ScreeningCancelResponse:
    """Cancel a screening in progress.

    Args:
        screening_id: The screening identifier.
        ctx: Request context with tenant info.
        state_manager: State manager for updates.

    Returns:
        ScreeningCancelResponse confirming cancellation.

    Raises:
        HTTPException: If screening not found or cannot be cancelled.
    """
    logger.info(
        "Cancelling screening",
        screening_id=str(screening_id),
        tenant_id=str(ctx.tenant_id),
    )

    # Get current state
    state = await state_manager.load_state(screening_id)

    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "message": f"Screening not found: {screening_id}",
                "request_id": str(ctx.request_id),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    # Verify tenant access
    if state.tenant_id != ctx.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": ErrorCode.FORBIDDEN.value,
                "message": "Access denied to this screening",
                "request_id": str(ctx.request_id),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    # Check if cancellation is allowed
    non_cancellable = {
        ScreeningStatus.COMPLETE,
        ScreeningStatus.FAILED,
        ScreeningStatus.CANCELLED,
        ScreeningStatus.COMPLIANCE_BLOCKED,
    }

    if state.status in non_cancellable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "CANNOT_CANCEL",
                "message": f"Cannot cancel screening in status: {state.status.value}",
                "request_id": str(ctx.request_id),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    # Cancel the screening
    await state_manager.cancel_screening(screening_id, "Cancelled by user")

    # Update stored result if exists
    result = _get_stored_result(screening_id)
    if result:
        result.status = ScreeningStatus.CANCELLED
        result.completed_at = datetime.now(UTC)
        result.error_message = "Cancelled by user"
        _store_result(screening_id, result)

    logger.info(
        "Screening cancelled",
        screening_id=str(screening_id),
    )

    return ScreeningCancelResponse(
        screening_id=screening_id,
        status=ScreeningStatus.CANCELLED,
        cancelled_at=datetime.now(UTC),
    )


@router.get(
    "/",
    response_model=ScreeningListResponse,
    summary="List screenings",
    description="""
    List screenings for the current tenant.

    Results are paginated and can be filtered by status.
    """,
    responses={
        200: {"description": "List of screenings"},
    },
)
async def list_screenings(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    status_filter: Annotated[
        ScreeningStatus | None,
        Query(alias="status", description="Filter by status"),
    ] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> ScreeningListResponse:
    """List screenings for the current tenant.

    Args:
        ctx: Request context with tenant info.
        status_filter: Optional status filter.
        page: Page number (1-indexed).
        page_size: Number of items per page.

    Returns:
        ScreeningListResponse with paginated results.
    """
    logger.debug(
        "Listing screenings",
        tenant_id=str(ctx.tenant_id),
        status_filter=status_filter.value if status_filter else None,
        page=page,
        page_size=page_size,
    )

    # Get all screenings for tenant from stored results
    tenant_screenings = _get_tenant_results(ctx.tenant_id)

    # Filter by status
    if status_filter:
        tenant_screenings = [s for s in tenant_screenings if s.status == status_filter]

    # Sort by started_at descending
    tenant_screenings.sort(key=lambda s: s.started_at or datetime.min, reverse=True)

    # Paginate
    total = len(tenant_screenings)
    start = (page - 1) * page_size
    end = start + page_size
    page_results = tenant_screenings[start:end]

    # Convert to response
    items = [screening_response_from_result(r) for r in page_results]

    return ScreeningListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=end < total,
    )


# =============================================================================
# Helpers
# =============================================================================


def _parse_date(date_str: str | None) -> str | None:
    """Parse date string, returning None if invalid or empty."""
    if not date_str:
        return None
    return date_str


# Simple in-memory result storage (replace with database in production)
# Use string keys to avoid uuid_utils.UUID vs uuid.UUID type mismatch
_stored_results: dict[str, ScreeningResult] = {}


def _store_result(screening_id: UUID, result: ScreeningResult) -> None:
    """Store a screening result for later retrieval."""
    # Convert to string to ensure consistent key type
    key = str(screening_id)
    _stored_results[key] = result


def _get_stored_result(screening_id: UUID) -> ScreeningResult | None:
    """Get a stored screening result."""
    # Convert to string to match storage key type
    key = str(screening_id)
    return _stored_results.get(key)


def _get_tenant_results(tenant_id: UUID) -> list[ScreeningResult]:
    """Get all stored results for a tenant."""
    # Convert tenant_id to string for comparison
    tenant_str = str(tenant_id)
    return [r for r in _stored_results.values() if str(r.tenant_id) == tenant_str]
