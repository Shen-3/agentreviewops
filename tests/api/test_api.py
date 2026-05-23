from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from agentreview_api.db import create_session_factory
from agentreview_api.main import app, get_session
from agentreview_api.repository import create_api_key, create_organization, create_repository, create_repository_membership, create_user

PROJECT_ROOT = Path(__file__).parents[2]


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    database_url = f"sqlite:///{tmp_path / 'agentreview-test.db'}"
    monkeypatch.setenv("AGENTREVIEW_DATABASE_URL", database_url)

    alembic_config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(alembic_config, "head")

    session_factory = create_session_factory(database_url)
    with session_factory() as session:
        organization = create_organization(session, slug="acme", name="Acme Engineering")
        user = create_user(session, organization_id=organization.id, email="reviewer@example.com", name="Reviewer")
        repository = create_repository(
            session,
            organization_id=organization.id,
            provider="github",
            owner="platform",
            name="checkout-api",
            default_branch="main",
            visibility="private",
        )
        create_repository_membership(session, repository_id=repository.id, user_id=user.id)
        _, api_key = create_api_key(session, organization_id=organization.id, name="CI")

    def override_get_session():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as test_client:
            test_client.headers.update({"X-AgentReview-API-Key": api_key})
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_health(client: TestClient) -> None:
    client.headers.clear()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "agentreview-api"}


def test_auth_me_returns_api_key_context(client: TestClient) -> None:
    response = client.get("/api/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body["organization_id"]
    assert body["api_key_id"]
    assert body["api_key_name"] == "CI"


def test_analysis_endpoints_reject_anonymous_requests(client: TestClient) -> None:
    client.headers.clear()

    response = client.get("/api/analysis-runs")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Valid AgentReviewOps API key required"}


def test_policy_create_list_and_org_override_applies_to_analysis(client: TestClient) -> None:
    policy_response = client.post(
        "/api/policies",
        json={
            "name": "Low-friction docs pilot",
            "config": {
                "version": 1,
                "critical_paths": ["never/**"],
                "rules": {
                    "require_tests_for_code_changes": False,
                    "flag_auth_changes": False,
                },
            },
            "enabled": True,
        },
    )

    assert policy_response.status_code == 200
    policy_body = policy_response.json()
    assert policy_body["policy_id"]
    assert policy_body["name"] == "Low-friction docs pilot"
    assert policy_body["config"]["critical_paths"] == ["never/**"]

    list_response = client.get("/api/policies")

    assert list_response.status_code == 200
    assert list_response.json()[0]["policy_id"] == policy_body["policy_id"]

    diff_text = (PROJECT_ROOT / "examples" / "sample.diff").read_text(encoding="utf-8")
    analysis_response = client.post(
        "/api/analyze/diff",
        json={
            "diff": diff_text,
            "config": {
                "version": 1,
                "critical_paths": ["auth/**"],
            },
        },
    )

    assert analysis_response.status_code == 200
    analysis_body = analysis_response.json()
    assert analysis_body["risk_score"] == 0
    assert analysis_body["risk_level"] == "low"
    assert {finding["rule_id"] for finding in analysis_body["findings"]} == {"missing-docs", "small-focused-diff"}


def test_invalid_policy_config_returns_precise_validation_error(client: TestClient) -> None:
    response = client.post(
        "/api/policies",
        json={
            "name": "Invalid",
            "config": {
                "version": 2,
            },
        },
    )

    assert response.status_code == 422
    assert "unsupported config version" in str(response.json())


def test_analyze_diff_persists_and_returns_report(client: TestClient) -> None:
    diff_text = (PROJECT_ROOT / "examples" / "sample.diff").read_text(encoding="utf-8")

    response = client.post(
        "/api/analyze/diff",
        json={
            "diff": diff_text,
            "repository": "platform/checkout-api",
            "pull_request_number": 1842,
            "title": "Tighten inactive-user session handling",
            "author": "codex-agent",
            "agent_name": "Codex",
            "branch": "codex/auth-session-hardening",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["analysis_run_id"]
    assert body["created_at"]
    assert body["risk_score"] == 55
    assert body["risk_level"] == "high"
    assert body["changed_files"][0]["path"] == "auth/session.py"
    assert body["findings"][0]["rule_id"] == "critical-path-change"
    assert body["markdown"].startswith("# AgentReviewOps Report")

    report_response = client.get(f"/api/analysis-runs/{body['analysis_run_id']}/report")

    assert report_response.status_code == 200
    report_body = report_response.json()
    assert report_body["analysis_run_id"] == body["analysis_run_id"]
    assert report_body["markdown"] == body["markdown"]
    assert report_body["changed_files"][0]["path"] == "auth/session.py"


def test_list_analysis_runs_returns_dashboard_summaries(client: TestClient) -> None:
    diff_text = (PROJECT_ROOT / "examples" / "sample.diff").read_text(encoding="utf-8")

    create_response = client.post(
        "/api/analyze/diff",
        json={
            "diff": diff_text,
            "repository": "platform/checkout-api",
            "pull_request_number": 1842,
            "title": "Tighten inactive-user session handling",
            "author": "codex-agent",
            "agent_name": "Codex",
            "branch": "codex/auth-session-hardening",
        },
    )
    assert create_response.status_code == 200
    analysis_run_id = create_response.json()["analysis_run_id"]

    list_response = client.get("/api/analysis-runs")

    assert list_response.status_code == 200
    summaries = list_response.json()
    assert summaries[0]["analysis_run_id"] == analysis_run_id
    assert summaries[0]["repository"] == "platform/checkout-api"
    assert summaries[0]["pull_request_number"] == 1842
    assert summaries[0]["title"] == "Tighten inactive-user session handling"
    assert summaries[0]["agent_name"] == "Codex"
    assert summaries[0]["risk_level"] == "high"
    assert summaries[0]["changed_file_count"] == 1
    assert summaries[0]["finding_count"] > 0

    detail_response = client.get(f"/api/analysis-runs/{analysis_run_id}")

    assert detail_response.status_code == 200
    assert detail_response.json()["analysis_run_id"] == analysis_run_id


def test_report_fetch_returns_404_for_missing_run(client: TestClient) -> None:
    response = client.get("/api/analysis-runs/missing/report")

    assert response.status_code == 404
    assert response.json() == {"detail": "Analysis run not found"}


def test_analyze_diff_validates_empty_diff(client: TestClient) -> None:
    response = client.post("/api/analyze/diff", json={"diff": ""})

    assert response.status_code == 422
