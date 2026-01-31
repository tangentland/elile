"""Add tenant infrastructure

Revision ID: 003
Revises: 002
Create Date: 2026-01-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create tenants table
    op.create_table(
        "tenants",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
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

    # Create indexes for tenants table
    op.create_index("idx_tenant_slug", "tenants", ["slug"], unique=True)
    op.create_index("idx_tenant_active", "tenants", ["is_active"])
    op.create_index("idx_tenant_created", "tenants", ["created_at"])

    # Add foreign key: cached_data_sources.customer_id -> tenants.tenant_id
    # ON DELETE CASCADE: if tenant is deleted, remove their customer-provided cache entries
    op.create_foreign_key(
        "fk_cache_customer_tenant",
        "cached_data_sources",
        "tenants",
        ["customer_id"],
        ["tenant_id"],
        ondelete="CASCADE",
    )

    # Add foreign key: audit_events.tenant_id -> tenants.tenant_id
    # ON DELETE SET NULL: preserve audit history even if tenant is deleted
    op.create_foreign_key(
        "fk_audit_tenant",
        "audit_events",
        "tenants",
        ["tenant_id"],
        ["tenant_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Remove foreign keys
    op.drop_constraint("fk_audit_tenant", "audit_events", type_="foreignkey")
    op.drop_constraint("fk_cache_customer_tenant", "cached_data_sources", type_="foreignkey")

    # Drop tenants table
    op.drop_table("tenants")
