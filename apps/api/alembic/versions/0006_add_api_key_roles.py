"""add api key roles

Revision ID: 0006_add_api_key_roles
Revises: 0005_add_repository_scoped_policies
Create Date: 2026-06-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_add_api_key_roles"
down_revision = "0005_add_repository_scoped_policies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("role", sa.String(length=50), nullable=False, server_default="admin"))
    op.create_index("ix_api_keys_org_role", "api_keys", ["organization_id", "role"])


def downgrade() -> None:
    op.drop_index("ix_api_keys_org_role", table_name="api_keys")
    op.drop_column("api_keys", "role")
