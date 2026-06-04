"""add auth and organization foundation

Revision ID: 0002_add_auth_foundation
Revises: 0001_create_analysis_tables
Create Date: 2026-05-24
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_add_auth_foundation"
down_revision = "0001_create_analysis_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("slug", sa.String(length=100), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "repositories",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("default_branch", sa.String(length=255), nullable=True),
        sa.Column("visibility", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "provider", "owner", "name", name="uq_repositories_identity"),
    )
    op.create_table(
        "repository_memberships",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "repository_id", sa.String(length=36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("repository_id", "user_id", name="uq_repository_memberships_user"),
    )
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("key_prefix", sa.String(length=32), nullable=False, unique=True),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("analysis_runs", sa.Column("organization_id", sa.String(length=36), nullable=True))
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_analysis_runs_organization_id",
            "analysis_runs",
            "organizations",
            ["organization_id"],
            ["id"],
        )
    op.create_index("ix_analysis_runs_organization_id", "analysis_runs", ["organization_id"])
    op.create_index("ix_api_keys_organization_id", "api_keys", ["organization_id"])
    op.create_index("ix_repositories_organization_id", "repositories", ["organization_id"])
    op.create_index("ix_repository_memberships_repository_id", "repository_memberships", ["repository_id"])
    op.create_index("ix_repository_memberships_user_id", "repository_memberships", ["user_id"])
    op.create_index("ix_users_organization_id", "users", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_index("ix_repository_memberships_user_id", table_name="repository_memberships")
    op.drop_index("ix_repository_memberships_repository_id", table_name="repository_memberships")
    op.drop_index("ix_repositories_organization_id", table_name="repositories")
    op.drop_index("ix_api_keys_organization_id", table_name="api_keys")
    op.drop_index("ix_analysis_runs_organization_id", table_name="analysis_runs")
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_analysis_runs_organization_id", "analysis_runs", type_="foreignkey")
    op.drop_column("analysis_runs", "organization_id")
    op.drop_table("api_keys")
    op.drop_table("repository_memberships")
    op.drop_table("repositories")
    op.drop_table("users")
    op.drop_table("organizations")
