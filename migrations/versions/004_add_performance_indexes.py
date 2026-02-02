"""Add performance indexes for database optimization

Revision ID: 004
Revises: 003
Create Date: 2026-02-02

This migration adds strategic indexes to improve query performance:
- Composite indexes for common query patterns
- Partial indexes for filtered queries (WHERE active = true)
- GIN indexes for JSONB columns
- Descending indexes for timestamp-ordered queries
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # Entities Table Indexes
    # =========================================================================

    # GIN index for efficient JSONB lookups on canonical_identifiers
    # Supports queries like: canonical_identifiers @> '{"ssn": "123-45-6789"}'
    op.execute("""
        CREATE INDEX idx_entities_canonical_identifiers_gin
        ON entities USING gin (canonical_identifiers)
        """)

    # Composite index for tenant + type lookups
    op.create_index(
        "idx_entities_tenant_type",
        "entities",
        ["tenant_id", "entity_type"],
    )

    # Composite index for data origin + created_at (for cache management queries)
    op.create_index(
        "idx_entities_origin_created",
        "entities",
        ["data_origin", sa.text("created_at DESC")],
    )

    # =========================================================================
    # Entity Profiles Table Indexes
    # =========================================================================

    # Composite index for entity + version (descending) for latest version queries
    op.create_index(
        "idx_profiles_entity_version_desc",
        "entity_profiles",
        ["entity_id", sa.text("version DESC")],
    )

    # Index for trigger type queries with descending created_at
    op.create_index(
        "idx_profiles_trigger_created_desc",
        "entity_profiles",
        ["trigger_type", sa.text("created_at DESC")],
    )

    # GIN index for findings JSONB for efficient finding searches
    op.execute("""
        CREATE INDEX idx_profiles_findings_gin
        ON entity_profiles USING gin (findings)
        """)

    # GIN index for risk_score JSONB
    op.execute("""
        CREATE INDEX idx_profiles_risk_score_gin
        ON entity_profiles USING gin (risk_score)
        """)

    # =========================================================================
    # Entity Relations Table Indexes
    # =========================================================================

    # Composite index for bidirectional relationship lookups
    op.create_index(
        "idx_relations_bidirectional",
        "entity_relations",
        ["from_entity_id", "to_entity_id", "relation_type"],
    )

    # Index for reverse lookups with relation type
    op.create_index(
        "idx_relations_to_type",
        "entity_relations",
        ["to_entity_id", "relation_type"],
    )

    # Index for high-confidence relations
    op.execute("""
        CREATE INDEX idx_relations_high_confidence
        ON entity_relations (from_entity_id, to_entity_id)
        WHERE confidence_score >= 0.85
        """)

    # =========================================================================
    # Audit Events Table Indexes
    # =========================================================================

    # Composite index for tenant + timestamp (descending) for audit log pagination
    op.create_index(
        "idx_audit_tenant_timestamp_desc",
        "audit_events",
        ["tenant_id", sa.text("created_at DESC")],
    )

    # Composite index for event type + severity for filtering
    op.create_index(
        "idx_audit_type_severity",
        "audit_events",
        ["event_type", "severity"],
    )

    # Index for entity-based audit queries with timestamp ordering
    op.create_index(
        "idx_audit_entity_timestamp_desc",
        "audit_events",
        ["entity_id", sa.text("created_at DESC")],
    )

    # Partial index for high-severity events only (warning, error, critical)
    op.execute("""
        CREATE INDEX idx_audit_high_severity
        ON audit_events (created_at DESC)
        WHERE severity IN ('warning', 'error', 'critical')
        """)

    # =========================================================================
    # Cached Data Sources Table Indexes
    # =========================================================================

    # Composite index for entity + provider + check type (cache lookup pattern)
    op.create_index(
        "idx_cache_entity_provider_check",
        "cached_data_sources",
        ["entity_id", "provider_id", "check_type"],
    )

    # Index for freshness-based queries with expiration
    op.create_index(
        "idx_cache_freshness_until",
        "cached_data_sources",
        ["freshness_status", "fresh_until"],
    )

    # Partial index for fresh/stale cache entries only
    op.execute("""
        CREATE INDEX idx_cache_active_entries
        ON cached_data_sources (entity_id, check_type)
        WHERE freshness_status IN ('fresh', 'stale')
        """)

    # Index for cost analysis queries
    op.create_index(
        "idx_cache_cost_acquired",
        "cached_data_sources",
        ["customer_id", "provider_id", sa.text("acquired_at DESC")],
    )

    # =========================================================================
    # Tenants Table Indexes
    # =========================================================================

    # Partial index for active tenants only
    op.execute("""
        CREATE INDEX idx_tenants_active_name
        ON tenants (name)
        WHERE is_active = true
        """)


def downgrade() -> None:
    # Drop all indexes in reverse order

    # Tenants
    op.execute("DROP INDEX IF EXISTS idx_tenants_active_name")

    # Cached Data Sources
    op.drop_index("idx_cache_cost_acquired", "cached_data_sources")
    op.execute("DROP INDEX IF EXISTS idx_cache_active_entries")
    op.drop_index("idx_cache_freshness_until", "cached_data_sources")
    op.drop_index("idx_cache_entity_provider_check", "cached_data_sources")

    # Audit Events
    op.execute("DROP INDEX IF EXISTS idx_audit_high_severity")
    op.drop_index("idx_audit_entity_timestamp_desc", "audit_events")
    op.drop_index("idx_audit_type_severity", "audit_events")
    op.drop_index("idx_audit_tenant_timestamp_desc", "audit_events")

    # Entity Relations
    op.execute("DROP INDEX IF EXISTS idx_relations_high_confidence")
    op.drop_index("idx_relations_to_type", "entity_relations")
    op.drop_index("idx_relations_bidirectional", "entity_relations")

    # Entity Profiles
    op.execute("DROP INDEX IF EXISTS idx_profiles_risk_score_gin")
    op.execute("DROP INDEX IF EXISTS idx_profiles_findings_gin")
    op.drop_index("idx_profiles_trigger_created_desc", "entity_profiles")
    op.drop_index("idx_profiles_entity_version_desc", "entity_profiles")

    # Entities
    op.drop_index("idx_entities_origin_created", "entities")
    op.drop_index("idx_entities_tenant_type", "entities")
    op.execute("DROP INDEX IF EXISTS idx_entities_canonical_identifiers_gin")
