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
