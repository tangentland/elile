"""Unit tests for QueryExecutor."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4, uuid7

import pytest

from elile.compliance.types import CheckType, Locale
from elile.agent.state import InformationType
from elile.investigation.query_executor import (
    ExecutionSummary,
    ExecutorConfig,
    QueryExecutor,
    QueryResult,
    QueryStatus,
    create_query_executor,
)
from elile.investigation.query_planner import QueryType, SearchQuery
from elile.providers.router import (
    FailureReason,
    RequestRouter,
    RouteFailure,
    RoutedResult,
)
from elile.agent.state import ServiceTier
from elile.providers.types import ProviderResult


@pytest.fixture
def mock_router():
    """Create a mock RequestRouter."""
    router = MagicMock(spec=RequestRouter)
    router.route_batch = AsyncMock(return_value=[])
    return router


@pytest.fixture
def executor(mock_router):
    """Create a QueryExecutor with mock router."""
    return QueryExecutor(router=mock_router)


@pytest.fixture
def sample_query():
    """Create a sample SearchQuery."""
    return SearchQuery(
        query_id=uuid7(),
        info_type=InformationType.CRIMINAL,
        query_type=QueryType.INITIAL,
        provider_id="sterling",
        check_type=CheckType.CRIMINAL_NATIONAL,
        search_params={
            "full_name": "John Smith",
            "date_of_birth": "1990-01-15",
            "ssn": "123-45-6789",
        },
        iteration_number=1,
        priority=1,
    )


@pytest.fixture
def successful_routed_result():
    """Create a successful RoutedResult."""
    return RoutedResult(
        request_id=uuid7(),
        check_type=CheckType.CRIMINAL_NATIONAL,
        success=True,
        result=ProviderResult(
            provider_id="sterling",
            check_type=CheckType.CRIMINAL_NATIONAL,
            locale=Locale.US,
            success=True,
            normalized_data={"records": [{"id": "1", "type": "criminal"}]},
        ),
        provider_id="sterling",
        attempts=1,
        total_duration=timedelta(milliseconds=150),
        cache_hit=False,
    )


@pytest.fixture
def failed_routed_result():
    """Create a failed RoutedResult."""
    return RoutedResult(
        request_id=uuid7(),
        check_type=CheckType.CRIMINAL_NATIONAL,
        success=False,
        failure=RouteFailure(
            reason=FailureReason.ALL_PROVIDERS_FAILED,
            message="All providers failed",
            provider_errors=[("sterling", "Connection timeout")],
        ),
        attempts=3,
        total_duration=timedelta(seconds=5),
    )


class TestQueryResult:
    """Tests for QueryResult dataclass."""

    def test_result_creation(self):
        """Test QueryResult creation with all fields."""
        query_id = uuid7()
        result = QueryResult(
            query_id=query_id,
            provider_id="sterling",
            check_type="criminal_national",
            status=QueryStatus.SUCCESS,
            normalized_data={"records": [{"id": "1"}]},
            findings_count=1,
            duration_ms=100,
        )

        assert result.query_id == query_id
        assert result.provider_id == "sterling"
        assert result.status == QueryStatus.SUCCESS
        assert result.is_success is True
        assert result.has_data is True
        assert result.findings_count == 1

    def test_failed_result(self):
        """Test failed QueryResult properties."""
        result = QueryResult(
            query_id=uuid7(),
            provider_id="sterling",
            check_type="criminal_national",
            status=QueryStatus.FAILED,
            error_message="Connection failed",
        )

        assert result.is_success is False
        assert result.has_data is False
        assert result.error_message == "Connection failed"

    def test_result_without_data(self):
        """Test QueryResult with empty normalized data."""
        result = QueryResult(
            query_id=uuid7(),
            provider_id="sterling",
            check_type="criminal_national",
            status=QueryStatus.SUCCESS,
            normalized_data={},
        )

        assert result.is_success is True
        assert result.has_data is False


class TestExecutionSummary:
    """Tests for ExecutionSummary dataclass."""

    def test_empty_summary(self):
        """Test empty execution summary."""
        summary = ExecutionSummary()

        assert summary.total_queries == 0
        assert summary.success_rate == 0.0
        assert summary.is_complete is True

    def test_update_from_success(self):
        """Test updating summary from successful result."""
        summary = ExecutionSummary(total_queries=1)
        result = QueryResult(
            query_id=uuid7(),
            provider_id="sterling",
            check_type="criminal_national",
            status=QueryStatus.SUCCESS,
            cache_hit=True,
        )

        summary.update_from_result(result)

        assert summary.successful == 1
        assert summary.cache_hits == 1
        assert summary.success_rate == 100.0
        assert "sterling" in summary.providers_used

    def test_update_from_failure(self):
        """Test updating summary from failed result."""
        summary = ExecutionSummary(total_queries=1)
        result = QueryResult(
            query_id=uuid7(),
            provider_id="sterling",
            check_type="criminal_national",
            status=QueryStatus.FAILED,
        )

        summary.update_from_result(result)

        assert summary.failed == 1
        assert "sterling" in summary.providers_failed

    def test_update_from_timeout(self):
        """Test updating summary from timeout result."""
        summary = ExecutionSummary(total_queries=1)
        result = QueryResult(
            query_id=uuid7(),
            provider_id="sterling",
            check_type="criminal_national",
            status=QueryStatus.TIMEOUT,
        )

        summary.update_from_result(result)

        assert summary.timed_out == 1

    def test_update_from_rate_limited(self):
        """Test updating summary from rate limited result."""
        summary = ExecutionSummary(total_queries=1)
        result = QueryResult(
            query_id=uuid7(),
            provider_id=None,
            check_type="criminal_national",
            status=QueryStatus.RATE_LIMITED,
        )

        summary.update_from_result(result)

        assert summary.rate_limited == 1

    def test_success_rate_calculation(self):
        """Test success rate calculation with mixed results."""
        summary = ExecutionSummary(total_queries=4)

        # 2 successful, 1 failed, 1 timeout
        for status in [QueryStatus.SUCCESS, QueryStatus.SUCCESS, QueryStatus.FAILED, QueryStatus.TIMEOUT]:
            result = QueryResult(
                query_id=uuid7(),
                provider_id="sterling",
                check_type="criminal_national",
                status=status,
            )
            summary.update_from_result(result)

        assert summary.success_rate == 50.0
        assert summary.is_complete is True


class TestExecutorConfig:
    """Tests for ExecutorConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ExecutorConfig()

        assert config.max_concurrent_queries == 10
        assert config.batch_size == 10
        assert config.process_by_priority is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ExecutorConfig(
            max_concurrent_queries=5,
            batch_size=20,
            process_by_priority=False,
        )

        assert config.max_concurrent_queries == 5
        assert config.batch_size == 20
        assert config.process_by_priority is False


