from pathlib import Path

from typer.testing import CliRunner

from agentreview.cli import app


def test_help_shows_product_name() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "AgentReviewOps" in result.output
    assert "admin" in result.output
    assert "scan-diff" in result.output
    assert "submit-diff" in result.output
    assert "scan-pr" in result.output
    assert "--version" in result.output


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
