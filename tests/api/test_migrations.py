from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command

PROJECT_ROOT = Path(__file__).parents[2]


def test_alembic_upgrade_creates_analysis_tables(tmp_path: Path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'migration-test.db'}"
    monkeypatch.setenv("AGENTREVIEW_DATABASE_URL", database_url)

    alembic_config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(alembic_config, "head")

    inspector = inspect(create_engine(database_url))

    assert set(inspector.get_table_names()) >= {
        "organizations",
        "users",
        "repositories",
        "repository_memberships",
        "api_keys",
        "policies",
        "audit_events",
        "analysis_runs",
        "changed_files",
        "risk_findings",
        "alembic_version",
    }

    analysis_columns = {column["name"] for column in inspector.get_columns("analysis_runs")}
    assert "organization_id" in analysis_columns
    assert "review_requirements_json" in analysis_columns

    api_key_columns = {column["name"] for column in inspector.get_columns("api_keys")}
    assert "role" in api_key_columns

    api_key_indexes = {index["name"] for index in inspector.get_indexes("api_keys")}
    assert "ix_api_keys_org_role" in api_key_indexes

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    assert "github_login" in user_columns

    user_indexes = {index["name"] for index in inspector.get_indexes("users")}
    assert "uq_users_org_github_login" in user_indexes

    audit_columns = {column["name"] for column in inspector.get_columns("audit_events")}
    assert {
        "organization_id",
        "actor_type",
        "actor_id",
        "action",
        "target_type",
        "target_id",
        "metadata_json",
    } <= audit_columns

    audit_indexes = {index["name"] for index in inspector.get_indexes("audit_events")}
    assert {
        "ix_audit_events_org_action",
        "ix_audit_events_org_actor",
        "ix_audit_events_org_target",
    } <= audit_indexes

    policy_columns = {column["name"] for column in inspector.get_columns("policies")}
    assert "repository_id" in policy_columns

    policy_indexes = {index["name"] for index in inspector.get_indexes("policies")}
    assert {
        "ix_policies_repository_id",
        "ix_policies_org_scope_repo_enabled",
    } <= policy_indexes

    version_columns = {column["name"]: column for column in inspector.get_columns("alembic_version")}
    version_num_type = version_columns["version_num"]["type"]
    assert getattr(version_num_type, "length", None) == 255
