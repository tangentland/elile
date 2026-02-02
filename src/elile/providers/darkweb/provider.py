"""Dark web monitoring provider implementation.

This module provides the DarkWebProvider class for monitoring dark web
sources for credential leaks, marketplace activity, and threat intelligence.
"""

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid7

from elile.agent.state import SearchDegree, ServiceTier
from elile.compliance.types import CheckType, Locale
from elile.core.logging import get_logger
from elile.entity.types import SubjectIdentifiers
from elile.providers.protocol import BaseDataProvider
from elile.providers.types import (
    CostTier,
    DataSourceCategory,
    ProviderCapability,
    ProviderHealth,
    ProviderInfo,
    ProviderResult,
    ProviderStatus,
)

from .breach_database import BreachDatabase, create_breach_database
from .types import (
    ConfidenceLevel,
    CredentialLeak,
    CredentialType,
    DarkWebProviderConfig,
    DarkWebSearchResult,
    DarkWebSource,
    ForumMention,
    MarketplaceListing,
    MentionType,
    SeverityLevel,
    ThreatIndicator,
)

logger = get_logger(__name__)


class DarkWebProvider(BaseDataProvider):
    """Dark web monitoring provider.

    Monitors dark web sources for:
    - Credential leaks from data breaches
    - Marketplace listings selling personal data
    - Forum mentions and discussions
    - Threat intelligence indicators

    Usage:
        provider = DarkWebProvider()

        # Search for dark web mentions
        result = await provider.search_dark_web(
            subject_name="John Smith",
            identifiers=["john.smith@example.com", "jsmith123"],
        )

        if result.has_findings():
            print(f"Found {result.total_findings} dark web findings")
            for leak in result.credential_leaks:
                print(f"Credential leak: {leak.breach.breach_name}")
    """

    def __init__(self, config: DarkWebProviderConfig | None = None) -> None:
        """Initialize the dark web provider.

        Args:
            config: Optional provider configuration.
        """
        self._config = config or DarkWebProviderConfig()
        self._breach_db = create_breach_database()

        # Provider info
        provider_info = ProviderInfo(
            provider_id="darkweb_provider",
            name="Dark Web Monitoring Provider",
            description="Dark web monitoring for credentials, marketplaces, and threat intel",
            category=DataSourceCategory.PREMIUM,  # Premium tier provider
            capabilities=[
                ProviderCapability(
                    check_type=CheckType.DARK_WEB_MONITORING,
                    supported_locales=list(Locale),
                    cost_tier=CostTier.HIGH,
                    average_latency_ms=5000,
                    reliability_score=0.90,
                ),
            ],
            base_url=self._config.api_url,
            rate_limit_per_minute=60,
            rate_limit_per_day=1000,
            requires_api_key=True,
            supports_batch=True,
        )

        super().__init__(provider_info)

        logger.info(
            "darkweb_provider_initialized",
            credential_monitoring=self._config.enable_credential_monitoring,
            marketplace_monitoring=self._config.enable_marketplace_monitoring,
            forum_monitoring=self._config.enable_forum_monitoring,
            threat_intel=self._config.enable_threat_intel,
        )

    @property
    def config(self) -> DarkWebProviderConfig:
        """Get the provider configuration."""
        return self._config

    @property
    def breach_database(self) -> BreachDatabase:
        """Get the breach database."""
        return self._breach_db

    async def execute_check(
        self,
        check_type: CheckType,
        subject: SubjectIdentifiers,
        locale: Locale,
        *,
        degree: SearchDegree = SearchDegree.D1,  # noqa: ARG002
        service_tier: ServiceTier = ServiceTier.STANDARD,  # noqa: ARG002
        timeout_ms: int = 60000,  # noqa: ARG002
    ) -> ProviderResult:
        """Execute a dark web monitoring check.

        Args:
            check_type: Type of check (DARK_WEB_SCAN).
            subject: Subject identifiers to search for.
            locale: Locale for compliance context.
            degree: Search degree (reserved for future use).
            service_tier: Service tier (reserved for future use).
            timeout_ms: Request timeout (reserved for future use).

        Returns:
            ProviderResult with dark web findings.
        """
        start_time = datetime.now(UTC)
        query_id = uuid7()

        try:
            # Build subject name and identifiers
            subject_name = self._build_subject_name(subject)
            identifiers = self._extract_identifiers(subject)

            if not subject_name and not identifiers:
                return ProviderResult(
                    provider_id=self.provider_id,
                    check_type=check_type,
                    locale=locale,
                    success=False,
                    error_code="INVALID_SUBJECT",
                    error_message="No identifiers provided for dark web search",
                    query_id=query_id,
                )

            # Execute search
            search_result = await self._search_dark_web(
                subject_name=subject_name or "Unknown",
                identifiers=identifiers,
                query_id=query_id,
            )

            # Calculate latency
            latency_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
            search_result.search_time_ms = latency_ms

            # Build normalized data
            normalized_data = self._normalize_search_result(search_result)

            logger.info(
                "darkweb_check_complete",
                query_id=str(query_id),
                check_type=check_type.value,
                subject_name=subject_name,
                identifiers_count=len(identifiers),
                total_findings=search_result.total_findings,
                critical_findings=search_result.get_critical_findings(),
                latency_ms=latency_ms,
                locale=locale.value,
            )

            return ProviderResult(
                provider_id=self.provider_id,
                check_type=check_type,
                locale=locale,
                success=True,
                normalized_data=normalized_data,
                query_id=query_id,
                latency_ms=latency_ms,
                cost_incurred=self._calculate_cost(search_result),
            )

        except Exception as e:
            latency_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
            logger.error(
                "darkweb_check_failed",
                query_id=str(query_id),
                check_type=check_type.value,
                error=str(e),
            )
            return ProviderResult(
                provider_id=self.provider_id,
                check_type=check_type,
                locale=locale,
                success=False,
                error_code="SEARCH_ERROR",
                error_message=str(e),
                retryable=True,
                query_id=query_id,
                latency_ms=latency_ms,
            )

    async def health_check(self) -> ProviderHealth:
        """Check provider health.

        Returns:
            ProviderHealth with current status.
        """
        # In production, would check actual dark web API connectivity
        return ProviderHealth(
            provider_id=self.provider_id,
            status=ProviderStatus.HEALTHY,
            last_check=datetime.now(UTC),
            latency_ms=200,
            success_rate_24h=0.90,
        )

    async def search_dark_web(
        self,
        subject_name: str,
        identifiers: list[str],
        *,
        locale: str = "US",  # noqa: ARG002
    ) -> DarkWebSearchResult:
        """Search dark web for mentions of a subject.

        Public method for direct search without the provider interface.

        Args:
            subject_name: Name of the subject.
            identifiers: List of identifiers (emails, usernames, etc.).
            locale: Locale for audit logging (reserved for future use).

        Returns:
            DarkWebSearchResult with all findings.
        """
        return await self._search_dark_web(
            subject_name=subject_name,
            identifiers=identifiers,
            query_id=uuid7(),
        )

    async def check_credential_leaks(
        self,
        email: str,
    ) -> list[CredentialLeak]:
        """Check for credential leaks for a specific email.

        Args:
            email: Email address to check.

        Returns:
            List of CredentialLeak findings.
        """
        result = await self._search_dark_web(
            subject_name="",
            identifiers=[email],
            query_id=uuid7(),
        )
        return result.credential_leaks

    async def get_breach_info(self, breach_id: str) -> dict[str, Any] | None:
        """Get information about a specific breach.

        Args:
            breach_id: The breach identifier.

        Returns:
            Breach information as dictionary or None.
        """
        breach = self._breach_db.get_breach(breach_id)
        if breach:
            return {
                "breach_id": breach.breach_id,
                "breach_name": breach.breach_name,
                "source_company": breach.source_company,
                "breach_date": (breach.breach_date.isoformat() if breach.breach_date else None),
                "records_affected": breach.records_affected,
                "data_types": breach.data_types,
                "is_verified": breach.is_verified,
                "description": breach.breach_description,
            }
        return None

    async def _search_dark_web(
        self,
        subject_name: str,
        identifiers: list[str],
        query_id: UUID,
    ) -> DarkWebSearchResult:
        """Internal method to search dark web sources.

        Args:
            subject_name: Name of the subject.
            identifiers: Identifiers to search for.
            query_id: Query identifier.

        Returns:
            DarkWebSearchResult with findings.
        """
        result = DarkWebSearchResult(
            search_id=query_id,
            subject_name=subject_name,
            search_identifiers=identifiers,
        )

        # Search for credential leaks
        if self._config.enable_credential_monitoring:
            leaks = await self._search_credential_leaks(identifiers, query_id)
            result.credential_leaks = leaks

        # Search marketplace listings
        if self._config.enable_marketplace_monitoring:
            listings = await self._search_marketplaces(identifiers, query_id)
            result.marketplace_listings = listings

        # Search forum mentions
        if self._config.enable_forum_monitoring:
            mentions = await self._search_forums(subject_name, identifiers, query_id)
            result.forum_mentions = mentions

        # Get threat indicators
        if self._config.enable_threat_intel:
            indicators = await self._get_threat_indicators(identifiers, query_id)
            result.threat_indicators = indicators

        # Calculate totals
        result.total_findings = (
            len(result.credential_leaks)
            + len(result.marketplace_listings)
            + len(result.forum_mentions)
            + len(result.threat_indicators)
        )

        # Calculate severity summary
        result.severity_summary = self._calculate_severity_summary(result)

        return result

    async def _search_credential_leaks(
        self,
        identifiers: list[str],
        query_id: UUID,  # noqa: ARG002
    ) -> list[CredentialLeak]:
        """Search for credential leaks.

        Simulates breach database lookup. In production, would query
        actual dark web monitoring APIs.

        Args:
            identifiers: Identifiers to search for.
            query_id: Query identifier.

        Returns:
            List of CredentialLeak findings.
        """
        leaks: list[CredentialLeak] = []

        for identifier in identifiers:
            # Check if it's an email
            if "@" in identifier:
                domain = identifier.split("@")[1].lower()

                # Check against known breaches (simulated matching)
                # In production, would actually check if email is in breach dumps
                breaches = self._breach_db.search_by_domain(domain)

                # Simulate finding the email in some breaches based on hash
                identifier_hash = int(hashlib.md5(identifier.encode()).hexdigest(), 16)

                for breach in breaches:
                    # Simulate ~30% chance of finding email in a breach
                    if identifier_hash % 10 < 3:
                        leaks.append(
                            CredentialLeak(
                                leak_id=uuid7(),
                                email=identifier,
                                credential_type=CredentialType.EMAIL_PASSWORD,
                                breach=breach,
                                source=DarkWebSource.BREACH_DATABASE,
                                discovered_at=datetime.now(UTC),
                                last_seen_at=breach.discovered_date,
                                is_active=None,  # Not checked
                            )
                        )

        return leaks

    async def _search_marketplaces(
        self,
        identifiers: list[str],
        query_id: UUID,  # noqa: ARG002
    ) -> list[MarketplaceListing]:
        """Search dark web marketplaces.

        Simulates marketplace search. In production, would query
        actual dark web marketplace monitors.

        Args:
            identifiers: Identifiers to search for.
            query_id: Query identifier.

        Returns:
            List of MarketplaceListing findings.
        """
        listings: list[MarketplaceListing] = []

        # Simulate ~10% chance of finding marketplace listing
        for identifier in identifiers:
            identifier_hash = int(hashlib.md5(identifier.encode()).hexdigest(), 16)

            if identifier_hash % 10 == 0:  # 10% chance
                listings.append(
                    MarketplaceListing(
                        listing_id=uuid7(),
                        title=f"Personal data package - {identifier[:3]}***",
                        description="Full profile with verified information",
                        price=50.00,
                        currency="USD",
                        marketplace="DarkMarket",
                        seller="vendor_x_12345",
                        seller_reputation=4.2,
                        mention_type=MentionType.IDENTITY_FOR_SALE,
                        subject_identifiers=[identifier],
                        discovered_at=datetime.now(UTC),
                        listing_url_hash=hashlib.sha256(
                            f"listing_{identifier}".encode()
                        ).hexdigest()[:16],
                        is_active=True,
                    )
                )

        return listings

    async def _search_forums(
        self,
        subject_name: str,
        identifiers: list[str],
        query_id: UUID,  # noqa: ARG002
    ) -> list[ForumMention]:
        """Search dark web forums.

        Simulates forum search. In production, would query
        actual dark web forum monitors.

        Args:
            subject_name: Subject name.
            identifiers: Identifiers to search for.
            query_id: Query identifier.

        Returns:
            List of ForumMention findings.
        """
        mentions: list[ForumMention] = []

        # Simulate ~5% chance of finding forum mention
        combined = subject_name + "".join(identifiers)
        combined_hash = int(hashlib.md5(combined.encode()).hexdigest(), 16)

        if combined_hash % 20 == 0:  # 5% chance
            mentions.append(
                ForumMention(
                    mention_id=uuid7(),
                    forum_name="HackerForum",
                    thread_title="Data dump discussion",
                    post_content=f"[REDACTED] mentioned in relation to {subject_name[:3]}***",
                    author="anonymous_user",
                    mention_type=MentionType.THREAT_MENTION,
                    subject_identifiers=identifiers[:1] if identifiers else [],
                    posted_at=datetime.now(UTC),
                    discovered_at=datetime.now(UTC),
                    thread_url_hash=hashlib.sha256(combined.encode()).hexdigest()[:16],
                    is_verified=False,
                )
            )

        return mentions

    async def _get_threat_indicators(
        self,
        identifiers: list[str],
        query_id: UUID,  # noqa: ARG002
    ) -> list[ThreatIndicator]:
        """Get threat intelligence indicators.

        Simulates threat intel lookup. In production, would query
        actual threat intelligence feeds.

        Args:
            identifiers: Identifiers to search for.
            query_id: Query identifier.

        Returns:
            List of ThreatIndicator findings.
        """
        indicators: list[ThreatIndicator] = []

        # Simulate ~15% chance of finding threat indicator
        for identifier in identifiers:
            if "@" in identifier:  # Email-based indicators
                identifier_hash = int(hashlib.md5(identifier.encode()).hexdigest(), 16)

                if identifier_hash % 7 == 0:  # ~15% chance
                    indicators.append(
                        ThreatIndicator(
                            indicator_id=uuid7(),
                            indicator_type="email",
                            indicator_value=identifier,
                            threat_type="phishing_target",
                            severity=SeverityLevel.MEDIUM,
                            confidence=ConfidenceLevel.MEDIUM,
                            source=DarkWebSource.FORUM_HACKER,
                            first_seen=datetime.now(UTC),
                            description="Email found in phishing campaign target list",
                            tags=["phishing", "social_engineering"],
                        )
                    )

        return indicators

    def _calculate_severity_summary(
        self,
        result: DarkWebSearchResult,
    ) -> dict[str, int]:
        """Calculate severity summary for findings.

        Args:
            result: Search result with findings.

        Returns:
            Dictionary mapping severity level to count.
        """
        summary: dict[str, int] = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "informational": 0,
        }

        # Credential leaks are high severity
        for leak in result.credential_leaks:
            if (
                leak.credential_type == CredentialType.PLAINTEXT
                or (leak.breach and "ssn" in leak.breach.data_types)
            ):
                summary["critical"] += 1
            else:
                summary["high"] += 1

        # Marketplace listings are high severity
        for listing in result.marketplace_listings:
            if listing.mention_type == MentionType.SOCIAL_SECURITY:
                summary["critical"] += 1
            elif listing.mention_type in (
                MentionType.IDENTITY_FOR_SALE,
                MentionType.FINANCIAL_DATA,
            ):
                summary["high"] += 1
            else:
                summary["medium"] += 1

        # Forum mentions vary
        for mention in result.forum_mentions:
            if mention.mention_type in (MentionType.THREAT_MENTION, MentionType.HACKING_TARGET):
                summary["high"] += 1
            else:
                summary["medium"] += 1

        # Threat indicators by their own severity
        for indicator in result.threat_indicators:
            severity_key = indicator.severity.value
            if severity_key in summary:
                summary[severity_key] += 1

        return summary

    def _normalize_search_result(
        self,
        result: DarkWebSearchResult,
    ) -> dict[str, Any]:
        """Normalize search result to standard format."""
        return {
            "search": {
                "search_id": str(result.search_id),
                "subject_name": result.subject_name,
                "identifiers_searched": len(result.search_identifiers),
                "total_findings": result.total_findings,
                "has_critical": result.get_critical_findings() > 0,
                "severity_summary": result.severity_summary,
                "searched_at": result.searched_at.isoformat(),
                "search_time_ms": result.search_time_ms,
            },
            "credential_leaks": [
                {
                    "leak_id": str(leak.leak_id),
                    "email": leak.email,
                    "credential_type": leak.credential_type.value,
                    "breach_name": leak.breach.breach_name if leak.breach else None,
                    "breach_date": (
                        leak.breach.breach_date.isoformat()
                        if leak.breach and leak.breach.breach_date
                        else None
                    ),
                    "source": leak.source.value,
                    "discovered_at": leak.discovered_at.isoformat(),
                }
                for leak in result.credential_leaks
            ],
            "marketplace_listings": [
                {
                    "listing_id": str(listing.listing_id),
                    "title": listing.title,
                    "price": listing.price,
                    "marketplace": listing.marketplace,
                    "mention_type": listing.mention_type.value,
                    "is_active": listing.is_active,
                    "discovered_at": listing.discovered_at.isoformat(),
                }
                for listing in result.marketplace_listings
            ],
            "forum_mentions": [
                {
                    "mention_id": str(mention.mention_id),
                    "forum_name": mention.forum_name,
                    "thread_title": mention.thread_title,
                    "mention_type": mention.mention_type.value,
                    "is_verified": mention.is_verified,
                    "discovered_at": mention.discovered_at.isoformat(),
                }
                for mention in result.forum_mentions
            ],
            "threat_indicators": [
                {
                    "indicator_id": str(indicator.indicator_id),
                    "indicator_type": indicator.indicator_type,
                    "threat_type": indicator.threat_type,
                    "severity": indicator.severity.value,
                    "confidence": indicator.confidence.value,
                    "description": indicator.description,
                }
                for indicator in result.threat_indicators
            ],
        }

    def _calculate_cost(self, result: DarkWebSearchResult) -> Decimal:
        """Calculate cost based on search performed."""
        # Base cost for dark web search
        base_cost = Decimal("25.00")

        # Additional cost per finding
        finding_cost = Decimal("2.00") * result.total_findings

        # Premium for critical findings
        critical_cost = Decimal("5.00") * result.get_critical_findings()

        return base_cost + finding_cost + critical_cost

    def _build_subject_name(self, subject: SubjectIdentifiers) -> str:
        """Build subject name from identifiers."""
        if subject.full_name:
            return subject.full_name

        parts = []
        if subject.first_name:
            parts.append(subject.first_name)
        if subject.middle_name:
            parts.append(subject.middle_name)
        if subject.last_name:
            parts.append(subject.last_name)

        return " ".join(parts)

    def _extract_identifiers(self, subject: SubjectIdentifiers) -> list[str]:
        """Extract searchable identifiers from subject."""
        identifiers: list[str] = []

        # Add name variants
        if subject.full_name:
            identifiers.append(subject.full_name)
        if subject.name_variants:
            identifiers.extend(subject.name_variants)

        # Add email-like identifiers (would need to be extended)
        # In production, would extract from subject's known email addresses

        # Add SSN if available (for breach matching)
        if subject.ssn:
            # Don't add raw SSN, but could be used for breach matching
            pass

        return identifiers


# =============================================================================
# Factory functions
# =============================================================================

_provider_instance: DarkWebProvider | None = None


def get_darkweb_provider(
    config: DarkWebProviderConfig | None = None,
) -> DarkWebProvider:
    """Get the singleton dark web provider instance.

    Args:
        config: Optional configuration for first initialization.

    Returns:
        The DarkWebProvider singleton.
    """
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = DarkWebProvider(config)
    return _provider_instance


def create_darkweb_provider(
    config: DarkWebProviderConfig | None = None,
) -> DarkWebProvider:
    """Create a new dark web provider instance.

    Use this for testing or when you need a fresh provider.

    Args:
        config: Optional configuration.

    Returns:
        A new DarkWebProvider instance.
    """
    return DarkWebProvider(config)
