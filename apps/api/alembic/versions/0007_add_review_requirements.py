"""add review requirements

Revision ID: 0007_add_review_requirements
Revises: 0006_add_api_key_roles
Create Date: 2026-06-02
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007_add_review_requirements"
down_revision = "0006_add_api_key_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analysis_runs",
        sa.Column("review_requirements_json", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("analysis_runs", "review_requirements_json")
