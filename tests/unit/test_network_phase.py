"""Tests for the NetworkPhaseHandler module.

Tests cover:
- Entity type and relation type enums
- Discovered entity tracking
- Entity relation modeling
- Risk connection identification
- Network profile aggregation
- Phase execution and results
"""

import pytest
from uuid import uuid4

from elile.investigation.phases.network import (
    ConnectionStrength,
    DiscoveredEntity,
    EntityRelation,
    EntityType,
    NetworkConfig,
    NetworkPhaseHandler,
    NetworkPhaseResult,
    NetworkProfile,
    RelationType,
    RiskConnection,
    RiskLevel,
    create_network_phase_handler,
)


class TestEntityType:
    """Tests for EntityType enum."""

    def test_all_entity_types_exist(self) -> None:
        """Test all expected entity types exist."""
        assert EntityType.PERSON.value == "person"
        assert EntityType.COMPANY.value == "company"
        assert EntityType.ORGANIZATION.value == "organization"
        assert EntityType.TRUST.value == "trust"
        assert EntityType.GOVERNMENT_ENTITY.value == "government_entity"
        assert EntityType.SHELL_COMPANY.value == "shell_company"
        assert EntityType.UNKNOWN.value == "unknown"


class TestRelationType:
    """Tests for RelationType enum."""

    def test_primary_relation_types_exist(self) -> None:
        """Test primary relation types exist."""
        assert RelationType.FAMILY.value == "family"
        assert RelationType.BUSINESS.value == "business"
        assert RelationType.OWNERSHIP.value == "ownership"
        assert RelationType.FINANCIAL.value == "financial"
        assert RelationType.EMPLOYMENT.value == "employment"

    def test_detailed_business_relations_exist(self) -> None:
        """Test detailed business relations exist."""
        assert RelationType.EMPLOYER.value == "employer"
        assert RelationType.BUSINESS_PARTNER.value == "business_partner"
        assert RelationType.SHAREHOLDER.value == "shareholder"
        assert RelationType.BENEFICIAL_OWNER.value == "beneficial_owner"

    def test_detailed_personal_relations_exist(self) -> None:
        """Test detailed personal relations exist."""
        assert RelationType.SPOUSE.value == "spouse"
        assert RelationType.ASSOCIATE.value == "associate"
        assert RelationType.FRIEND.value == "friend"


class TestRiskLevel:
    """Tests for RiskLevel enum."""

    def test_all_risk_levels_exist(self) -> None:
        """Test all expected risk levels exist."""
        assert RiskLevel.NONE.value == "none"
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MODERATE.value == "moderate"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"


class TestConnectionStrength:
    """Tests for ConnectionStrength enum."""

    def test_all_connection_strengths_exist(self) -> None:
        """Test all expected connection strengths exist."""
        assert ConnectionStrength.WEAK.value == "weak"
        assert ConnectionStrength.MODERATE.value == "moderate"
        assert ConnectionStrength.STRONG.value == "strong"
        assert ConnectionStrength.DIRECT.value == "direct"


class TestDiscoveredEntity:
    """Tests for DiscoveredEntity dataclass."""

    def test_discovered_entity_defaults(self) -> None:
        """Test default entity values."""
        entity = DiscoveredEntity()
        assert entity.entity_type == EntityType.UNKNOWN
        assert entity.name == ""
        assert entity.discovery_degree == 2
        assert entity.is_sanctioned is False
        assert entity.is_pep is False

    def test_discovered_entity_person(self) -> None:
        """Test person entity."""
        entity = DiscoveredEntity(
            entity_type=EntityType.PERSON,
            name="John Doe",
            aliases=["J. Doe", "Johnny"],
            jurisdiction="US",
            discovery_degree=2,
            confidence=0.9,
        )
        assert entity.entity_type == EntityType.PERSON
        assert len(entity.aliases) == 2

    def test_discovered_entity_sanctioned(self) -> None:
        """Test sanctioned entity."""
        entity = DiscoveredEntity(
            entity_type=EntityType.COMPANY,
            name="Shell Corp LLC",
            is_sanctioned=True,
            risk_indicators=["ofac_match", "shell_company"],
        )
        assert entity.is_sanctioned is True
        assert len(entity.risk_indicators) == 2

    def test_discovered_entity_pep(self) -> None:
        """Test PEP entity."""
        entity = DiscoveredEntity(
            entity_type=EntityType.PERSON,
            name="Government Official",
            is_pep=True,
        )
        assert entity.is_pep is True

    def test_discovered_entity_to_dict(self) -> None:
        """Test entity serialization."""
        entity = DiscoveredEntity(
            entity_type=EntityType.ORGANIZATION,
            name="Test Org",
            confidence=0.85,
        )
        d = entity.to_dict()
        assert d["entity_type"] == "organization"
        assert d["name"] == "Test Org"
        assert d["confidence"] == 0.85
        assert "entity_id" in d


