from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
import os

import httpx
import typer

from agentreview import __version__
from agentreview.ai import AIProviderConfigError, AIProviderRequestError
from agentreview.analysis_output import write_analysis_json_output
from agentreview.analysis import analyze_diff_text
from agentreview.checks import analysis_to_check_run_content
from agentreview.config import ConfigError, DEFAULT_CONFIG_PATH, load_config
from agentreview.github_reviewers import (
    GitHubReviewerRequestPlan,
    filter_github_reviewer_request_plan,
    resolve_github_reviewer_request_plan,
)
from agentreview.integrations.github import (
    GITHUB_API_BASE_URL,
    GitHubIntegrationError,
    MissingGitHubTokenError,
    create_or_update_check_run,
    fetch_pull_request_diff,
    request_pull_request_reviewers,
    upsert_pull_request_comment,
)
from agentreview.models import ReviewRequirement
from agentreview.plugins import PluginError
from agentreview.routing import load_codeowners_text

app = typer.Typer(
    name="agentreview",
    help="AgentReviewOps: evaluate and govern AI-generated pull requests.",
    no_args_is_help=True,
)
admin_app = typer.Typer(help="Administrative commands for self-hosted AgentReviewOps.")
app.add_typer(admin_app, name="admin")


class FailOnLevel(str, Enum):
    NEVER = "never"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCK = "block"


class ReviewerRequestMode(str, Enum):
    USERS = "users"
    TEAMS = "teams"
    USERS_AND_TEAMS = "users-and-teams"


