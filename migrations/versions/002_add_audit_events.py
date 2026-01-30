"""Add audit_events table

Revision ID: 002
Revises: 001
Create Date: 2026-01-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create audit_events table
    op.create_table(
        "audit_events",
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="info"),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("event_data", postgresql.JSONB, nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Create indexes for common queries
    op.create_index("idx_audit_tenant", "audit_events", ["tenant_id"])
    op.create_index("idx_audit_correlation", "audit_events", ["correlation_id"])
    op.create_index("idx_audit_event_type", "audit_events", ["event_type"])
    op.create_index("idx_audit_entity", "audit_events", ["entity_id"])
    op.create_index("idx_audit_created", "audit_events", ["created_at"])
    op.create_index("idx_audit_severity", "audit_events", ["severity"])
    op.create_index("idx_audit_resource", "audit_events", ["resource_type", "resource_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
