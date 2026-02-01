"""Tests for the RecordsPhaseHandler module.

Tests cover:
- Record type enums
- Criminal, civil, financial, license, regulatory, and sanctions records
- Records profile aggregation and risk calculation
- Phase execution and results
"""

import pytest
from datetime import date

from elile.agent.state import ServiceTier
from elile.compliance.types import Locale
from elile.investigation.phases.records import (
    CivilRecord,
    CriminalRecord,
    FinancialRecord,
    LicenseRecord,
    RecordsConfig,
    RecordsPhaseHandler,
    RecordsPhaseResult,
    RecordsProfile,
    RecordSeverity,
    RecordType,
    RegulatoryRecord,
    SanctionsRecord,
    create_records_phase_handler,
)


class TestRecordType:
    """Tests for RecordType enum."""

    def test_all_record_types_exist(self) -> None:
        """Test all expected record types exist."""
        assert RecordType.CRIMINAL.value == "criminal"
        assert RecordType.CIVIL.value == "civil"
        assert RecordType.FINANCIAL.value == "financial"
        assert RecordType.LICENSE.value == "license"
        assert RecordType.REGULATORY.value == "regulatory"
        assert RecordType.SANCTIONS.value == "sanctions"


class TestRecordSeverity:
    """Tests for RecordSeverity enum."""

    def test_all_severities_exist(self) -> None:
        """Test all expected severities exist."""
        assert RecordSeverity.NONE.value == "none"
        assert RecordSeverity.LOW.value == "low"
        assert RecordSeverity.MEDIUM.value == "medium"
        assert RecordSeverity.HIGH.value == "high"
        assert RecordSeverity.CRITICAL.value == "critical"


class TestCriminalRecord:
    """Tests for CriminalRecord dataclass."""

    def test_criminal_record_defaults(self) -> None:
        """Test default criminal record values."""
        record = CriminalRecord()
        assert record.offense_type == ""
        assert record.severity == RecordSeverity.MEDIUM
        assert record.confidence == 0.0

    def test_criminal_record_with_data(self) -> None:
        """Test criminal record with data."""
        record = CriminalRecord(
            offense_type="theft",
            offense_date=date(2020, 5, 15),
            jurisdiction="California",
            disposition="convicted",
            severity=RecordSeverity.HIGH,
            source="court_records",
            confidence=0.95,
        )
        assert record.offense_type == "theft"
        assert record.jurisdiction == "California"
        assert record.severity == RecordSeverity.HIGH

    def test_criminal_record_to_dict(self) -> None:
        """Test criminal record serialization."""
        record = CriminalRecord(
            offense_type="fraud",
            severity=RecordSeverity.CRITICAL,
        )
        d = record.to_dict()
        assert d["offense_type"] == "fraud"
        assert d["severity"] == "critical"
        assert "record_id" in d


class TestCivilRecord:
    """Tests for CivilRecord dataclass."""

    def test_civil_record_defaults(self) -> None:
        """Test default civil record values."""
        record = CivilRecord()
        assert record.case_type == ""
        assert record.role == ""
        assert record.severity == RecordSeverity.LOW

    def test_civil_record_with_data(self) -> None:
        """Test civil record with data."""
        record = CivilRecord(
            case_type="contract_dispute",
            filing_date=date(2019, 3, 20),
            jurisdiction="New York",
            role="defendant",
            status="settled",
        )
        assert record.case_type == "contract_dispute"
        assert record.role == "defendant"

    def test_civil_record_to_dict(self) -> None:
        """Test civil record serialization."""
        record = CivilRecord(case_type="personal_injury")
        d = record.to_dict()
        assert d["case_type"] == "personal_injury"
        assert d["severity"] == "low"


class TestFinancialRecord:
    """Tests for FinancialRecord dataclass."""

    def test_financial_record_defaults(self) -> None:
        """Test default financial record values."""
        record = FinancialRecord()
        assert record.record_type == ""
        assert record.amount is None
        assert record.severity == RecordSeverity.MEDIUM

    def test_financial_record_bankruptcy(self) -> None:
        """Test bankruptcy record."""
        record = FinancialRecord(
            record_type="bankruptcy",
            filing_date=date(2018, 1, 10),
            amount=250000.00,
            status="discharged",
            severity=RecordSeverity.HIGH,
        )
        assert record.record_type == "bankruptcy"
        assert record.amount == 250000.00

    def test_financial_record_to_dict(self) -> None:
        """Test financial record serialization."""
        record = FinancialRecord(record_type="lien", amount=50000.00)
        d = record.to_dict()
        assert d["record_type"] == "lien"
        assert d["amount"] == 50000.00


