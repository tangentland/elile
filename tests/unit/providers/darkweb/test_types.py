"""Tests for dark web provider type definitions."""

from datetime import datetime
from uuid import uuid7

from elile.providers.darkweb.types import (
    BreachInfo,
    ConfidenceLevel,
    CredentialLeak,
    CredentialType,
    DarkWebProviderConfig,
    DarkWebProviderError,
    DarkWebRateLimitError,
    DarkWebSearchError,
    DarkWebSearchResult,
    DarkWebServiceUnavailableError,
    DarkWebSource,
    ForumMention,
    MarketplaceListing,
    MentionType,
    SeverityLevel,
    ThreatIndicator,
)


class TestDarkWebSource:
    """Tests for DarkWebSource enum."""

    def test_marketplace_sources(self) -> None:
        """Test marketplace source types."""
        assert DarkWebSource.MARKETPLACE_GENERAL == "marketplace_general"
        assert DarkWebSource.MARKETPLACE_FINANCIAL == "marketplace_financial"
        assert DarkWebSource.MARKETPLACE_IDENTITY == "marketplace_identity"

    def test_forum_sources(self) -> None:
        """Test forum source types."""
        assert DarkWebSource.FORUM_HACKER == "forum_hacker"
        assert DarkWebSource.FORUM_FRAUD == "forum_fraud"
        assert DarkWebSource.FORUM_LEAK == "forum_leak"

    def test_breach_sources(self) -> None:
        """Test breach source types."""
        assert DarkWebSource.BREACH_DATABASE == "breach_database"
        assert DarkWebSource.CREDENTIAL_DUMP == "credential_dump"

    def test_chat_sources(self) -> None:
        """Test chat source types."""
        assert DarkWebSource.TELEGRAM_CHANNEL == "telegram_channel"
        assert DarkWebSource.IRC_CHANNEL == "irc_channel"

    def test_network_sources(self) -> None:
        """Test network source types."""
        assert DarkWebSource.TOR_HIDDEN_SERVICE == "tor_hidden_service"
        assert DarkWebSource.I2P_SITE == "i2p_site"


class TestMentionType:
    """Tests for MentionType enum."""

    def test_data_types(self) -> None:
        """Test data mention types."""
        assert MentionType.CREDENTIAL_LEAK == "credential_leak"
        assert MentionType.IDENTITY_FOR_SALE == "identity_for_sale"
        assert MentionType.FINANCIAL_DATA == "financial_data"
        assert MentionType.SOCIAL_SECURITY == "social_security"

    def test_threat_types(self) -> None:
        """Test threat mention types."""
        assert MentionType.THREAT_MENTION == "threat_mention"
        assert MentionType.HACKING_TARGET == "hacking_target"
        assert MentionType.REPUTATION_ATTACK == "reputation_attack"


class TestSeverityLevel:
    """Tests for SeverityLevel enum."""

    def test_severity_levels(self) -> None:
        """Test all severity levels exist."""
        assert SeverityLevel.CRITICAL == "critical"
        assert SeverityLevel.HIGH == "high"
        assert SeverityLevel.MEDIUM == "medium"
        assert SeverityLevel.LOW == "low"
        assert SeverityLevel.INFORMATIONAL == "informational"


class TestConfidenceLevel:
    """Tests for ConfidenceLevel enum."""

    def test_confidence_levels(self) -> None:
        """Test all confidence levels exist."""
        assert ConfidenceLevel.CONFIRMED == "confirmed"
        assert ConfidenceLevel.HIGH == "high"
        assert ConfidenceLevel.MEDIUM == "medium"
        assert ConfidenceLevel.LOW == "low"
        assert ConfidenceLevel.UNVERIFIED == "unverified"


class TestCredentialType:
    """Tests for CredentialType enum."""

    def test_credential_types(self) -> None:
        """Test all credential types exist."""
        assert CredentialType.EMAIL_PASSWORD == "email_password"
        assert CredentialType.USERNAME_PASSWORD == "username_password"
        assert CredentialType.EMAIL_ONLY == "email_only"
        assert CredentialType.HASH_ONLY == "hash_only"
        assert CredentialType.PLAINTEXT == "plaintext"
        assert CredentialType.TOKEN == "token"


