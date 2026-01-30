"""Unit tests for Profile models."""

from uuid import uuid4

import pytest

from elile.db.models.profile import EntityProfile, ProfileTrigger


def test_profile_creation():
    """Test creating an EntityProfile instance."""
    entity_id = uuid4()
    profile = EntityProfile(
        profile_id=uuid4(),
        entity_id=entity_id,
        version=1,
        trigger_type=ProfileTrigger.SCREENING,
        findings={},
        risk_score={"overall": 0.1},
        connections={},
        connection_count=0,
        data_sources_used=[],
        stale_data_used={},
    )
    assert profile.entity_id == entity_id
    assert profile.version == 1
    assert profile.trigger_type == ProfileTrigger.SCREENING


def test_profile_trigger_enum():
    """Test ProfileTrigger enum values."""
    assert ProfileTrigger.SCREENING == "screening"
    assert ProfileTrigger.MONITORING == "monitoring"
    assert ProfileTrigger.MANUAL == "manual"


def test_profile_with_evolution():
    """Test creating a profile with evolution tracking."""
    profile = EntityProfile(
        entity_id=uuid4(),
        version=2,
        trigger_type=ProfileTrigger.MONITORING,
        findings={},
        risk_score={"overall": 0.3},
        connections={},
        connection_count=5,
        data_sources_used=[],
        stale_data_used={},
        previous_version=1,
        delta={"new_findings": 3, "risk_increase": 0.2},
        evolution_signals={"pattern": "increasing_risk"},
    )
    assert profile.previous_version == 1
    assert profile.delta is not None
    assert "pattern" in profile.evolution_signals


def test_profile_repr():
    """Test EntityProfile __repr__ method."""
    entity_id = uuid4()
    profile_id = uuid4()
    profile = EntityProfile(
        profile_id=profile_id,
        entity_id=entity_id,
        version=1,
        trigger_type=ProfileTrigger.SCREENING,
        findings={},
        risk_score={},
        connections={},
        connection_count=0,
        data_sources_used=[],
        stale_data_used={},
    )
    repr_str = repr(profile)
    assert "EntityProfile" in repr_str
    assert str(entity_id) in repr_str
    assert "version=1" in repr_str
