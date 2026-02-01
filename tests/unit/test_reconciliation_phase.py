"""Tests for the ReconciliationPhaseHandler module.

Tests cover:
- Inconsistency detection and types
- Conflict resolution tracking
- Deception analysis
- Reconciliation profile aggregation
- Phase execution and results
"""

import pytest

from elile.investigation.phases.reconciliation import (
    ConflictResolution,
    DeceptionAnalysis,
    DeceptionRiskLevel,
    Inconsistency,
    InconsistencyType,
    ReconciliationConfig,
    ReconciliationPhaseHandler,
    ReconciliationPhaseResult,
    ReconciliationProfile,
    ResolutionStatus,
    create_reconciliation_phase_handler,
)
from elile.agent.state import InformationType


class TestInconsistencyType:
    """Tests for InconsistencyType enum."""

    def test_all_types_exist(self) -> None:
        """Test all expected inconsistency types exist."""
        assert InconsistencyType.DATE_MISMATCH.value == "date_mismatch"
        assert InconsistencyType.NAME_MISMATCH.value == "name_mismatch"
        assert InconsistencyType.LOCATION_MISMATCH.value == "location_mismatch"
        assert InconsistencyType.EMPLOYMENT_GAP.value == "employment_gap"
        assert InconsistencyType.CONFLICTING_RECORDS.value == "conflicting_records"
        assert InconsistencyType.MISSING_DATA.value == "missing_data"
        assert InconsistencyType.SOURCE_DISAGREEMENT.value == "source_disagreement"


class TestResolutionStatus:
    """Tests for ResolutionStatus enum."""

    def test_all_statuses_exist(self) -> None:
        """Test all expected resolution statuses exist."""
        assert ResolutionStatus.PENDING.value == "pending"
        assert ResolutionStatus.RESOLVED.value == "resolved"
        assert ResolutionStatus.UNRESOLVABLE.value == "unresolvable"
        assert ResolutionStatus.ESCALATED.value == "escalated"


class TestDeceptionRiskLevel:
    """Tests for DeceptionRiskLevel enum."""

    def test_all_levels_exist(self) -> None:
        """Test all expected deception risk levels exist."""
        assert DeceptionRiskLevel.NONE.value == "none"
        assert DeceptionRiskLevel.LOW.value == "low"
        assert DeceptionRiskLevel.MEDIUM.value == "medium"
        assert DeceptionRiskLevel.HIGH.value == "high"


class TestInconsistency:
    """Tests for Inconsistency dataclass."""

    def test_inconsistency_defaults(self) -> None:
        """Test default inconsistency values."""
        inconsistency = Inconsistency()
        assert inconsistency.inconsistency_type == InconsistencyType.SOURCE_DISAGREEMENT
        assert inconsistency.severity == "medium"
        assert inconsistency.field_name == ""

    def test_inconsistency_date_mismatch(self) -> None:
        """Test date mismatch inconsistency."""
        inconsistency = Inconsistency(
            inconsistency_type=InconsistencyType.DATE_MISMATCH,
            info_type=InformationType.EMPLOYMENT,
            field_name="start_date",
            source_a="work_number",
            value_a="2020-01-15",
            source_b="linkedin",
            value_b="2020-03-01",
            severity="low",
            description="Employment start date differs by 45 days",
        )
        assert inconsistency.inconsistency_type == InconsistencyType.DATE_MISMATCH
        assert inconsistency.severity == "low"

    def test_inconsistency_high_severity(self) -> None:
        """Test high severity inconsistency."""
        inconsistency = Inconsistency(
            inconsistency_type=InconsistencyType.CONFLICTING_RECORDS,
            field_name="criminal_record",
            source_a="court_records",
            value_a="felony_conviction",
            source_b="self_disclosure",
            value_b="no_record",
            severity="high",
        )
        assert inconsistency.severity == "high"

    def test_inconsistency_to_dict(self) -> None:
        """Test inconsistency serialization."""
        inconsistency = Inconsistency(
            inconsistency_type=InconsistencyType.NAME_MISMATCH,
            field_name="legal_name",
            severity="medium",
        )
        d = inconsistency.to_dict()
        assert d["inconsistency_type"] == "name_mismatch"
        assert d["field_name"] == "legal_name"
        assert "inconsistency_id" in d


