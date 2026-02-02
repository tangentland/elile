"""Tests for dark web monitoring provider."""

from decimal import Decimal

import pytest

from elile.compliance.types import CheckType, Locale
from elile.entity.types import SubjectIdentifiers
from elile.providers.darkweb.provider import (
    DarkWebProvider,
    create_darkweb_provider,
    get_darkweb_provider,
)
from elile.providers.darkweb.types import (
    ConfidenceLevel,
    DarkWebProviderConfig,
)
from elile.providers.types import DataSourceCategory, ProviderStatus


class TestDarkWebProviderInit:
    """Tests for DarkWebProvider initialization."""

    def test_default_initialization(self) -> None:
        """Test provider initializes with default config."""
        provider = DarkWebProvider()
        assert provider.provider_id == "darkweb_provider"
        assert provider.config.enable_credential_monitoring is True
        assert provider.config.enable_marketplace_monitoring is True

    def test_custom_config_initialization(self) -> None:
        """Test provider initializes with custom config."""
        config = DarkWebProviderConfig(
            enable_marketplace_monitoring=False,
            min_confidence=ConfidenceLevel.HIGH,
        )
        provider = DarkWebProvider(config)
        assert provider.config.enable_marketplace_monitoring is False
        assert provider.config.min_confidence == ConfidenceLevel.HIGH

    def test_provider_info(self) -> None:
        """Test provider info is correctly set."""
        provider = DarkWebProvider()
        info = provider.provider_info

        assert info.provider_id == "darkweb_provider"
        assert info.name == "Dark Web Monitoring Provider"
        assert info.category == DataSourceCategory.PREMIUM
        assert len(info.capabilities) >= 1

    def test_supported_checks(self) -> None:
        """Test supported check types."""
        provider = DarkWebProvider()
        checks = provider.supported_checks

        assert CheckType.DARK_WEB_MONITORING in checks


class TestDarkWebProviderExecuteCheck:
    """Tests for DarkWebProvider.execute_check method."""

    @pytest.fixture
    def provider(self) -> DarkWebProvider:
        """Create a provider instance."""
        return DarkWebProvider()

    @pytest.mark.asyncio
    async def test_execute_check_no_identifiers(self, provider: DarkWebProvider) -> None:
        """Test execute_check fails without identifiers."""
        subject = SubjectIdentifiers()  # No identifiers

        result = await provider.execute_check(
            check_type=CheckType.DARK_WEB_MONITORING,
            subject=subject,
            locale=Locale.US,
        )

        assert result.success is False
        assert result.error_code == "INVALID_SUBJECT"

    @pytest.mark.asyncio
    async def test_execute_check_with_name(self, provider: DarkWebProvider) -> None:
        """Test execute_check with subject name."""
        subject = SubjectIdentifiers(full_name="John Smith")

        result = await provider.execute_check(
            check_type=CheckType.DARK_WEB_MONITORING,
            subject=subject,
            locale=Locale.US,
        )

        assert result.success is True
        assert result.provider_id == "darkweb_provider"
        assert result.query_id is not None
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_check_includes_normalized_data(self, provider: DarkWebProvider) -> None:
        """Test execute_check returns normalized data."""
        subject = SubjectIdentifiers(
            full_name="Test User",
            name_variants=["testuser@example.com"],
        )

        result = await provider.execute_check(
            check_type=CheckType.DARK_WEB_MONITORING,
            subject=subject,
            locale=Locale.US,
        )

        assert result.success is True
        assert "search" in result.normalized_data
        assert "credential_leaks" in result.normalized_data
        assert "marketplace_listings" in result.normalized_data
        assert "forum_mentions" in result.normalized_data
        assert "threat_indicators" in result.normalized_data

    @pytest.mark.asyncio
    async def test_execute_check_includes_cost(self, provider: DarkWebProvider) -> None:
        """Test that execute_check includes cost information."""
        subject = SubjectIdentifiers(full_name="Cost Test")

        result = await provider.execute_check(
            check_type=CheckType.DARK_WEB_MONITORING,
            subject=subject,
            locale=Locale.US,
        )

        assert result.cost_incurred is not None
        assert result.cost_incurred >= Decimal("25.00")  # Base cost