class TestQueryExecutor:
    """Tests for QueryExecutor class."""

    @pytest.mark.asyncio
    async def test_execute_empty_queries(self, executor):
        """Test executing empty query list."""
        results, summary = await executor.execute_queries(
            queries=[],
            entity_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.US,
        )

        assert results == []
        assert summary.total_queries == 0
        assert summary.is_complete is True

    @pytest.mark.asyncio
    async def test_execute_single_query_success(self, mock_router, sample_query, successful_routed_result):
        """Test executing a single successful query."""
        mock_router.route_batch.return_value = [successful_routed_result]
        executor = QueryExecutor(router=mock_router)

        results, summary = await executor.execute_queries(
            queries=[sample_query],
            entity_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.US,
        )

        assert len(results) == 1
        assert results[0].status == QueryStatus.SUCCESS
        assert results[0].provider_id == "sterling"
        assert results[0].findings_count == 1
        assert summary.successful == 1
        assert summary.success_rate == 100.0

    @pytest.mark.asyncio
    async def test_execute_single_query_failure(self, mock_router, sample_query, failed_routed_result):
        """Test executing a single failed query."""
        mock_router.route_batch.return_value = [failed_routed_result]
        executor = QueryExecutor(router=mock_router)

        results, summary = await executor.execute_queries(
            queries=[sample_query],
            entity_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.US,
        )

        assert len(results) == 1
        assert results[0].status == QueryStatus.FAILED
        assert results[0].error_message == "All providers failed"
        assert summary.failed == 1

    @pytest.mark.asyncio
    async def test_execute_no_provider(self, mock_router, sample_query):
        """Test executing query with no provider available."""
        routed_result = RoutedResult(
            request_id=uuid7(),
            check_type=CheckType.CRIMINAL_NATIONAL,
            success=False,
            failure=RouteFailure(
                reason=FailureReason.NO_PROVIDER,
                message="No provider available",
            ),
            total_duration=timedelta(milliseconds=10),
        )
        mock_router.route_batch.return_value = [routed_result]
        executor = QueryExecutor(router=mock_router)

        results, summary = await executor.execute_queries(
            queries=[sample_query],
            entity_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.US,
        )

        assert results[0].status == QueryStatus.NO_PROVIDER
        assert summary.no_provider == 1

    @pytest.mark.asyncio
    async def test_execute_timeout(self, mock_router, sample_query):
        """Test executing query with timeout."""
        routed_result = RoutedResult(
            request_id=uuid7(),
            check_type=CheckType.CRIMINAL_NATIONAL,
            success=False,
            failure=RouteFailure(
                reason=FailureReason.TIMEOUT,
                message="Request timed out",
            ),
            total_duration=timedelta(seconds=30),
        )
        mock_router.route_batch.return_value = [routed_result]
        executor = QueryExecutor(router=mock_router)

        results, summary = await executor.execute_queries(
            queries=[sample_query],
            entity_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.US,
        )

        assert results[0].status == QueryStatus.TIMEOUT
        assert summary.timed_out == 1

    @pytest.mark.asyncio
    async def test_execute_rate_limited(self, mock_router, sample_query):
        """Test executing query with rate limiting."""
        routed_result = RoutedResult(
            request_id=uuid7(),
            check_type=CheckType.CRIMINAL_NATIONAL,
            success=False,
            failure=RouteFailure(
                reason=FailureReason.ALL_RATE_LIMITED,
                message="All providers rate limited",
            ),
            total_duration=timedelta(milliseconds=100),
        )
        mock_router.route_batch.return_value = [routed_result]
        executor = QueryExecutor(router=mock_router)

        results, summary = await executor.execute_queries(
            queries=[sample_query],
            entity_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.US,
        )

        assert results[0].status == QueryStatus.RATE_LIMITED
        assert summary.rate_limited == 1

    @pytest.mark.asyncio
    async def test_execute_with_cache_hit(self, mock_router, sample_query):
        """Test executing query with cache hit."""
        routed_result = RoutedResult(
            request_id=uuid7(),
            check_type=CheckType.CRIMINAL_NATIONAL,
            success=True,
            result=ProviderResult(
                provider_id="sterling",
                check_type=CheckType.CRIMINAL_NATIONAL,
                locale=Locale.US,
                success=True,
                normalized_data={"records": []},
            ),
            provider_id="sterling",
            cache_hit=True,
            total_duration=timedelta(milliseconds=5),
        )
        mock_router.route_batch.return_value = [routed_result]
        executor = QueryExecutor(router=mock_router)

        results, summary = await executor.execute_queries(
            queries=[sample_query],
            entity_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.US,
        )

        assert results[0].cache_hit is True
        assert summary.cache_hits == 1


