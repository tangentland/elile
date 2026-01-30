"""Initial database schema

Revision ID: 001
Revises: None
Create Date: 2026-01-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create entities table
    op.create_table(
        "entities",
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("canonical_identifiers", postgresql.JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_entity_type", "entities", ["entity_type"])
    op.create_index("idx_entity_created", "entities", ["created_at"])

    # Create entity_profiles table
    op.create_table(
        "entity_profiles",
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column("trigger_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("findings", postgresql.JSONB, nullable=False),
        sa.Column("risk_score", postgresql.JSONB, nullable=False),
        sa.Column("connections", postgresql.JSONB, nullable=False),
        sa.Column("connection_count", sa.Integer, nullable=False),
        sa.Column("data_sources_used", postgresql.JSONB, nullable=False),
        sa.Column("stale_data_used", postgresql.JSONB, nullable=False),
        sa.Column("previous_version", sa.Integer, nullable=True),
        sa.Column("delta", postgresql.JSONB, nullable=True),
        sa.Column("evolution_signals", postgresql.JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.entity_id"], ondelete="CASCADE"),
    )
    op.create_index("idx_profile_entity", "entity_profiles", ["entity_id"])
    op.create_index(
        "idx_profile_version", "entity_profiles", ["entity_id", "version"], unique=True
    )
    op.create_index("idx_profile_trigger", "entity_profiles", ["trigger_type", "trigger_id"])
    op.create_index("idx_profile_created", "entity_profiles", ["created_at"])

    # Create cached_data_sources table
    op.create_table(
        "cached_data_sources",
        sa.Column("cache_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_id", sa.String(100), nullable=False),
        sa.Column("check_type", sa.String(100), nullable=False),
        sa.Column("data_origin", sa.String(50), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freshness_status", sa.String(50), nullable=False),
        sa.Column("fresh_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stale_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_response", sa.LargeBinary, nullable=False),
        sa.Column("normalized_data", postgresql.JSONB, nullable=False),
        sa.Column("cost_incurred", sa.Numeric(10, 2), nullable=False),
        sa.Column("cost_currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.entity_id"], ondelete="CASCADE"),
    )
    op.create_index("idx_cache_entity_check", "cached_data_sources", ["entity_id", "check_type"])
    op.create_index(
        "idx_cache_freshness", "cached_data_sources", ["freshness_status", "fresh_until"]
    )
    op.create_index("idx_cache_provider", "cached_data_sources", ["provider_id"])
    op.create_index("idx_cache_customer", "cached_data_sources", ["customer_id"])
    op.create_index("idx_cache_origin", "cached_data_sources", ["data_origin"])

    # Create entity_relations table
    op.create_table(
        "entity_relations",
        sa.Column("relation_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("from_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("to_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relation_type", sa.String(100), nullable=False),
        sa.Column("confidence_score", sa.Float, nullable=False),
        sa.Column("discovered_in_screening", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["from_entity_id"], ["entities.entity_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_entity_id"], ["entities.entity_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["discovered_in_screening"], ["entity_profiles.profile_id"], ondelete="SET NULL"
        ),
    )
    op.create_index("idx_from_entity", "entity_relations", ["from_entity_id"])
    op.create_index("idx_to_entity", "entity_relations", ["to_entity_id"])
    op.create_index("idx_relation_type", "entity_relations", ["relation_type"])


def downgrade() -> None:
    op.drop_table("entity_relations")
    op.drop_table("cached_data_sources")
    op.drop_table("entity_profiles")
    op.drop_table("entities")
