"""Unit tests for degree handlers.

Tests D1, D2, and D3 investigation handlers.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from uuid_utils import uuid7

from elile.agent.state import (
    InformationType,
    KnowledgeBase,
    ServiceTier,
)
from elile.compliance.types import Locale, RoleCategory
from elile.investigation.phases.network import (
    ConnectionStrength,
    DiscoveredEntity,
    EntityRelation,
    EntityType,
)
from elile.investigation.sar_orchestrator import InvestigationResult, TypeCycleResult
from elile.risk.connection_analyzer import ConnectionAnalysisResult
from elile.screening.degree_handlers import (
    D1Result,
    D2Result,
    D3Result,
    DegreeHandlerConfig,
    create_d1_handler,
    create_d2_handler,
    create_d3_handler,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def config():
    """Create test configuration."""
    return DegreeHandlerConfig(
        d2_max_entities=5,
        d2_min_relevance=0.4,
        d3_max_entities=10,
        d3_min_relevance=0.3,
    )


@pytest.fixture
def knowledge_base():
    """Create test knowledge base."""
    kb = KnowledgeBase()
    kb.confirmed_names.append("John Smith")
    kb.confirmed_dob = "1985-03-15"
    return kb


@pytest.fixture
def mock_sar_orchestrator():
    """Create mock SAR orchestrator."""
    orchestrator = MagicMock()
    orchestrator.execute_investigation = AsyncMock(
        return_value=InvestigationResult(
            is_complete=True,
            total_facts=50,
            total_queries=20,
            types_completed=8,
            type_results={
                InformationType.IDENTITY: TypeCycleResult(
                    info_type=InformationType.IDENTITY,
                    iterations_completed=2,
                    final_confidence=0.92,
                    total_facts_extracted=10,
                    total_queries_executed=4,
                ),
            },
        )
    )
    return orchestrator


@pytest.fixture
def mock_connection_analyzer():
    """Create mock connection analyzer."""
    analyzer = MagicMock()
    analyzer.analyze_connections = MagicMock(
        return_value=ConnectionAnalysisResult(
            subject_entity_id=uuid7(),
            connections_analyzed=5,
            risk_connections_found=[],
            total_propagated_risk=0.15,
        )
    )
    return analyzer


@pytest.fixture
def discovered_entities():
    """Create test discovered entities."""
    return [
        DiscoveredEntity(
            entity_id=uuid7(),
            entity_type=EntityType.ORGANIZATION,
            name="Acme Corp",
            confidence=0.95,
            source_providers=["employment_verification"],
            metadata={"relationship": "employer"},
        ),
        DiscoveredEntity(
            entity_id=uuid7(),
            entity_type=EntityType.PERSON,
            name="Jane Doe",
            confidence=0.85,
            source_providers=["network_analysis"],
            metadata={"relationship": "business_partner"},
        ),
        DiscoveredEntity(
            entity_id=uuid7(),
            entity_type=EntityType.PERSON,
            name="Bob Wilson",
            confidence=0.9,
            source_providers=["identity_verification"],
            metadata={"relationship": "family"},
        ),
        DiscoveredEntity(
            entity_id=uuid7(),
            entity_type=EntityType.PERSON,
            name="Alice Johnson",
            confidence=0.6,
            source_providers=["social_media"],
            metadata={"relationship": "social"},
        ),
    ]


@pytest.fixture
def d1_result(knowledge_base, discovered_entities):
    """Create test D1 result."""
    return D1Result(
        findings=[],
        discovered_entities=discovered_entities,
        entity_queue=[],
        knowledge_base=knowledge_base,
        total_facts=50,
        total_queries=20,
        types_completed=8,
    )


@pytest.fixture
def d2_result(d1_result, discovered_entities):
    """Create test D2 result."""
    return D2Result(
        d1_result=d1_result,
        entity_findings={},
        investigated_entities=discovered_entities[:2],
        connections=[],
        risk_connections=[],
        entities_investigated=2,
        entities_skipped=2,
        total_propagated_risk=0.15,
    )


# =============================================================================
# D1Handler Tests
# =============================================================================


class TestD1Handler:
    """Tests for D1Handler."""

    def test_create_d1_handler(self, config):
        """Test D1 handler creation."""
        handler = create_d1_handler(config=config)

        assert handler is not None
        assert handler.config == config
        assert handler.sar_orchestrator is None

    def test_create_d1_handler_with_orchestrator(self, mock_sar_orchestrator, config):
        """Test D1 handler creation with SAR orchestrator."""
        handler = create_d1_handler(
            sar_orchestrator=mock_sar_orchestrator,
            config=config,
        )

        assert handler.sar_orchestrator == mock_sar_orchestrator

    @pytest.mark.asyncio
    async def test_execute_d1_basic(self, knowledge_base, config):
        """Test basic D1 execution without orchestrator."""
        handler = create_d1_handler(config=config)

        result = await handler.execute_d1(
            knowledge_base=knowledge_base,
            subject_name="John Smith",
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            role_category=RoleCategory.STANDARD,
            available_providers=["sterling"],
        )

        assert isinstance(result, D1Result)
        assert result.entity_queue == []  # D1 does not queue entities
        assert result.completed_at is not None
        assert result.duration_seconds is not None

    @pytest.mark.asyncio
    async def test_execute_d1_with_orchestrator(
        self, knowledge_base, mock_sar_orchestrator, config
    ):
        """Test D1 execution with SAR orchestrator."""
        handler = create_d1_handler(
            sar_orchestrator=mock_sar_orchestrator,
            config=config,
        )

        result = await handler.execute_d1(
            knowledge_base=knowledge_base,
            subject_name="John Smith",
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            role_category=RoleCategory.STANDARD,
            available_providers=["sterling"],
        )

        assert result.total_facts == 50
        assert result.total_queries == 20
        assert result.types_completed == 8
        mock_sar_orchestrator.execute_investigation.assert_called_once()

    def test_d1_result_to_dict(self, d1_result):
        """Test D1 result serialization."""
        result_dict = d1_result.to_dict()

        assert "result_id" in result_dict
        assert result_dict["findings_count"] == 0
        assert result_dict["discovered_entities_count"] == 4
        assert result_dict["entity_queue_count"] == 0
        assert result_dict["total_facts"] == 50

    def test_extract_entities_from_knowledge_base(self, config):
        """Test entity extraction from knowledge base."""
        from elile.agent.state import EmployerRecord, PersonEntity

        handler = create_d1_handler(config=config)

        kb = KnowledgeBase()
        kb.employers = [
            EmployerRecord(employer_name="Acme Corp", source="test"),
            EmployerRecord(employer_name="Tech Inc", source="test"),
        ]
        kb.discovered_people = [PersonEntity(name="Jane Doe", source="test")]

        entities = handler._extract_entities(kb)

        assert len(entities) == 3
        assert any(e.name == "Acme Corp" for e in entities)
        assert any(e.name == "Tech Inc" for e in entities)
        assert any(e.name == "Jane Doe" for e in entities)


# =============================================================================
# D2Handler Tests
# =============================================================================


class TestD2Handler:
    """Tests for D2Handler."""

    def test_create_d2_handler(self, config):
        """Test D2 handler creation."""
        handler = create_d2_handler(config=config)

        assert handler is not None
        assert handler.config == config
        assert handler.connection_analyzer is not None

    def test_create_d2_handler_with_analyzer(self, mock_connection_analyzer, config):
        """Test D2 handler creation with connection analyzer."""
        handler = create_d2_handler(
            connection_analyzer=mock_connection_analyzer,
            config=config,
        )

        assert handler.connection_analyzer == mock_connection_analyzer

    @pytest.mark.asyncio
    async def test_execute_d2_basic(self, d1_result, mock_connection_analyzer, config):
        """Test basic D2 execution."""
        handler = create_d2_handler(
            connection_analyzer=mock_connection_analyzer,
            config=config,
        )

        result = await handler.execute_d2(
            d1_result=d1_result,
            locale=Locale.US,
            tier=ServiceTier.ENHANCED,
            role_category=RoleCategory.STANDARD,
            available_providers=["sterling"],
        )

        assert isinstance(result, D2Result)
        assert result.d1_result == d1_result
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_execute_d2_limits_entities(self, d1_result, config):
        """Test D2 respects max entity limit."""
        config.d2_max_entities = 2
        handler = create_d2_handler(config=config)

        result = await handler.execute_d2(
            d1_result=d1_result,
            locale=Locale.US,
            tier=ServiceTier.ENHANCED,
            role_category=RoleCategory.STANDARD,
            available_providers=["sterling"],
        )

        assert result.entities_investigated <= 2
        assert result.entities_skipped >= 0

    def test_prioritize_entities(self, discovered_entities, config):
        """Test entity prioritization."""
        handler = create_d2_handler(config=config)

        prioritized = handler._prioritize_entities(discovered_entities, max_count=2)

        assert len(prioritized) <= 2
        # Higher relevance entities should be prioritized
        names = [e.name for e in prioritized]
        assert "Acme Corp" in names  # employer has high relevance

    def test_prioritize_entities_respects_min_relevance(self, config):
        """Test entity prioritization filters by min relevance."""
        config.d2_min_relevance = 0.9  # High threshold
        handler = create_d2_handler(config=config)

        # Low relevance entities
        entities = [
            DiscoveredEntity(
                entity_id=uuid7(),
                entity_type=EntityType.PERSON,
                name="Low Relevance",
                confidence=0.3,
                source_providers=["test"],
                metadata={"relationship": "social"},
            )
        ]

        prioritized = handler._prioritize_entities(entities, max_count=10)

        assert len(prioritized) == 0  # All filtered out

    def test_calculate_entity_priority(self, config):
        """Test entity priority calculation."""
        handler = create_d2_handler(config=config)

        # High priority entity
        high_entity = DiscoveredEntity(
            entity_id=uuid7(),
            entity_type=EntityType.ORGANIZATION,
            name="Important Corp",
            confidence=0.95,
            source_providers=["test"],
            metadata={"relationship": "employer"},
        )

        # Low priority entity
        low_entity = DiscoveredEntity(
            entity_id=uuid7(),
            entity_type=EntityType.PERSON,
            name="Acquaintance",
            confidence=0.3,
            source_providers=["test"],
            metadata={"relationship": "social"},
        )

        high_score = handler._calculate_entity_priority(high_entity)
        low_score = handler._calculate_entity_priority(low_entity)

        assert high_score > low_score

    def test_get_relationship_score(self, config):
        """Test relationship scoring."""
        handler = create_d2_handler(config=config)

        assert handler._get_relationship_score("employer") > handler._get_relationship_score(
            "social"
        )
        assert handler._get_relationship_score(
            "business_partner"
        ) > handler._get_relationship_score("educational")

    def test_build_connections(self, discovered_entities, config):
        """Test connection building."""
        handler = create_d2_handler(config=config)

        investigated = discovered_entities[:2]
        connections = handler._build_connections(discovered_entities, investigated)

        assert len(connections) == 2
        assert all(isinstance(c, EntityRelation) for c in connections)

    def test_d2_result_to_dict(self, d2_result):
        """Test D2 result serialization."""
        result_dict = d2_result.to_dict()

        assert "result_id" in result_dict
        assert result_dict["entities_investigated"] == 2
        assert result_dict["entities_skipped"] == 2
        assert "d1_result" in result_dict


# =============================================================================
# D3Handler Tests
# =============================================================================


class TestD3Handler:
    """Tests for D3Handler."""

    def test_create_d3_handler(self, config):
        """Test D3 handler creation."""
        handler = create_d3_handler(config=config)

        assert handler is not None
        assert handler.config == config
        assert handler.connection_analyzer is not None

    def test_create_d3_handler_with_d2(self, mock_connection_analyzer, config):
        """Test D3 handler creation with D2 handler."""
        d2_handler = create_d2_handler(config=config)
        handler = create_d3_handler(
            d2_handler=d2_handler,
            connection_analyzer=mock_connection_analyzer,
            config=config,
        )

        assert handler.d2_handler == d2_handler
        assert handler.connection_analyzer == mock_connection_analyzer

    @pytest.mark.asyncio
    async def test_execute_d3_basic(self, d2_result, config):
        """Test basic D3 execution."""
        handler = create_d3_handler(config=config)

        result = await handler.execute_d3(
            d2_result=d2_result,
            locale=Locale.US,
            tier=ServiceTier.ENHANCED,
            role_category=RoleCategory.EXECUTIVE,
            available_providers=["sterling"],
        )

        assert isinstance(result, D3Result)
        assert result.d2_result == d2_result
        assert result.completed_at is not None
        assert result.network_depth == config.d3_max_depth

    def test_prioritize_extended_entities(self, discovered_entities, config):
        """Test extended entity prioritization."""
        handler = create_d3_handler(config=config)

        prioritized = handler._prioritize_extended_entities(discovered_entities, max_count=5)

        # D3 uses stricter filtering
        assert len(prioritized) <= 5

    def test_calculate_extended_priority(self, config):
        """Test extended priority calculation."""
        handler = create_d3_handler(config=config)

        entity = DiscoveredEntity(
            entity_id=uuid7(),
            entity_type=EntityType.PERSON,
            name="Test Person",
            confidence=0.7,
            source_providers=["test"],
            metadata={"relationship": "network_connection"},
        )

        score = handler._calculate_extended_priority(entity)

        # D3 has lower base score
        assert 0.0 <= score <= 1.0

    def test_build_extended_connections(self, discovered_entities, config):
        """Test extended connection building."""
        handler = create_d3_handler(config=config)

        d2_entities = discovered_entities[:2]
        d3_entities = discovered_entities[2:]

        connections = handler._build_extended_connections(d2_entities, d3_entities)

        assert len(connections) == len(d3_entities)
        assert all(c.strength == ConnectionStrength.WEAK for c in connections)

    def test_d3_result_to_dict(self, d2_result, config):  # noqa: ARG002
        """Test D3 result serialization."""
        result = D3Result(
            d2_result=d2_result,
            extended_entities_investigated=3,
            extended_entities_skipped=5,
            network_depth=2,
            network_breadth=10,
            total_network_risk=0.25,
        )

        result_dict = result.to_dict()

        assert "result_id" in result_dict
        assert result_dict["extended_entities_investigated"] == 3
        assert result_dict["network_depth"] == 2
        assert result_dict["total_network_risk"] == 0.25


# =============================================================================
# Configuration Tests
# =============================================================================


class TestDegreeHandlerConfig:
    """Tests for DegreeHandlerConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = DegreeHandlerConfig()

        assert config.d2_max_entities == 10
        assert config.d2_min_relevance == 0.5
        assert config.d3_max_entities == 25
        assert config.d3_min_relevance == 0.4
        assert config.d3_max_depth == 2

    def test_custom_config(self):
        """Test custom configuration."""
        config = DegreeHandlerConfig(
            d2_max_entities=5,
            d3_max_entities=15,
            weight_entity_risk=0.5,
        )

        assert config.d2_max_entities == 5
        assert config.d3_max_entities == 15
        assert config.weight_entity_risk == 0.5