class TestBatchExecution:
    """Tests for batch query execution."""

    @pytest.mark.asyncio
    async def test_execute_multiple_queries(self, mock_router):
        """Test executing multiple queries."""
        queries = [
            SearchQuery(
                query_id=uuid7(),
                info_type=InformationType.CRIMINAL,
                query_type=QueryType.INITIAL,
                provider_id="sterling",
                check_type=CheckType.CRIMINAL_NATIONAL,
                search_params={"full_name": "John Smith"},
                iteration_number=1,
                priority=1,
            ),
            SearchQuery(
                query_id=uuid7(),
                info_type=InformationType.EMPLOYMENT,
                query_type=QueryType.ENRICHED,
                provider_id="checkr",
                check_type=CheckType.EMPLOYMENT_VERIFICATION,
                search_params={"full_name": "John Smith"},
                iteration_number=1,
                priority=2,
            ),
        ]

        routed_results = [
            RoutedResult(
                request_id=uuid7(),
                check_type=CheckType.CRIMINAL_NATIONAL,
                success=True,
                result=ProviderResult(
                    provider_id="sterling",
                    check_type=CheckType.CRIMINAL_NATIONAL,
                    locale=Locale.US,
                    success=True,
                    normalized_data={"records": [{"id": "1"}]},
                ),
                provider_id="sterling",
                total_duration=timedelta(milliseconds=100),
            ),
            RoutedResult(
                request_id=uuid7(),
                check_type=CheckType.EMPLOYMENT_VERIFICATION,
                success=True,
                result=ProviderResult(
                    provider_id="checkr",
                    check_type=CheckType.EMPLOYMENT_VERIFICATION,
                    locale=Locale.US,
                    success=True,
                    normalized_data={"records": [{"id": "2"}]},
                ),
                provider_id="checkr",
                total_duration=timedelta(milliseconds=120),
            ),
        ]
        mock_router.route_batch.return_value = routed_results
        executor = QueryExecutor(router=mock_router)

        results, summary = await executor.execute_queries(
            queries=queries,
            entity_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.US,
        )

        assert len(results) == 2
        assert summary.total_queries == 2
        assert summary.successful == 2
        assert "sterling" in summary.providers_used
        assert "checkr" in summary.providers_used

    @pytest.mark.asyncio
    async def test_priority_sorting(self, mock_router):
        """Test queries are sorted by priority."""
        queries = [
            SearchQuery(
                query_id=uuid7(),
                info_type=InformationType.CRIMINAL,
                query_type=QueryType.REFINEMENT,
                provider_id="sterling",
                check_type=CheckType.CRIMINAL_NATIONAL,
                search_params={"full_name": "John Smith"},
                iteration_number=2,
                priority=3,  # Low priority
            ),
            SearchQuery(
                query_id=uuid7(),
                info_type=InformationType.IDENTITY,
                query_type=QueryType.INITIAL,
                provider_id="checkr",
                check_type=CheckType.IDENTITY_BASIC,
                search_params={"full_name": "John Smith"},
                iteration_number=1,
                priority=1,  # High priority
            ),
        ]

        mock_router.route_batch.return_value = [
            RoutedResult(
                request_id=uuid7(),
                check_type=CheckType.IDENTITY_BASIC,
                success=True,
                result=ProviderResult(
                    provider_id="checkr",
                    check_type=CheckType.IDENTITY_BASIC,
                    locale=Locale.US,
                    success=True,
                    normalized_data={},
                ),
                provider_id="checkr",
                total_duration=timedelta(milliseconds=50),
            ),
            RoutedResult(
                request_id=uuid7(),
                check_type=CheckType.CRIMINAL_NATIONAL,
                success=True,
                result=ProviderResult(
                    provider_id="sterling",
                    check_type=CheckType.CRIMINAL_NATIONAL,
                    locale=Locale.US,
                    success=True,
                    normalized_data={},
                ),
                provider_id="sterling",
                total_duration=timedelta(milliseconds=60),
            ),
        ]

        config = ExecutorConfig(process_by_priority=True)
        executor = QueryExecutor(router=mock_router, config=config)

        await executor.execute_queries(
            queries=queries,
            entity_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.US,
        )

        # Verify route_batch was called
        mock_router.route_batch.assert_called_once()
        call_args = mock_router.route_batch.call_args[0][0]

        # First request should be identity (priority 1)
        assert call_args[0].check_type == CheckType.IDENTITY_BASIC
        # Second request should be criminal (priority 3)
        assert call_args[1].check_type == CheckType.CRIMINAL_NATIONAL