class TestLicenseRecord:
    """Tests for LicenseRecord dataclass."""

    def test_license_record_defaults(self) -> None:
        """Test default license record values."""
        record = LicenseRecord()
        assert record.license_type == ""
        assert record.disciplinary_actions == []

    def test_license_record_with_disciplinary(self) -> None:
        """Test license with disciplinary actions."""
        record = LicenseRecord(
            license_type="CPA",
            issuing_authority="State Board of Accountancy",
            status="active",
            issue_date=date(2015, 6, 1),
            disciplinary_actions=["Warning 2020", "Fine 2021"],
        )
        assert len(record.disciplinary_actions) == 2

    def test_license_record_to_dict(self) -> None:
        """Test license record serialization."""
        record = LicenseRecord(license_type="MD")
        d = record.to_dict()
        assert d["license_type"] == "MD"
        assert d["disciplinary_actions"] == []


class TestRegulatoryRecord:
    """Tests for RegulatoryRecord dataclass."""

    def test_regulatory_record_defaults(self) -> None:
        """Test default regulatory record values."""
        record = RegulatoryRecord()
        assert record.agency == ""
        assert record.severity == RecordSeverity.HIGH

    def test_regulatory_record_with_data(self) -> None:
        """Test regulatory record with data."""
        record = RegulatoryRecord(
            agency="SEC",
            action_type="enforcement",
            action_date=date(2021, 7, 15),
            description="Securities violations",
            severity=RecordSeverity.CRITICAL,
        )
        assert record.agency == "SEC"
        assert record.severity == RecordSeverity.CRITICAL


class TestSanctionsRecord:
    """Tests for SanctionsRecord dataclass."""

    def test_sanctions_record_defaults(self) -> None:
        """Test default sanctions record values."""
        record = SanctionsRecord()
        assert record.list_name == ""
        assert record.severity == RecordSeverity.CRITICAL

    def test_sanctions_record_ofac(self) -> None:
        """Test OFAC sanctions match."""
        record = SanctionsRecord(
            list_name="OFAC SDN",
            match_type="exact",
            match_score=0.98,
            reason="Terrorism financing",
        )
        assert record.list_name == "OFAC SDN"
        assert record.match_score == 0.98


class TestRecordsProfile:
    """Tests for RecordsProfile dataclass."""

    def test_records_profile_defaults(self) -> None:
        """Test default profile values."""
        profile = RecordsProfile()
        assert profile.total_records == 0
        assert profile.overall_risk == RecordSeverity.NONE

    def test_calculate_risk_none(self) -> None:
        """Test risk calculation with no records."""
        profile = RecordsProfile()
        risk = profile.calculate_risk()
        assert risk == RecordSeverity.NONE

    def test_calculate_risk_sanctions_critical(self) -> None:
        """Test sanctions always result in critical risk."""
        profile = RecordsProfile(
            sanctions_records=[SanctionsRecord(list_name="OFAC")]
        )
        risk = profile.calculate_risk()
        assert risk == RecordSeverity.CRITICAL

    def test_calculate_risk_criminal_high(self) -> None:
        """Test high severity criminal raises risk."""
        profile = RecordsProfile(
            criminal_records=[
                CriminalRecord(severity=RecordSeverity.HIGH)
            ]
        )
        risk = profile.calculate_risk()
        assert risk == RecordSeverity.HIGH

    def test_calculate_risk_regulatory_high(self) -> None:
        """Test regulatory records raise risk."""
        profile = RecordsProfile(
            regulatory_records=[RegulatoryRecord(agency="SEC")]
        )
        risk = profile.calculate_risk()
        assert risk == RecordSeverity.HIGH

    def test_calculate_risk_financial_medium(self) -> None:
        """Test financial records result in medium risk."""
        profile = RecordsProfile(
            financial_records=[FinancialRecord(record_type="bankruptcy")]
        )
        risk = profile.calculate_risk()
        assert risk == RecordSeverity.MEDIUM

    def test_records_profile_to_dict(self) -> None:
        """Test profile serialization."""
        profile = RecordsProfile(
            criminal_records=[CriminalRecord(offense_type="theft")],
            total_records=1,
        )
        d = profile.to_dict()
        assert d["total_records"] == 1
        assert len(d["criminal_records"]) == 1