# =============================================================================
# Integration Tests
# =============================================================================


class TestDegreeHandlerIntegration:
    """Integration tests for degree handlers."""

    @pytest.mark.asyncio
    async def test_d1_to_d2_flow(self, knowledge_base, config):
        """Test D1 result flows into D2."""
        d1_handler = create_d1_handler(config=config)
        d2_handler = create_d2_handler(config=config)

        # Execute D1
        d1_result = await d1_handler.execute_d1(
            knowledge_base=knowledge_base,
            subject_name="John Smith",
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            role_category=RoleCategory.STANDARD,
            available_providers=["sterling"],
        )

        # D1 result should have empty entity queue
        assert d1_result.entity_queue == []

        # Execute D2 with D1 result
        d2_result = await d2_handler.execute_d2(
            d1_result=d1_result,
            locale=Locale.US,
            tier=ServiceTier.ENHANCED,
            role_category=RoleCategory.STANDARD,
            available_providers=["sterling"],
        )

        assert d2_result.d1_result == d1_result
        assert d2_result.completed_at is not None

    @pytest.mark.asyncio
    async def test_d2_to_d3_flow(self, d1_result, config):
        """Test D2 result flows into D3."""
        d2_handler = create_d2_handler(config=config)
        d3_handler = create_d3_handler(config=config)

        # Execute D2
        d2_result = await d2_handler.execute_d2(
            d1_result=d1_result,
            locale=Locale.US,
            tier=ServiceTier.ENHANCED,
            role_category=RoleCategory.STANDARD,
            available_providers=["sterling"],
        )

        # Execute D3 with D2 result
        d3_result = await d3_handler.execute_d3(
            d2_result=d2_result,
            locale=Locale.US,
            tier=ServiceTier.ENHANCED,
            role_category=RoleCategory.EXECUTIVE,
            available_providers=["sterling"],
        )

        assert d3_result.d2_result == d2_result
        assert d3_result.completed_at is not None

    @pytest.mark.asyncio
    async def test_full_d1_d2_d3_flow(self, knowledge_base, config):
        """Test complete D1 -> D2 -> D3 flow."""
        d1_handler = create_d1_handler(config=config)
        d2_handler = create_d2_handler(config=config)
        d3_handler = create_d3_handler(config=config)

        # D1
        d1_result = await d1_handler.execute_d1(
            knowledge_base=knowledge_base,
            subject_name="John Smith",
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            role_category=RoleCategory.STANDARD,
            available_providers=["sterling"],
        )

        # D2
        d2_result = await d2_handler.execute_d2(
            d1_result=d1_result,
            locale=Locale.US,
            tier=ServiceTier.ENHANCED,
            role_category=RoleCategory.STANDARD,
            available_providers=["sterling"],
        )

        # D3
        d3_result = await d3_handler.execute_d3(
            d2_result=d2_result,
            locale=Locale.US,
            tier=ServiceTier.ENHANCED,
            role_category=RoleCategory.EXECUTIVE,
            available_providers=["sterling"],
        )

        # Verify chain
        assert d3_result.d2_result.d1_result == d1_result
        assert d3_result.completed_at is not None
        assert d2_result.completed_at is not None
        assert d1_result.completed_at is not None


