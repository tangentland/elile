"""Unit tests for InformationTypeManager."""

import pytest

from elile.agent.state import InformationType, ServiceTier
from elile.compliance.types import Locale, RoleCategory
from elile.investigation.information_type_manager import (
    PHASE_ORDER,
    PHASE_TYPES,
    TYPE_DEPENDENCIES,
    InformationPhase,
    InformationTypeManager,
    TypeDependency,
    TypeSequence,
    create_information_type_manager,
)


class TestInformationPhase:
    """Tests for InformationPhase enum."""

    def test_phase_values(self):
        """Test that all expected phases exist."""
        assert InformationPhase.FOUNDATION == "foundation"
        assert InformationPhase.RECORDS == "records"
        assert InformationPhase.INTELLIGENCE == "intelligence"
        assert InformationPhase.NETWORK == "network"
        assert InformationPhase.RECONCILIATION == "reconciliation"

    def test_phase_order(self):
        """Test that phase order is correct."""
        assert PHASE_ORDER[0] == InformationPhase.FOUNDATION
        assert PHASE_ORDER[1] == InformationPhase.RECORDS
        assert PHASE_ORDER[2] == InformationPhase.INTELLIGENCE
        assert PHASE_ORDER[3] == InformationPhase.NETWORK
        assert PHASE_ORDER[4] == InformationPhase.RECONCILIATION


class TestTypeDependency:
    """Tests for TypeDependency dataclass."""

    def test_dependency_creation(self):
        """Test creating a type dependency."""
        dep = TypeDependency(
            info_type=InformationType.IDENTITY,
            phase=InformationPhase.FOUNDATION,
            depends_on=[],
        )

        assert dep.info_type == InformationType.IDENTITY
        assert dep.phase == InformationPhase.FOUNDATION
        assert dep.depends_on == []
        assert dep.requires_enhanced is False

    def test_dependency_with_requirements(self):
        """Test dependency with enhanced requirement."""
        dep = TypeDependency(
            info_type=InformationType.DIGITAL_FOOTPRINT,
            phase=InformationPhase.INTELLIGENCE,
            depends_on=[InformationType.IDENTITY],
            requires_enhanced=True,
        )

        assert dep.requires_enhanced is True
        assert InformationType.IDENTITY in dep.depends_on


class TestTypeSequence:
    """Tests for TypeSequence dataclass."""

    def test_empty_sequence(self):
        """Test creating an empty sequence."""
        seq = TypeSequence(
            next_types=[],
            current_phase=InformationPhase.FOUNDATION,
            phase_complete=False,
            all_complete=False,
        )

        assert seq.next_types == []
        assert seq.current_phase == InformationPhase.FOUNDATION
        assert seq.phase_complete is False
        assert seq.all_complete is False

    def test_sequence_with_blocked(self):
        """Test sequence with blocked types."""
        seq = TypeSequence(
            next_types=[InformationType.IDENTITY],
            current_phase=InformationPhase.FOUNDATION,
            phase_complete=False,
            all_complete=False,
            blocked_types=[InformationType.EMPLOYMENT],
            blocked_reasons={InformationType.EMPLOYMENT: "Waiting for: identity"},
        )

        assert InformationType.EMPLOYMENT in seq.blocked_types
        assert "identity" in seq.blocked_reasons[InformationType.EMPLOYMENT].lower()


