"""Query executor for SAR loop investigation.

This module implements the query execution layer that bridges the investigation
domain (SearchQuery, QueryResult) with the provider infrastructure (RequestRouter,
RoutedRequest, RoutedResult). It handles batch execution, result collection,
and maintains execution statistics for the SAR loop.

The executor leverages the existing provider infrastructure for:
- Retry with exponential backoff
- Rate limiting per provider
- Circuit breaker protection
- Response caching
- Cost tracking
- Fallback provider selection
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from elile.agent.state import ServiceTier
from elile.compliance.types import Locale
from elile.core.logging import get_logger
from elile.entity.types import SubjectIdentifiers
from elile.investigation.query_planner import SearchQuery
from elile.providers.router import (
    FailureReason,
    RequestRouter,
    RoutedRequest,
    RoutedResult,
    RoutingConfig,
)

logger = get_logger(__name__)


class QueryStatus(str, Enum):
    """Status of a query execution."""

    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    NO_PROVIDER = "no_provider"
    SKIPPED = "skipped"  # Query was skipped (e.g., duplicate check)


@dataclass
class QueryResult:
    """Result from executing a single search query.

    Contains both the execution outcome and any data returned by the provider.
    Used by the SAR loop to assess findings and calculate confidence.
    """

    query_id: UUID
    provider_id: str | None
    check_type: str  # CheckType value
    status: QueryStatus

    # Results (populated on success)
    raw_data: dict[str, Any] | None = None
    normalized_data: dict[str, Any] | None = None
    findings_count: int = 0

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_ms: int | None = None

    # Execution details
    retry_count: int = 0
    cache_hit: bool = False

    # Error information
    error_message: str | None = None
    failure_reason: str | None = None

    @property
    def is_success(self) -> bool:
        """Check if query executed successfully."""
        return self.status == QueryStatus.SUCCESS

    @property
    def has_data(self) -> bool:
        """Check if query returned data."""
        return self.normalized_data is not None and len(self.normalized_data) > 0


@dataclass
class ExecutionSummary:
    """Summary of batch query execution.

    Provides aggregate statistics for SAR loop iteration assessment.
    """

    total_queries: int = 0
    successful: int = 0
    failed: int = 0
    timed_out: int = 0
    rate_limited: int = 0
    no_provider: int = 0
    skipped: int = 0
    cache_hits: int = 0

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    total_duration: timedelta = field(default_factory=lambda: timedelta(0))

    # Providers used
    providers_used: set[str] = field(default_factory=set)
    providers_failed: set[str] = field(default_factory=set)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_queries == 0:
            return 0.0
        return (self.successful / self.total_queries) * 100.0

    @property
    def is_complete(self) -> bool:
        """Check if all queries were executed (none pending)."""
        return (
            self.successful + self.failed + self.timed_out + self.rate_limited + self.no_provider + self.skipped
        ) == self.total_queries

    def update_from_result(self, result: QueryResult) -> None:
        """Update summary statistics from a query result."""
        if result.status == QueryStatus.SUCCESS:
            self.successful += 1
            if result.provider_id:
                self.providers_used.add(result.provider_id)
            if result.cache_hit:
                self.cache_hits += 1
        elif result.status == QueryStatus.FAILED:
            self.failed += 1
            if result.provider_id:
                self.providers_failed.add(result.provider_id)
        elif result.status == QueryStatus.TIMEOUT:
            self.timed_out += 1
            if result.provider_id:
                self.providers_failed.add(result.provider_id)
        elif result.status == QueryStatus.RATE_LIMITED:
            self.rate_limited += 1
        elif result.status == QueryStatus.NO_PROVIDER:
            self.no_provider += 1
        elif result.status == QueryStatus.SKIPPED:
            self.skipped += 1


class ExecutorConfig(BaseModel):
    """Configuration for query executor."""

    # Concurrency control
    max_concurrent_queries: int = Field(
        default=10,
        description="Maximum number of queries to execute concurrently",
        ge=1,
        le=100,
    )

    # Batch processing
    batch_size: int = Field(
        default=10,
        description="Number of queries per batch when using batched execution",
        ge=1,
        le=50,
    )

    # Priority handling
    process_by_priority: bool = Field(
        default=True,
        description="Execute high-priority queries first",
    )

    # Routing config (passed to RequestRouter)
    routing_config: RoutingConfig = Field(
        default_factory=RoutingConfig,
        description="Configuration for the underlying request router",
    )


class QueryExecutor:
    """Executes search queries against data providers.

    The QueryExecutor bridges the investigation domain with the provider
    infrastructure, converting SearchQuery objects to RoutedRequest objects
    and collecting results as QueryResult objects.

    It leverages the RequestRouter for:
    - Retry with exponential backoff
    - Rate limiting per provider
    - Circuit breaker protection
    - Response caching
    - Cost tracking
    - Fallback provider selection

    Usage:
        executor = QueryExecutor(router=router)

        # Execute a list of queries from QueryPlanner
        results, summary = await executor.execute_queries(
            queries=planned_queries,
            entity_id=subject_entity_id,
            tenant_id=tenant_id,
            locale=Locale.US,
        )

        # Check results
        for result in results:
            if result.is_success:
                process_findings(result.normalized_data)
    """

    def __init__(
        self,
        router: RequestRouter,
        config: ExecutorConfig | None = None,
    ):
        """Initialize query executor.

        Args:
            router: Request router for provider execution.
            config: Executor configuration.
        """
        self._router = router
        self._config = config or ExecutorConfig()

    async def execute_queries(
        self,
        queries: Sequence[SearchQuery],
        entity_id: UUID,
        tenant_id: UUID,
        locale: Locale,
        *,
        service_tier: ServiceTier = ServiceTier.STANDARD,
        screening_id: UUID | None = None,
    ) -> tuple[list[QueryResult], ExecutionSummary]:
        """Execute a batch of search queries.

        Executes queries through the RequestRouter with concurrency control.
        High-priority queries are executed first if process_by_priority is enabled.

        Args:
            queries: List of search queries from QueryPlanner.
            entity_id: ID of the entity being investigated.
            tenant_id: ID of the tenant making the request.
            locale: Locale for compliance filtering.
            service_tier: Service tier (affects provider availability).
            screening_id: Optional screening session ID.

        Returns:
            Tuple of (results list, execution summary).
        """
        summary = ExecutionSummary(
            total_queries=len(queries),
            started_at=datetime.now(UTC),
        )

        if not queries:
            summary.completed_at = datetime.now(UTC)
            return [], summary

        # Sort by priority if configured
        sorted_queries = self._sort_queries(list(queries))

        # Convert to routed requests
        routed_requests = [
            self._to_routed_request(
                query=q,
                entity_id=entity_id,
                tenant_id=tenant_id,
                locale=locale,
                service_tier=service_tier,
                screening_id=screening_id,
            )
            for q in sorted_queries
        ]

        # Execute in batches through the router
        all_results: list[QueryResult] = []
        batch_size = self._config.batch_size

        for i in range(0, len(sorted_queries), batch_size):
            batch_queries = sorted_queries[i : i + batch_size]
            batch_requests = routed_requests[i : i + batch_size]

            # Execute batch
            routed_results = await self._router.route_batch(batch_requests)

            # Convert results
            for query, routed_result in zip(batch_queries, routed_results, strict=True):
                query_result = self._to_query_result(query, routed_result)
                all_results.append(query_result)
                summary.update_from_result(query_result)

        summary.completed_at = datetime.now(UTC)
        summary.total_duration = summary.completed_at - summary.started_at

        logger.info(
            "Query execution complete",
            total=summary.total_queries,
            successful=summary.successful,
            failed=summary.failed,
            cache_hits=summary.cache_hits,
            success_rate=f"{summary.success_rate:.1f}%",
            duration_ms=int(summary.total_duration.total_seconds() * 1000),
        )

        return all_results, summary

    async def execute_single(
        self,
        query: SearchQuery,
        entity_id: UUID,
        tenant_id: UUID,
        locale: Locale,
        *,
        service_tier: ServiceTier = ServiceTier.STANDARD,
        screening_id: UUID | None = None,
    ) -> QueryResult:
        """Execute a single search query.

        Convenience method for executing a single query.

        Args:
            query: Search query to execute.
            entity_id: ID of the entity being investigated.
            tenant_id: ID of the tenant making the request.
            locale: Locale for compliance filtering.
            service_tier: Service tier (affects provider availability).
            screening_id: Optional screening session ID.

        Returns:
            Query result.
        """
        results, _ = await self.execute_queries(
            queries=[query],
            entity_id=entity_id,
            tenant_id=tenant_id,
            locale=locale,
            service_tier=service_tier,
            screening_id=screening_id,
        )
        return results[0] if results else self._create_failed_result(query, "No result returned")

    def _sort_queries(self, queries: list[SearchQuery]) -> list[SearchQuery]:
        """Sort queries by priority if configured.

        Args:
            queries: Queries to sort.

        Returns:
            Sorted queries (priority 1 = highest).
        """
        if self._config.process_by_priority:
            return sorted(queries, key=lambda q: q.priority)
        return queries

    def _to_routed_request(
        self,
        query: SearchQuery,
        entity_id: UUID,
        tenant_id: UUID,
        locale: Locale,
        service_tier: ServiceTier,
        screening_id: UUID | None,
    ) -> RoutedRequest:
        """Convert a SearchQuery to a RoutedRequest.

        Maps search_params from the query to SubjectIdentifiers
        for the provider infrastructure.

        Args:
            query: Search query to convert.
            entity_id: Entity ID for the request.
            tenant_id: Tenant ID for the request.
            locale: Locale for compliance.
            service_tier: Service tier.
            screening_id: Optional screening session ID.

        Returns:
            RoutedRequest for the RequestRouter.
        """
        # Build subject identifiers from search params
        subject = self._build_subject_identifiers(query.search_params)

        return RoutedRequest.create(
            check_type=query.check_type,
            subject=subject,
            locale=locale,
            entity_id=entity_id,
            tenant_id=tenant_id,
            service_tier=service_tier,
            screening_id=screening_id,
        )

    def _build_subject_identifiers(self, search_params: dict[str, Any]) -> SubjectIdentifiers:
        """Build SubjectIdentifiers from query search parameters.

        Maps common search parameter names to SubjectIdentifiers fields.

        Args:
            search_params: Search parameters from SearchQuery.

        Returns:
            SubjectIdentifiers with mapped values.
        """
        # Map search params to subject identifier fields
        return SubjectIdentifiers(
            # Name information
            full_name=search_params.get("full_name") or search_params.get("name"),
            first_name=search_params.get("first_name"),
            last_name=search_params.get("last_name"),
            middle_name=search_params.get("middle_name"),
            name_variants=search_params.get("name_variants", []),
            # Date of birth
            date_of_birth=search_params.get("date_of_birth") or search_params.get("dob"),
            # Address
            street_address=search_params.get("street_address") or search_params.get("address"),
            city=search_params.get("city"),
            state=search_params.get("state"),
            postal_code=search_params.get("postal_code") or search_params.get("zip_code"),
            country=search_params.get("country", "US"),
            # Canonical identifiers
            ssn=search_params.get("ssn"),
            ein=search_params.get("ein"),
            passport=search_params.get("passport"),
            passport_country=search_params.get("passport_country"),
            drivers_license=search_params.get("drivers_license"),
            drivers_license_state=search_params.get("drivers_license_state"),
            national_id=search_params.get("national_id"),
            tax_id=search_params.get("tax_id"),
            email=search_params.get("email"),
            phone=search_params.get("phone"),
        )

    def _to_query_result(
        self,
        query: SearchQuery,
        routed_result: RoutedResult,
    ) -> QueryResult:
        """Convert a RoutedResult to a QueryResult.

        Maps the provider infrastructure result back to the investigation domain.

        Args:
            query: Original search query.
            routed_result: Result from the RequestRouter.

        Returns:
            QueryResult for the SAR loop.
        """
        # Map failure reason to query status
        status: QueryStatus
        error_message: str | None = None
        failure_reason: str | None = None

        if routed_result.success:
            status = QueryStatus.SUCCESS
        elif routed_result.failure:
            failure_reason = routed_result.failure.reason.value
            error_message = routed_result.failure.message

            if routed_result.failure.reason == FailureReason.NO_PROVIDER:
                status = QueryStatus.NO_PROVIDER
            elif routed_result.failure.reason == FailureReason.TIMEOUT:
                status = QueryStatus.TIMEOUT
            elif routed_result.failure.reason == FailureReason.ALL_RATE_LIMITED:
                status = QueryStatus.RATE_LIMITED
            else:
                status = QueryStatus.FAILED
        else:
            status = QueryStatus.FAILED
            error_message = "Unknown failure"

        # Extract data from provider result
        normalized_data: dict[str, Any] | None = None
        findings_count = 0

        if routed_result.result:
            normalized_data = routed_result.result.normalized_data
            # Count findings (results, records, matches, etc.)
            if normalized_data:
                for key in ("records", "results", "matches", "findings", "items"):
                    if key in normalized_data and isinstance(normalized_data[key], list):
                        findings_count = len(normalized_data[key])
                        break

        completed_at = datetime.now(UTC)
        duration_ms = int(routed_result.total_duration.total_seconds() * 1000)

        return QueryResult(
            query_id=query.query_id,
            provider_id=routed_result.provider_id,
            check_type=query.check_type.value,
            status=status,
            normalized_data=normalized_data,
            findings_count=findings_count,
            completed_at=completed_at,
            duration_ms=duration_ms,
            retry_count=routed_result.attempts,
            cache_hit=routed_result.cache_hit,
            error_message=error_message,
            failure_reason=failure_reason,
        )

    def _create_failed_result(
        self,
        query: SearchQuery,
        error_message: str,
    ) -> QueryResult:
        """Create a failed query result.

        Args:
            query: Original query.
            error_message: Error description.

        Returns:
            Failed QueryResult.
        """
        return QueryResult(
            query_id=query.query_id,
            provider_id=None,
            check_type=query.check_type.value,
            status=QueryStatus.FAILED,
            error_message=error_message,
            completed_at=datetime.now(UTC),
        )


def create_query_executor(
    router: RequestRouter,
    config: ExecutorConfig | None = None,
) -> QueryExecutor:
    """Factory function to create a query executor.

    Args:
        router: Request router for provider execution.
        config: Optional executor configuration.

    Returns:
        Configured QueryExecutor instance.
    """
    return QueryExecutor(router=router, config=config)