# =============================================================================
# Edge Cases
# =============================================================================


class TestDegreeHandlerEdgeCases:
    """Edge case tests for degree handlers."""

    @pytest.mark.asyncio
    async def test_d1_empty_knowledge_base(self, config):
        """Test D1 with empty knowledge base."""
        handler = create_d1_handler(config=config)
        kb = KnowledgeBase()

        result = await handler.execute_d1(
            knowledge_base=kb,
            subject_name="Unknown",
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            role_category=RoleCategory.STANDARD,
            available_providers=[],
        )

        assert result.entity_queue == []
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_d2_no_discovered_entities(self, config):
        """Test D2 with no discovered entities."""
        handler = create_d2_handler(config=config)
        d1_result = D1Result(discovered_entities=[])

        result = await handler.execute_d2(
            d1_result=d1_result,
            locale=Locale.US,
            tier=ServiceTier.ENHANCED,
            role_category=RoleCategory.STANDARD,
            available_providers=[],
        )

        assert result.entities_investigated == 0
        assert result.entities_skipped == 0

    @pytest.mark.asyncio
    async def test_d3_no_investigated_entities(self, d1_result, config):
        """Test D3 when D2 investigated no entities."""
        d2_result = D2Result(d1_result=d1_result, investigated_entities=[])
        handler = create_d3_handler(config=config)

        result = await handler.execute_d3(
            d2_result=d2_result,
            locale=Locale.US,
            tier=ServiceTier.ENHANCED,
            role_category=RoleCategory.EXECUTIVE,
            available_providers=[],
        )

        assert result.extended_entities_investigated == 0
        assert result.completed_at is not None

    def test_prioritize_empty_list(self, config):
        """Test prioritization with empty entity list."""
        d2_handler = create_d2_handler(config=config)
        d3_handler = create_d3_handler(config=config)

        assert d2_handler._prioritize_entities([], max_count=10) == []
        assert d3_handler._prioritize_extended_entities([], max_count=10) == []

    def test_prioritize_single_entity(self, config):
        """Test prioritization with single entity."""
        handler = create_d2_handler(config=config)
        entity = DiscoveredEntity(
            entity_id=uuid7(),
            entity_type=EntityType.PERSON,
            name="Solo Entity",
            confidence=0.9,
            source_providers=["test"],
            metadata={"relationship": "employer"},
        )

        prioritized = handler._prioritize_entities([entity], max_count=10)

        assert len(prioritized) == 1
        assert prioritized[0] == entity