class TestSubjectIdentifierMapping:
    """Tests for search params to SubjectIdentifiers mapping."""

    @pytest.mark.asyncio
    async def test_full_subject_mapping(self, mock_router):
        """Test mapping all search params to SubjectIdentifiers."""
        query = SearchQuery(
            query_id=uuid7(),
            info_type=InformationType.CRIMINAL,
            query_type=QueryType.INITIAL,
            provider_id="sterling",
            check_type=CheckType.CRIMINAL_NATIONAL,
            search_params={
                "full_name": "John Smith",
                "first_name": "John",
                "last_name": "Smith",
                "middle_name": "Q",
                "name_variants": ["Johnny Smith"],
                "date_of_birth": "1990-01-15",
                "street_address": "123 Main St",
                "city": "New York",
                "state": "NY",
                "postal_code": "10001",
                "country": "US",
                "ssn": "123-45-6789",
                "email": "john@example.com",
                "phone": "+1-555-123-4567",
            },
            iteration_number=1,
            priority=1,
        )

        mock_router.route_batch.return_value = [
            RoutedResult(
                request_id=uuid7(),
                check_type=CheckType.CRIMINAL_NATIONAL,
                success=True,
                result=ProviderResult(
                    provider_id="sterling",
                    check_type=CheckType.CRIMINAL_NATIONAL,
                    locale=Locale.US,
                    success=True,
                    normalized_data={},
                ),
                provider_id="sterling",
                total_duration=timedelta(milliseconds=50),
            ),
        ]

        executor = QueryExecutor(router=mock_router)
        await executor.execute_queries(
            queries=[query],
            entity_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.US,
        )

        # Verify the request was created with correct subject identifiers
        call_args = mock_router.route_batch.call_args[0][0]
        subject = call_args[0].subject

        assert subject.full_name == "John Smith"
        assert subject.first_name == "John"
        assert subject.last_name == "Smith"
        assert subject.ssn == "123-45-6789"
        assert subject.email == "john@example.com"


