from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


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
        "analysis_runs",
        "changed_files",
        "risk_findings",
        "alembic_version",
    }

    analysis_columns = {column["name"] for column in inspector.get_columns("analysis_runs")}
    assert "organization_id" in analysis_columns