# =============================================================================
# Task 7.8 Enhanced Feature Tests
# =============================================================================


class TestD3ReviewPoints:
    """Tests for D3 review point creation (Task 7.8)."""

    def test_d3_review_point_types(self):
        """Test D3ReviewPointType enum values."""
        from elile.screening.degree_handlers import D3ReviewPointType

        assert D3ReviewPointType.HIGH_RISK_ENTITY.value == "high_risk_entity"
        assert D3ReviewPointType.SANCTIONS_HIT.value == "sanctions_hit"
        assert D3ReviewPointType.PEP_CONNECTION.value == "pep_connection"
        assert D3ReviewPointType.NETWORK_CLUSTER.value == "network_cluster"
        assert D3ReviewPointType.ADVERSE_MEDIA.value == "adverse_media"

    def test_d3_review_point_creation(self):
        """Test creating a D3ReviewPoint."""
        from elile.screening.degree_handlers import D3ReviewPoint, D3ReviewPointType

        review = D3ReviewPoint(
            review_type=D3ReviewPointType.HIGH_RISK_ENTITY,
            entity_name="Test Entity",
            description="Test description",
            severity="high",
        )

        assert review.review_type == D3ReviewPointType.HIGH_RISK_ENTITY
        assert review.entity_name == "Test Entity"
        assert review.severity == "high"
        assert review.reviewed is False
        assert review.review_id is not None

    def test_d3_review_point_to_dict(self):
        """Test D3ReviewPoint serialization."""
        from elile.screening.degree_handlers import D3ReviewPoint, D3ReviewPointType

        review = D3ReviewPoint(
            review_type=D3ReviewPointType.SANCTIONS_HIT,
            entity_name="Sanctioned Entity",
            description="Potential sanctions match",
            severity="critical",
        )

        review_dict = review.to_dict()

        assert "review_id" in review_dict
        assert review_dict["review_type"] == "sanctions_hit"
        assert review_dict["entity_name"] == "Sanctioned Entity"
        assert review_dict["severity"] == "critical"
        assert review_dict["reviewed"] is False


