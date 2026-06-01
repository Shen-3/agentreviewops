import csv
import json
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select

from agentreview_api.auth import key_prefix
from agentreview_api.db import AnalysisRunRecord, AuditEventRecord, create_session_factory
from agentreview_api.main import app, get_session
from agentreview_api.repository import (
    create_api_key,
    create_audit_event,
    create_organization,
    create_repository,
    create_repository_membership,
    create_user,
)

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
    assert users[0]["role"] == "admin"

    create_user_response = client.post(
        "/api/users",
        json={
            "email": "Payments.Owner@Example.COM",
            "name": "Payments Owner",
            "role": "reviewer",
        },
    )

    assert create_user_response.status_code == 200
    created_user = create_user_response.json()
    assert created_user["user_id"]
    assert created_user["email"] == "payments.owner@example.com"
    assert created_user["name"] == "Payments Owner"
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
    reviewer_emails = {reviewer["email"]: reviewer["role"] for reviewer in remove_membership_response.json()["reviewers"]}
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
    assert demote_current_key_response.json() == {"detail": "Cannot change the current admin API key to a non-admin role"}

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
    reviewer_roles = {reviewer["email"]: reviewer["role"] for reviewer in update_membership_response.json()["reviewers"]}
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

    audit_response = client.get("/api/audit-events", params={"action": "analysis.created"})
    assert audit_response.status_code == 200
    analysis_audit = audit_response.json()[0]
    assert analysis_audit["metadata"]["config_source"] == "repository_policy"
    assert analysis_audit["metadata"]["policy_id"] == repo_policy["policy_id"]
    assert analysis_audit["metadata"]["policy_name"] == "Checkout API policy"
    assert analysis_audit["metadata"]["repository_id"] == repository["repository_id"]
    assert analysis_audit["metadata"]["routed_reviewer_count"] == 1
    assert analysis_audit["metadata"]["routed_reviewer_roles"] == ["maintainer"]

    unknown_repo_response = client.post(
        "/api/analyze/diff",
        json={
            "diff": diff_text,
            "repository": "platform/unknown-api",
        },
    )

    assert unknown_repo_response.status_code == 200
    assert unknown_repo_response.json()["risk_score"] == 0


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
    assert body["markdown"].startswith("# AgentReviewOps Report")

    report_response = client.get(f"/api/analysis-runs/{body['analysis_run_id']}/report")

    assert report_response.status_code == 200
    report_body = report_response.json()
    assert report_body["analysis_run_id"] == body["analysis_run_id"]
    assert report_body["markdown"] == body["markdown"]
    assert report_body["changed_files"][0]["path"] == "auth/session.py"

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
