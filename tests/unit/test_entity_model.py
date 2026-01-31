"""Unit tests for Entity models."""

from uuid import uuid7

import pytest

from elile.db.models.entity import Entity, EntityRelation, EntityType


def test_entity_creation():
    """Test creating an Entity instance."""
    entity = Entity(
        entity_id=uuid7(), entity_type=EntityType.INDIVIDUAL, canonical_identifiers={"ssn": "123"}
    )
    assert entity.entity_type == EntityType.INDIVIDUAL
    assert "ssn" in entity.canonical_identifiers


def test_entity_type_enum():
    """Test EntityType enum values."""
    assert EntityType.INDIVIDUAL == "individual"
    assert EntityType.ORGANIZATION == "organization"
    assert EntityType.ADDRESS == "address"


def test_entity_relation_creation():
    """Test creating an EntityRelation instance."""
    from_id = uuid7()
    to_id = uuid7()
    relation = EntityRelation(
        relation_id=uuid7(),
        from_entity_id=from_id,
        to_entity_id=to_id,
        relation_type="employer",
        confidence_score=0.95,
    )
    assert relation.from_entity_id == from_id
    assert relation.to_entity_id == to_id
    assert relation.confidence_score == 0.95


def test_entity_repr():
    """Test Entity __repr__ method."""
    entity_id = uuid7()
    entity = Entity(entity_id=entity_id, entity_type=EntityType.INDIVIDUAL)
    repr_str = repr(entity)
    assert "Entity" in repr_str
    assert str(entity_id) in repr_str