class TestPhasesAndDependencies:
    """Tests for phase and dependency constants."""

    def test_foundation_types(self):
        """Test foundation phase types."""
        foundation = PHASE_TYPES[InformationPhase.FOUNDATION]
        assert InformationType.IDENTITY in foundation
        assert InformationType.EMPLOYMENT in foundation
        assert InformationType.EDUCATION in foundation

    def test_records_types(self):
        """Test records phase types."""
        records = PHASE_TYPES[InformationPhase.RECORDS]
        assert InformationType.CRIMINAL in records
        assert InformationType.CIVIL in records
        assert InformationType.FINANCIAL in records
        assert InformationType.LICENSES in records
        assert InformationType.SANCTIONS in records

    def test_intelligence_types(self):
        """Test intelligence phase types."""
        intel = PHASE_TYPES[InformationPhase.INTELLIGENCE]
        assert InformationType.ADVERSE_MEDIA in intel
        assert InformationType.DIGITAL_FOOTPRINT in intel

    def test_network_types(self):
        """Test network phase types."""
        network = PHASE_TYPES[InformationPhase.NETWORK]
        assert InformationType.NETWORK_D2 in network
        assert InformationType.NETWORK_D3 in network

    def test_identity_has_no_dependencies(self):
        """Test that identity has no dependencies."""
        dep = TYPE_DEPENDENCIES[InformationType.IDENTITY]
        assert dep.depends_on == []

    def test_employment_depends_on_identity(self):
        """Test that employment depends on identity."""
        dep = TYPE_DEPENDENCIES[InformationType.EMPLOYMENT]
        assert InformationType.IDENTITY in dep.depends_on

    def test_criminal_depends_on_identity(self):
        """Test that criminal depends on identity."""
        dep = TYPE_DEPENDENCIES[InformationType.CRIMINAL]
        assert InformationType.IDENTITY in dep.depends_on

    def test_digital_footprint_requires_enhanced(self):
        """Test that digital footprint requires enhanced tier."""
        dep = TYPE_DEPENDENCIES[InformationType.DIGITAL_FOOTPRINT]
        assert dep.requires_enhanced is True

    def test_network_d3_requires_enhanced(self):
        """Test that network D3 requires enhanced tier."""
        dep = TYPE_DEPENDENCIES[InformationType.NETWORK_D3]
        assert dep.requires_enhanced is True


class TestInformationTypeManager:
    """Tests for InformationTypeManager class."""

    @pytest.fixture
    def manager(self):
        """Create a manager without compliance engine."""
        return InformationTypeManager()

    def test_creation_without_compliance(self):
        """Test creating manager without compliance engine."""
        manager = InformationTypeManager()
        assert manager.compliance is None

    def test_get_types_for_foundation_phase(self, manager):
        """Test getting types for foundation phase."""
        types = manager.get_types_for_phase(
            phase=InformationPhase.FOUNDATION,
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
        )

        assert InformationType.IDENTITY in types
        assert InformationType.EMPLOYMENT in types
        assert InformationType.EDUCATION in types

    def test_get_types_for_records_phase(self, manager):
        """Test getting types for records phase."""
        types = manager.get_types_for_phase(
            phase=InformationPhase.RECORDS,
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
        )

        assert InformationType.CRIMINAL in types
        assert InformationType.SANCTIONS in types

    def test_enhanced_types_filtered_for_standard_tier(self, manager):
        """Test that enhanced-only types are filtered for standard tier."""
        intel_types = manager.get_types_for_phase(
            phase=InformationPhase.INTELLIGENCE,
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
        )

        # Digital footprint requires enhanced
        assert InformationType.DIGITAL_FOOTPRINT not in intel_types
        assert InformationType.ADVERSE_MEDIA in intel_types

    def test_enhanced_types_included_for_enhanced_tier(self, manager):
        """Test that enhanced types are included for enhanced tier."""
        intel_types = manager.get_types_for_phase(
            phase=InformationPhase.INTELLIGENCE,
            tier=ServiceTier.ENHANCED,
            locale=Locale.US,
        )

        assert InformationType.DIGITAL_FOOTPRINT in intel_types
        assert InformationType.ADVERSE_MEDIA in intel_types


