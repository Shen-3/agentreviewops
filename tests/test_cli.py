import json
from pathlib import Path
from urllib.parse import urlsplit

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from agentreview.cli import app
from agentreview_api.db import create_session_factory
from agentreview_api.main import app as api_app
from agentreview_api.main import get_session
from agentreview_api.repository import create_api_key, create_organization


def test_help_shows_product_name() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "AgentReviewOps" in result.output
    assert "admin" in result.output
    assert "scan-diff" in result.output
    assert "submit-diff" in result.output
    assert "scan-pr" in result.output
    assert "comment-pr" in result.output
    assert "request-reviewers" in result.output


def test_version_shows_package_version() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "agentreview 0.1.0" in result.output


def test_scan_diff_writes_report(tmp_path: Path) -> None:
    runner = CliRunner()
    project_root = Path(__file__).parents[1]
    output_path = tmp_path / "agentreview-report.md"

    result = runner.invoke(
        app,
        [
            "scan-diff",
            "--diff-file",
            str(project_root / "examples" / "sample.diff"),
            "--config",
            str(project_root / ".agentreview.example.yml"),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "AgentReviewOps" in result.output
    assert "Risk: HIGH 55/100" in result.output
    assert "HIGH critical-path-change: auth/session.py" in result.output
    assert f"Report written to: {output_path}" in result.output
    assert output_path.read_text(encoding="utf-8").startswith("# AgentReviewOps Report")


def test_scan_diff_writes_structured_json_output(tmp_path: Path) -> None:
    runner = CliRunner()
    project_root = Path(__file__).parents[1]
    output_path = tmp_path / "agentreview-report.md"
    json_output_path = tmp_path / "artifacts" / "agentreview-report.json"
    codeowners_path = tmp_path / "CODEOWNERS"
    codeowners_path.write_text(
        "auth/** @alice @octo/security-team owner@example.com\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "scan-diff",
            "--diff-file",
            str(project_root / "examples" / "sample.diff"),
            "--config",
            str(project_root / ".agentreview.example.yml"),
            "--output",
            str(output_path),
            "--codeowners-file",
            str(codeowners_path),
            "--json-output",
            str(json_output_path),
        ],
    )

    assert result.exit_code == 0
    assert str(json_output_path) not in result.output
    payload = json.loads(json_output_path.read_text(encoding="utf-8"))
    assert payload["risk_score"] == 55
    assert payload["risk_level"] == "high"
    assert payload["decision"] == {"fail_on": "never", "should_fail": False}
    assert payload["summary"] == "1 changed file(s), high risk (55/100)."
    assert payload["changed_files"][0]["path"] == "auth/session.py"
    assert {finding["rule_id"] for finding in payload["findings"]} >= {"critical-path-change"}
    assert payload["metadata"]["source"] == "scan-diff"
    assert payload["metadata"]["agentreview_version"] == "0.1.0"
    assert payload["metadata"]["generated_at"].endswith("Z")
    reviewer_identifiers = {
        reviewer["identifier"]
        for requirement in payload["review_requirements"]
        for reviewer in requirement["suggested_reviewers"]
    }
    assert {"@alice", "@octo/security-team", "owner@example.com"} <= reviewer_identifiers


def test_scan_diff_missing_config_uses_defaults(tmp_path: Path) -> None:
    runner = CliRunner()
    project_root = Path(__file__).parents[1]
    output_path = tmp_path / "report.md"

    result = runner.invoke(
        app,
        [
            "scan-diff",
            "--diff-file",
            str(project_root / "examples" / "sample.diff"),
            "--config",
            str(tmp_path / "missing.yml"),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert output_path.exists()


def test_scan_diff_codeowners_file_adds_reviewer_to_report(tmp_path: Path) -> None:
    runner = CliRunner()
    project_root = Path(__file__).parents[1]
    output_path = tmp_path / "report.md"
    codeowners_path = tmp_path / "CODEOWNERS"
    codeowners_path.write_text("auth/** @security-team\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "scan-diff",
            "--diff-file",
            str(project_root / "examples" / "sample.diff"),
            "--codeowners-file",
            str(codeowners_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    report = output_path.read_text(encoding="utf-8")
    assert "## Required human review" in report
    assert "CODEOWNERS: @security-team" in report


def test_scan_diff_without_codeowners_file_does_not_fail(tmp_path: Path) -> None:
    runner = CliRunner()
    project_root = Path(__file__).parents[1]
    output_path = tmp_path / "report.md"

    result = runner.invoke(
        app,
        [
            "scan-diff",
            "--diff-file",
            str(project_root / "examples" / "sample.diff"),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert output_path.exists()


def test_scan_diff_explicit_missing_codeowners_file_fails_clearly(tmp_path: Path) -> None:
    runner = CliRunner()
    project_root = Path(__file__).parents[1]

    result = runner.invoke(
        app,
        [
            "scan-diff",
            "--diff-file",
            str(project_root / "examples" / "sample.diff"),
            "--codeowners-file",
            str(tmp_path / "missing-CODEOWNERS"),
            "--output",
            str(tmp_path / "report.md"),
        ],
    )

    assert result.exit_code == 1
    assert "Could not read CODEOWNERS file" in result.output


def test_scan_diff_fail_on_never_does_not_fail_on_high(tmp_path: Path) -> None:
    runner = CliRunner()
    project_root = Path(__file__).parents[1]

    result = runner.invoke(
        app,
        [
            "scan-diff",
            "--diff-file",
            str(project_root / "examples" / "sample.diff"),
            "--fail-on",
            "never",
            "--output",
            str(tmp_path / "report.md"),
        ],
    )

    assert result.exit_code == 0
    assert "Risk: HIGH 55/100" in result.output
    assert "CI gate failed" not in result.output


def test_scan_diff_fail_on_block_fails_only_on_block(tmp_path: Path) -> None:
    runner = CliRunner()
    project_root = Path(__file__).parents[1]
    block_diff = _write_diff(tmp_path, "block.diff", _block_risk_diff())

    high_result = runner.invoke(
        app,
        [
            "scan-diff",
            "--diff-file",
            str(project_root / "examples" / "sample.diff"),
            "--fail-on",
            "block",
            "--output",
            str(tmp_path / "high-report.md"),
        ],
    )
    block_result = runner.invoke(
        app,
        [
            "scan-diff",
            "--diff-file",
            str(block_diff),
            "--fail-on",
            "block",
            "--output",
            str(tmp_path / "block-report.md"),
        ],
    )

    assert high_result.exit_code == 0
    assert block_result.exit_code == 1
    assert "CI gate failed: risk BLOCK" in block_result.output


def test_scan_diff_fail_on_high_fails_on_high_and_block(tmp_path: Path) -> None:
    runner = CliRunner()
    project_root = Path(__file__).parents[1]
    block_diff = _write_diff(tmp_path, "block.diff", _block_risk_diff())

    high_result = runner.invoke(
        app,
        [
            "scan-diff",
            "--diff-file",
            str(project_root / "examples" / "sample.diff"),
            "--fail-on",
            "high",
            "--output",
            str(tmp_path / "high-report.md"),
        ],
    )
    block_result = runner.invoke(
        app,
        [
            "scan-diff",
            "--diff-file",
            str(block_diff),
            "--fail-on",
            "high",
            "--output",
            str(tmp_path / "block-report.md"),
        ],
    )

    assert high_result.exit_code == 1
    assert block_result.exit_code == 1
    assert "meets --fail-on high threshold" in high_result.output
    assert "meets --fail-on high threshold" in block_result.output


def test_scan_diff_fail_on_medium_fails_on_medium_high_and_block(tmp_path: Path) -> None:
    runner = CliRunner()
    project_root = Path(__file__).parents[1]
    medium_diff = _write_diff(tmp_path, "medium.diff", _medium_risk_diff())
    block_diff = _write_diff(tmp_path, "block.diff", _block_risk_diff())

    medium_result = runner.invoke(
        app,
        [
            "scan-diff",
            "--diff-file",
            str(medium_diff),
            "--fail-on",
            "medium",
            "--output",
            str(tmp_path / "medium-report.md"),
        ],
    )
    high_result = runner.invoke(
        app,
        [
            "scan-diff",
            "--diff-file",
            str(project_root / "examples" / "sample.diff"),
            "--fail-on",
            "medium",
            "--output",
            str(tmp_path / "high-report.md"),
        ],
    )
    block_result = runner.invoke(
        app,
        [
            "scan-diff",
            "--diff-file",
            str(block_diff),
            "--fail-on",
            "medium",
            "--output",
            str(tmp_path / "block-report.md"),
        ],
    )

    assert medium_result.exit_code == 1
    assert high_result.exit_code == 1
    assert block_result.exit_code == 1
    assert "Risk: MEDIUM" in medium_result.output
    assert "Risk: HIGH" in high_result.output
    assert "Risk: BLOCK" in block_result.output


def test_scan_diff_invalid_fail_on_is_rejected_by_typer(tmp_path: Path) -> None:
    runner = CliRunner()
    project_root = Path(__file__).parents[1]

    result = runner.invoke(
        app,
        [
            "scan-diff",
            "--diff-file",
            str(project_root / "examples" / "sample.diff"),
            "--fail-on",
            "critical",
            "--output",
            str(tmp_path / "report.md"),
        ],
    )

    assert result.exit_code == 2
    assert "critical" in result.output


def test_scan_diff_includes_enabled_ai_summary(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_root = Path(__file__).parents[1]
    output_path = tmp_path / "ai-report.md"
    config_path = tmp_path / "agentreview-ai.yml"
    config_path.write_text(
        """
version: 1
ai:
  enabled: true
  provider: openai
  model: review-model
""",
        encoding="utf-8",
    )

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": '{"summary":"AI reviewer summary.","checklist":["Inspect auth path."]}'}}]}

    monkeypatch.setenv("AGENTREVIEW_OPENAI_API_KEY", "test-ai-key")
    monkeypatch.setattr("agentreview.ai.httpx.post", lambda *_args, **_kwargs: Response())

    result = runner.invoke(
        app,
        [
            "scan-diff",
            "--diff-file",
            str(project_root / "examples" / "sample.diff"),
            "--config",
            str(config_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    report = output_path.read_text(encoding="utf-8")
    assert "## AI Summary" in report
    assert "AI reviewer summary." in report
    assert "Inspect auth path." in report


def test_submit_diff_posts_to_self_hosted_api(monkeypatch) -> None:
    runner = CliRunner()
    project_root = Path(__file__).parents[1]
    calls = []

    class Response:
        status_code = 200
        reason_phrase = "OK"

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "analysis_run_id": "run_123",
                "risk_score": 55,
                "risk_level": "high",
                "findings": [{"rule_id": "critical-path-change"}],
                "changed_files": [{"path": "auth/session.py"}],
                "markdown": "# AgentReviewOps Report",
            }

    def fake_post(url, *, json, headers, timeout):
        calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return Response()

    monkeypatch.setenv("AGENTREVIEW_API_KEY", "arok_secret_test")
    monkeypatch.setattr("agentreview.cli.httpx.post", fake_post)

    result = runner.invoke(
        app,
        [
            "submit-diff",
            "--diff-file",
            str(project_root / "examples" / "sample.diff"),
            "--config",
            str(project_root / ".agentreview.example.yml"),
            "--api-url",
            "https://agentreview.example",
            "--repository",
            "platform/checkout-api",
            "--pr",
            "1842",
            "--title",
            "Tighten inactive-user session handling",
            "--author",
            "codex-agent",
            "--agent-name",
            "Codex",
            "--branch",
            "codex/auth-session-hardening",
        ],
    )

    assert result.exit_code == 0
    assert "Submitted analysis run: run_123" in result.output
    assert "Risk: HIGH 55/100" in result.output
    assert "arok_secret_test" not in result.output
    assert calls[0]["url"] == "https://agentreview.example/api/analyze/diff"
    assert calls[0]["headers"]["Authorization"] == "Bearer arok_secret_test"
    assert calls[0]["json"]["repository"] == "platform/checkout-api"
    assert calls[0]["json"]["pull_request_number"] == 1842
    assert calls[0]["json"]["agent_name"] == "Codex"
    assert calls[0]["json"]["config"]["version"] == 1
    assert calls[0]["json"]["diff"].startswith("diff --git")


def test_request_reviewers_dry_run_prints_resolved_plan(tmp_path: Path) -> None:
    runner = CliRunner()
    analysis_file = _write_analysis_json(
        tmp_path,
        [
            {
                "requirement_id": "security-review",
                "title": "Security review",
                "reason": "Sensitive change",
                "suggested_reviewers": [
                    {"source": "codeowners", "identifier": "@alice"},
                    {"source": "codeowners", "identifier": "@octo/security-team"},
                    {"source": "repository_membership", "identifier": "owner@example.com", "role": "maintainer"},
                ],
            }
        ],
    )

    result = runner.invoke(
        app,
        [
            "request-reviewers",
            "--repo",
            "octo/example",
            "--pr",
            "123",
            "--analysis-file",
            str(analysis_file),
            "--author",
            "alice",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert "Requested individual reviewers: none" in result.output
    assert "Requested team reviewers: security-team" in result.output
    assert "- @alice: pull_request_author (codeowners)" in result.output
    assert "- owner@example.com: email_identifier_not_requestable (repository_membership)" in result.output
    assert "GitHub API call: dry-run" in result.output


def test_request_reviewers_noop_does_not_require_token(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    analysis_file = _write_analysis_json(tmp_path, [])

    result = runner.invoke(
        app,
        [
            "request-reviewers",
            "--repo",
            "octo/example",
            "--pr",
            "123",
            "--analysis-file",
            str(analysis_file),
        ],
    )

    assert result.exit_code == 0
    assert "Requested individual reviewers: none" in result.output
    assert "Requested team reviewers: none" in result.output
    assert "GitHub API call: no-op" in result.output


def test_submit_diff_requires_api_key(monkeypatch) -> None:
    runner = CliRunner()
    project_root = Path(__file__).parents[1]
    monkeypatch.delenv("AGENTREVIEW_API_KEY", raising=False)

    result = runner.invoke(
        app,
        [
            "submit-diff",
            "--diff-file",
            str(project_root / "examples" / "sample.diff"),
        ],
    )

    assert result.exit_code == 2
    assert "API key required" in result.output


def test_submit_diff_persists_analysis_with_api(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_root = Path(__file__).parents[1]
    database_url = f"sqlite:///{tmp_path / 'submit-flow.db'}"
    monkeypatch.setenv("AGENTREVIEW_DATABASE_URL", database_url)

    alembic_config = Config(str(project_root / "alembic.ini"))
    command.upgrade(alembic_config, "head")

    session_factory = create_session_factory(database_url)
    with session_factory() as session:
        organization = create_organization(session, slug="acme", name="Acme Engineering")
        _, api_key = create_api_key(session, organization_id=organization.id, name="CI")

    def override_get_session():
        with session_factory() as session:
            yield session

    api_app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(api_app) as api_client:
            def post_to_testclient(url, *, json, headers, timeout):
                return api_client.post(urlsplit(url).path, json=json, headers=headers)

            monkeypatch.setenv("AGENTREVIEW_API_KEY", api_key)
            monkeypatch.setattr("agentreview.cli.httpx.post", post_to_testclient)

            result = runner.invoke(
                app,
                [
                    "submit-diff",
                    "--diff-file",
                    str(project_root / "examples" / "sample.diff"),
                    "--config",
                    str(project_root / ".agentreview.example.yml"),
                    "--api-url",
                    "http://testserver",
                    "--repository",
                    "platform/checkout-api",
                    "--pr",
                    "1842",
                    "--title",
                    "Tighten inactive-user session handling",
                    "--author",
                    "codex-agent",
                    "--agent-name",
                    "Codex",
                    "--branch",
                    "codex/auth-session-hardening",
                ],
            )

            assert result.exit_code == 0
            assert "Submitted analysis run:" in result.output
            assert "Risk: HIGH 55/100" in result.output

            list_response = api_client.get("/api/analysis-runs", headers={"X-AgentReview-API-Key": api_key})
            assert list_response.status_code == 200
            summaries = list_response.json()
            assert len(summaries) == 1
            assert summaries[0]["repository"] == "platform/checkout-api"
            assert summaries[0]["pull_request_number"] == 1842
            assert summaries[0]["risk_level"] == "high"
    finally:
        api_app.dependency_overrides.clear()


def _write_diff(tmp_path: Path, name: str, diff_text: str) -> Path:
    diff_path = tmp_path / name
    diff_path.write_text(diff_text, encoding="utf-8")
    return diff_path


def _write_analysis_json(tmp_path: Path, review_requirements: list[dict]) -> Path:
    analysis_path = tmp_path / "agentreview-report.json"
    analysis_path.write_text(
        json.dumps(
            {
                "risk_score": 55,
                "risk_level": "high",
                "review_requirements": review_requirements,
            }
        ),
        encoding="utf-8",
    )
    return analysis_path


def _medium_risk_diff() -> str:
    return """diff --git a/pyproject.toml b/pyproject.toml
index 1111111..2222222 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -1 +1,3 @@
 [project]
+dependencies = ["httpx"]
+requires-python = ">=3.12"
"""


def _block_risk_diff() -> str:
    return """diff --git a/.github/workflows/agentreview.yml b/.github/workflows/agentreview.yml
index 1111111..2222222 100644
--- a/.github/workflows/agentreview.yml
+++ b/.github/workflows/agentreview.yml
@@ -1 +1,8 @@
 name: AgentReviewOps
+permissions: write-all
+on:
+  pull_request_target:
+jobs:
+  scan:
+    steps:
+      - uses: actions/checkout@main
"""