class TestRecordsConfig:
    """Tests for RecordsConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = RecordsConfig()
        assert config.enable_criminal is True
        assert config.enable_sanctions is True
        assert config.lookback_years == 7
        assert config.parallel_execution is True

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = RecordsConfig(
            enable_civil=False,
            lookback_years=10,
        )
        assert config.enable_civil is False
        assert config.lookback_years == 10


class TestRecordsPhaseResult:
    """Tests for RecordsPhaseResult."""

    def test_result_defaults(self) -> None:
        """Test default result values."""
        result = RecordsPhaseResult()
        assert result.success is True
        assert result.record_types_checked == []

    def test_result_to_dict(self) -> None:
        """Test result serialization."""
        result = RecordsPhaseResult(
            success=True,
            record_types_checked=[RecordType.CRIMINAL, RecordType.CIVIL],
        )
        d = result.to_dict()
        assert d["success"] is True
        assert "criminal" in d["record_types_checked"]


class TestRecordsPhaseHandler:
    """Tests for RecordsPhaseHandler."""

    @pytest.fixture
    def handler(self) -> RecordsPhaseHandler:
        """Create a handler with default config."""
        return RecordsPhaseHandler()

    @pytest.mark.asyncio
    async def test_execute_with_full_data(self, handler: RecordsPhaseHandler) -> None:
        """Test execution with full subject data."""
        result = await handler.execute(
            subject_name="John Smith",
            subject_dob=date(1985, 3, 15),
            addresses=["123 Main St, Anytown, USA"],
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
        )

        assert result.success is True
        assert RecordType.CRIMINAL in result.record_types_checked
        assert RecordType.SANCTIONS in result.record_types_checked

    @pytest.mark.asyncio
    async def test_execute_with_minimal_data(self, handler: RecordsPhaseHandler) -> None:
        """Test execution with minimal subject data."""
        result = await handler.execute(
            subject_name="Jane Doe",
        )

        assert result.success is True
        # All enabled record types should be checked
        assert len(result.record_types_checked) == 6

    @pytest.mark.asyncio
    async def test_execute_respects_config(self) -> None:
        """Test that execution respects config settings."""
        config = RecordsConfig(
            enable_criminal=True,
            enable_civil=False,
            enable_financial=False,
            enable_licenses=False,
            enable_regulatory=False,
            enable_sanctions=True,
        )
        handler = RecordsPhaseHandler(config=config)
        result = await handler.execute(subject_name="Test Subject")

        assert RecordType.CRIMINAL in result.record_types_checked
        assert RecordType.SANCTIONS in result.record_types_checked
        assert RecordType.CIVIL not in result.record_types_checked

    @pytest.mark.asyncio
    async def test_execute_calculates_risk(self, handler: RecordsPhaseHandler) -> None:
        """Test that execution calculates risk level."""
        result = await handler.execute(subject_name="John Smith")

        # Stub returns empty records, so risk should be NONE
        assert result.profile.overall_risk == RecordSeverity.NONE

    @pytest.mark.asyncio
    async def test_execute_records_timing(self, handler: RecordsPhaseHandler) -> None:
        """Test that execution records timing."""
        result = await handler.execute(subject_name="John Smith")

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.duration_ms >= 0

    def test_custom_config(self) -> None:
        """Test handler with custom configuration."""
        config = RecordsConfig(
            lookback_years=10,
            parallel_execution=False,
        )
        handler = RecordsPhaseHandler(config=config)

        assert handler.config.lookback_years == 10
        assert handler.config.parallel_execution is False


class TestCreateRecordsPhaseHandler:
    """Tests for factory function."""

    def test_create_with_defaults(self) -> None:
        """Test creating handler with defaults."""
        handler = create_records_phase_handler()
        assert isinstance(handler, RecordsPhaseHandler)

    def test_create_with_config(self) -> None:
        """Test creating handler with custom config."""
        config = RecordsConfig(lookback_years=5)
        handler = create_records_phase_handler(config=config)
        assert handler.config.lookback_years == 5
