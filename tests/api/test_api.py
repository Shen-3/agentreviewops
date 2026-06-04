import csv
import json
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select

from agentreview.models import (
    AgentReviewConfig,
    DiffFile,
    ReviewRequirement,
    RiskAnalysis,
    RiskFinding,
    SuggestedReviewer,
)
from agentreview_api.auth import key_prefix
from agentreview_api.db import AnalysisRunRecord, AuditEventRecord, create_session_factory
from agentreview_api.main import app, get_session
from agentreview_api.repository import (
    create_analysis_run,
    create_api_key,
    create_audit_event,
    create_organization,
    create_repository,
    create_repository_membership,
    create_user,
)
from alembic import command

PROJECT_ROOT = Path(__file__).parents[2]


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    database_url = f"sqlite:///{tmp_path / 'agentreview-test.db'}"
    monkeypatch.setenv("AGENTREVIEW_DATABASE_URL", database_url)

    alembic_config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(alembic_config, "head")

    session_factory = create_session_factory(database_url)
    app.state.test_session_factory = session_factory
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
        if hasattr(app.state, "test_session_factory"):
            delattr(app.state, "test_session_factory")


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
    assert body["api_key_role"] == "admin"


def test_analysis_endpoints_reject_anonymous_requests(client: TestClient) -> None:
    client.headers.clear()

    response = client.get("/api/analysis-runs")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Valid AgentReviewOps API key required"}


def test_metrics_endpoints_reject_anonymous_requests(client: TestClient) -> None:
    client.headers.clear()

    response = client.get("/api/metrics/overview")

    assert response.status_code == 401
    assert response.json() == {"detail": "Valid AgentReviewOps API key required"}


def test_audit_events_reject_anonymous_requests(client: TestClient) -> None:
    client.headers.clear()

    response = client.get("/api/audit-events")

    assert response.status_code == 401
    assert response.json() == {"detail": "Valid AgentReviewOps API key required"}


def test_api_key_management_rejects_anonymous_requests(client: TestClient) -> None:
    client.headers.clear()

    response = client.get("/api/api-keys")

    assert response.status_code == 401
    assert response.json() == {"detail": "Valid AgentReviewOps API key required"}


def test_user_management_rejects_anonymous_requests(client: TestClient) -> None:
    client.headers.clear()

    response = client.get("/api/users")

    assert response.status_code == 401
    assert response.json() == {"detail": "Valid AgentReviewOps API key required"}


