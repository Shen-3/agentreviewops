from __future__ import annotations

from pathlib import Path
import os

import httpx
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


def version_callback(value: bool | None) -> None:
    if value:
        typer.echo(f"agentreview {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
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


@app.command("submit-diff")
def submit_diff(
    diff_file: Path = typer.Option(
        ...,
        "--diff-file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Unified diff file to submit to a self-hosted AgentReviewOps API.",
    ),
    config_path: Path = typer.Option(
        Path(DEFAULT_CONFIG_PATH),
        "--config",
        help="Path to .agentreview.yml. Missing files use built-in defaults unless an organization policy overrides them.",
    ),
    api_url: str = typer.Option(
        "http://127.0.0.1:8000",
        "--api-url",
        envvar="AGENTREVIEW_API_URL",
        help="Base URL for the AgentReviewOps API.",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        envvar="AGENTREVIEW_API_KEY",
        help="AgentReviewOps API key. Prefer AGENTREVIEW_API_KEY in CI.",
    ),
    repository: str | None = typer.Option(None, "--repository", help="Repository identifier such as owner/name."),
    pull_request_number: int | None = typer.Option(None, "--pr", min=1, help="Pull request number, when available."),
    title: str | None = typer.Option(None, "--title", help="Pull request or analysis title."),
    author: str | None = typer.Option(None, "--author", help="Pull request author or agent account."),
    agent_name: str | None = typer.Option(None, "--agent-name", help="Detected or supplied AI agent name."),
    branch: str | None = typer.Option(None, "--branch", help="Source branch name."),
    timeout_seconds: float = typer.Option(15.0, "--timeout", min=1.0, max=120.0, help="API request timeout in seconds."),
) -> None:
    """Submit a unified diff to the self-hosted API and persist the analysis run."""
    if not api_key:
        typer.echo("API key required. Set AGENTREVIEW_API_KEY or pass --api-key.", err=True)
        raise typer.Exit(code=2)

    try:
        config = load_config(config_path)
        diff_text = diff_file.read_text(encoding="utf-8")
    except ConfigError as exc:
        typer.echo(f"Config error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except OSError as exc:
        typer.echo(f"Could not read diff file {diff_file}: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    payload = {
        "diff": diff_text,
        "config": config.model_dump(mode="json"),
        "repository": repository,
        "pull_request_number": pull_request_number,
        "title": title,
        "author": author,
        "agent_name": agent_name,
        "branch": branch,
    }
    try:
        response = httpx.post(
            f"{api_url.rstrip('/')}/api/analyze/diff",
            json={key: value for key, value in payload.items() if value is not None},
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": f"agentreview/{__version__}",
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
    except httpx.HTTPStatusError as exc:
        typer.echo(f"API error: {_response_error_detail(exc.response)}", err=True)
        raise typer.Exit(code=1) from exc
    except httpx.HTTPError as exc:
        typer.echo(f"API request failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        typer.echo("API response was not valid JSON.", err=True)
        raise typer.Exit(code=1) from exc

    try:
        analysis_run_id = body["analysis_run_id"]
        risk_level = str(body["risk_level"]).upper()
        risk_score = body["risk_score"]
        finding_count = len(body.get("findings", []))
        changed_file_count = len(body.get("changed_files", []))
    except KeyError as exc:
        typer.echo(f"API response missing expected field: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("AgentReviewOps")
    typer.echo(f"Submitted analysis run: {analysis_run_id}")
    typer.echo(f"Risk: {risk_level} {risk_score}/100")
    typer.echo(f"Changed files: {changed_file_count}")
    typer.echo(f"Findings: {finding_count}")
    typer.echo(f"Report API: {api_url.rstrip('/')}/api/analysis-runs/{analysis_run_id}/report")


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


def _response_error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"{response.status_code} {response.reason_phrase}"
    detail = body.get("detail") if isinstance(body, dict) else None
    return f"{response.status_code} {detail or response.reason_phrase}"


if __name__ == "__main__":
    app()
