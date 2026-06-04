"""add policy storage

Revision ID: 0003_add_policies
Revises: 0002_add_auth_foundation
Create Date: 2026-05-24
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003_add_policies"
down_revision = "0002_add_auth_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "policies",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("scope", sa.String(length=50), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_policies_organization_id", "policies", ["organization_id"])
    op.create_index("ix_policies_org_enabled", "policies", ["organization_id", "enabled"])


def downgrade() -> None:
    op.drop_index("ix_policies_org_enabled", table_name="policies")
    op.drop_index("ix_policies_organization_id", table_name="policies")
    op.drop_table("policies")
