"""Type definitions for dark web monitoring.

This module defines the core types for dark web monitoring including
credential leaks, marketplace mentions, and threat intelligence.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DarkWebSource(str, Enum):
    """Sources of dark web data."""

    # Marketplaces
    MARKETPLACE_GENERAL = "marketplace_general"  # General dark web marketplaces
    MARKETPLACE_FINANCIAL = "marketplace_financial"  # Financial fraud marketplaces
    MARKETPLACE_IDENTITY = "marketplace_identity"  # Identity documents

    # Forums
    FORUM_HACKER = "forum_hacker"  # Hacker forums
    FORUM_FRAUD = "forum_fraud"  # Fraud discussion forums
    FORUM_LEAK = "forum_leak"  # Data leak forums

    # Paste Sites
    PASTE_SITE = "paste_site"  # Paste sites (pastebin, etc.)

    # Breach Databases
    BREACH_DATABASE = "breach_database"  # Known breach databases
    CREDENTIAL_DUMP = "credential_dump"  # Credential dumps

    # Chat Services
    TELEGRAM_CHANNEL = "telegram_channel"  # Telegram channels
    IRC_CHANNEL = "irc_channel"  # IRC channels

    # Other
    TOR_HIDDEN_SERVICE = "tor_hidden_service"  # Tor hidden services
    I2P_SITE = "i2p_site"  # I2P sites
    UNKNOWN = "unknown"  # Unknown source


class MentionType(str, Enum):
    """Types of dark web mentions."""

    CREDENTIAL_LEAK = "credential_leak"  # Email/password exposed
    IDENTITY_FOR_SALE = "identity_for_sale"  # Personal info being sold
    FINANCIAL_DATA = "financial_data"  # Credit card, bank info
    SOCIAL_SECURITY = "social_security"  # SSN exposed
    PASSPORT_DATA = "passport_data"  # Passport information
    MEDICAL_RECORDS = "medical_records"  # Healthcare data
    CORPORATE_DATA = "corporate_data"  # Company information
    THREAT_MENTION = "threat_mention"  # Threat against subject
    HACKING_TARGET = "hacking_target"  # Subject as hacking target
    REPUTATION_ATTACK = "reputation_attack"  # Reputation damage
    UNKNOWN = "unknown"  # Unknown mention type


class SeverityLevel(str, Enum):
    """Severity level of dark web findings."""

    CRITICAL = "critical"  # Immediate action required
    HIGH = "high"  # High priority
    MEDIUM = "medium"  # Moderate priority
    LOW = "low"  # Low priority
    INFORMATIONAL = "informational"  # FYI only


class ConfidenceLevel(str, Enum):
    """Confidence level of a match."""

    CONFIRMED = "confirmed"  # Verified match
    HIGH = "high"  # High confidence
    MEDIUM = "medium"  # Medium confidence
    LOW = "low"  # Low confidence
    UNVERIFIED = "unverified"  # Needs verification


class CredentialType(str, Enum):
    """Types of credentials found."""

    EMAIL_PASSWORD = "email_password"  # Email and password combination
    USERNAME_PASSWORD = "username_password"  # Username and password
    EMAIL_ONLY = "email_only"  # Email address exposed
    HASH_ONLY = "hash_only"  # Password hash exposed
    PLAINTEXT = "plaintext"  # Plaintext password
    TOKEN = "token"  # API token or session token
    UNKNOWN = "unknown"  # Unknown credential type


class BreachInfo(BaseModel):
    """Information about a data breach.

    Attributes:
        breach_id: Unique identifier for the breach.
        breach_name: Name of the breach (e.g., "LinkedIn 2021").
        breach_date: When the breach occurred.
        discovered_date: When the breach was discovered.
        source_company: Company that was breached.
        records_affected: Number of records in the breach.
        data_types: Types of data exposed.
        is_verified: Whether breach is verified.
        breach_description: Description of the breach.
    """

    breach_id: str
    breach_name: str
    breach_date: datetime | None = None
    discovered_date: datetime | None = None
    source_company: str | None = None
    records_affected: int | None = None
    data_types: list[str] = Field(default_factory=list)
    is_verified: bool = False
    breach_description: str | None = None


class CredentialLeak(BaseModel):
    """A leaked credential found on the dark web.

    Attributes:
        leak_id: Unique identifier for this leak.
        email: Email address if exposed.
        username: Username if exposed.
        password_hash: Password hash if available.
        password_plaintext: Plaintext password if available (redacted).
        credential_type: Type of credential.
        breach: Associated breach information.
        source: Where the leak was found.
        discovered_at: When we found this leak.
        last_seen_at: When the leak was last seen.
        is_active: Whether credentials are still valid (if checked).
    """

    leak_id: UUID
    email: str | None = None
    username: str | None = None
    password_hash: str | None = None
    password_plaintext: str | None = None  # Should be redacted/masked
    credential_type: CredentialType = CredentialType.UNKNOWN
    breach: BreachInfo | None = None
    source: DarkWebSource = DarkWebSource.UNKNOWN
    discovered_at: datetime = Field(default_factory=lambda: datetime.now())
    last_seen_at: datetime | None = None
    is_active: bool | None = None  # None means not checked


class MarketplaceListing(BaseModel):
    """A dark web marketplace listing.

    Attributes:
        listing_id: Unique identifier for this listing.
        title: Listing title.
        description: Listing description.
        price: Price in USD equivalent.
        currency: Original currency.
        marketplace: Name of marketplace.
        seller: Seller username/identifier.
        seller_reputation: Seller reputation score if available.
        mention_type: Type of data being sold.
        subject_identifiers: Identifiers matching the subject.
        discovered_at: When we found this listing.
        listing_url_hash: Hash of original URL (for reference).
        is_active: Whether listing is still active.
    """

    listing_id: UUID
    title: str
    description: str | None = None
    price: float | None = None
    currency: str = "USD"
    marketplace: str | None = None
    seller: str | None = None
    seller_reputation: float | None = None
    mention_type: MentionType = MentionType.UNKNOWN
    subject_identifiers: list[str] = Field(default_factory=list)
    discovered_at: datetime = Field(default_factory=lambda: datetime.now())
    listing_url_hash: str | None = None
    is_active: bool = True


class ForumMention(BaseModel):
    """A mention in a dark web forum.

    Attributes:
        mention_id: Unique identifier for this mention.
        forum_name: Name of the forum.
        thread_title: Title of the thread.
        post_content: Excerpt of the post content.
        author: Post author.
        mention_type: Type of mention.
        subject_identifiers: Identifiers matching the subject.
        posted_at: When the post was made.
        discovered_at: When we found this mention.
        thread_url_hash: Hash of thread URL.
        is_verified: Whether mention is verified.
    """

    mention_id: UUID
    forum_name: str | None = None
    thread_title: str | None = None
    post_content: str | None = None
    author: str | None = None
    mention_type: MentionType = MentionType.UNKNOWN
    subject_identifiers: list[str] = Field(default_factory=list)
    posted_at: datetime | None = None
    discovered_at: datetime = Field(default_factory=lambda: datetime.now())
    thread_url_hash: str | None = None
    is_verified: bool = False


class ThreatIndicator(BaseModel):
    """A threat indicator from dark web intelligence.

    Attributes:
        indicator_id: Unique identifier.
        indicator_type: Type of indicator (IP, domain, email, etc.).
        indicator_value: The indicator value.
        threat_type: Type of threat.
        severity: Severity level.
        confidence: Confidence level.
        source: Where the indicator was found.
        first_seen: When first observed.
        last_seen: When last observed.
        description: Threat description.
        tags: Associated tags.
    """

    indicator_id: UUID
    indicator_type: str  # ip, domain, email, hash, etc.
    indicator_value: str
    threat_type: str | None = None
    severity: SeverityLevel = SeverityLevel.MEDIUM
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    source: DarkWebSource = DarkWebSource.UNKNOWN
    first_seen: datetime = Field(default_factory=lambda: datetime.now())
    last_seen: datetime | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class DarkWebSearchResult(BaseModel):
    """Complete result of a dark web search.

    Attributes:
        search_id: Unique identifier for this search.
        subject_name: Name of the subject searched.
        search_identifiers: Identifiers used in the search.
        credential_leaks: Found credential leaks.
        marketplace_listings: Found marketplace listings.
        forum_mentions: Found forum mentions.
        threat_indicators: Associated threat indicators.
        total_findings: Total number of findings.
        severity_summary: Summary by severity level.
        searched_at: When the search completed.
        search_time_ms: How long the search took.
        cached: Whether result was from cache.
    """

    search_id: UUID
    subject_name: str
    search_identifiers: list[str] = Field(default_factory=list)
    credential_leaks: list[CredentialLeak] = Field(default_factory=list)
    marketplace_listings: list[MarketplaceListing] = Field(default_factory=list)
    forum_mentions: list[ForumMention] = Field(default_factory=list)
    threat_indicators: list[ThreatIndicator] = Field(default_factory=list)
    total_findings: int = 0
    severity_summary: dict[str, int] = Field(default_factory=dict)
    searched_at: datetime = Field(default_factory=lambda: datetime.now())
    search_time_ms: float = 0.0
    cached: bool = False

    def has_findings(self) -> bool:
        """Check if any findings were found."""
        return self.total_findings > 0

    def get_critical_findings(self) -> int:
        """Get count of critical findings."""
        return self.severity_summary.get("critical", 0)

    def get_high_severity_findings(self) -> int:
        """Get count of high or critical severity findings."""
        return self.severity_summary.get("critical", 0) + self.severity_summary.get("high", 0)


class DarkWebProviderConfig(BaseModel):
    """Configuration for the dark web monitoring provider.

    Attributes:
        api_key: API key for dark web monitoring service.
        api_url: API endpoint URL.
        enable_credential_monitoring: Whether to monitor for credential leaks.
        enable_marketplace_monitoring: Whether to monitor marketplaces.
        enable_forum_monitoring: Whether to monitor forums.
        enable_threat_intel: Whether to include threat intelligence.
        cache_ttl_seconds: How long to cache results.
        timeout_ms: Request timeout in milliseconds.
        min_confidence: Minimum confidence level to report.
    """

    api_key: str | None = None
    api_url: str = "https://api.darkweb-monitor.example.com/v1"
    enable_credential_monitoring: bool = True
    enable_marketplace_monitoring: bool = True
    enable_forum_monitoring: bool = True
    enable_threat_intel: bool = True
    cache_ttl_seconds: int = 3600  # 1 hour
    timeout_ms: int = 60000  # 60 seconds (dark web queries can be slow)
    min_confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM


# =============================================================================
# Exceptions
# =============================================================================


class DarkWebProviderError(Exception):
    """Base exception for dark web provider errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class DarkWebSearchError(DarkWebProviderError):
    """Raised when a dark web search fails."""

    def __init__(self, search_id: UUID, reason: str) -> None:
        super().__init__(
            f"Dark web search {search_id} failed: {reason}",
            details={"search_id": str(search_id), "reason": reason},
        )
        self.search_id = search_id
        self.reason = reason


class DarkWebRateLimitError(DarkWebProviderError):
    """Raised when rate limited by dark web service."""

    def __init__(self, retry_after_seconds: int | None = None) -> None:
        super().__init__(
            "Rate limited by dark web monitoring service",
            details={"retry_after_seconds": retry_after_seconds},
        )
        self.retry_after_seconds = retry_after_seconds


class DarkWebServiceUnavailableError(DarkWebProviderError):
    """Raised when dark web service is unavailable."""

    def __init__(self, service_name: str, reason: str) -> None:
        super().__init__(
            f"Dark web service {service_name} unavailable: {reason}",
            details={"service_name": service_name, "reason": reason},
        )
        self.service_name = service_name
        self.reason = reason
