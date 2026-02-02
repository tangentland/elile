"""Sanctions and watchlist screening provider.

This module provides comprehensive sanctions screening capabilities including:
- OFAC SDN (US Treasury Specially Designated Nationals)
- UN Security Council Consolidated List
- EU Consolidated Financial Sanctions List
- Interpol Red and Yellow Notices
- PEP (Politically Exposed Persons) databases

Example:
    from elile.providers.sanctions import (
        SanctionsProvider,
        create_sanctions_provider,
        get_sanctions_provider,
    )

    # Create provider
    provider = create_sanctions_provider()

    # Screen a subject
    result = await provider.execute_check(
        check_type=CheckType.SANCTIONS_OFAC,
        subject=SubjectIdentifiers(full_name="John Smith"),
        locale=Locale.US,
    )
"""

from .matcher import NameMatcher, create_name_matcher
from .provider import (
    SanctionsProvider,
    SanctionsProviderConfig,
    create_sanctions_provider,
    get_sanctions_provider,
)
from .types import (
    EntityType,
    FuzzyMatchConfig,
    MatchType,
    SanctionedEntity,
    SanctionsAddress,
    SanctionsAlias,
    SanctionsIdentifier,
    SanctionsList,
    SanctionsListUnavailableError,
    SanctionsMatch,
    SanctionsProviderError,
    SanctionsScreeningError,
    SanctionsScreeningResult,
)

__all__ = [
    # Provider
    "SanctionsProvider",
    "SanctionsProviderConfig",
    "create_sanctions_provider",
    "get_sanctions_provider",
    # Matcher
    "NameMatcher",
    "create_name_matcher",
    # Types
    "EntityType",
    "FuzzyMatchConfig",
    "MatchType",
    "SanctionedEntity",
    "SanctionsAddress",
    "SanctionsAlias",
    "SanctionsIdentifier",
    "SanctionsList",
    "SanctionsMatch",
    "SanctionsScreeningResult",
    # Exceptions
    "SanctionsProviderError",
    "SanctionsScreeningError",
    "SanctionsListUnavailableError",
]