class TestDarkWebProviderSearchDarkWeb:
    """Tests for DarkWebProvider.search_dark_web method."""

    @pytest.fixture
    def provider(self) -> DarkWebProvider:
        """Create a provider instance."""
        return DarkWebProvider()

    @pytest.mark.asyncio
    async def test_search_dark_web_basic(self, provider: DarkWebProvider) -> None:
        """Test basic dark web search."""
        result = await provider.search_dark_web(
            subject_name="Test Subject",
            identifiers=["test@example.com"],
        )

        assert result.search_id is not None
        assert result.subject_name == "Test Subject"
        assert "test@example.com" in result.search_identifiers
        assert isinstance(result.total_findings, int)

    @pytest.mark.asyncio
    async def test_search_dark_web_multiple_identifiers(self, provider: DarkWebProvider) -> None:
        """Test dark web search with multiple identifiers."""
        result = await provider.search_dark_web(
            subject_name="Multi ID Test",
            identifiers=["id1@example.com", "id2@example.com", "username123"],
        )

        assert len(result.search_identifiers) == 3

    @pytest.mark.asyncio
    async def test_search_dark_web_severity_summary(self, provider: DarkWebProvider) -> None:
        """Test that search result includes severity summary."""
        result = await provider.search_dark_web(
            subject_name="Severity Test",
            identifiers=["severity@example.com"],
        )

        assert "critical" in result.severity_summary
        assert "high" in result.severity_summary
        assert "medium" in result.severity_summary
        assert "low" in result.severity_summary
        assert "informational" in result.severity_summary


class TestDarkWebProviderCredentialLeaks:
    """Tests for credential leak detection."""

    @pytest.fixture
    def provider(self) -> DarkWebProvider:
        """Create a provider instance."""
        return DarkWebProvider()

    @pytest.mark.asyncio
    async def test_check_credential_leaks(self, provider: DarkWebProvider) -> None:
        """Test credential leak check for email."""
        leaks = await provider.check_credential_leaks("test@linkedin.com")

        # Results depend on mock simulation
        assert isinstance(leaks, list)

    @pytest.mark.asyncio
    async def test_check_credential_leaks_with_domain(self, provider: DarkWebProvider) -> None:
        """Test credential leak check includes domain-specific breaches."""
        # Use email with known breach domain
        result = await provider.search_dark_web(
            subject_name="LinkedIn Test",
            identifiers=["user@linkedin.com"],
        )

        # Should have searched for credential leaks
        assert isinstance(result.credential_leaks, list)


class TestDarkWebProviderBreachInfo:
    """Tests for breach info retrieval."""

    @pytest.fixture
    def provider(self) -> DarkWebProvider:
        """Create a provider instance."""
        return DarkWebProvider()

    @pytest.mark.asyncio
    async def test_get_breach_info_exists(self, provider: DarkWebProvider) -> None:
        """Test getting breach info for known breach."""
        info = await provider.get_breach_info("linkedin_2021")

        assert info is not None
        assert info["breach_id"] == "linkedin_2021"
        assert info["breach_name"] == "LinkedIn 2021"
        assert info["is_verified"] is True

    @pytest.mark.asyncio
    async def test_get_breach_info_not_found(self, provider: DarkWebProvider) -> None:
        """Test getting breach info for unknown breach."""
        info = await provider.get_breach_info("nonexistent_breach")
        assert info is None


class TestDarkWebProviderHealthCheck:
    """Tests for DarkWebProvider.health_check method."""

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        """Test health check returns healthy status."""
        provider = DarkWebProvider()
        health = await provider.health_check()

        assert health.provider_id == "darkweb_provider"
        assert health.status == ProviderStatus.HEALTHY
        assert health.latency_ms >= 0