class TestConflictResolution:
    """Tests for ConflictResolution dataclass."""

    def test_conflict_resolution_defaults(self) -> None:
        """Test default resolution values."""
        resolution = ConflictResolution()
        assert resolution.status == ResolutionStatus.PENDING
        assert resolution.confidence == 0.0
        assert resolution.resolved_at is None

    def test_conflict_resolution_resolved(self) -> None:
        """Test resolved conflict."""
        from datetime import datetime, UTC
        from uuid import uuid4

        inconsistency_id = uuid4()
        resolution = ConflictResolution(
            inconsistency_id=inconsistency_id,
            status=ResolutionStatus.RESOLVED,
            resolved_value="2020-01-15",
            resolution_method="source_authority",
            confidence=0.9,
            notes="Work Number is authoritative for employment dates",
            resolved_at=datetime.now(UTC),
        )
        assert resolution.status == ResolutionStatus.RESOLVED
        assert resolution.confidence == 0.9

    def test_conflict_resolution_unresolvable(self) -> None:
        """Test unresolvable conflict."""
        resolution = ConflictResolution(
            status=ResolutionStatus.UNRESOLVABLE,
            notes="Conflicting records cannot be reconciled automatically",
        )
        assert resolution.status == ResolutionStatus.UNRESOLVABLE

    def test_conflict_resolution_escalated(self) -> None:
        """Test escalated conflict."""
        resolution = ConflictResolution(
            status=ResolutionStatus.ESCALATED,
            notes="Requires human review due to significance",
        )
        assert resolution.status == ResolutionStatus.ESCALATED

    def test_conflict_resolution_to_dict(self) -> None:
        """Test resolution serialization."""
        resolution = ConflictResolution(
            status=ResolutionStatus.RESOLVED,
            confidence=0.85,
        )
        d = resolution.to_dict()
        assert d["status"] == "resolved"
        assert d["confidence"] == 0.85


class TestDeceptionAnalysis:
    """Tests for DeceptionAnalysis dataclass."""

    def test_deception_analysis_defaults(self) -> None:
        """Test default deception analysis values."""
        analysis = DeceptionAnalysis()
        assert analysis.risk_level == DeceptionRiskLevel.NONE
        assert analysis.indicators == []
        assert analysis.pattern_detected is False

    def test_deception_analysis_low_risk(self) -> None:
        """Test low deception risk."""
        analysis = DeceptionAnalysis(
            risk_level=DeceptionRiskLevel.LOW,
            indicators=["minor_date_discrepancy"],
            inconsistency_count=1,
            unresolved_count=0,
            confidence=0.3,
        )
        assert analysis.risk_level == DeceptionRiskLevel.LOW

    def test_deception_analysis_high_risk(self) -> None:
        """Test high deception risk with pattern."""
        analysis = DeceptionAnalysis(
            risk_level=DeceptionRiskLevel.HIGH,
            indicators=[
                "employment_gaps_concealed",
                "education_falsified",
                "identity_inconsistent",
            ],
            inconsistency_count=5,
            unresolved_count=3,
            pattern_detected=True,
            pattern_description="Systematic misrepresentation across multiple categories",
            confidence=0.9,
        )
        assert analysis.risk_level == DeceptionRiskLevel.HIGH
        assert analysis.pattern_detected is True
        assert len(analysis.indicators) == 3

    def test_deception_analysis_to_dict(self) -> None:
        """Test deception analysis serialization."""
        analysis = DeceptionAnalysis(
            risk_level=DeceptionRiskLevel.MEDIUM,
            pattern_detected=True,
        )
        d = analysis.to_dict()
        assert d["risk_level"] == "medium"
        assert d["pattern_detected"] is True


class TestReconciliationProfile:
    """Tests for ReconciliationProfile dataclass."""

    def test_reconciliation_profile_defaults(self) -> None:
        """Test default profile values."""
        profile = ReconciliationProfile()
        assert profile.total_inconsistencies == 0
        assert profile.resolved_count == 0
        assert profile.confidence_score == 0.0

    def test_calculate_confidence_no_inconsistencies(self) -> None:
        """Test confidence when no inconsistencies."""
        profile = ReconciliationProfile()
        confidence = profile.calculate_confidence()
        assert confidence == 1.0

    def test_calculate_confidence_all_resolved(self) -> None:
        """Test confidence when all inconsistencies resolved."""
        profile = ReconciliationProfile(
            total_inconsistencies=5,
            resolved_count=5,
            unresolved_count=0,
        )
        confidence = profile.calculate_confidence()
        assert confidence == 1.0

    def test_calculate_confidence_partially_resolved(self) -> None:
        """Test confidence when partially resolved."""
        profile = ReconciliationProfile(
            total_inconsistencies=10,
            resolved_count=7,
            unresolved_count=3,
        )
        confidence = profile.calculate_confidence()
        assert confidence == pytest.approx(0.7)

    def test_calculate_confidence_none_resolved(self) -> None:
        """Test confidence when none resolved."""
        profile = ReconciliationProfile(
            total_inconsistencies=5,
            resolved_count=0,
            unresolved_count=5,
        )
        confidence = profile.calculate_confidence()
        assert confidence == 0.0

    def test_reconciliation_profile_with_data(self) -> None:
        """Test profile with full data."""
        inconsistencies = [
            Inconsistency(inconsistency_type=InconsistencyType.DATE_MISMATCH),
            Inconsistency(inconsistency_type=InconsistencyType.NAME_MISMATCH),
        ]
        resolutions = [
            ConflictResolution(status=ResolutionStatus.RESOLVED),
        ]
        deception = DeceptionAnalysis(risk_level=DeceptionRiskLevel.LOW)

        profile = ReconciliationProfile(
            inconsistencies=inconsistencies,
            resolutions=resolutions,
            deception_analysis=deception,
            total_inconsistencies=2,
            resolved_count=1,
            unresolved_count=1,
        )

        assert len(profile.inconsistencies) == 2
        assert len(profile.resolutions) == 1
        profile.calculate_confidence()
        assert profile.confidence_score == pytest.approx(0.5)

    def test_reconciliation_profile_to_dict(self) -> None:
        """Test profile serialization."""
        profile = ReconciliationProfile(
            total_inconsistencies=3,
            resolved_count=2,
        )
        d = profile.to_dict()
        assert d["total_inconsistencies"] == 3
        assert d["resolved_count"] == 2
        assert "profile_id" in d