class TestGetNextTypes:
    """Tests for get_next_types method."""

    @pytest.fixture
    def manager(self):
        """Create a manager."""
        return InformationTypeManager()

    def test_initial_types_empty_completed(self, manager):
        """Test getting initial types with nothing completed."""
        sequence = manager.get_next_types(
            completed_types=[],
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
        )

        # Only identity should be ready (others depend on it)
        assert InformationType.IDENTITY in sequence.next_types
        assert sequence.current_phase == InformationPhase.FOUNDATION
        assert sequence.phase_complete is False
        assert sequence.all_complete is False

    def test_types_after_identity_complete(self, manager):
        """Test types available after identity completes."""
        sequence = manager.get_next_types(
            completed_types=[InformationType.IDENTITY],
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
        )

        # Employment and education should be ready
        assert InformationType.EMPLOYMENT in sequence.next_types
        assert InformationType.EDUCATION in sequence.next_types

        # Criminal should also be ready (only depends on identity)
        assert InformationType.CRIMINAL in sequence.next_types

    def test_types_after_foundation_complete(self, manager):
        """Test types available after foundation completes."""
        sequence = manager.get_next_types(
            completed_types=[
                InformationType.IDENTITY,
                InformationType.EMPLOYMENT,
                InformationType.EDUCATION,
            ],
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
        )

        assert sequence.current_phase == InformationPhase.RECORDS
        # All records types should be ready
        assert InformationType.CRIMINAL in sequence.next_types
        assert InformationType.CIVIL in sequence.next_types
        assert InformationType.FINANCIAL in sequence.next_types

    def test_blocked_types_tracking(self, manager):
        """Test that blocked types are tracked with reasons."""
        sequence = manager.get_next_types(
            completed_types=[],
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
        )

        # Employment should be blocked waiting for identity
        assert InformationType.EMPLOYMENT in sequence.blocked_types
        assert InformationType.EMPLOYMENT in sequence.blocked_reasons

    def test_all_complete_detection(self, manager):
        """Test detection when all types are complete."""
        # Complete all standard tier types
        all_types = [
            InformationType.IDENTITY,
            InformationType.EMPLOYMENT,
            InformationType.EDUCATION,
            InformationType.CRIMINAL,
            InformationType.CIVIL,
            InformationType.FINANCIAL,
            InformationType.LICENSES,
            InformationType.REGULATORY,
            InformationType.SANCTIONS,
            InformationType.ADVERSE_MEDIA,
            InformationType.NETWORK_D2,
            InformationType.RECONCILIATION,
        ]

        sequence = manager.get_next_types(
            completed_types=all_types,
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
        )

        assert sequence.all_complete is True
        assert len(sequence.next_types) == 0


class TestDependencyResolution:
    """Tests for dependency resolution logic."""

    @pytest.fixture
    def manager(self):
        """Create a manager."""
        return InformationTypeManager()

    def test_get_type_dependencies(self, manager):
        """Test getting dependencies for a type."""
        deps = manager.get_type_dependencies(InformationType.EMPLOYMENT)
        assert InformationType.IDENTITY in deps

    def test_get_type_dependencies_no_deps(self, manager):
        """Test getting dependencies for type with none."""
        deps = manager.get_type_dependencies(InformationType.IDENTITY)
        assert deps == []

    def test_get_type_phase(self, manager):
        """Test getting phase for a type."""
        phase = manager.get_type_phase(InformationType.CRIMINAL)
        assert phase == InformationPhase.RECORDS

    def test_is_foundation_type_true(self, manager):
        """Test is_foundation_type for foundation types."""
        assert manager.is_foundation_type(InformationType.IDENTITY) is True
        assert manager.is_foundation_type(InformationType.EMPLOYMENT) is True
        assert manager.is_foundation_type(InformationType.EDUCATION) is True

    def test_is_foundation_type_false(self, manager):
        """Test is_foundation_type for non-foundation types."""
        assert manager.is_foundation_type(InformationType.CRIMINAL) is False
        assert manager.is_foundation_type(InformationType.SANCTIONS) is False

    def test_requires_foundation_complete(self, manager):
        """Test that foundation is always required first."""
        assert manager.requires_foundation_complete() is True


class TestPhaseComplete:
    """Tests for phase completion detection."""

    @pytest.fixture
    def manager(self):
        """Create a manager."""
        return InformationTypeManager()

    def test_foundation_not_complete_empty(self, manager):
        """Test foundation phase incomplete when empty."""
        sequence = manager.get_next_types(
            completed_types=[],
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
        )
        assert sequence.phase_complete is False

    def test_foundation_complete_all_types(self, manager):
        """Test foundation phase complete when all types done."""
        sequence = manager.get_next_types(
            completed_types=[
                InformationType.IDENTITY,
                InformationType.EMPLOYMENT,
                InformationType.EDUCATION,
            ],
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
        )

        # Current phase should be records after foundation complete
        assert sequence.current_phase == InformationPhase.RECORDS