class TestDarkWebProviderConfig:
    """Tests for provider configuration effects."""

    @pytest.mark.asyncio
    async def test_disable_credential_monitoring(self) -> None:
        """Test disabling credential monitoring."""
        config = DarkWebProviderConfig(enable_credential_monitoring=False)
        provider = DarkWebProvider(config)

        result = await provider.search_dark_web(
            subject_name="Test",
            identifiers=["test@example.com"],
        )

        # Credential leaks should be empty when disabled
        assert len(result.credential_leaks) == 0

    @pytest.mark.asyncio
    async def test_disable_marketplace_monitoring(self) -> None:
        """Test disabling marketplace monitoring."""
        config = DarkWebProviderConfig(enable_marketplace_monitoring=False)
        provider = DarkWebProvider(config)

        result = await provider.search_dark_web(
            subject_name="Test",
            identifiers=["test@example.com"],
        )

        # Marketplace listings should be empty when disabled
        assert len(result.marketplace_listings) == 0

    @pytest.mark.asyncio
    async def test_disable_forum_monitoring(self) -> None:
        """Test disabling forum monitoring."""
        config = DarkWebProviderConfig(enable_forum_monitoring=False)
        provider = DarkWebProvider(config)

        result = await provider.search_dark_web(
            subject_name="Test",
            identifiers=["test@example.com"],
        )

        # Forum mentions should be empty when disabled
        assert len(result.forum_mentions) == 0

    @pytest.mark.asyncio
    async def test_disable_threat_intel(self) -> None:
        """Test disabling threat intelligence."""
        config = DarkWebProviderConfig(enable_threat_intel=False)
        provider = DarkWebProvider(config)

        result = await provider.search_dark_web(
            subject_name="Test",
            identifiers=["test@example.com"],
        )

        # Threat indicators should be empty when disabled
        assert len(result.threat_indicators) == 0


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_darkweb_provider(self) -> None:
        """Test create_darkweb_provider factory."""
        provider = create_darkweb_provider()
        assert isinstance(provider, DarkWebProvider)

    def test_create_darkweb_provider_with_config(self) -> None:
        """Test create_darkweb_provider with custom config."""
        config = DarkWebProviderConfig(enable_forum_monitoring=False)
        provider = create_darkweb_provider(config)
        assert provider.config.enable_forum_monitoring is False

    def test_get_darkweb_provider_singleton(self) -> None:
        """Test get_darkweb_provider returns singleton."""
        provider1 = get_darkweb_provider()
        provider2 = get_darkweb_provider()
        assert provider1 is provider2


class TestNormalizedOutput:
    """Tests for normalized output structure."""

    @pytest.fixture
    def provider(self) -> DarkWebProvider:
        """Create a provider instance."""
        return DarkWebProvider()

    @pytest.mark.asyncio
    async def test_normalized_data_structure(self, provider: DarkWebProvider) -> None:
        """Test normalized data has expected structure."""
        subject = SubjectIdentifiers(full_name="Structure Test")

        result = await provider.execute_check(
            check_type=CheckType.DARK_WEB_MONITORING,
            subject=subject,
            locale=Locale.US,
        )

        data = result.normalized_data

        # Check search section
        assert "search" in data
        search = data["search"]
        assert "search_id" in search
        assert "subject_name" in search
        assert "total_findings" in search
        assert "has_critical" in search
        assert "severity_summary" in search
        assert "searched_at" in search

        # Check arrays exist
        assert isinstance(data["credential_leaks"], list)
        assert isinstance(data["marketplace_listings"], list)
        assert isinstance(data["forum_mentions"], list)
        assert isinstance(data["threat_indicators"], list)


class TestCostCalculation:
    """Tests for cost calculation."""

    @pytest.fixture
    def provider(self) -> DarkWebProvider:
        """Create a provider instance."""
        return DarkWebProvider()

    @pytest.mark.asyncio
    async def test_base_cost(self, provider: DarkWebProvider) -> None:
        """Test base cost is applied."""
        subject = SubjectIdentifiers(full_name="Cost Test")

        result = await provider.execute_check(
            check_type=CheckType.DARK_WEB_MONITORING,
            subject=subject,
            locale=Locale.US,
        )

        # Base cost should be at least $25
        assert result.cost_incurred >= Decimal("25.00")
