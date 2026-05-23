"""create analysis persistence tables

Revision ID: 0001_create_analysis_tables
Revises:
Create Date: 2026-05-23
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_create_analysis_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("repository", sa.String(length=255), nullable=True),
        sa.Column("pull_request_number", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("agent_name", sa.String(length=100), nullable=True),
        sa.Column("branch", sa.String(length=255), nullable=True),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "changed_files",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("analysis_run_id", sa.String(length=36), sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("previous_path", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("additions", sa.Integer(), nullable=False),
        sa.Column("deletions", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=50), nullable=True),
        sa.Column("is_test_file", sa.Boolean(), nullable=False),
        sa.Column("is_critical_file", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "risk_findings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("analysis_run_id", sa.String(length=36), sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("score_delta", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_changed_files_analysis_run_id", "changed_files", ["analysis_run_id"])
    op.create_index("ix_risk_findings_analysis_run_id", "risk_findings", ["analysis_run_id"])


def downgrade() -> None:
    op.drop_index("ix_risk_findings_analysis_run_id", table_name="risk_findings")
    op.drop_index("ix_changed_files_analysis_run_id", table_name="changed_files")
    op.drop_table("risk_findings")
    op.drop_table("changed_files")
    op.drop_table("analysis_runs")