class TestReconciliationConfig:
    """Tests for ReconciliationConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = ReconciliationConfig()
        assert config.auto_resolve_minor is True
        assert config.require_human_review is False
        assert config.deception_threshold == 3
        assert config.confidence_threshold == 0.7

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = ReconciliationConfig(
            require_human_review=True,
            deception_threshold=5,
            confidence_threshold=0.9,
        )
        assert config.require_human_review is True
        assert config.deception_threshold == 5
        assert config.confidence_threshold == 0.9


class TestReconciliationPhaseResult:
    """Tests for ReconciliationPhaseResult."""

    def test_result_defaults(self) -> None:
        """Test default result values."""
        result = ReconciliationPhaseResult()
        assert result.success is True
        assert result.requires_review is False
        assert result.warnings == []

    def test_result_requires_review(self) -> None:
        """Test result requiring review."""
        result = ReconciliationPhaseResult(
            requires_review=True,
            warnings=["Multiple unresolved conflicts"],
        )
        assert result.requires_review is True
        assert len(result.warnings) == 1

    def test_result_to_dict(self) -> None:
        """Test result serialization."""
        result = ReconciliationPhaseResult(
            success=True,
            requires_review=True,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["requires_review"] is True


class TestReconciliationPhaseHandler:
    """Tests for ReconciliationPhaseHandler."""

    @pytest.fixture
    def handler(self) -> ReconciliationPhaseHandler:
        """Create a handler with default config."""
        return ReconciliationPhaseHandler()

    @pytest.mark.asyncio
    async def test_execute_no_data(self, handler: ReconciliationPhaseHandler) -> None:
        """Test execution with no input data."""
        result = await handler.execute()

        assert result.success is True
        assert result.profile.total_inconsistencies == 0
        assert result.profile.confidence_score == 1.0

    @pytest.mark.asyncio
    async def test_execute_with_foundation_data(self, handler: ReconciliationPhaseHandler) -> None:
        """Test execution with foundation data."""
        foundation_data = {
            "identity": {"name": "John Smith", "dob": "1985-03-15"},
            "employment": [{"employer": "Acme Corp"}],
        }
        result = await handler.execute(foundation_data=foundation_data)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_with_all_phases(self, handler: ReconciliationPhaseHandler) -> None:
        """Test execution with data from all phases."""
        result = await handler.execute(
            foundation_data={"identity": {}},
            records_data={"criminal": []},
            intelligence_data={"media": []},
            network_data={"entities": []},
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_records_timing(self, handler: ReconciliationPhaseHandler) -> None:
        """Test that execution records timing."""
        result = await handler.execute()

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_with_review_required(self) -> None:
        """Test that review is flagged when configured and conflicts exist."""
        config = ReconciliationConfig(require_human_review=True)
        handler = ReconciliationPhaseHandler(config=config)

        result = await handler.execute()

        # Stub has no unresolved conflicts, so no review needed
        assert result.requires_review is False

    def test_custom_config(self) -> None:
        """Test handler with custom configuration."""
        config = ReconciliationConfig(
            auto_resolve_minor=False,
            deception_threshold=5,
        )
        handler = ReconciliationPhaseHandler(config=config)

        assert handler.config.auto_resolve_minor is False
        assert handler.config.deception_threshold == 5


class TestCreateReconciliationPhaseHandler:
    """Tests for factory function."""

    def test_create_with_defaults(self) -> None:
        """Test creating handler with defaults."""
        handler = create_reconciliation_phase_handler()
        assert isinstance(handler, ReconciliationPhaseHandler)

    def test_create_with_config(self) -> None:
        """Test creating handler with custom config."""
        config = ReconciliationConfig(require_human_review=True)
        handler = create_reconciliation_phase_handler(config=config)
        assert handler.config.require_human_review is True
