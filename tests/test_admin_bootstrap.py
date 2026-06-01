from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select
from typer.testing import CliRunner

from agentreview.cli import app
from agentreview_api.auth import authenticate_api_key, key_prefix
from agentreview_api.db import ApiKeyRecord, AuditEventRecord, create_session_factory


PROJECT_ROOT = Path(__file__).parents[1]


def test_admin_bootstrap_creates_org_user_and_one_time_api_key(tmp_path: Path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'bootstrap.db'}"
    monkeypatch.setenv("AGENTREVIEW_DATABASE_URL", database_url)
    alembic_config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(alembic_config, "head")

    result = CliRunner().invoke(
        app,
        [
            "admin",
            "bootstrap",
            "--org-slug",
            "acme",
            "--org-name",
            "Acme Engineering",
            "--email",
            "Reviewer@Example.COM",
            "--user-name",
            "Reviewer",
            "--api-key-name",
            "Local CI",
        ],
    )

    assert result.exit_code == 0
    assert "AgentReviewOps bootstrap complete" in result.output
    assert "Organization: acme" in result.output
    assert "Admin user: reviewer@example.com" in result.output
    api_key = _extract_api_key(result.output)
    assert api_key.startswith("arok_")

    session_factory = create_session_factory(database_url)
    with session_factory() as session:
        record = session.scalar(select(ApiKeyRecord).where(ApiKeyRecord.key_prefix == key_prefix(api_key)))
        assert record is not None
        assert record.name == "Local CI"
        assert record.role == "admin"
        assert record.key_hash != api_key
        auth = authenticate_api_key(session, api_key)
        audit_events = list(session.scalars(select(AuditEventRecord).order_by(AuditEventRecord.created_at)).all())

    assert auth is not None
    assert auth.api_key_name == "Local CI"
    assert auth.api_key_role == "admin"
    assert [event.action for event in audit_events] == ["organization.bootstrapped", "api_key.created"]
    assert "Reviewer@Example.COM" not in str([event.metadata_json for event in audit_events])
    assert api_key not in str([event.metadata_json for event in audit_events])


def test_admin_bootstrap_reuses_org_and_user_but_issues_new_key(tmp_path: Path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'bootstrap-repeat.db'}"
    monkeypatch.setenv("AGENTREVIEW_DATABASE_URL", database_url)
    alembic_config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(alembic_config, "head")
    runner = CliRunner()
    args = [
        "admin",
        "bootstrap",
        "--org-slug",
        "acme",
        "--org-name",
        "Acme Engineering",
        "--email",
        "reviewer@example.com",
    ]

    first = runner.invoke(app, args)
    second = runner.invoke(app, args)

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert _extract_api_key(first.output) != _extract_api_key(second.output)


def _extract_api_key(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("API key: "):
            return line.removeprefix("API key: ").strip()
    raise AssertionError(f"No API key line found in output:\n{output}")