class TestExecuteSingle:
    """Tests for execute_single method."""

    @pytest.mark.asyncio
    async def test_execute_single_success(self, mock_router, sample_query, successful_routed_result):
        """Test execute_single with successful query."""
        mock_router.route_batch.return_value = [successful_routed_result]
        executor = QueryExecutor(router=mock_router)

        result = await executor.execute_single(
            query=sample_query,
            entity_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.US,
        )

        assert result.status == QueryStatus.SUCCESS
        assert result.provider_id == "sterling"


class TestFactoryFunction:
    """Tests for create_query_executor factory."""

    def test_create_executor(self, mock_router):
        """Test creating executor with factory function."""
        executor = create_query_executor(router=mock_router)

        assert isinstance(executor, QueryExecutor)

    def test_create_executor_with_config(self, mock_router):
        """Test creating executor with custom config."""
        config = ExecutorConfig(batch_size=5)
        executor = create_query_executor(router=mock_router, config=config)

        assert executor._config.batch_size == 5


class TestFindingsCount:
    """Tests for findings count extraction."""

    @pytest.mark.asyncio
    async def test_findings_from_records(self, mock_router, sample_query):
        """Test extracting findings count from records array."""
        routed_result = RoutedResult(
            request_id=uuid7(),
            check_type=CheckType.CRIMINAL_NATIONAL,
            success=True,
            result=ProviderResult(
                provider_id="sterling",
                check_type=CheckType.CRIMINAL_NATIONAL,
                locale=Locale.US,
                success=True,
                normalized_data={"records": [{"id": "1"}, {"id": "2"}, {"id": "3"}]},
            ),
            provider_id="sterling",
            total_duration=timedelta(milliseconds=100),
        )
        mock_router.route_batch.return_value = [routed_result]
        executor = QueryExecutor(router=mock_router)

        results, _ = await executor.execute_queries(
            queries=[sample_query],
            entity_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.US,
        )

        assert results[0].findings_count == 3

    @pytest.mark.asyncio
    async def test_findings_from_matches(self, mock_router, sample_query):
        """Test extracting findings count from matches array."""
        routed_result = RoutedResult(
            request_id=uuid7(),
            check_type=CheckType.CRIMINAL_NATIONAL,
            success=True,
            result=ProviderResult(
                provider_id="sterling",
                check_type=CheckType.CRIMINAL_NATIONAL,
                locale=Locale.US,
                success=True,
                normalized_data={"matches": [{"id": "1"}, {"id": "2"}]},
            ),
            provider_id="sterling",
            total_duration=timedelta(milliseconds=100),
        )
        mock_router.route_batch.return_value = [routed_result]
        executor = QueryExecutor(router=mock_router)

        results, _ = await executor.execute_queries(
            queries=[sample_query],
            entity_id=uuid7(),
            tenant_id=uuid7(),
            locale=Locale.US,
        )

        assert results[0].findings_count == 2