class TestEnhancedTierTypes:
    """Tests for enhanced tier type handling."""

    @pytest.fixture
    def manager(self):
        """Create a manager."""
        return InformationTypeManager()

    def test_network_d3_available_enhanced(self, manager):
        """Test network D3 available for enhanced tier."""
        network_types = manager.get_types_for_phase(
            phase=InformationPhase.NETWORK,
            tier=ServiceTier.ENHANCED,
            locale=Locale.US,
        )

        assert InformationType.NETWORK_D3 in network_types
        assert InformationType.NETWORK_D2 in network_types

    def test_network_d3_not_available_standard(self, manager):
        """Test network D3 not available for standard tier."""
        network_types = manager.get_types_for_phase(
            phase=InformationPhase.NETWORK,
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
        )

        assert InformationType.NETWORK_D3 not in network_types
        assert InformationType.NETWORK_D2 in network_types


class TestRegulatoryDependencies:
    """Tests for regulatory type dependencies."""

    @pytest.fixture
    def manager(self):
        """Create a manager."""
        return InformationTypeManager()

    def test_regulatory_needs_employment(self, manager):
        """Test that regulatory depends on employment."""
        deps = manager.get_type_dependencies(InformationType.REGULATORY)
        assert InformationType.EMPLOYMENT in deps
        assert InformationType.IDENTITY in deps

    def test_regulatory_blocked_without_employment(self, manager):
        """Test regulatory blocked when employment not complete."""
        sequence = manager.get_next_types(
            completed_types=[InformationType.IDENTITY],
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
        )

        # Regulatory should be blocked
        assert InformationType.REGULATORY in sequence.blocked_types


class TestFactoryFunction:
    """Tests for create_information_type_manager factory."""

    def test_create_manager_default(self):
        """Test creating manager with defaults."""
        manager = create_information_type_manager()
        assert isinstance(manager, InformationTypeManager)
        assert manager.compliance is None

    def test_create_manager_with_compliance(self):
        """Test creating manager with compliance engine."""
        # Create a mock compliance engine
        class MockComplianceEngine:
            def evaluate_check(self, locale, check_type, role_category, tier):
                class MockResult:
                    permitted = True

                return MockResult()

        engine = MockComplianceEngine()
        manager = create_information_type_manager(compliance_engine=engine)

        assert manager.compliance is engine


class TestNetworkPhaseSequencing:
    """Tests for network phase sequencing."""

    @pytest.fixture
    def manager(self):
        """Create a manager."""
        return InformationTypeManager()

    def test_network_d2_after_foundation(self, manager):
        """Test network D2 available after foundation."""
        sequence = manager.get_next_types(
            completed_types=[
                InformationType.IDENTITY,
                InformationType.EMPLOYMENT,
            ],
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
        )

        # Network D2 should be available (only needs identity and employment)
        assert InformationType.NETWORK_D2 in sequence.next_types

    def test_network_d3_needs_d2(self, manager):
        """Test network D3 depends on D2."""
        deps = manager.get_type_dependencies(InformationType.NETWORK_D3)
        assert InformationType.NETWORK_D2 in deps


class TestReconciliationPhase:
    """Tests for reconciliation phase."""

    @pytest.fixture
    def manager(self):
        """Create a manager."""
        return InformationTypeManager()

    def test_reconciliation_in_final_phase(self):
        """Test reconciliation is in final phase."""
        assert InformationType.RECONCILIATION in PHASE_TYPES[InformationPhase.RECONCILIATION]

    def test_reconciliation_depends_on_multiple(self, manager):
        """Test reconciliation depends on multiple types."""
        deps = manager.get_type_dependencies(InformationType.RECONCILIATION)
        assert InformationType.IDENTITY in deps
        assert InformationType.EMPLOYMENT in deps
        assert InformationType.EDUCATION in deps
        assert InformationType.CRIMINAL in deps
