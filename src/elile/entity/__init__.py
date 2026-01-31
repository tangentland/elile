"""Entity management package for Elile.

This package provides entity resolution, deduplication, and management
functionality for the Elile platform.

Usage:
    from elile.entity import EntityMatcher, SubjectIdentifiers

    matcher = EntityMatcher(session)
    identifiers = SubjectIdentifiers(
        full_name="John Smith",
        ssn="123-45-6789",
        date_of_birth=date(1980, 1, 15),
    )
    result = await matcher.resolve(identifiers)
"""

from elile.entity.matcher import EntityMatcher
from elile.entity.types import (
    IdentifierRecord,
    IdentifierType,
    MatchedField,
    MatchResult,
    MatchType,
    RelationType,
    ResolutionDecision,
    SubjectIdentifiers,
)

__all__ = [
    # Matcher
    "EntityMatcher",
    # Types
    "IdentifierRecord",
    "IdentifierType",
    "MatchedField",
    "MatchResult",
    "MatchType",
    "RelationType",
    "ResolutionDecision",
    "SubjectIdentifiers",
]