class TestEntityRelation:
    """Tests for EntityRelation dataclass."""

    def test_entity_relation_defaults(self) -> None:
        """Test default relation values."""
        relation = EntityRelation()
        assert relation.relation_type == RelationType.UNKNOWN
        assert relation.strength == ConnectionStrength.MODERATE
        assert relation.bidirectional is False

    def test_entity_relation_business(self) -> None:
        """Test business relation."""
        source_id = uuid4()
        target_id = uuid4()
        relation = EntityRelation(
            source_entity_id=source_id,
            target_entity_id=target_id,
            relation_type=RelationType.BUSINESS_PARTNER,
            strength=ConnectionStrength.STRONG,
            bidirectional=True,
            confidence=0.9,
        )
        assert relation.relation_type == RelationType.BUSINESS_PARTNER
        assert relation.bidirectional is True

    def test_entity_relation_is_current(self) -> None:
        """Test is_current property."""
        relation = EntityRelation(end_date=None)
        assert relation.is_current is True

    def test_entity_relation_is_not_current(self) -> None:
        """Test is_current property for ended relation."""
        from datetime import datetime, UTC

        relation = EntityRelation(end_date=datetime.now(UTC))
        assert relation.is_current is False

    def test_entity_relation_to_dict(self) -> None:
        """Test relation serialization."""
        relation = EntityRelation(
            relation_type=RelationType.EMPLOYER,
            strength=ConnectionStrength.DIRECT,
        )
        d = relation.to_dict()
        assert d["relation_type"] == "employer"
        assert d["strength"] == "direct"
        assert d["is_current"] is True


class TestRiskConnection:
    """Tests for RiskConnection dataclass."""

    def test_risk_connection_defaults(self) -> None:
        """Test default risk connection values."""
        risk = RiskConnection()
        assert risk.risk_level == RiskLevel.MODERATE
        assert risk.path_length == 1
        assert risk.requires_review is False

    def test_risk_connection_high(self) -> None:
        """Test high risk connection."""
        source_id = uuid4()
        target_id = uuid4()
        risk = RiskConnection(
            source_entity_id=source_id,
            target_entity_id=target_id,
            risk_level=RiskLevel.HIGH,
            risk_types=["pep_connection"],
            path_length=1,
            risk_factors=["Connection to government official"],
            recommendations=["Enhanced due diligence"],
            requires_review=True,
            confidence=0.85,
        )
        assert risk.risk_level == RiskLevel.HIGH
        assert risk.requires_review is True

    def test_risk_connection_critical(self) -> None:
        """Test critical risk connection (sanctions)."""
        risk = RiskConnection(
            risk_level=RiskLevel.CRITICAL,
            risk_types=["sanctions_hit"],
            requires_review=True,
        )
        assert risk.risk_level == RiskLevel.CRITICAL

    def test_risk_connection_to_dict(self) -> None:
        """Test risk connection serialization."""
        risk = RiskConnection(
            risk_level=RiskLevel.HIGH,
            risk_factors=["Factor 1", "Factor 2"],
        )
        d = risk.to_dict()
        assert d["risk_level"] == "high"
        assert len(d["risk_factors"]) == 2