def test_repository_onboarding_lists_creates_audits_and_blocks_duplicates(client: TestClient) -> None:
    list_response = client.get("/api/repositories")

    assert list_response.status_code == 200
    repositories = list_response.json()
    assert len(repositories) == 1
    assert repositories[0]["full_name"] == "platform/checkout-api"
    assert repositories[0]["provider"] == "github"
    assert repositories[0]["reviewers"] == [
        {
            "user_id": repositories[0]["reviewers"][0]["user_id"],
            "email": "reviewer@example.com",
            "name": "Reviewer",
            "github_login": None,
            "role": "maintainer",
        }
    ]

    create_response = client.post(
        "/api/repositories",
        json={
            "provider": "GitHub",
            "owner": "platform",
            "name": "billing-api",
            "default_branch": "main",
            "visibility": "Private",
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["repository_id"]
    assert created["provider"] == "github"
    assert created["full_name"] == "platform/billing-api"
    assert created["default_branch"] == "main"
    assert created["visibility"] == "private"

    duplicate_response = client.post(
        "/api/repositories",
        json={
            "provider": "github",
            "owner": "platform",
            "name": "billing-api",
        },
    )
    assert duplicate_response.status_code == 409

    audit_response = client.get("/api/audit-events", params={"action": "repository.created"})
    assert audit_response.status_code == 200
    audit_event = audit_response.json()[0]
    assert audit_event["target_id"] == created["repository_id"]
    assert audit_event["metadata"] == {
        "provider": "github",
        "owner": "platform",
        "name": "billing-api",
        "default_branch": "main",
        "visibility": "private",
    }


def test_repository_delete_removes_scoped_governance_and_audits(client: TestClient) -> None:
    create_response = client.post(
        "/api/repositories",
        json={
            "provider": "github",
            "owner": "platform",
            "name": "legacy-api",
        },
    )
    assert create_response.status_code == 200
    repository = create_response.json()

    policy_response = client.post(
        "/api/policies",
        json={
            "name": "Legacy API policy",
            "scope": "repository",
            "repository_id": repository["repository_id"],
            "config": {
                "version": 1,
                "critical_paths": ["legacy/**"],
            },
        },
    )
    assert policy_response.status_code == 200

    delete_response = client.delete(f"/api/repositories/{repository['repository_id']}")

    assert delete_response.status_code == 204
    assert delete_response.text == ""

    list_response = client.get("/api/repositories")
    assert list_response.status_code == 200
    assert "platform/legacy-api" not in {record["full_name"] for record in list_response.json()}

    policy_list_response = client.get("/api/policies")
    assert policy_list_response.status_code == 200
    assert policy_response.json()["policy_id"] not in {record["policy_id"] for record in policy_list_response.json()}

    delete_again_response = client.delete(f"/api/repositories/{repository['repository_id']}")
    assert delete_again_response.status_code == 404

    audit_response = client.get("/api/audit-events", params={"action": "repository.deleted"})
    assert audit_response.status_code == 200
    audit_event = audit_response.json()[0]
    assert audit_event["target_id"] == repository["repository_id"]
    assert audit_event["metadata"]["repository"] == "platform/legacy-api"


def test_user_management_and_repository_membership_assignment(client: TestClient) -> None:
    list_response = client.get("/api/users")

    assert list_response.status_code == 200
    users = list_response.json()
    assert len(users) == 1
    assert users[0]["email"] == "reviewer@example.com"
    assert users[0]["github_login"] is None
    assert users[0]["role"] == "admin"

    create_user_response = client.post(
        "/api/users",
        json={
            "email": "Payments.Owner@Example.COM",
            "name": "Payments Owner",
            "github_login": " @payments-owner ",
            "role": "reviewer",
        },
    )

    assert create_user_response.status_code == 200
    created_user = create_user_response.json()
    assert created_user["user_id"]
    assert created_user["email"] == "payments.owner@example.com"
    assert created_user["name"] == "Payments Owner"
    assert created_user["github_login"] == "payments-owner"
    assert created_user["role"] == "reviewer"

    duplicate_user_response = client.post(
        "/api/users",
        json={
            "email": "payments.owner@example.com",
            "role": "reviewer",
        },
    )
    assert duplicate_user_response.status_code == 409

    repository = client.get("/api/repositories").json()[0]
    assign_response = client.post(
        f"/api/repositories/{repository['repository_id']}/memberships",
        json={
            "user_id": created_user["user_id"],
            "role": "owner",
        },
    )

    assert assign_response.status_code == 200
    updated_repository = assign_response.json()
    reviewer_emails = {reviewer["email"]: reviewer["role"] for reviewer in updated_repository["reviewers"]}
    assert reviewer_emails["reviewer@example.com"] == "maintainer"
    assert reviewer_emails["payments.owner@example.com"] == "owner"
    reviewer_logins = {reviewer["email"]: reviewer["github_login"] for reviewer in updated_repository["reviewers"]}
    assert reviewer_logins["payments.owner@example.com"] == "payments-owner"

    duplicate_membership_response = client.post(
        f"/api/repositories/{repository['repository_id']}/memberships",
        json={
            "user_id": created_user["user_id"],
            "role": "owner",
        },
    )
    assert duplicate_membership_response.status_code == 409

    remove_membership_response = client.delete(
        f"/api/repositories/{repository['repository_id']}/memberships/{created_user['user_id']}",
    )
    assert remove_membership_response.status_code == 200
    reviewer_emails = {
        reviewer["email"]: reviewer["role"] for reviewer in remove_membership_response.json()["reviewers"]
    }
    assert "payments.owner@example.com" not in reviewer_emails

    delete_user_response = client.delete(f"/api/users/{created_user['user_id']}")
    assert delete_user_response.status_code == 204

    list_after_delete_response = client.get("/api/users")
    assert list_after_delete_response.status_code == 200
    assert [user["email"] for user in list_after_delete_response.json()] == ["reviewer@example.com"]

    delete_last_admin_response = client.delete(f"/api/users/{users[0]['user_id']}")
    assert delete_last_admin_response.status_code == 400
    assert delete_last_admin_response.json() == {"detail": "Cannot delete the last organization admin"}

    audit_response = client.get("/api/audit-events")
    assert audit_response.status_code == 200
    actions = [event["action"] for event in audit_response.json()[:4]]
    assert actions == ["user.deleted", "repository_membership.deleted", "repository_membership.created", "user.created"]
    membership_event = audit_response.json()[2]
    assert membership_event["target_id"] == repository["repository_id"]
    assert membership_event["metadata"]["repository"] == "platform/checkout-api"
    assert membership_event["metadata"]["user_id"] == created_user["user_id"]
    assert membership_event["metadata"]["membership_role"] == "owner"
    assert "payments.owner@example.com" not in json.dumps(membership_event)


def test_user_github_login_validation_update_clear_and_duplicate_detection(client: TestClient) -> None:
    first_response = client.post(
        "/api/users",
        json={
            "email": "alice@example.com",
            "github_login": "@Alice-Reviewer",
            "role": "reviewer",
        },
    )
    assert first_response.status_code == 200
    first_user = first_response.json()
    assert first_user["github_login"] == "Alice-Reviewer"

    update_response = client.patch(
        f"/api/users/{first_user['user_id']}",
        json={"github_login": "alice-reviewer-2"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["github_login"] == "alice-reviewer-2"

    clear_response = client.patch(
        f"/api/users/{first_user['user_id']}",
        json={"github_login": ""},
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["github_login"] is None

    invalid_response = client.post(
        "/api/users",
        json={
            "email": "invalid-login@example.com",
            "github_login": "-invalid",
            "role": "reviewer",
        },
    )
    assert invalid_response.status_code == 400
    assert "Invalid GitHub login" in invalid_response.json()["detail"]

    reset_response = client.patch(
        f"/api/users/{first_user['user_id']}",
        json={"github_login": "Alice"},
    )
    assert reset_response.status_code == 200

    duplicate_response = client.post(
        "/api/users",
        json={
            "email": "duplicate-login@example.com",
            "github_login": "alice",
            "role": "reviewer",
        },
    )
    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {"detail": "GitHub login already belongs to another user"}


def test_api_key_management_lists_creates_and_revokes_keys(client: TestClient) -> None:
    list_response = client.get("/api/api-keys")

    assert list_response.status_code == 200
    initial_keys = list_response.json()
    assert len(initial_keys) == 1
    assert initial_keys[0]["name"] == "CI"
    assert initial_keys[0]["role"] == "admin"
    assert initial_keys[0]["is_current"] is True
    assert initial_keys[0]["revoked_at"] is None
    assert "api_key" not in initial_keys[0]
    assert "key_hash" not in initial_keys[0]

    create_response = client.post("/api/api-keys", json={"name": "Dashboard operator"})

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["api_key_id"]
    assert created["name"] == "Dashboard operator"
    assert created["role"] == "admin"
    assert created["api_key"].startswith("arok_")
    assert created["key_prefix"] == key_prefix(created["api_key"])
    assert created["is_current"] is False
    assert created["revoked_at"] is None

    audit_response = client.get("/api/audit-events", params={"action": "api_key.created"})
    assert audit_response.status_code == 200
    audit_event = audit_response.json()[0]
    assert audit_event["target_id"] == created["api_key_id"]
    assert audit_event["metadata"] == {
        "api_key_name": "Dashboard operator",
        "api_key_role": "admin",
        "source": "api",
    }
    assert created["api_key"] not in str(audit_event)

    list_response = client.get("/api/api-keys")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert [record["name"] for record in listed] == ["Dashboard operator", "CI"]
    assert all("api_key" not in record for record in listed)
    assert all("key_hash" not in record for record in listed)

    revoke_response = client.post(f"/api/api-keys/{created['api_key_id']}/revoke")

    assert revoke_response.status_code == 200
    revoked = revoke_response.json()
    assert revoked["api_key_id"] == created["api_key_id"]
    assert revoked["role"] == "admin"
    assert revoked["revoked_at"]

    auth_with_revoked_key = client.get("/api/auth/me", headers={"X-AgentReview-API-Key": created["api_key"]})
    assert auth_with_revoked_key.status_code == 401

    revoke_audit_response = client.get("/api/audit-events", params={"action": "api_key.revoked"})
    assert revoke_audit_response.status_code == 200
    assert revoke_audit_response.json()[0]["metadata"] == {"api_key_name": "Dashboard operator"}


def test_api_key_management_blocks_self_revoke_and_cross_org_revoke(client: TestClient) -> None:
    current_key = client.get("/api/auth/me").json()["api_key_id"]

    self_revoke_response = client.post(f"/api/api-keys/{current_key}/revoke")

    assert self_revoke_response.status_code == 400
    assert self_revoke_response.json() == {"detail": "Cannot revoke the API key used for this request"}

    with app.state.test_session_factory() as session:
        other_org = create_organization(session, slug="keys-other", name="Keys Other")
        other_key, _ = create_api_key(session, organization_id=other_org.id, name="Other org key")

    cross_org_response = client.post(f"/api/api-keys/{other_key.id}/revoke")

    assert cross_org_response.status_code == 404
    assert cross_org_response.json() == {"detail": "API key not found"}


def test_api_key_roles_limit_mutating_and_analysis_access(client: TestClient) -> None:
    ci_response = client.post(
        "/api/api-keys",
        json={
            "name": "CI submitter",
            "role": "ci",
        },
    )
    assert ci_response.status_code == 200
    ci_key = ci_response.json()["api_key"]
    assert ci_response.json()["role"] == "ci"

    read_only_response = client.post(
        "/api/api-keys",
        json={
            "name": "Read only reviewer",
            "role": "read_only",
        },
    )
    assert read_only_response.status_code == 200
    read_only_key = read_only_response.json()["api_key"]
    assert read_only_response.json()["role"] == "read_only"

    diff_text = (PROJECT_ROOT / "examples" / "sample.diff").read_text(encoding="utf-8")
    ci_analysis_response = client.post(
        "/api/analyze/diff",
        headers={"X-AgentReview-API-Key": ci_key},
        json={
            "diff": diff_text,
            "repository": "platform/checkout-api",
        },
    )
    assert ci_analysis_response.status_code == 200

    ci_admin_response = client.post(
        "/api/users",
        headers={"X-AgentReview-API-Key": ci_key},
        json={
            "email": "ci-admin@example.com",
            "role": "reviewer",
        },
    )
    assert ci_admin_response.status_code == 403
    assert ci_admin_response.json() == {"detail": "Admin AgentReviewOps API key required"}

    read_only_analysis_response = client.post(
        "/api/analyze/diff",
        headers={"X-AgentReview-API-Key": read_only_key},
        json={
            "diff": diff_text,
            "repository": "platform/checkout-api",
        },
    )
    assert read_only_analysis_response.status_code == 403
    assert read_only_analysis_response.json() == {"detail": "Admin or CI AgentReviewOps API key required"}

    read_only_list_response = client.get(
        "/api/analysis-runs",
        headers={"X-AgentReview-API-Key": read_only_key},
    )
    assert read_only_list_response.status_code == 200


def test_role_update_endpoints_audit_and_protect_admins(client: TestClient) -> None:
    initial_admin = client.get("/api/users").json()[0]
    create_user_response = client.post(
        "/api/users",
        json={
            "email": "role-editor@example.com",
            "name": "Role Editor",
            "role": "reviewer",
        },
    )
    assert create_user_response.status_code == 200
    role_editor = create_user_response.json()

    promote_response = client.patch(
        f"/api/users/{role_editor['user_id']}",
        json={"role": "admin"},
    )
    assert promote_response.status_code == 200
    assert promote_response.json()["role"] == "admin"

    demote_first_admin_response = client.patch(
        f"/api/users/{initial_admin['user_id']}",
        json={"role": "reviewer"},
    )
    assert demote_first_admin_response.status_code == 200
    assert demote_first_admin_response.json()["role"] == "reviewer"

    demote_last_admin_response = client.patch(
        f"/api/users/{role_editor['user_id']}",
        json={"role": "reviewer"},
    )
    assert demote_last_admin_response.status_code == 400
    assert demote_last_admin_response.json() == {"detail": "Cannot demote the last organization admin"}

    key_response = client.post(
        "/api/api-keys",
        json={
            "name": "Mutable key",
            "role": "read_only",
        },
    )
    assert key_response.status_code == 200
    key_id = key_response.json()["api_key_id"]
    update_key_response = client.patch(
        f"/api/api-keys/{key_id}",
        json={"role": "ci"},
    )
    assert update_key_response.status_code == 200
    assert update_key_response.json()["role"] == "ci"

    current_key_id = client.get("/api/auth/me").json()["api_key_id"]
    demote_current_key_response = client.patch(
        f"/api/api-keys/{current_key_id}",
        json={"role": "read_only"},
    )
    assert demote_current_key_response.status_code == 400
    assert demote_current_key_response.json() == {
        "detail": "Cannot change the current admin API key to a non-admin role"
    }

    repository = client.get("/api/repositories").json()[0]
    assign_response = client.post(
        f"/api/repositories/{repository['repository_id']}/memberships",
        json={
            "user_id": role_editor["user_id"],
            "role": "reviewer",
        },
    )
    assert assign_response.status_code == 200

    update_membership_response = client.patch(
        f"/api/repositories/{repository['repository_id']}/memberships/{role_editor['user_id']}",
        json={"role": "owner"},
    )
    assert update_membership_response.status_code == 200
    reviewer_roles = {
        reviewer["email"]: reviewer["role"] for reviewer in update_membership_response.json()["reviewers"]
    }
    assert reviewer_roles["role-editor@example.com"] == "owner"

    actions = [event["action"] for event in client.get("/api/audit-events").json()]
    assert "user.updated" in actions
    assert "api_key.updated" in actions
    assert "repository_membership.updated" in actions


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
    assert policy_body["scope"] == "organization"
    assert policy_body["repository_id"] is None
    assert policy_body["repository_full_name"] is None
    assert policy_body["config"]["critical_paths"] == ["never/**"]

    audit_response = client.get("/api/audit-events")

    assert audit_response.status_code == 200
    audit_events = audit_response.json()
    assert audit_events[0]["action"] == "policy.created"
    assert audit_events[0]["target_type"] == "policy"
    assert audit_events[0]["target_id"] == policy_body["policy_id"]
    assert audit_events[0]["actor_type"] == "api_key"
    assert audit_events[0]["metadata"]["policy_name"] == "Low-friction docs pilot"
    assert "config" not in audit_events[0]["metadata"]

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

    update_response = client.patch(
        f"/api/policies/{policy_body['policy_id']}",
        json={"enabled": False, "name": "Low-friction docs pilot disabled"},
    )

    assert update_response.status_code == 200
    updated_policy = update_response.json()
    assert updated_policy["policy_id"] == policy_body["policy_id"]
    assert updated_policy["enabled"] is False
    assert updated_policy["name"] == "Low-friction docs pilot disabled"

    fallback_analysis_response = client.post(
        "/api/analyze/diff",
        json={
            "diff": diff_text,
            "config": {
                "version": 1,
                "critical_paths": ["auth/**"],
            },
        },
    )

    assert fallback_analysis_response.status_code == 200
    fallback_analysis_body = fallback_analysis_response.json()
    assert fallback_analysis_body["risk_level"] == "high"
    assert "critical-path-change" in {finding["rule_id"] for finding in fallback_analysis_body["findings"]}

    audit_response = client.get("/api/audit-events")
    assert [event["action"] for event in audit_response.json()[:4]] == [
        "analysis.created",
        "policy.updated",
        "analysis.created",
        "policy.created",
    ]
    assert audit_response.json()[1]["metadata"]["previous_enabled"] is True

    policy_filter_response = client.get("/api/audit-events", params={"action": "policy.created"})
    assert policy_filter_response.status_code == 200
    assert [event["action"] for event in policy_filter_response.json()] == ["policy.created"]

    policy_update_filter_response = client.get("/api/audit-events", params={"action": "policy.updated"})
    assert policy_update_filter_response.status_code == 200
    assert [event["action"] for event in policy_update_filter_response.json()] == ["policy.updated"]


def test_repository_scoped_policy_overrides_org_policy_and_records_routing(client: TestClient) -> None:
    repositories_response = client.get("/api/repositories")
    assert repositories_response.status_code == 200
    repository = repositories_response.json()[0]

    org_policy_response = client.post(
        "/api/policies",
        json={
            "name": "Relaxed organization policy",
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
    assert org_policy_response.status_code == 200

    repo_policy_response = client.post(
        "/api/policies",
        json={
            "name": "Checkout API policy",
            "scope": "repository",
            "repository_id": repository["repository_id"],
            "config": {
                "version": 1,
                "critical_paths": ["auth/**"],
                "rules": {
                    "require_tests_for_code_changes": False,
                    "flag_auth_changes": False,
                },
            },
            "enabled": True,
        },
    )
    assert repo_policy_response.status_code == 200
    repo_policy = repo_policy_response.json()
    assert repo_policy["scope"] == "repository"
    assert repo_policy["repository_id"] == repository["repository_id"]
    assert repo_policy["repository_full_name"] == "platform/checkout-api"

    diff_text = (PROJECT_ROOT / "examples" / "sample.diff").read_text(encoding="utf-8")
    analysis_response = client.post(
        "/api/analyze/diff",
        json={
            "diff": diff_text,
            "repository": "platform/checkout-api",
        },
    )

    assert analysis_response.status_code == 200
    analysis_body = analysis_response.json()
    assert "critical-path-change" in {finding["rule_id"] for finding in analysis_body["findings"]}
    assert analysis_body["risk_score"] > 0
    assert analysis_body["review_requirements"][0]["requirement_id"] == "security-review"
    assert analysis_body["review_requirements"][0]["suggested_reviewers"] == [
        {
            "source": "repository_membership",
            "identifier": "reviewer@example.com",
            "role": "maintainer",
        }
    ]

    audit_response = client.get("/api/audit-events", params={"action": "analysis.created"})
    assert audit_response.status_code == 200
    analysis_audit = audit_response.json()[0]
    assert analysis_audit["metadata"]["config_source"] == "repository_policy"
    assert analysis_audit["metadata"]["policy_id"] == repo_policy["policy_id"]
    assert analysis_audit["metadata"]["policy_name"] == "Checkout API policy"
    assert analysis_audit["metadata"]["repository_id"] == repository["repository_id"]
    assert analysis_audit["metadata"]["routed_reviewer_count"] == 1
    assert analysis_audit["metadata"]["routed_reviewer_roles"] == ["maintainer"]
    assert analysis_audit["metadata"]["review_requirement_count"] == 1
    assert analysis_audit["metadata"]["unconfigured_review_requirement_count"] == 0
    assert analysis_audit["metadata"]["reviewer_sources"] == ["repository_membership"]
    assert analysis_audit["metadata"]["required_roles"] == ["maintainer", "owner"]

    unknown_repo_response = client.post(
        "/api/analyze/diff",
        json={
            "diff": diff_text,
            "repository": "platform/unknown-api",
        },
    )

    assert unknown_repo_response.status_code == 200
    assert unknown_repo_response.json()["risk_score"] == 0


def test_repository_membership_with_github_login_routes_requestable_reviewer(client: TestClient) -> None:
    user = client.get("/api/users").json()[0]
    update_response = client.patch(
        f"/api/users/{user['user_id']}",
        json={"github_login": "@checkout-reviewer"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["github_login"] == "checkout-reviewer"

    diff_text = (PROJECT_ROOT / "examples" / "sample.diff").read_text(encoding="utf-8")
    analysis_response = client.post(
        "/api/analyze/diff",
        json={
            "diff": diff_text,
            "repository": "platform/checkout-api",
        },
    )

    assert analysis_response.status_code == 200
    analysis_body = analysis_response.json()
    assert analysis_body["review_requirements"][0]["suggested_reviewers"] == [
        {
            "source": "repository_membership",
            "identifier": "@checkout-reviewer",
            "role": "maintainer",
        }
    ]
    assert "Repository membership: @checkout-reviewer" in analysis_body["markdown"]


def test_repository_policy_requires_repository_from_same_org(client: TestClient) -> None:
    missing_repository_response = client.post(
        "/api/policies",
        json={
            "name": "Repository policy",
            "scope": "repository",
            "config": {"version": 1},
        },
    )
    assert missing_repository_response.status_code == 422
    assert missing_repository_response.json() == {"detail": "repository_id is required for repository-scoped policies"}

    with app.state.test_session_factory() as session:
        other_org = create_organization(session, slug="policy-other", name="Policy Other")
        other_repo = create_repository(
            session,
            organization_id=other_org.id,
            provider="github",
            owner="platform",
            name="other-api",
        )

    cross_org_response = client.post(
        "/api/policies",
        json={
            "name": "Cross org policy",
            "scope": "repository",
            "repository_id": other_repo.id,
            "config": {"version": 1},
        },
    )
    assert cross_org_response.status_code == 404
    assert cross_org_response.json() == {"detail": "Repository not found"}


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
    assert body["review_requirements"][0]["requirement_id"] == "security-review"
    assert body["review_requirements"][0]["suggested_reviewers"][0]["identifier"] == "reviewer@example.com"
    assert body["markdown"].startswith("# AgentReviewOps Report")
    assert "Repository membership: reviewer@example.com" in body["markdown"]

    report_response = client.get(f"/api/analysis-runs/{body['analysis_run_id']}/report")

    assert report_response.status_code == 200
    report_body = report_response.json()
    assert report_body["analysis_run_id"] == body["analysis_run_id"]
    assert report_body["markdown"] == body["markdown"]
    assert report_body["changed_files"][0]["path"] == "auth/session.py"
    assert report_body["review_requirements"] == body["review_requirements"]

    audit_response = client.get("/api/audit-events")

    assert audit_response.status_code == 200
    audit_event = audit_response.json()[0]
    assert audit_event["action"] == "analysis.created"
    assert audit_event["target_type"] == "analysis_run"
    assert audit_event["target_id"] == body["analysis_run_id"]
    assert audit_event["metadata"]["repository"] == "platform/checkout-api"
    assert audit_event["metadata"]["risk_level"] == "high"
    assert audit_event["metadata"]["risk_score"] == 55
    assert audit_event["metadata"]["agent_name"] == "Codex"
    assert audit_event["metadata"]["branch"] == "codex/auth-session-hardening"
    assert audit_event["metadata"]["review_requirement_count"] == 1
    assert audit_event["metadata"]["unconfigured_review_requirement_count"] == 0
    assert audit_event["metadata"]["reviewer_sources"] == ["repository_membership"]
    assert audit_event["metadata"]["required_roles"] == ["maintainer", "owner"]
    assert "diff" not in audit_event["metadata"]
    assert "markdown" not in audit_event["metadata"]

    target_filter_response = client.get(
        "/api/audit-events",
        params={
            "target_type": "analysis_run",
            "target_id": body["analysis_run_id"],
            "limit": 1,
        },
    )
    assert target_filter_response.status_code == 200
    assert target_filter_response.json()[0]["target_id"] == body["analysis_run_id"]


def test_analyze_diff_runs_enabled_builtin_plugin(client: TestClient) -> None:
    diff_text = """diff --git a/package.json b/package.json
index 1111111..2222222 100644
--- a/package.json
+++ b/package.json
@@ -1,3 +1,4 @@
 {
-  "dependencies": {}
+  "dependencies": {"left-pad": "1.3.0"}
 }
"""

    response = client.post(
        "/api/analyze/diff",
        json={
            "diff": diff_text,
            "config": {
                "version": 1,
                "plugins": [
                    {
                        "id": "dependency-manifest",
                        "enabled": True,
                        "permissions": ["read_diff"],
                    }
                ],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    rule_ids = {finding["rule_id"] for finding in body["findings"]}
    assert "plugin-dependency-manifest" in rule_ids
    assert body["markdown"].count("plugin-dependency-manifest") == 1


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


def test_metrics_overview_rules_and_routing_are_aggregated_from_persisted_runs(client: TestClient) -> None:
    with app.state.test_session_factory() as session:
        organization_id = client.get("/api/auth/me").json()["organization_id"]
        _create_metric_analysis_run(
            session,
            organization_id=organization_id,
            repository="platform/checkout-api",
            risk_level="high",
            risk_score=70,
            agent_name="Codex",
            findings=[
                _finding("critical-path-change", severity="high", score_delta=30),
                _finding("missing-tests", severity="medium", score_delta=15),
            ],
            review_requirements=[
                _requirement(
                    "security-review",
                    required_roles=["maintainer"],
                    reviewers=[
                        SuggestedReviewer(source="repository_membership", identifier="@alice", role="maintainer")
                    ],
                )
            ],
        )
        _create_metric_analysis_run(
            session,
            organization_id=organization_id,
            repository="platform/billing-api",
            risk_level="low",
            risk_score=5,
            agent_name="Cursor",
            findings=[_finding("missing-docs", severity="info", score_delta=0)],
            review_requirements=[_requirement("owner-review", required_roles=["owner"], reviewers=[])],
        )

    overview_response = client.get("/api/metrics/overview")
    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert overview["analysis_count"] == 2
    assert overview["risk_distribution"] == {"low": 1, "medium": 0, "high": 1, "block": 0}
    assert overview["high_or_block_count"] == 1
    assert overview["average_risk_score"] == 37.5
    assert overview["unique_repository_count"] == 2
    assert overview["unique_agent_count"] == 2
    assert overview["analysis_count_by_agent"] == {"Codex": 1, "Cursor": 1}
    assert len(overview["recent_trend"]) == 30

    rules_response = client.get("/api/metrics/rules")
    assert rules_response.status_code == 200
    rules = rules_response.json()
    assert rules["total_finding_count"] == 3
    assert rules["severity_distribution"]["high"] == 1
    assert rules["severity_distribution"]["medium"] == 1
    assert rules["high_impact_rule_count"] == 1
    assert rules["top_rules"][0] == {
        "rule_id": "critical-path-change",
        "finding_count": 1,
        "average_score_delta": 30.0,
        "high_impact_count": 1,
    }

    routing_response = client.get("/api/metrics/routing")
    assert routing_response.status_code == 200
    routing = routing_response.json()
    assert routing["total_review_requirement_count"] == 2
    assert routing["configured_review_requirement_count"] == 1
    assert routing["unconfigured_review_requirement_count"] == 1
    assert routing["routing_hit_rate"] == 0.5
    assert routing["reviewer_source_distribution"] == {"repository_membership": 1}
    assert routing["required_role_distribution"] == {"maintainer": 1, "owner": 1}
    assert routing["top_unconfigured_requirements"] == [
        {"requirement_id": "owner-review", "title": "Owner review", "count": 1}
    ]


def test_repository_metrics_are_organization_scoped_and_days_filtered(client: TestClient) -> None:
    now = datetime.now(timezone.utc)
    with app.state.test_session_factory() as session:
        organization_id = client.get("/api/auth/me").json()["organization_id"]
        _create_metric_analysis_run(
            session,
            organization_id=organization_id,
            repository="platform/checkout-api",
            risk_level="block",
            risk_score=90,
            agent_name="Codex",
            findings=[_finding("critical-path-change", severity="critical", score_delta=40)],
            review_requirements=[_requirement("security-review", required_roles=["owner"], reviewers=[])],
            created_at=now - timedelta(days=2),
        )
        _create_metric_analysis_run(
            session,
            organization_id=organization_id,
            repository="platform/old-api",
            risk_level="high",
            risk_score=60,
            agent_name="Codex",
            findings=[_finding("dependency-change", severity="medium", score_delta=20)],
            review_requirements=[],
            created_at=now - timedelta(days=45),
        )
        other_org = create_organization(session, slug="metrics-other", name="Metrics Other")
        _create_metric_analysis_run(
            session,
            organization_id=other_org.id,
            repository="platform/other-api",
            risk_level="block",
            risk_score=100,
            agent_name="Codex",
            findings=[_finding("other-rule", severity="critical", score_delta=80)],
            review_requirements=[],
            created_at=now - timedelta(days=1),
        )

    repositories_response = client.get("/api/metrics/repositories", params={"days": 7})
    assert repositories_response.status_code == 200
    repositories = repositories_response.json()["repositories"]
    assert [row["repository"] for row in repositories] == ["platform/checkout-api"]
    assert repositories[0]["analysis_count"] == 1
    assert repositories[0]["top_risk_level"] == "block"
    assert repositories[0]["unconfigured_review_requirement_count"] == 1
    assert repositories[0]["top_triggered_rule_ids"] == ["critical-path-change"]

    overview_response = client.get("/api/metrics/overview", params={"days": 7, "repository": "platform/old-api"})
    assert overview_response.status_code == 200
    assert overview_response.json()["analysis_count"] == 0

    invalid_response = client.get("/api/metrics/overview", params={"days": 0})
    assert invalid_response.status_code == 422


def test_audit_events_are_scoped_to_authenticated_organization(client: TestClient) -> None:
    policy_response = client.post(
        "/api/policies",
        json={
            "name": "Scoped policy",
            "config": {"version": 1},
        },
    )
    assert policy_response.status_code == 200

    with app.state.test_session_factory() as session:
        other_org = create_organization(session, slug="other", name="Other Org")
        create_audit_event(
            session,
            organization_id=other_org.id,
            actor_type="system",
            actor_id=None,
            action="other.created",
            target_type="organization",
            target_id=other_org.id,
        )

    response = client.get("/api/audit-events")

    assert response.status_code == 200
    actions = {event["action"] for event in response.json()}
    assert "policy.created" in actions
    assert "other.created" not in actions


def test_audit_events_export_json_and_csv_are_scoped_filtered_and_sanitized(client: TestClient) -> None:
    policy_response = client.post(
        "/api/policies",
        json={
            "name": "Exported policy",
            "config": {"version": 1},
        },
    )
    assert policy_response.status_code == 200

    with app.state.test_session_factory() as session:
        other_org = create_organization(session, slug="export-other", name="Export Other")
        create_audit_event(
            session,
            organization_id=other_org.id,
            actor_type="system",
            actor_id=None,
            action="policy.created",
            target_type="policy",
            target_id="other-policy",
            metadata={
                "policy_name": "Other policy",
                "token": "do-not-export",
            },
        )

    json_response = client.get("/api/audit-events/export", params={"format": "json", "action": "policy.created"})

    assert json_response.status_code == 200
    assert json_response.headers["content-disposition"] == 'attachment; filename="agentreview-audit-events.json"'
    json_events = json_response.json()
    assert [event["action"] for event in json_events] == ["policy.created"]
    assert json_events[0]["metadata"]["policy_name"] == "Exported policy"
    assert "Other policy" not in json.dumps(json_events)
    assert "do-not-export" not in json.dumps(json_events)

    csv_response = client.get("/api/audit-events/export", params={"format": "csv", "action": "policy.created"})

    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(StringIO(csv_response.text)))
    assert len(rows) == 1
    assert rows[0]["action"] == "policy.created"
    assert rows[0]["metadata"] == '{"enabled":true,"policy_name":"Exported policy","scope":"organization"}'
    assert "Other policy" not in csv_response.text
    assert "do-not-export" not in csv_response.text


def test_retention_purge_rejects_anonymous_requests(client: TestClient) -> None:
    client.headers.clear()

    response = client.post("/api/retention/purge", json={"older_than_days": 30})

    assert response.status_code == 401
    assert response.json() == {"detail": "Valid AgentReviewOps API key required"}


def test_retention_purge_dry_run_and_confirmed_delete(client: TestClient) -> None:
    diff_text = (PROJECT_ROOT / "examples" / "sample.diff").read_text(encoding="utf-8")
    create_response = client.post(
        "/api/analyze/diff",
        json={
            "diff": diff_text,
            "repository": "platform/checkout-api",
        },
    )
    assert create_response.status_code == 200
    analysis_run_id = create_response.json()["analysis_run_id"]
    old_timestamp = datetime.now(timezone.utc) - timedelta(days=45)

    with app.state.test_session_factory() as session:
        analysis_run = session.get(AnalysisRunRecord, analysis_run_id)
        assert analysis_run is not None
        analysis_run.created_at = old_timestamp
        analysis_audit = session.scalar(select(AuditEventRecord).where(AuditEventRecord.target_id == analysis_run_id))
        assert analysis_audit is not None
        analysis_audit.created_at = old_timestamp
        old_audit = create_audit_event(
            session,
            organization_id=analysis_run.organization_id,
            actor_type="api_key",
            actor_id="old-key",
            action="policy.created",
            target_type="policy",
            target_id="old-policy",
            metadata={"policy_name": "Old policy"},
        )
        old_audit.created_at = old_timestamp
        session.add_all([analysis_run, analysis_audit, old_audit])
        session.commit()

    dry_run_response = client.post(
        "/api/retention/purge",
        json={
            "older_than_days": 30,
            "include_analysis_runs": True,
            "include_audit_events": True,
        },
    )

    assert dry_run_response.status_code == 200
    dry_run = dry_run_response.json()
    assert dry_run["dry_run"] is True
    assert dry_run["analysis_run_count"] == 1
    assert dry_run["audit_event_count"] == 2

    detail_response = client.get(f"/api/analysis-runs/{analysis_run_id}")
    assert detail_response.status_code == 200

    unconfirmed_response = client.post(
        "/api/retention/purge",
        json={
            "older_than_days": 30,
            "include_analysis_runs": True,
            "include_audit_events": True,
            "dry_run": False,
        },
    )
    assert unconfirmed_response.status_code == 400
    assert unconfirmed_response.json() == {"detail": "Set confirm=true to run a non-dry-run retention purge"}

    purge_response = client.post(
        "/api/retention/purge",
        json={
            "older_than_days": 30,
            "include_analysis_runs": True,
            "include_audit_events": True,
            "dry_run": False,
            "confirm": True,
        },
    )

    assert purge_response.status_code == 200
    purge = purge_response.json()
    assert purge["dry_run"] is False
    assert purge["analysis_run_count"] == 1
    assert purge["audit_event_count"] == 2

    detail_response = client.get(f"/api/analysis-runs/{analysis_run_id}")
    assert detail_response.status_code == 404

    old_audit_response = client.get("/api/audit-events", params={"target_id": "old-policy"})
    assert old_audit_response.status_code == 200
    assert old_audit_response.json() == []

    retention_audit_response = client.get("/api/audit-events", params={"action": "retention.purged"})
    assert retention_audit_response.status_code == 200
    retention_event = retention_audit_response.json()[0]
    assert retention_event["metadata"]["older_than_days"] == 30
    assert retention_event["metadata"]["analysis_run_count"] == 1
    assert retention_event["metadata"]["audit_event_count"] == 2


def test_report_fetch_returns_404_for_missing_run(client: TestClient) -> None:
    response = client.get("/api/analysis-runs/missing/report")

    assert response.status_code == 404
    assert response.json() == {"detail": "Analysis run not found"}


def test_analyze_diff_validates_empty_diff(client: TestClient) -> None:
    response = client.post("/api/analyze/diff", json={"diff": ""})

    assert response.status_code == 422


def _create_metric_analysis_run(
    session,
    *,
    organization_id: str,
    repository: str,
    risk_level: str,
    risk_score: int,
    agent_name: str,
    findings: list[RiskFinding],
    review_requirements: list[ReviewRequirement],
    created_at: datetime | None = None,
) -> AnalysisRunRecord:
    record = create_analysis_run(
        session,
        organization_id=organization_id,
        repository=repository,
        agent_name=agent_name,
        changed_files=[DiffFile(path="app.py", status="modified", additions=3, deletions=1)],
        analysis=RiskAnalysis(risk_score=risk_score, risk_level=risk_level, findings=findings),
        review_requirements=review_requirements,
        markdown="# Metric test\n",
        config=AgentReviewConfig(),
    )
    if created_at is not None:
        record.created_at = created_at
        session.add(record)
        session.commit()
        session.refresh(record)
    return record


def _finding(rule_id: str, *, severity: str, score_delta: int) -> RiskFinding:
    return RiskFinding(
        rule_id=rule_id,
        severity=severity,
        title=rule_id.replace("-", " ").title(),
        description=f"{rule_id} triggered.",
        score_delta=score_delta,
        file_path="app.py",
    )


def _requirement(
    requirement_id: str,
    *,
    required_roles: list[str],
    reviewers: list[SuggestedReviewer],
) -> ReviewRequirement:
    return ReviewRequirement(
        requirement_id=requirement_id,
        title=requirement_id.replace("-", " ").capitalize(),
        reason="Metric test requirement.",
        required_roles=required_roles,
        suggested_reviewers=reviewers,
    )
