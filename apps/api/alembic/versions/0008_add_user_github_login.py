"""add user github login

Revision ID: 0008_add_user_github_login
Revises: 0007_add_review_requirements
Create Date: 2026-06-05
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008_add_user_github_login"
down_revision = "0007_add_review_requirements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("github_login", sa.String(length=39), nullable=True))
    op.create_index(
        "uq_users_org_github_login",
        "users",
        ["organization_id", "github_login"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_users_org_github_login", table_name="users")
    op.drop_column("users", "github_login")