class TestD3SourceCoverage:
    """Tests for D3 source coverage tracking (Task 7.8)."""

    def test_source_coverage_creation(self):
        """Test D3SourceCoverage creation."""
        from elile.screening.degree_handlers import D3SourceCoverage

        coverage = D3SourceCoverage(total_sources_queried=10)

        assert coverage.total_sources_queried == 10
        assert coverage.coverage_score == 0.0
        assert len(coverage.sanctions_sources_used) == 0

    def test_source_coverage_categorization(self, config):
        """Test provider categorization into source types."""
        from elile.screening.degree_handlers import D3SourceCoverage

        coverage = D3SourceCoverage()

        # Create a D3Handler and use its categorization method
        handler = create_d3_handler(config=config)
        providers = [
            "identity_verify_inc",
            "ofac_sanctions",
            "adverse_media_search",
            "linkedin_social",
        ]
        handler._categorize_providers(providers, coverage)

        assert "identity_verify_inc" in coverage.identity_sources_used
        assert "ofac_sanctions" in coverage.sanctions_sources_used
        assert "adverse_media_search" in coverage.adverse_media_sources_used
        assert "linkedin_social" in coverage.social_media_sources_used

    def test_coverage_score_calculation(self):
        """Test coverage score calculation."""
        from elile.screening.degree_handlers import D3SourceCoverage

        coverage = D3SourceCoverage(total_sources_queried=5)
        coverage.identity_sources_used = ["id1"]
        coverage.sanctions_sources_used = ["sanctions1"]
        coverage.adverse_media_sources_used = ["adverse1"]

        score = coverage.calculate_coverage_score()

        assert 0.0 < score <= 1.0
        assert coverage.coverage_score == score

    def test_source_coverage_to_dict(self):
        """Test D3SourceCoverage serialization."""
        from elile.screening.degree_handlers import D3SourceCoverage

        coverage = D3SourceCoverage(
            total_sources_queried=10,
            sources_with_hits=5,
        )
        coverage.sanctions_sources_used = ["ofac", "un"]

        coverage_dict = coverage.to_dict()

        assert coverage_dict["total_sources_queried"] == 10
        assert coverage_dict["sources_with_hits"] == 5
        assert coverage_dict["sanctions_sources"] == ["ofac", "un"]