class TestNetworkProfile:
    """Tests for NetworkProfile dataclass."""

    def test_network_profile_defaults(self) -> None:
        """Test default profile values."""
        profile = NetworkProfile()
        assert profile.entity_count == 0
        assert profile.relation_count == 0
        assert profile.high_risk_count == 0
        assert profile.d2_complete is False
        assert profile.d3_complete is False

    def test_network_profile_post_init_counts(self) -> None:
        """Test post_init calculates counts correctly."""
        entities = [
            DiscoveredEntity(name="Entity 1"),
            DiscoveredEntity(name="Entity 2"),
        ]
        relations = [EntityRelation()]
        risk_connections = [
            RiskConnection(risk_level=RiskLevel.HIGH),
            RiskConnection(risk_level=RiskLevel.CRITICAL),
            RiskConnection(risk_level=RiskLevel.LOW),
        ]
        profile = NetworkProfile(
            entities=entities,
            relations=relations,
            risk_connections=risk_connections,
        )
        assert profile.entity_count == 2
        assert profile.relation_count == 1
        assert profile.high_risk_count == 2  # HIGH + CRITICAL

    def test_get_entity(self) -> None:
        """Test getting entity by ID."""
        entity = DiscoveredEntity(name="Test Entity")
        profile = NetworkProfile(entities=[entity])

        found = profile.get_entity(entity.entity_id)
        assert found is not None
        assert found.name == "Test Entity"

    def test_get_entity_not_found(self) -> None:
        """Test getting non-existent entity."""
        profile = NetworkProfile()
        found = profile.get_entity(uuid4())
        assert found is None

    def test_get_relations_for_entity(self) -> None:
        """Test getting relations for entity."""
        entity_id = uuid4()
        other_id = uuid4()
        relations = [
            EntityRelation(source_entity_id=entity_id, target_entity_id=other_id),
            EntityRelation(source_entity_id=other_id, target_entity_id=entity_id),
            EntityRelation(source_entity_id=uuid4(), target_entity_id=uuid4()),
        ]
        profile = NetworkProfile(relations=relations)

        found = profile.get_relations_for_entity(entity_id)
        assert len(found) == 2

    def test_get_risk_connections_for_entity(self) -> None:
        """Test getting risk connections for entity."""
        entity_id = uuid4()
        risk_connections = [
            RiskConnection(source_entity_id=entity_id),
            RiskConnection(target_entity_id=entity_id),
            RiskConnection(source_entity_id=uuid4()),
        ]
        profile = NetworkProfile(risk_connections=risk_connections)

        found = profile.get_risk_connections_for_entity(entity_id)
        assert len(found) == 2

    def test_network_profile_to_dict(self) -> None:
        """Test profile serialization."""
        entities = [DiscoveredEntity(name=f"Entity {i}") for i in range(5)]
        profile = NetworkProfile(
            d2_complete=True,
            entities=entities,
        )
        d = profile.to_dict()
        assert d["d2_complete"] is True
        assert d["entity_count"] == 5


