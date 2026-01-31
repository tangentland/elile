"""Entity management package for Elile.

This package provides entity resolution, deduplication, and management
functionality for the Elile platform.

Usage:
    from elile.entity import EntityManager, SubjectIdentifiers

    manager = EntityManager(session)
    identifiers = SubjectIdentifiers(
        full_name="John Smith",
        ssn="123-45-6789",
        date_of_birth=date(1980, 1, 15),
    )
    result = await manager.create_entity(EntityType.INDIVIDUAL, identifiers)

Resolution:
    from elile.entity import EntityMatcher

    matcher = EntityMatcher(session)
    result = await matcher.resolve(identifiers)

Deduplication:
    from elile.entity import EntityDeduplicator

    dedup = EntityDeduplicator(session)
    result = await dedup.check_duplicate(identifiers)

Relationships:
    from elile.entity import RelationshipGraph, RelationType

    graph = RelationshipGraph(session)
    neighbors = await graph.get_neighbors(entity_id, depth=2)
"""

from elile.entity.deduplication import (
    DeduplicationResult,
    DuplicateCandidate,
    EntityDeduplicator,
    MergeResult,
)
from elile.entity.graph import (
    PathSegment,
    RelationshipEdge,
    RelationshipGraph,
    RelationshipPath,
)
from elile.entity.identifiers import IdentifierManager, IdentifierUpdate
from elile.entity.manager import EntityCreateResult, EntityManager
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
from elile.entity.validation import (
    EntityValidator,
    ValidationError,
    ValidationResult,
    ValidationSeverity,
    ValidationWarning,
    validate_identifier,
    validate_or_raise,
    validate_subject,
)

__all__ = [
    # Manager
    "EntityCreateResult",
    "EntityManager",
    # Matcher
    "EntityMatcher",
    # Deduplication
    "DeduplicationResult",
    "DuplicateCandidate",
    "EntityDeduplicator",
    "MergeResult",
    # Identifiers
    "IdentifierManager",
    "IdentifierUpdate",
    # Graph
    "PathSegment",
    "RelationshipEdge",
    "RelationshipGraph",
    "RelationshipPath",
    # Types
    "IdentifierRecord",
    "IdentifierType",
    "MatchedField",
    "MatchResult",
    "MatchType",
    "RelationType",
    "ResolutionDecision",
    "SubjectIdentifiers",
    # Validation
    "EntityValidator",
    "ValidationError",
    "ValidationResult",
    "ValidationSeverity",
    "ValidationWarning",
    "validate_identifier",
    "validate_or_raise",
    "validate_subject",
]