class TestD3EnhancedConfig:
    """Tests for D3 enhanced configuration options (Task 7.8)."""

    def test_enhanced_config_defaults(self):
        """Test default values for D3 enhanced config."""
        config = DegreeHandlerConfig()

        assert config.d3_enable_review_points is True
        assert config.d3_review_risk_threshold == 0.7
        assert config.d3_review_on_sanctions_hit is True
        assert config.d3_review_on_pep_connection is True
        assert config.d3_checkpoint_interval == 5
        assert config.d3_extended_sources is True

    def test_enhanced_config_custom(self):
        """Test custom values for D3 enhanced config."""
        config = DegreeHandlerConfig(
            d3_enable_review_points=False,
            d3_review_risk_threshold=0.5,
            d3_checkpoint_interval=10,
        )

        assert config.d3_enable_review_points is False
        assert config.d3_review_risk_threshold == 0.5
        assert config.d3_checkpoint_interval == 10


class TestD3ResultEnhanced:
    """Tests for D3Result enhanced fields (Task 7.8)."""

    def test_d3_result_review_fields(self):
        """Test D3Result review point fields."""
        result = D3Result()

        assert result.review_points == []
        assert result.pending_reviews == 0
        assert result.reviews_completed == 0
        assert result.has_pending_reviews is False

    def test_d3_result_with_review_points(self):
        """Test D3Result with review points."""
        from elile.screening.degree_handlers import D3ReviewPoint, D3ReviewPointType

        result = D3Result()
        result.review_points = [
            D3ReviewPoint(review_type=D3ReviewPointType.SANCTIONS_HIT),
            D3ReviewPoint(review_type=D3ReviewPointType.PEP_CONNECTION),
            D3ReviewPoint(review_type=D3ReviewPointType.SANCTIONS_HIT),
        ]
        result.pending_reviews = 3

        assert result.has_pending_reviews is True
        assert result.review_summary == {"sanctions_hit": 2, "pep_connection": 1}

    def test_d3_result_source_coverage(self):
        """Test D3Result source coverage field."""
        from elile.screening.degree_handlers import D3SourceCoverage

        result = D3Result()
        result.source_coverage = D3SourceCoverage(total_sources_queried=10)

        assert result.source_coverage.total_sources_queried == 10

    def test_d3_result_checkpoint_fields(self):
        """Test D3Result checkpoint reference fields."""
        result = D3Result()

        assert result.checkpoint_ids == []
        assert result.last_checkpoint_id is None
        assert result.investigation_id is None

    def test_d3_result_enhanced_to_dict(self):
        """Test D3Result enhanced serialization."""
        from elile.screening.degree_handlers import (
            D3ReviewPoint,
            D3ReviewPointType,
            D3SourceCoverage,
        )

        result = D3Result()
        result.review_points = [D3ReviewPoint(review_type=D3ReviewPointType.HIGH_RISK_ENTITY)]
        result.pending_reviews = 1
        result.source_coverage = D3SourceCoverage(total_sources_queried=5)

        result_dict = result.to_dict()

        assert len(result_dict["review_points"]) == 1
        assert result_dict["pending_reviews"] == 1
        assert result_dict["source_coverage"]["total_sources_queried"] == 5
        assert "review_summary" in result_dict


