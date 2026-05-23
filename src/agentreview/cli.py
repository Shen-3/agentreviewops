from __future__ import annotations

from pathlib import Path
import os

import typer

from agentreview import __version__
from agentreview.config import ConfigError, DEFAULT_CONFIG_PATH, load_config
from agentreview.gitdiff import parse_diff_file
from agentreview.gitdiff import parse_unified_diff
from agentreview.integrations.github import GitHubIntegrationError, MissingGitHubTokenError, fetch_pull_request_diff
from agentreview.report import generate_markdown_report
from agentreview.risk import analyze_risk

app = typer.Typer(
    name="agentreview",
    help="AgentReviewOps: evaluate and govern AI-generated pull requests.",
    no_args_is_help=True,
)
admin_app = typer.Typer(help="Administrative commands for self-hosted AgentReviewOps.")
app.add_typer(admin_app, name="admin")


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"agentreview {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show the installed AgentReviewOps version.",
    ),
) -> None:
    """AgentReviewOps command line interface."""


@admin_app.command("bootstrap")
def bootstrap_admin(
    org_slug: str = typer.Option(
        ...,
        "--org-slug",
        help="Stable organization slug, for example acme.",
    ),
    org_name: str = typer.Option(
        ...,
        "--org-name",
        help="Human-readable organization name.",
    ),
    email: str = typer.Option(
        ...,
        "--email",
        help="Initial admin user email.",
    ),
    user_name: str | None = typer.Option(
        None,
        "--user-name",
        help="Initial admin display name.",
    ),
    api_key_name: str = typer.Option(
        "Bootstrap key",
        "--api-key-name",
        help="Name for the one-time API key to create.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to AGENTREVIEW_DATABASE_URL or local SQLite.",
    ),
) -> None:
    """Create the first organization, admin user, and API key."""
    try:
        from sqlalchemy.exc import SQLAlchemyError

        from agentreview_api.bootstrap import BootstrapError, bootstrap_account
        from agentreview_api.db import create_session_factory, get_database_url

        resolved_database_url = database_url or get_database_url()
        session_factory = create_session_factory(resolved_database_url)
        with session_factory() as session:
            result = bootstrap_account(
                session,
                org_slug=org_slug,
                org_name=org_name,
                email=email,
                user_name=user_name,
                api_key_name=api_key_name,
            )
    except BootstrapError as exc:
        typer.echo(f"Bootstrap error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except SQLAlchemyError as exc:
        typer.echo(f"Database error: {exc}", err=True)
        typer.echo("Run `alembic upgrade head` before bootstrapping a fresh database.", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("AgentReviewOps bootstrap complete")
    typer.echo(f"Organization: {result.organization_slug} ({result.organization_id})")
    typer.echo(f"Admin user: {result.user_email} ({result.user_id})")
    typer.echo(f"API key: {result.api_key_secret}")
    typer.echo("")
    typer.echo("Store this API key now. It is hashed in the database and cannot be shown again.")


@app.command("scan-diff")
def scan_diff(
    diff_file: Path = typer.Option(
        ...,
        "--diff-file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Unified diff file to analyze.",
    ),
    config_path: Path = typer.Option(
        Path(DEFAULT_CONFIG_PATH),
        "--config",
        help="Path to .agentreview.yml. Missing files use built-in defaults.",
    ),
    output: Path = typer.Option(
        Path("agentreview-report.md"),
        "--output",
        dir_okay=False,
        help="Path where the Markdown report will be written.",
    ),
) -> None:
    """Analyze a unified diff and write a Markdown review report."""
    try:
        config = load_config(config_path)
        changed_files = parse_diff_file(diff_file, config=config)
        analysis = analyze_risk(changed_files, config=config)
        report = generate_markdown_report(analysis, changed_files, config=config)
    except ConfigError as exc:
        typer.echo(f"Config error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
    except OSError as exc:
        typer.echo(f"Could not write report to {output}: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("AgentReviewOps")
    typer.echo(f"Risk: {analysis.risk_level.upper()} {analysis.risk_score}/100")
    typer.echo("")
    typer.echo("Findings:")
    positive_findings = [finding for finding in analysis.findings if finding.score_delta > 0]
    if positive_findings:
        for finding in positive_findings:
            file_path = finding.file_path or "change set"
            typer.echo(f"- {finding.severity.upper()} {finding.rule_id}: {file_path}")
    else:
        typer.echo("- INFO none: no positive risk findings")
    typer.echo("")
    typer.echo(f"Report written to: {output}")


@app.command("scan-pr")
def scan_pr(
    repo: str = typer.Option(
        ...,
        "--repo",
        help="GitHub repository in owner/name format.",
    ),
    pr_number: int = typer.Option(
        ...,
        "--pr",
        min=1,
        help="Pull request number to scan.",
    ),
    config_path: Path = typer.Option(
        Path(DEFAULT_CONFIG_PATH),
        "--config",
        help="Path to .agentreview.yml. Missing files use built-in defaults.",
    ),
    output: Path = typer.Option(
        Path("agentreview-report.md"),
        "--output",
        dir_okay=False,
        help="Path where the Markdown report will be written.",
    ),
) -> None:
    """Fetch a GitHub pull request diff and write a Markdown review report."""
    try:
        config = load_config(config_path)
        diff_text = fetch_pull_request_diff(repo=repo, pr_number=pr_number, token=os.environ.get("GITHUB_TOKEN"))
        changed_files = parse_unified_diff(diff_text, config=config)
        analysis = analyze_risk(changed_files, config=config)
        report = generate_markdown_report(analysis, changed_files, config=config)
    except ConfigError as exc:
        typer.echo(f"Config error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except MissingGitHubTokenError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except GitHubIntegrationError as exc:
        typer.echo(f"GitHub error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
    except OSError as exc:
        typer.echo(f"Could not write report to {output}: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("AgentReviewOps")
    typer.echo(f"GitHub PR: {repo}#{pr_number}")
    typer.echo(f"Risk: {analysis.risk_level.upper()} {analysis.risk_score}/100")
    typer.echo(f"Report written to: {output}")


if __name__ == "__main__":
    app()