class TestBreachInfo:
    """Tests for BreachInfo model."""

    def test_breach_info_creation(self) -> None:
        """Test basic breach info creation."""
        breach = BreachInfo(
            breach_id="linkedin_2021",
            breach_name="LinkedIn 2021",
        )
        assert breach.breach_id == "linkedin_2021"
        assert breach.breach_name == "LinkedIn 2021"
        assert breach.is_verified is False

    def test_breach_info_full(self) -> None:
        """Test breach info with all fields."""
        breach = BreachInfo(
            breach_id="test_breach",
            breach_name="Test Breach",
            breach_date=datetime(2023, 1, 15),
            discovered_date=datetime(2023, 3, 1),
            source_company="Test Corp",
            records_affected=1000000,
            data_types=["email", "password", "ssn"],
            is_verified=True,
            breach_description="Major data breach",
        )

        assert breach.breach_id == "test_breach"
        assert breach.source_company == "Test Corp"
        assert breach.records_affected == 1000000
        assert len(breach.data_types) == 3
        assert "ssn" in breach.data_types
        assert breach.is_verified is True


class TestCredentialLeak:
    """Tests for CredentialLeak model."""

    def test_credential_leak_creation(self) -> None:
        """Test basic credential leak creation."""
        leak = CredentialLeak(
            leak_id=uuid7(),
            email="test@example.com",
        )
        assert leak.email == "test@example.com"
        assert leak.credential_type == CredentialType.UNKNOWN
        assert leak.source == DarkWebSource.UNKNOWN

    def test_credential_leak_with_breach(self) -> None:
        """Test credential leak with associated breach."""
        breach = BreachInfo(
            breach_id="test",
            breach_name="Test Breach",
        )
        leak = CredentialLeak(
            leak_id=uuid7(),
            email="test@example.com",
            username="testuser",
            password_hash="abc123hash",
            credential_type=CredentialType.EMAIL_PASSWORD,
            breach=breach,
            source=DarkWebSource.BREACH_DATABASE,
        )

        assert leak.email == "test@example.com"
        assert leak.username == "testuser"
        assert leak.password_hash == "abc123hash"
        assert leak.breach is not None
        assert leak.breach.breach_name == "Test Breach"


class TestMarketplaceListing:
    """Tests for MarketplaceListing model."""

    def test_marketplace_listing_creation(self) -> None:
        """Test basic marketplace listing creation."""
        listing = MarketplaceListing(
            listing_id=uuid7(),
            title="Personal data for sale",
        )
        assert listing.title == "Personal data for sale"
        assert listing.currency == "USD"
        assert listing.is_active is True

    def test_marketplace_listing_full(self) -> None:
        """Test marketplace listing with all fields."""
        listing = MarketplaceListing(
            listing_id=uuid7(),
            title="Identity package",
            description="Full identity with SSN",
            price=500.00,
            currency="BTC",
            marketplace="DarkMarket",
            seller="vendor123",
            seller_reputation=4.5,
            mention_type=MentionType.IDENTITY_FOR_SALE,
            subject_identifiers=["john@example.com"],
            listing_url_hash="abc123",
        )

        assert listing.title == "Identity package"
        assert listing.price == 500.00
        assert listing.marketplace == "DarkMarket"
        assert listing.seller_reputation == 4.5
        assert listing.mention_type == MentionType.IDENTITY_FOR_SALE


class TestForumMention:
    """Tests for ForumMention model."""

    def test_forum_mention_creation(self) -> None:
        """Test basic forum mention creation."""
        mention = ForumMention(
            mention_id=uuid7(),
        )
        assert mention.mention_type == MentionType.UNKNOWN
        assert mention.is_verified is False

    def test_forum_mention_full(self) -> None:
        """Test forum mention with all fields."""
        mention = ForumMention(
            mention_id=uuid7(),
            forum_name="HackerForum",
            thread_title="Data dump thread",
            post_content="Found interesting data...",
            author="anonymous",
            mention_type=MentionType.THREAT_MENTION,
            subject_identifiers=["target@example.com"],
            posted_at=datetime(2023, 6, 15),
            thread_url_hash="xyz789",
            is_verified=True,
        )

        assert mention.forum_name == "HackerForum"
        assert mention.thread_title == "Data dump thread"
        assert mention.mention_type == MentionType.THREAT_MENTION
        assert mention.is_verified is True