class TestD3HandlerEnhanced:
    """Tests for D3Handler enhanced methods (Task 7.8)."""

    @pytest.mark.asyncio
    async def test_execute_d3_with_enhanced_features(self, d2_result, config):
        """Test D3 execution includes enhanced features."""
        config.d3_enable_review_points = True
        config.d3_extended_sources = True
        handler = create_d3_handler(config=config)

        result = await handler.execute_d3(
            d2_result=d2_result,
            locale=Locale.US,
            tier=ServiceTier.ENHANCED,
            role_category=RoleCategory.EXECUTIVE,
            available_providers=["sanctions_check", "pep_lookup"],
        )

        # Should have source coverage initialized
        assert result.source_coverage is not None
        # Should have investigation ID
        assert result.investigation_id is not None

    @pytest.mark.asyncio
    async def test_execute_d3_without_review_points(self, d2_result, config):
        """Test D3 execution with review points disabled."""
        config.d3_enable_review_points = False
        handler = create_d3_handler(config=config)

        result = await handler.execute_d3(
            d2_result=d2_result,
            locale=Locale.US,
            tier=ServiceTier.ENHANCED,
            role_category=RoleCategory.EXECUTIVE,
            available_providers=[],
        )

        assert result.review_points == []
        assert result.pending_reviews == 0

    def test_check_network_review_points_high_risk(self, config):
        """Test network-level review points for high risk."""
        config.d3_review_risk_threshold = 0.5
        handler = create_d3_handler(config=config)

        result = D3Result()
        result.total_network_risk = 0.8  # Above threshold

        reviews = handler._check_network_review_points(result)

        assert len(reviews) >= 1
        assert any(r.review_type.value == "network_cluster" for r in reviews)

    def test_check_network_review_points_depth_threshold(self, config):
        """Test network-level review point for depth threshold."""
        config.d3_max_depth = 2
        handler = create_d3_handler(config=config)

        result = D3Result()
        result.network_depth = 2  # At max depth

        reviews = handler._check_network_review_points(result)

        assert any(r.review_type.value == "depth_threshold" for r in reviews)

    def test_mark_review_complete(self, config):
        """Test marking a review point as complete."""
        from elile.screening.degree_handlers import D3ReviewPoint, D3ReviewPointType

        handler = create_d3_handler(config=config)
        result = D3Result()
        review = D3ReviewPoint(review_type=D3ReviewPointType.HIGH_RISK_ENTITY)
        result.review_points = [review]
        result.pending_reviews = 1

        success = handler.mark_review_complete(
            result=result,
            review_id=review.review_id,
            reviewer_notes="Investigated and cleared",
            decision="continue",
        )

        assert success is True
        assert review.reviewed is True
        assert review.reviewer_notes == "Investigated and cleared"
        assert review.decision == "continue"
        assert result.pending_reviews == 0
        assert result.reviews_completed == 1

    def test_mark_review_complete_not_found(self, config):
        """Test marking a non-existent review point."""
        handler = create_d3_handler(config=config)
        result = D3Result()

        success = handler.mark_review_complete(
            result=result,
            review_id=uuid7(),
            reviewer_notes="",
            decision="continue",
        )

        assert success is False

    def test_get_pending_reviews(self, config):
        """Test getting pending review points."""
        from elile.screening.degree_handlers import D3ReviewPoint, D3ReviewPointType

        handler = create_d3_handler(config=config)
        result = D3Result()

        reviewed = D3ReviewPoint(review_type=D3ReviewPointType.HIGH_RISK_ENTITY)
        reviewed.reviewed = True

        pending = D3ReviewPoint(review_type=D3ReviewPointType.SANCTIONS_HIT)

        result.review_points = [reviewed, pending]

        pending_reviews = handler.get_pending_reviews(result)

        assert len(pending_reviews) == 1
        assert pending_reviews[0].review_id == pending.review_id

    def test_create_d3_handler_with_checkpoint_manager(self, config):
        """Test D3Handler creation with checkpoint manager."""
        from elile.investigation.checkpoint import create_checkpoint_manager

        checkpoint_manager = create_checkpoint_manager()
        handler = create_d3_handler(
            checkpoint_manager=checkpoint_manager,
            config=config,
        )

        assert handler.checkpoint_manager is checkpoint_manager
