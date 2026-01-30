"""Unit tests for Cache models."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from elile.db.models.cache import CachedDataSource, DataOrigin, FreshnessStatus


def test_cache_creation():
    """Test creating a CachedDataSource instance."""
    entity_id = uuid4()
    now = datetime.now(timezone.utc)
    cache = CachedDataSource(
        cache_id=uuid4(),
        entity_id=entity_id,
        provider_id="sterling",
        check_type="criminal_record",
        data_origin=DataOrigin.PAID_EXTERNAL,
        acquired_at=now,
        freshness_status=FreshnessStatus.FRESH,
        fresh_until=now + timedelta(days=30),
        stale_until=now + timedelta(days=90),
        raw_response=b"encrypted_data",
        normalized_data={"status": "clear"},
        cost_incurred=Decimal("25.00"),
        cost_currency="USD",
    )
    assert cache.entity_id == entity_id
    assert cache.provider_id == "sterling"
    assert cache.freshness_status == FreshnessStatus.FRESH


def test_data_origin_enum():
    """Test DataOrigin enum values."""
    assert DataOrigin.PAID_EXTERNAL == "paid_external"
    assert DataOrigin.CUSTOMER_PROVIDED == "customer_provided"


def test_freshness_status_enum():
    """Test FreshnessStatus enum values."""
    assert FreshnessStatus.FRESH == "fresh"
    assert FreshnessStatus.STALE == "stale"
    assert FreshnessStatus.EXPIRED == "expired"


def test_customer_provided_cache():
    """Test creating a customer-provided cache entry."""
    customer_id = uuid4()
    now = datetime.now(timezone.utc)
    cache = CachedDataSource(
        entity_id=uuid4(),
        provider_id="customer_hris",
        check_type="employment_verification",
        data_origin=DataOrigin.CUSTOMER_PROVIDED,
        customer_id=customer_id,
        acquired_at=now,
        freshness_status=FreshnessStatus.FRESH,
        fresh_until=now + timedelta(days=30),
        stale_until=now + timedelta(days=90),
        raw_response=b"encrypted_data",
        normalized_data={"employer": "Acme Corp"},
        cost_incurred=Decimal("0.00"),
        cost_currency="USD",
    )
    assert cache.customer_id == customer_id
    assert cache.data_origin == DataOrigin.CUSTOMER_PROVIDED


def test_cache_repr():
    """Test CachedDataSource __repr__ method."""
    cache_id = uuid4()
    entity_id = uuid4()
    now = datetime.now(timezone.utc)
    cache = CachedDataSource(
        cache_id=cache_id,
        entity_id=entity_id,
        provider_id="sterling",
        check_type="criminal_record",
        data_origin=DataOrigin.PAID_EXTERNAL,
        acquired_at=now,
        freshness_status=FreshnessStatus.FRESH,
        fresh_until=now + timedelta(days=30),
        stale_until=now + timedelta(days=90),
        raw_response=b"encrypted_data",
        normalized_data={},
        cost_incurred=Decimal("25.00"),
    )
    repr_str = repr(cache)
    assert "CachedDataSource" in repr_str
    assert str(entity_id) in repr_str
    assert "sterling" in repr_str
