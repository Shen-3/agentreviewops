from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]
WEB_ROOT = PROJECT_ROOT / "apps" / "web"
WEB_SRC = WEB_ROOT / "src"


def test_dashboard_contains_required_views() -> None:
    html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
    app_tsx = (WEB_SRC / "main.tsx").read_text(encoding="utf-8")

    assert 'id="root"' in html
    assert "Analysis runs" in app_tsx
    assert "Analysis detail" in app_tsx
    assert "Submit diff" in app_tsx
    assert "Analyze diff" in app_tsx
    assert "Repositories" in app_tsx
    assert "repositoryForm" in app_tsx
    assert "Users" in app_tsx
    assert "userForm" in app_tsx
    assert "Review routing" in app_tsx
    assert "membershipForm" in app_tsx
    assert "onRemoveMembership" in app_tsx
    assert "Findings" in app_tsx
    assert "Report preview" in app_tsx
    assert "Policy editor" in app_tsx
    assert "Repository policy" in app_tsx
    assert "Save policy" in app_tsx
    assert "onToggleEnabled" in app_tsx
    assert "/api/policies/${policy.id}" in app_tsx
    assert "policy.updated" in app_tsx
    assert "API keys" in app_tsx
    assert "New key role" in app_tsx
    assert "read_only" in app_tsx
    assert "Audit history" in app_tsx
    assert "Download" in app_tsx
    assert "riskFilter" in app_tsx
    assert "auditActionFilter" in app_tsx
    assert "API key" in app_tsx
    assert "Authorization" in app_tsx
    assert "/api/auth/me" in app_tsx
    assert "canSubmitAnalysis" in app_tsx
    assert "canManageGovernance" in app_tsx
    assert "Read-only keys can inspect analyses but cannot submit diffs." in app_tsx
    assert "CI keys can submit analyses but cannot manage governance." in app_tsx


def test_dashboard_contains_empty_loading_error_states() -> None:
    app_tsx = (WEB_SRC / "main.tsx").read_text(encoding="utf-8")

    assert "Loading workspace data" in app_tsx
    assert "Unable to load workspace data" in app_tsx
    assert "No analysis runs or audit events" in app_tsx
    assert "/api/analysis-runs" in app_tsx
    assert "/api/analyze/diff" in app_tsx
    assert "/api/api-keys" in app_tsx
    assert "/api/users" in app_tsx
    assert "/api/repositories" in app_tsx
    assert "/memberships" in app_tsx
    assert 'method: "PATCH"' in app_tsx
    assert 'method: "DELETE"' in app_tsx
    assert "/api/policies" in app_tsx
    assert "repository_id" in app_tsx
    assert "/api/audit-events?limit=50" in app_tsx
    assert "/api/audit-events/export" in app_tsx
    assert "No API key configured. Showing demo analysis and audit data." in app_tsx
    assert "Unable to load workspace data. Check the API URL, API key, or retry later." in app_tsx
    assert "require_tests_for_code_changes" in app_tsx
    assert "critical_paths" in app_tsx


def test_dashboard_does_not_expose_debug_state_controls() -> None:
    app_tsx = (WEB_SRC / "main.tsx").read_text(encoding="utf-8")

    assert "AlertTriangle" not in app_tsx
    assert "Database" not in app_tsx
    assert "Live data" not in app_tsx
    assert "Refresh" in app_tsx
    assert "No API key configured. Showing demo analysis and audit data." in app_tsx


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