class TestNetworkConfig:
    """Tests for NetworkConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = NetworkConfig()
        assert config.max_entities_per_degree == 20
        assert config.enable_d2 is True
        assert config.enable_d3 is False
        assert config.auto_flag_sanctions is True
        assert config.auto_flag_pep is True

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = NetworkConfig(
            max_entities_per_degree=50,
            enable_d3=True,
            historical_lookback_years=10,
        )
        assert config.max_entities_per_degree == 50
        assert config.enable_d3 is True
        assert config.historical_lookback_years == 10


class TestNetworkPhaseResult:
    """Tests for NetworkPhaseResult."""

    def test_result_defaults(self) -> None:
        """Test default result values."""
        result = NetworkPhaseResult()
        assert result.success is True
        assert result.entities_analyzed == 0
        assert result.relations_found == 0

    def test_result_to_dict(self) -> None:
        """Test result serialization."""
        result = NetworkPhaseResult(
            success=True,
            entities_analyzed=10,
            relations_found=25,
            risks_identified=3,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["entities_analyzed"] == 10
        assert d["relations_found"] == 25


class TestNetworkPhaseHandler:
    """Tests for NetworkPhaseHandler."""

    @pytest.fixture
    def handler(self) -> NetworkPhaseHandler:
        """Create a handler with default config."""
        return NetworkPhaseHandler()

    @pytest.mark.asyncio
    async def test_execute_d2(self, handler: NetworkPhaseHandler) -> None:
        """Test D2 execution."""
        subject_id = uuid4()
        result = await handler.execute(
            subject_entity_id=subject_id,
            degree=2,
        )

        assert result.success is True
        assert result.profile.d2_complete is True
        assert result.profile.d3_complete is False

    @pytest.mark.asyncio
    async def test_execute_d3(self, handler: NetworkPhaseHandler) -> None:
        """Test D3 execution."""
        subject_id = uuid4()
        result = await handler.execute(
            subject_entity_id=subject_id,
            degree=3,
        )

        assert result.success is True
        assert result.profile.d2_complete is True
        assert result.profile.d3_complete is True

    @pytest.mark.asyncio
    async def test_execute_with_intelligence(self, handler: NetworkPhaseHandler) -> None:
        """Test execution with intelligence data."""
        subject_id = uuid4()
        intelligence_data = {
            "employment": [{"company": "Test Corp"}],
            "associations": [{"name": "Known Associate"}],
        }
        result = await handler.execute(
            subject_entity_id=subject_id,
            intelligence_data=intelligence_data,
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_records_timing(self, handler: NetworkPhaseHandler) -> None:
        """Test that execution records timing."""
        result = await handler.execute(subject_entity_id=uuid4())

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.duration_ms >= 0

    def test_identify_risk_connections_sanctions(self) -> None:
        """Test that sanctioned entities are flagged."""
        handler = NetworkPhaseHandler()
        subject_id = uuid4()
        entities = [
            DiscoveredEntity(name="Sanctioned Entity", is_sanctioned=True),
        ]

        risks = handler._identify_risk_connections(entities, [], subject_id)

        assert len(risks) == 1
        assert risks[0].risk_level == RiskLevel.CRITICAL
        assert "sanctions_connection" in risks[0].risk_types

    def test_identify_risk_connections_pep(self) -> None:
        """Test that PEP connections are flagged."""
        handler = NetworkPhaseHandler()
        subject_id = uuid4()
        entities = [
            DiscoveredEntity(name="Government Official", is_pep=True),
        ]

        risks = handler._identify_risk_connections(entities, [], subject_id)

        assert len(risks) == 1
        assert risks[0].risk_level == RiskLevel.HIGH
        assert "pep_connection" in risks[0].risk_types

    def test_identify_risk_connections_disabled(self) -> None:
        """Test that auto-flagging can be disabled."""
        config = NetworkConfig(
            auto_flag_sanctions=False,
            auto_flag_pep=False,
        )
        handler = NetworkPhaseHandler(config=config)
        subject_id = uuid4()
        entities = [
            DiscoveredEntity(name="Sanctioned", is_sanctioned=True),
            DiscoveredEntity(name="PEP", is_pep=True),
        ]

        risks = handler._identify_risk_connections(entities, [], subject_id)

        assert len(risks) == 0

    def test_custom_config(self) -> None:
        """Test handler with custom configuration."""
        config = NetworkConfig(
            max_entities_per_degree=50,
            enable_d3=True,
        )
        handler = NetworkPhaseHandler(config=config)

        assert handler.config.max_entities_per_degree == 50
        assert handler.config.enable_d3 is True


class TestCreateNetworkPhaseHandler:
    """Tests for factory function."""

    def test_create_with_defaults(self) -> None:
        """Test creating handler with defaults."""
        handler = create_network_phase_handler()
        assert isinstance(handler, NetworkPhaseHandler)

    def test_create_with_config(self) -> None:
        """Test creating handler with custom config."""
        config = NetworkConfig(enable_d3=True)
        handler = create_network_phase_handler(config=config)
        assert handler.config.enable_d3 is True
