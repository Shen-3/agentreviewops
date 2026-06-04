from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]
WEB_ROOT = PROJECT_ROOT / "apps" / "web"
WEB_SRC = WEB_ROOT / "src"


def _dashboard_source() -> str:
    paths = [
        WEB_SRC / "App.tsx",
        WEB_SRC / "api" / "client.ts",
        WEB_SRC / "api" / "types.ts",
        WEB_SRC / "hooks" / "useLocalStorage.ts",
    ]
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def test_dashboard_contains_required_views() -> None:
    html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
    source = _dashboard_source()

    assert 'id="root"' in html
    assert "Analysis runs" in source
    assert "Analysis detail" in source
    assert "Submit diff" in source
    assert "Analyze diff" in source
    assert "Repositories" in source
    assert "repositoryForm" in source
    assert "deleteDashboardRepository" in source
    assert "/api/repositories/${repositoryId}" in source
    assert "Users" in source
    assert "userForm" in source
    assert "Review routing" in source
    assert "membershipForm" in source
    assert "onRemoveMembership" in source
    assert "Findings" in source
    assert "Required review" in source
    assert "reviewRequirements" in source
    assert "Report preview" in source
    assert "Policy editor" in source
    assert "Repository policy" in source
    assert "Save policy" in source
    assert "onToggleEnabled" in source
    assert "/api/policies/${policyId}" in source
    assert "policy.updated" in source
    assert "API keys" in source
    assert "New key role" in source
    assert "read_only" in source
    assert "Audit history" in source
    assert "Download" in source
    assert "riskFilter" in source
    assert "auditActionFilter" in source
    assert "API key" in source
    assert "Authorization" in source
    assert "/api/auth/me" in source
    assert "canSubmitAnalysis" in source
    assert "canManageGovernance" in source
    assert "Read-only keys can inspect analyses but cannot submit diffs." in source
    assert "CI keys can submit analyses but cannot manage governance." in source


def test_dashboard_contains_empty_loading_error_states() -> None:
    source = _dashboard_source()

    assert "Loading workspace data" in source
    assert "Unable to load workspace data" in source
    assert "No analysis runs or audit events" in source
    assert "/api/analysis-runs" in source
    assert "/api/analyze/diff" in source
    assert "/api/api-keys" in source
    assert "/api/users" in source
    assert "/api/repositories" in source
    assert "/memberships" in source
    assert 'method: "PATCH"' in source
    assert 'method: "DELETE"' in source
    assert "/api/policies" in source
    assert "repository_id" in source
    assert "/api/audit-events?limit=${limit}" in source
    assert "/api/audit-events/export" in source
    assert "No API key configured. Showing demo analysis and audit data." in source
    assert "Unable to load workspace data. Check the API URL, API key, or retry later." in source
    assert "require_tests_for_code_changes" in source
    assert "critical_paths" in source


def test_dashboard_does_not_expose_debug_state_controls() -> None:
    source = _dashboard_source()

    assert "AlertTriangle" not in source
    assert "Database" not in source
    assert "Live data" not in source
    assert "Refresh" in source
    assert "No API key configured. Showing demo analysis and audit data." in source


def test_dashboard_documents_safer_api_key_storage() -> None:
    source = _dashboard_source()

    assert "Session only" in source
    assert "Browser storage" in source
    assert "Clear API key" in source
    assert "API keys are stored in your browser for this self-hosted dashboard" in source
    assert "sessionStorage" in source
    assert "agentreviewops.apiKey" in source


def test_dashboard_has_responsive_styles() -> None:
    css = (WEB_SRC / "styles.css").read_text(encoding="utf-8")

    assert "@media (max-width: 1040px)" in css
    assert "@media (max-width: 640px)" in css
    assert ".risk-badge" in css
    assert ".policy-panel" in css
    assert ".policy-form" in css
    assert ".access-badge" in css
    assert ".user-panel" in css
    assert ".user-create-form" in css
    assert ".api-key-table" in css
    assert ".audit-table" in css
    assert ".audit-toolbar" in css
