"""Provider request routing service for Elile.

This module provides intelligent request routing with provider selection,
retry with exponential backoff, fallback to alternate providers, and
integration with circuit breaker, rate limiting, caching, and cost tracking.
"""

import asyncio
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.agent.state import ServiceTier
from elile.compliance.types import CheckType, Locale
from elile.core.logging import get_logger
from elile.entity.types import SubjectIdentifiers

from .cache import ProviderCacheService
from .cost import ProviderCostService
from .health import CircuitBreakerRegistry, CircuitOpenError
from .rate_limit import ProviderRateLimitRegistry, RateLimitExceededError
from .registry import NoProviderAvailableError, ProviderRegistry
from .types import ProviderResult

if TYPE_CHECKING:
    from .protocol import DataProvider

logger = get_logger(__name__)


class FailureReason(str, Enum):
    """Reason for routing failure."""

    NO_PROVIDER = "no_provider"  # No provider available for check type
    ALL_PROVIDERS_FAILED = "all_providers_failed"  # All providers failed
    ALL_CIRCUITS_OPEN = "all_circuits_open"  # All circuit breakers open
    ALL_RATE_LIMITED = "all_rate_limited"  # All providers rate limited
    TIMEOUT = "timeout"  # Request timed out
    CANCELLED = "cancelled"  # Request was cancelled


class RoutingConfig(BaseModel):
    """Configuration for request routing behavior."""

    max_retries: int = Field(default=3, description="Maximum retry attempts per provider")
    base_retry_delay: float = Field(default=0.5, description="Base delay between retries in seconds")
    max_retry_delay: float = Field(default=10.0, description="Maximum delay between retries in seconds")
    retry_jitter: float = Field(default=0.1, description="Jitter factor (±10%) for retry delay")
    timeout: float = Field(default=30.0, description="Timeout per request in seconds")
    parallel_batch: bool = Field(default=True, description="Run batch requests in parallel")
    include_stale_cache: bool = Field(default=False, description="Use stale cache entries if fresh not available")


@dataclass
class RoutedRequest:
    """Request to be routed to a provider."""

    request_id: UUID
    check_type: CheckType
    subject: SubjectIdentifiers
    locale: Locale
    entity_id: UUID
    tenant_id: UUID
    service_tier: ServiceTier = ServiceTier.STANDARD
    screening_id: UUID | None = None

    @classmethod
    def create(
        cls,
        check_type: CheckType,
        subject: SubjectIdentifiers,
        locale: Locale,
        entity_id: UUID,
        tenant_id: UUID,
        *,
        service_tier: ServiceTier = ServiceTier.STANDARD,
        screening_id: UUID | None = None,
    ) -> "RoutedRequest":
        """Create a new routed request with auto-generated ID."""
        return cls(
            request_id=uuid7(),
            check_type=check_type,
            subject=subject,
            locale=locale,
            entity_id=entity_id,
            tenant_id=tenant_id,
            service_tier=service_tier,
            screening_id=screening_id,
        )


@dataclass
class RouteFailure:
    """Details about a routing failure."""

    reason: FailureReason
    message: str
    provider_errors: list[tuple[str, str]] = field(default_factory=list)  # (provider_id, error_message)

    def add_error(self, provider_id: str, error_message: str) -> None:
        """Add a provider error to the failure."""
        self.provider_errors.append((provider_id, error_message))


@dataclass
class RoutedResult:
    """Result of a routed request."""

    request_id: UUID
    check_type: CheckType
    success: bool
    result: ProviderResult | None = None

    # Execution details
    provider_id: str | None = None
    attempts: int = 0
    total_duration: timedelta = field(default_factory=lambda: timedelta(0))

    # Cache status
    cache_hit: bool = False
    cache_entry_id: UUID | None = None

    # Cost tracking
    cost_incurred: Decimal = field(default_factory=lambda: Decimal("0.00"))
    cost_saved: Decimal = field(default_factory=lambda: Decimal("0.00"))

    # Failure info
    failure: RouteFailure | None = None


