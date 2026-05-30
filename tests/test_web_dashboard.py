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
    assert "Findings" in app_tsx
    assert "Report preview" in app_tsx
    assert "Audit history" in app_tsx
    assert "riskFilter" in app_tsx
    assert "auditActionFilter" in app_tsx
    assert "API key" in app_tsx
    assert "Authorization" in app_tsx


def test_dashboard_contains_empty_loading_error_states() -> None:
    app_tsx = (WEB_SRC / "main.tsx").read_text(encoding="utf-8")

    assert "Loading workspace data" in app_tsx
    assert "Unable to load workspace data" in app_tsx
    assert "No analysis runs or audit events" in app_tsx
    assert "/api/analysis-runs" in app_tsx
    assert "/api/audit-events?limit=50" in app_tsx
    assert "API unavailable. Showing demo analysis and audit data." in app_tsx


def test_dashboard_has_responsive_styles() -> None:
    css = (WEB_SRC / "styles.css").read_text(encoding="utf-8")

    assert "@media (max-width: 1040px)" in css
    assert "@media (max-width: 640px)" in css
    assert ".risk-badge" in css
    assert ".audit-table" in css