RISK_LEVEL_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "block": 3,
}


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
    fail_on: FailOnLevel = typer.Option(
        FailOnLevel.NEVER,
        "--fail-on",
        help="Exit with code 1 when risk is at or above this level.",
    ),
    codeowners_file: Path | None = typer.Option(
        None,
        "--codeowners-file",
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="Optional CODEOWNERS file for human review routing. Defaults to standard CODEOWNERS paths.",
    ),
    repo: str | None = typer.Option(
        None,
        "--repo",
        help="GitHub repository in owner/name format. Required when --checks is enabled.",
    ),
    head_sha: str | None = typer.Option(
        None,
        "--head-sha",
        help="Pull request head SHA. Required when --checks is enabled.",
    ),
    checks: bool = typer.Option(
        False,
        "--checks",
        help="Publish an AgentReviewOps GitHub Check Run.",
    ),
    check_name: str = typer.Option(
        "AgentReviewOps",
        "--check-name",
        help="Name of the GitHub Check Run.",
    ),
    check_title: str = typer.Option(
        "AgentReviewOps policy gate",
        "--check-title",
        help="Title shown in the GitHub Check output.",
    ),
    api_base_url: str = typer.Option(
        GITHUB_API_BASE_URL,
        "--api-base-url",
        help="GitHub API base URL, for example a GitHub Enterprise API URL.",
    ),
    json_output: Path | None = typer.Option(
        None,
        "--json-output",
        dir_okay=False,
        help="Optional path where structured JSON analysis output will be written.",
    ),
) -> None:
    """Analyze a unified diff and write a Markdown review report."""
    _validate_checks_context(checks=checks, repo=repo, head_sha=head_sha)
    try:
        config = load_config(config_path)
        codeowners_text = _load_codeowners_for_cli(codeowners_file, config.review_routing.codeowners.path)
        result = analyze_diff_text(
            diff_file.read_text(encoding="utf-8"),
            config=config,
            codeowners_text=codeowners_text,
        )
    except ConfigError as exc:
        typer.echo(f"Config error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except PluginError as exc:
        typer.echo(f"Plugin error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except AIProviderConfigError as exc:
        typer.echo(f"AI configuration error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except AIProviderRequestError as exc:
        typer.echo(f"AI provider error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except OSError as exc:
        typer.echo(f"Could not read diff file {diff_file}: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result.markdown, encoding="utf-8")
    except OSError as exc:
        typer.echo(f"Could not write report to {output}: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    _write_json_output_for_cli(json_output, result, fail_on=fail_on.value, source="scan-diff")
    check_url = _publish_check_run_for_cli(
        checks=checks,
        result=result,
        repo=repo,
        head_sha=head_sha,
        fail_on=fail_on.value,
        check_name=check_name,
        check_title=check_title,
        api_base_url=api_base_url,
    )

    typer.echo("AgentReviewOps")
    typer.echo(f"Risk: {result.analysis.risk_level.upper()} {result.analysis.risk_score}/100")
    typer.echo("")
    typer.echo("Findings:")
    positive_findings = [finding for finding in result.analysis.findings if finding.score_delta > 0]
    if positive_findings:
        for finding in positive_findings:
            file_path = finding.file_path or "change set"
            typer.echo(f"- {finding.severity.upper()} {finding.rule_id}: {file_path}")
    else:
        typer.echo("- INFO none: no positive risk findings")
    typer.echo("")
    typer.echo(f"Report written to: {output}")
    if check_url is not None:
        typer.echo(f"GitHub check: {check_url}")
    _enforce_fail_on(result.analysis.risk_level, result.analysis.risk_score, fail_on)


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
    fail_on: FailOnLevel = typer.Option(
        FailOnLevel.NEVER,
        "--fail-on",
        help="Exit with code 1 when risk is at or above this level.",
    ),
    codeowners_file: Path | None = typer.Option(
        None,
        "--codeowners-file",
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="Optional CODEOWNERS file for human review routing. Defaults to standard CODEOWNERS paths.",
    ),
    head_sha: str | None = typer.Option(
        None,
        "--head-sha",
        help="Pull request head SHA. Required when --checks is enabled.",
    ),
    checks: bool = typer.Option(
        False,
        "--checks",
        help="Publish an AgentReviewOps GitHub Check Run.",
    ),
    check_name: str = typer.Option(
        "AgentReviewOps",
        "--check-name",
        help="Name of the GitHub Check Run.",
    ),
    check_title: str = typer.Option(
        "AgentReviewOps policy gate",
        "--check-title",
        help="Title shown in the GitHub Check output.",
    ),
    api_base_url: str = typer.Option(
        GITHUB_API_BASE_URL,
        "--api-base-url",
        help="GitHub API base URL, for example a GitHub Enterprise API URL.",
    ),
    comment: bool = typer.Option(
        False,
        "--comment/--no-comment",
        help="Post or update the generated report as a GitHub pull request comment.",
    ),
    json_output: Path | None = typer.Option(
        None,
        "--json-output",
        dir_okay=False,
        help="Optional path where structured JSON analysis output will be written.",
    ),
) -> None:
    """Fetch a GitHub pull request diff and write a Markdown review report."""
    _validate_checks_context(checks=checks, repo=repo, head_sha=head_sha)
    try:
        config = load_config(config_path)
        codeowners_text = _load_codeowners_for_cli(codeowners_file, config.review_routing.codeowners.path)
        diff_text = fetch_pull_request_diff(
            repo=repo,
            pr_number=pr_number,
            token=os.environ.get("GITHUB_TOKEN"),
            api_base_url=api_base_url,
        )
        result = analyze_diff_text(diff_text, config=config, codeowners_text=codeowners_text)
    except ConfigError as exc:
        typer.echo(f"Config error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except PluginError as exc:
        typer.echo(f"Plugin error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except AIProviderConfigError as exc:
        typer.echo(f"AI configuration error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except AIProviderRequestError as exc:
        typer.echo(f"AI provider error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except MissingGitHubTokenError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except GitHubIntegrationError as exc:
        typer.echo(f"GitHub error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result.markdown, encoding="utf-8")
    except OSError as exc:
        typer.echo(f"Could not write report to {output}: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    _write_json_output_for_cli(json_output, result, fail_on=fail_on.value, source="scan-pr")
    check_url = _publish_check_run_for_cli(
        checks=checks,
        result=result,
        repo=repo,
        head_sha=head_sha,
        fail_on=fail_on.value,
        check_name=check_name,
        check_title=check_title,
        api_base_url=api_base_url,
    )

    typer.echo("AgentReviewOps")
    typer.echo(f"GitHub PR: {repo}#{pr_number}")
    typer.echo(f"Risk: {result.analysis.risk_level.upper()} {result.analysis.risk_score}/100")
    typer.echo(f"Report written to: {output}")
    if comment:
        try:
            comment_url = upsert_pull_request_comment(
                repo=repo,
                pr_number=pr_number,
                body=result.markdown,
                token=os.environ.get("GITHUB_TOKEN"),
                api_base_url=api_base_url,
            )
        except MissingGitHubTokenError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
        except GitHubIntegrationError as exc:
            typer.echo(f"GitHub error: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        typer.echo(f"GitHub comment: {comment_url}")
    if check_url is not None:
        typer.echo(f"GitHub check: {check_url}")
    _enforce_fail_on(result.analysis.risk_level, result.analysis.risk_score, fail_on)


@app.command("request-reviewers")
def request_reviewers(
    repo: str = typer.Option(
        ...,
        "--repo",
        help="GitHub repository in owner/name format.",
    ),
    pr_number: int = typer.Option(
        ...,
        "--pr",
        min=1,
        help="Pull request number to request reviewers on.",
    ),
    analysis_file: Path = typer.Option(
        ...,
        "--analysis-file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Structured JSON analysis file produced by --json-output.",
    ),
    github_token: str | None = typer.Option(
        None,
        "--github-token",
        help="GitHub token. Prefer GITHUB_TOKEN in CI.",
    ),
    api_base_url: str = typer.Option(
        GITHUB_API_BASE_URL,
        "--api-base-url",
        help="GitHub API base URL, for example a GitHub Enterprise API URL.",
    ),
    reviewer_request_mode: ReviewerRequestMode = typer.Option(
        ReviewerRequestMode.USERS_AND_TEAMS,
        "--reviewer-request-mode",
        help="Which reviewers to request: users, teams, or users-and-teams.",
    ),
    author: str | None = typer.Option(
        None,
        "--author",
        help="Pull request author login to exclude from reviewer requests.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Resolve and print reviewer requests without calling the GitHub API.",
    ),
) -> None:
    """Request GitHub reviewers from structured AgentReviewOps analysis output."""
    review_requirements = _load_review_requirements_from_analysis_file(analysis_file)
    resolved_plan = resolve_github_reviewer_request_plan(review_requirements, author=author)
    plan = filter_github_reviewer_request_plan(resolved_plan, mode=reviewer_request_mode.value)

    api_call_status = "dry-run"
    if not dry_run:
        try:
            response = request_pull_request_reviewers(
                repo=repo,
                pr_number=pr_number,
                reviewers=plan.reviewers,
                team_reviewers=plan.team_reviewers,
                token=github_token,
                api_base_url=api_base_url,
            )
        except MissingGitHubTokenError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
        except GitHubIntegrationError as exc:
            typer.echo(f"GitHub error: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        api_call_status = "requested" if response.get("requested") else "no-op"

    typer.echo("AgentReviewOps")
    typer.echo(f"GitHub PR: {repo}#{pr_number}")
    typer.echo(f"Reviewer request mode: {reviewer_request_mode.value}")
    _echo_reviewer_request_summary(plan, api_call_status=api_call_status)


@app.command("comment-pr")
def comment_pr(
    repo: str = typer.Option(
        ...,
        "--repo",
        help="GitHub repository in owner/name format.",
    ),
    pr_number: int = typer.Option(
        ...,
        "--pr",
        min=1,
        help="Pull request number to comment on.",
    ),
    report_file: Path = typer.Option(
        Path("agentreview-report.md"),
        "--report-file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Markdown report file to post or update as a PR comment.",
    ),
) -> None:
    """Post or update an AgentReviewOps report comment on a GitHub pull request."""
    try:
        report = report_file.read_text(encoding="utf-8")
        comment_url = upsert_pull_request_comment(
            repo=repo,
            pr_number=pr_number,
            body=report,
            token=os.environ.get("GITHUB_TOKEN"),
        )
    except OSError as exc:
        typer.echo(f"Could not read report file {report_file}: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except MissingGitHubTokenError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except GitHubIntegrationError as exc:
        typer.echo(f"GitHub error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("AgentReviewOps")
    typer.echo(f"GitHub PR: {repo}#{pr_number}")
    typer.echo(f"GitHub comment: {comment_url}")


def _response_error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"{response.status_code} {response.reason_phrase}"
    detail = body.get("detail") if isinstance(body, dict) else None
    return f"{response.status_code} {detail or response.reason_phrase}"


def _load_codeowners_for_cli(codeowners_file: Path | None, configured_path: str | None = None) -> str | None:
    if codeowners_file is not None:
        try:
            return codeowners_file.read_text(encoding="utf-8")
        except OSError as exc:
            typer.echo(f"Could not read CODEOWNERS file {codeowners_file}: {exc}", err=True)
            raise typer.Exit(code=1) from exc
    if configured_path:
        try:
            return load_codeowners_text(configured_path)
        except OSError as exc:
            typer.echo(f"Could not read CODEOWNERS file {configured_path}: {exc}", err=True)
            raise typer.Exit(code=1) from exc
    try:
        return load_codeowners_text()
    except OSError:
        return None


def _write_json_output_for_cli(
    json_output: Path | None,
    result,
    *,
    fail_on: str,
    source: str,
) -> None:
    if json_output is None:
        return
    try:
        write_analysis_json_output(json_output, result, fail_on=fail_on, source=source)
    except OSError as exc:
        typer.echo(f"Could not write JSON analysis output to {json_output}: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _validate_checks_context(*, checks: bool, repo: str | None, head_sha: str | None) -> None:
    if not checks:
        return
    missing = []
    if not repo:
        missing.append("--repo")
    if not head_sha:
        missing.append("--head-sha")
    if missing:
        typer.echo(f"--checks requires {', '.join(missing)}.", err=True)
        raise typer.Exit(code=2)


def _publish_check_run_for_cli(
    *,
    checks: bool,
    result,
    repo: str | None,
    head_sha: str | None,
    fail_on: str,
    check_name: str,
    check_title: str,
    api_base_url: str,
) -> str | None:
    if not checks:
        return None
    check_content = analysis_to_check_run_content(result, fail_on=fail_on)
    try:
        response = create_or_update_check_run(
            repo=repo or "",
            head_sha=head_sha or "",
            name=check_name,
            title=check_title,
            summary=check_content.summary,
            text=check_content.text,
            conclusion=check_content.conclusion,
            annotations=check_content.annotations,
            token=os.environ.get("GITHUB_TOKEN"),
            api_base_url=api_base_url,
        )
    except MissingGitHubTokenError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except GitHubIntegrationError as exc:
        typer.echo(f"GitHub error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    for key in ("html_url", "details_url", "url"):
        value = response.get(key)
        if isinstance(value, str) and value:
            return value
    return "created"


def _load_review_requirements_from_analysis_file(analysis_file: Path) -> list[ReviewRequirement]:
    try:
        payload = json.loads(analysis_file.read_text(encoding="utf-8"))
    except OSError as exc:
        typer.echo(f"Could not read analysis file {analysis_file}: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except json.JSONDecodeError as exc:
        typer.echo(f"Analysis file {analysis_file} is not valid JSON: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    if not isinstance(payload, dict):
        typer.echo(f"Analysis file {analysis_file} must contain a JSON object.", err=True)
        raise typer.Exit(code=2)
    review_requirements_json = payload.get("review_requirements")
    if not isinstance(review_requirements_json, list):
        typer.echo(f"Analysis file {analysis_file} is missing review_requirements.", err=True)
        raise typer.Exit(code=2)
    try:
        return [
            ReviewRequirement.model_validate(requirement)
            for requirement in review_requirements_json
        ]
    except ValueError as exc:
        typer.echo(f"Analysis file {analysis_file} has invalid review_requirements: {exc}", err=True)
        raise typer.Exit(code=2) from exc


def _echo_reviewer_request_summary(plan: GitHubReviewerRequestPlan, *, api_call_status: str) -> None:
    typer.echo(f"Requested individual reviewers: {_format_list(plan.reviewers)}")
    typer.echo(f"Requested team reviewers: {_format_list(plan.team_reviewers)}")
    typer.echo("Skipped reviewers:")
    if plan.skipped:
        for skipped_reviewer in plan.skipped:
            typer.echo(
                f"- {skipped_reviewer.identifier}: "
                f"{skipped_reviewer.reason} ({skipped_reviewer.source})"
            )
    else:
        typer.echo("- none")
    typer.echo(f"GitHub API call: {api_call_status}")


def _format_list(values: list[str]) -> str:
    return ", ".join(values) if values else "none"


def _enforce_fail_on(risk_level: str, risk_score: int, fail_on: FailOnLevel) -> None:
    if fail_on == FailOnLevel.NEVER:
        return
    if RISK_LEVEL_ORDER[risk_level] < RISK_LEVEL_ORDER[fail_on.value]:
        return

    typer.echo(
        (
            "CI gate failed: "
            f"risk {risk_level.upper()} ({risk_score}/100) meets --fail-on {fail_on.value} threshold."
        ),
        err=True,
    )
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
