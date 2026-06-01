"""add repository scoped policies

Revision ID: 0005_add_repository_scoped_policies
Revises: 0004_add_audit_events
Create Date: 2026-06-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_add_repository_scoped_policies"
down_revision = "0004_add_audit_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("policies", sa.Column("repository_id", sa.String(length=36), nullable=True))
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_policies_repository_id",
            "policies",
            "repositories",
            ["repository_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.create_index("ix_policies_repository_id", "policies", ["repository_id"])
    op.create_index(
        "ix_policies_org_scope_repo_enabled",
        "policies",
        ["organization_id", "scope", "repository_id", "enabled"],
    )


def downgrade() -> None:
    op.drop_index("ix_policies_org_scope_repo_enabled", table_name="policies")
    op.drop_index("ix_policies_repository_id", table_name="policies")
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_policies_repository_id", "policies", type_="foreignkey")
    op.drop_column("policies", "repository_id")