class RequestRouter:
    """Service for routing provider requests with fallback and retry.

    Provides intelligent request routing with:
    - Provider selection based on check type, locale, and tier
    - Retry with exponential backoff on transient failures
    - Fallback to alternate providers on failure
    - Integration with circuit breaker, rate limiting, caching, and cost tracking

    Usage:
        router = RequestRouter(
            registry=get_provider_registry(),
            cache=ProviderCacheService(session),
            rate_limiter=get_rate_limit_registry(),
            circuit_registry=CircuitBreakerRegistry(),
            cost_service=get_cost_service(),
        )

        result = await router.route_request(
            check_type=CheckType.CRIMINAL_NATIONAL,
            subject=identifiers,
            locale=Locale.US,
            entity_id=entity_id,
            tenant_id=tenant_id,
        )
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        cache: ProviderCacheService | None = None,
        rate_limiter: ProviderRateLimitRegistry | None = None,
        circuit_registry: CircuitBreakerRegistry | None = None,
        cost_service: ProviderCostService | None = None,
        config: RoutingConfig | None = None,
    ):
        """Initialize request router.

        Args:
            registry: Provider registry for provider lookup.
            cache: Optional cache service for response caching.
            rate_limiter: Optional rate limiter registry.
            circuit_registry: Optional circuit breaker registry.
            cost_service: Optional cost tracking service.
            config: Routing configuration.
        """
        self._registry = registry
        self._cache = cache
        self._rate_limiter = rate_limiter
        self._circuit_registry = circuit_registry
        self._cost_service = cost_service
        self._config = config or RoutingConfig()

    async def route_request(
        self,
        check_type: CheckType,
        subject: SubjectIdentifiers,
        locale: Locale,
        *,
        entity_id: UUID,
        tenant_id: UUID,
        service_tier: ServiceTier = ServiceTier.STANDARD,
        screening_id: UUID | None = None,
    ) -> RoutedResult:
        """Route a single request to the best available provider.

        Args:
            check_type: Type of check to perform.
            subject: Subject identifiers for the check.
            locale: Locale for compliance filtering.
            entity_id: ID of the entity being checked.
            tenant_id: ID of the tenant making the request.
            service_tier: Service tier (affects provider availability).
            screening_id: Optional screening session ID.

        Returns:
            RoutedResult with success status and result or failure info.
        """
        request = RoutedRequest.create(
            check_type=check_type,
            subject=subject,
            locale=locale,
            entity_id=entity_id,
            tenant_id=tenant_id,
            service_tier=service_tier,
            screening_id=screening_id,
        )

        return await self._route_single(request)

    async def route_batch(
        self,
        requests: list[RoutedRequest],
        *,
        parallel: bool | None = None,
    ) -> list[RoutedResult]:
        """Route multiple requests, optionally in parallel.

        Args:
            requests: List of requests to route.
            parallel: Whether to run in parallel (defaults to config setting).

        Returns:
            List of RoutedResults in same order as requests.
        """
        if not requests:
            return []

        run_parallel = parallel if parallel is not None else self._config.parallel_batch

        if run_parallel:
            # Run all requests concurrently
            tasks = [self._route_single(req) for req in requests]
            return await asyncio.gather(*tasks)
        else:
            # Run sequentially
            results = []
            for req in requests:
                result = await self._route_single(req)
                results.append(result)
            return results

    async def _route_single(self, request: RoutedRequest) -> RoutedResult:
        """Route a single request through the full pipeline."""
        start_time = datetime.now(UTC)
        attempts = 0
        failure = RouteFailure(reason=FailureReason.NO_PROVIDER, message="", provider_errors=[])

        # 1. Check cache first
        cache_result = await self._check_cache(request)
        if cache_result is not None:
            return cache_result

        # 2. Get available providers
        try:
            providers = self._registry.get_providers_for_check(
                check_type=request.check_type,
                locale=request.locale,
                service_tier=request.service_tier,
                healthy_only=True,
            )
        except NoProviderAvailableError:
            providers = []

        if not providers:
            return RoutedResult(
                request_id=request.request_id,
                check_type=request.check_type,
                success=False,
                total_duration=datetime.now(UTC) - start_time,
                failure=RouteFailure(
                    reason=FailureReason.NO_PROVIDER,
                    message=f"No provider available for {request.check_type.value} in {request.locale.value}",
                ),
            )

        # 3. Try each provider with retries
        all_circuits_open = True
        all_rate_limited = True

        for provider in providers:
            provider_id = provider.provider_id

            # Check circuit breaker
            if not self._can_execute_on_circuit(provider_id):
                failure.add_error(provider_id, "Circuit breaker open")
                continue

            all_circuits_open = False

            # Check rate limiter
            rate_limit_result = await self._check_rate_limit(provider_id)
            if rate_limit_result is not None:
                failure.add_error(provider_id, f"Rate limited, retry after {rate_limit_result}s")
                continue

            all_rate_limited = False

            # Try with retries
            result = await self._try_provider_with_retries(
                provider=provider,
                request=request,
                failure=failure,
            )
            attempts += result.attempts

            if result.success:
                # Store in cache
                await self._store_in_cache(request, result)

                # Record cost
                await self._record_cost(request, result)

                return RoutedResult(
                    request_id=request.request_id,
                    check_type=request.check_type,
                    success=True,
                    result=result.result,
                    provider_id=result.provider_id,
                    attempts=attempts,
                    total_duration=datetime.now(UTC) - start_time,
                    cost_incurred=result.cost_incurred,
                )

        # All providers failed
        elapsed = datetime.now(UTC) - start_time

        if all_circuits_open:
            failure.reason = FailureReason.ALL_CIRCUITS_OPEN
            failure.message = "All provider circuit breakers are open"
        elif all_rate_limited:
            failure.reason = FailureReason.ALL_RATE_LIMITED
            failure.message = "All providers are rate limited"
        else:
            failure.reason = FailureReason.ALL_PROVIDERS_FAILED
            failure.message = f"All {len(providers)} providers failed"

        return RoutedResult(
            request_id=request.request_id,
            check_type=request.check_type,
            success=False,
            attempts=attempts,
            total_duration=elapsed,
            failure=failure,
        )

    async def _check_cache(self, request: RoutedRequest) -> RoutedResult | None:
        """Check cache for existing result."""
        if self._cache is None:
            return None

        lookup = await self._cache.get(
            entity_id=request.entity_id,
            provider_id=None,  # Any provider
            check_type=request.check_type,
        )

        if lookup.is_fresh_hit:
            # Fresh cache hit - use it
            entry = lookup.entry
            estimated_cost = self._estimate_cost(request.check_type)

            # Record cache savings
            if self._cost_service is not None:
                await self._cost_service.record_cache_savings(
                    query_id=request.request_id,
                    provider_id=entry.provider_id,
                    saved_amount=estimated_cost,
                    tenant_id=request.tenant_id,
                    check_type=request.check_type.value,
                )

            return RoutedResult(
                request_id=request.request_id,
                check_type=request.check_type,
                success=True,
                result=ProviderResult(
                    provider_id=entry.provider_id,
                    check_type=request.check_type,
                    locale=request.locale,
                    success=True,
                    normalized_data=entry.normalized_data,
                    query_id=request.request_id,
                ),
                provider_id=entry.provider_id,
                attempts=0,
                cache_hit=True,
                cache_entry_id=entry.cache_id,
                cost_saved=estimated_cost,
            )

        if self._config.include_stale_cache and lookup.is_stale_hit:
            # Use stale cache if configured
            entry = lookup.entry
            estimated_cost = self._estimate_cost(request.check_type)

            if self._cost_service is not None:
                await self._cost_service.record_cache_savings(
                    query_id=request.request_id,
                    provider_id=entry.provider_id,
                    saved_amount=estimated_cost,
                    tenant_id=request.tenant_id,
                    check_type=request.check_type.value,
                )

            return RoutedResult(
                request_id=request.request_id,
                check_type=request.check_type,
                success=True,
                result=ProviderResult(
                    provider_id=entry.provider_id,
                    check_type=request.check_type,
                    locale=request.locale,
                    success=True,
                    normalized_data=entry.normalized_data,
                    query_id=request.request_id,
                ),
                provider_id=entry.provider_id,
                attempts=0,
                cache_hit=True,
                cache_entry_id=entry.cache_id,
                cost_saved=estimated_cost,
            )

        return None

    async def _store_in_cache(self, request: RoutedRequest, result: RoutedResult) -> None:
        """Store result in cache."""
        if self._cache is None or result.result is None:
            return

        await self._cache.store(
            entity_id=request.entity_id,
            result=result.result,
            tenant_id=request.tenant_id,
        )

    async def _record_cost(self, request: RoutedRequest, result: RoutedResult) -> None:
        """Record cost for the request."""
        if self._cost_service is None or result.result is None:
            return

        await self._cost_service.record_cost(
            query_id=request.request_id,
            provider_id=result.provider_id or "",
            check_type=request.check_type.value,
            cost=result.cost_incurred,
            tenant_id=request.tenant_id,
            screening_id=request.screening_id,
        )

    def _can_execute_on_circuit(self, provider_id: str) -> bool:
        """Check if circuit breaker allows execution."""
        if self._circuit_registry is None:
            return True

        breaker = self._circuit_registry.get_breaker(provider_id)
        return breaker.can_execute()

    def _record_circuit_success(self, provider_id: str) -> None:
        """Record success to circuit breaker."""
        if self._circuit_registry is None:
            return

        breaker = self._circuit_registry.get_breaker(provider_id)
        breaker.record_success()

    def _record_circuit_failure(self, provider_id: str) -> None:
        """Record failure to circuit breaker."""
        if self._circuit_registry is None:
            return

        breaker = self._circuit_registry.get_breaker(provider_id)
        breaker.record_failure()

    async def _check_rate_limit(self, provider_id: str) -> float | None:
        """Check rate limit for provider.

        Returns:
            None if allowed, or retry-after seconds if limited.
        """
        if self._rate_limiter is None:
            return None

        result = await self._rate_limiter.check(provider_id)
        if result.allowed:
            return None
        return result.retry_after_seconds

    async def _acquire_rate_limit(self, provider_id: str) -> bool:
        """Acquire rate limit token.

        Returns:
            True if acquired, False if limited.
        """
        if self._rate_limiter is None:
            return True

        try:
            await self._rate_limiter.acquire_or_raise(provider_id)
            return True
        except RateLimitExceededError:
            return False

    async def _try_provider_with_retries(
        self,
        provider: "DataProvider",
        request: RoutedRequest,
        failure: RouteFailure,
    ) -> RoutedResult:
        """Try a provider with retries on transient failures."""
        provider_id = provider.provider_id
        attempts = 0
        last_error: str | None = None

        for attempt in range(self._config.max_retries):
            attempts += 1

            # Acquire rate limit token
            if not await self._acquire_rate_limit(provider_id):
                failure.add_error(provider_id, "Rate limited during retry")
                break

            try:
                # Execute the check with timeout
                result = await asyncio.wait_for(
                    provider.execute_check(
                        check_type=request.check_type,
                        subject=request.subject,
                        locale=request.locale,
                    ),
                    timeout=self._config.timeout,
                )

                if result.is_success:
                    self._record_circuit_success(provider_id)
                    return RoutedResult(
                        request_id=request.request_id,
                        check_type=request.check_type,
                        success=True,
                        result=result,
                        provider_id=provider_id,
                        attempts=attempts,
                        cost_incurred=result.cost_incurred,
                    )
                else:
                    # Provider returned an error
                    last_error = result.error_message or result.error_code or "Unknown error"

                    if result.retryable and attempt < self._config.max_retries - 1:
                        # Retry with backoff
                        await self._backoff(attempt)
                        continue
                    else:
                        # Non-retryable or max retries reached
                        self._record_circuit_failure(provider_id)
                        break

            except asyncio.TimeoutError:
                last_error = f"Timeout after {self._config.timeout}s"
                self._record_circuit_failure(provider_id)

                if attempt < self._config.max_retries - 1:
                    await self._backoff(attempt)
                    continue
                break

            except CircuitOpenError:
                last_error = "Circuit breaker opened during execution"
                break

            except Exception as e:
                last_error = str(e)
                self._record_circuit_failure(provider_id)

                if attempt < self._config.max_retries - 1:
                    await self._backoff(attempt)
                    continue
                break

        failure.add_error(provider_id, last_error or "Unknown error")
        return RoutedResult(
            request_id=request.request_id,
            check_type=request.check_type,
            success=False,
            provider_id=provider_id,
            attempts=attempts,
        )

    async def _backoff(self, attempt: int) -> None:
        """Wait with exponential backoff."""
        # Exponential backoff: base * 2^attempt
        delay = min(
            self._config.base_retry_delay * (2**attempt),
            self._config.max_retry_delay,
        )

        # Add jitter
        jitter = delay * self._config.retry_jitter * (random.random() * 2 - 1)
        delay = max(0, delay + jitter)

        await asyncio.sleep(delay)

    def _estimate_cost(self, check_type: CheckType) -> Decimal:
        """Estimate cost for a check type (for cache savings calculation)."""
        # Default cost estimates by check type category
        # In production, this would come from provider capability data
        cost_estimates = {
            CheckType.CRIMINAL_NATIONAL: Decimal("5.00"),
            CheckType.CRIMINAL_COUNTY: Decimal("3.00"),
            CheckType.CRIMINAL_STATE: Decimal("4.00"),
            CheckType.CRIMINAL_FEDERAL: Decimal("5.00"),
            CheckType.CREDIT_REPORT: Decimal("10.00"),
            CheckType.CREDIT_SCORE: Decimal("5.00"),
            CheckType.EMPLOYMENT_VERIFICATION: Decimal("8.00"),
            CheckType.EDUCATION_VERIFICATION: Decimal("6.00"),
            CheckType.LICENSE_VERIFICATION: Decimal("4.00"),
            CheckType.SANCTIONS_PEP: Decimal("3.00"),
            CheckType.WATCHLIST_INTERPOL: Decimal("5.00"),
        }
        return cost_estimates.get(check_type, Decimal("5.00"))
