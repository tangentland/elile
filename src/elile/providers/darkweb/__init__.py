"""Dark web monitoring provider module.

This module provides dark web monitoring for:
- Credential leaks from data breaches
- Marketplace listings selling personal data
- Forum mentions and discussions
- Threat intelligence indicators

Key Features:
- Breach database with known data breaches
- Credential leak detection
- Marketplace monitoring
- Forum mention tracking
- Threat intelligence aggregation

Usage:
    from elile.providers.darkweb import (
        DarkWebProvider,
        create_darkweb_provider,
        get_darkweb_provider,
    )

    # Create a provider
    provider = create_darkweb_provider()

    # Search dark web
    result = await provider.search_dark_web(
        subject_name="John Smith",
        identifiers=["john.smith@example.com"],
    )

    if result.has_findings():
        print(f"Found {result.total_findings} dark web findings")
        print(f"Critical findings: {result.get_critical_findings()}")
"""

from .breach_database import (
    BreachDatabase,
    create_breach_database,
)
from .provider import (
    DarkWebProvider,
    create_darkweb_provider,
    get_darkweb_provider,
)
from .types import (
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

__all__ = [
    # Provider
    "DarkWebProvider",
    "create_darkweb_provider",
    "get_darkweb_provider",
    # Types
    "BreachInfo",
    "ConfidenceLevel",
    "CredentialLeak",
    "CredentialType",
    "DarkWebProviderConfig",
    "DarkWebSearchResult",
    "DarkWebSource",
    "ForumMention",
    "MarketplaceListing",
    "MentionType",
    "SeverityLevel",
    "ThreatIndicator",
    # Breach Database
    "BreachDatabase",
    "create_breach_database",
    # Exceptions
    "DarkWebProviderError",
    "DarkWebSearchError",
    "DarkWebRateLimitError",
    "DarkWebServiceUnavailableError",
]
