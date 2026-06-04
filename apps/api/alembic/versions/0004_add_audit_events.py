"""add audit event log

Revision ID: 0004_add_audit_events
Revises: 0003_add_policies
Create Date: 2026-05-24
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004_add_audit_events"
down_revision = "0003_add_policies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor_type", sa.String(length=50), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=100), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_organization_id", "audit_events", ["organization_id"])
    op.create_index("ix_audit_events_org_created_at", "audit_events", ["organization_id", "created_at"])
    op.create_index("ix_audit_events_org_action", "audit_events", ["organization_id", "action"])
    op.create_index(
        "ix_audit_events_org_target", "audit_events", ["organization_id", "target_type", "target_id", "created_at"]
    )
    op.create_index(
        "ix_audit_events_org_actor", "audit_events", ["organization_id", "actor_type", "actor_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_org_actor", table_name="audit_events")
    op.drop_index("ix_audit_events_org_target", table_name="audit_events")
    op.drop_index("ix_audit_events_org_action", table_name="audit_events")
    op.drop_index("ix_audit_events_org_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_organization_id", table_name="audit_events")
    op.drop_table("audit_events")