class TestThreatIndicator:
    """Tests for ThreatIndicator model."""

    def test_threat_indicator_creation(self) -> None:
        """Test basic threat indicator creation."""
        indicator = ThreatIndicator(
            indicator_id=uuid7(),
            indicator_type="email",
            indicator_value="test@example.com",
        )
        assert indicator.indicator_type == "email"
        assert indicator.indicator_value == "test@example.com"
        assert indicator.severity == SeverityLevel.MEDIUM
        assert indicator.confidence == ConfidenceLevel.MEDIUM

    def test_threat_indicator_full(self) -> None:
        """Test threat indicator with all fields."""
        indicator = ThreatIndicator(
            indicator_id=uuid7(),
            indicator_type="ip",
            indicator_value="192.168.1.1",
            threat_type="malware_c2",
            severity=SeverityLevel.CRITICAL,
            confidence=ConfidenceLevel.CONFIRMED,
            source=DarkWebSource.FORUM_HACKER,
            description="Known malware command and control",
            tags=["malware", "c2", "botnet"],
        )

        assert indicator.indicator_type == "ip"
        assert indicator.threat_type == "malware_c2"
        assert indicator.severity == SeverityLevel.CRITICAL
        assert indicator.confidence == ConfidenceLevel.CONFIRMED
        assert len(indicator.tags) == 3


class TestDarkWebSearchResult:
    """Tests for DarkWebSearchResult model."""

    def test_search_result_creation(self) -> None:
        """Test basic search result creation."""
        result = DarkWebSearchResult(
            search_id=uuid7(),
            subject_name="John Smith",
        )
        assert result.subject_name == "John Smith"
        assert result.total_findings == 0
        assert result.has_findings() is False

    def test_search_result_with_findings(self) -> None:
        """Test search result with findings."""
        result = DarkWebSearchResult(
            search_id=uuid7(),
            subject_name="John Smith",
            search_identifiers=["john@example.com"],
            credential_leaks=[
                CredentialLeak(leak_id=uuid7(), email="john@example.com"),
            ],
            total_findings=1,
            severity_summary={"high": 1},
        )

        assert result.has_findings() is True
        assert len(result.credential_leaks) == 1
        assert result.total_findings == 1

    def test_get_critical_findings(self) -> None:
        """Test get_critical_findings method."""
        result = DarkWebSearchResult(
            search_id=uuid7(),
            subject_name="Test",
            severity_summary={"critical": 2, "high": 3, "medium": 1},
        )

        assert result.get_critical_findings() == 2

    def test_get_high_severity_findings(self) -> None:
        """Test get_high_severity_findings method."""
        result = DarkWebSearchResult(
            search_id=uuid7(),
            subject_name="Test",
            severity_summary={"critical": 2, "high": 3, "medium": 1},
        )

        assert result.get_high_severity_findings() == 5


class TestDarkWebProviderConfig:
    """Tests for DarkWebProviderConfig model."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = DarkWebProviderConfig()

        assert config.api_key is None
        assert config.enable_credential_monitoring is True
        assert config.enable_marketplace_monitoring is True
        assert config.enable_forum_monitoring is True
        assert config.enable_threat_intel is True
        assert config.cache_ttl_seconds == 3600
        assert config.timeout_ms == 60000

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = DarkWebProviderConfig(
            api_key="test-key",
            enable_marketplace_monitoring=False,
            timeout_ms=30000,
            min_confidence=ConfidenceLevel.HIGH,
        )

        assert config.api_key == "test-key"
        assert config.enable_marketplace_monitoring is False
        assert config.timeout_ms == 30000
        assert config.min_confidence == ConfidenceLevel.HIGH


class TestExceptions:
    """Tests for dark web provider exceptions."""

    def test_darkweb_provider_error(self) -> None:
        """Test base exception."""
        error = DarkWebProviderError("Test error", {"key": "value"})
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.details == {"key": "value"}

    def test_darkweb_search_error(self) -> None:
        """Test search error exception."""
        search_id = uuid7()
        error = DarkWebSearchError(search_id, "Timeout")
        assert str(search_id) in str(error)
        assert "Timeout" in str(error)
        assert error.search_id == search_id
        assert error.reason == "Timeout"

    def test_darkweb_rate_limit_error(self) -> None:
        """Test rate limit exception."""
        error = DarkWebRateLimitError(retry_after_seconds=60)
        assert "rate limited" in str(error).lower()
        assert error.retry_after_seconds == 60

    def test_darkweb_service_unavailable_error(self) -> None:
        """Test service unavailable exception."""
        error = DarkWebServiceUnavailableError("BreachAPI", "Connection refused")
        assert "BreachAPI" in str(error)
        assert error.service_name == "BreachAPI"
        assert error.reason == "Connection refused"
