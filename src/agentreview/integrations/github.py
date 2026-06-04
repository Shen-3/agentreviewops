from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_DIFF_ACCEPT = "application/vnd.github.v3.diff"
GITHUB_JSON_ACCEPT = "application/vnd.github+json"
AGENTREVIEW_COMMENT_MARKER = "<!-- agentreviewops-report -->"
USER_AGENT = "AgentReviewOps/0.1"
SUPPORTED_CHECK_CONCLUSIONS = {"success", "neutral", "failure"}
SUPPORTED_ANNOTATION_LEVELS = {"notice", "warning", "failure"}


class GitHubIntegrationError(RuntimeError):
    """Raised when GitHub PR diff retrieval fails."""


class MissingGitHubTokenError(GitHubIntegrationError):
    """Raised when GITHUB_TOKEN is required but missing."""


@dataclass(frozen=True)
class CheckRunAnnotation:
    path: str
    start_line: int
    end_line: int
    annotation_level: str
    message: str
    title: str | None = None
    raw_details: str | None = None

    def to_payload(self) -> dict:
        payload = {
            "path": self.path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "annotation_level": self.annotation_level,
            "message": self.message,
        }
        if self.title is not None:
            payload["title"] = self.title
        if self.raw_details is not None:
            payload["raw_details"] = self.raw_details
        return payload


def fetch_pull_request_diff(
    *,
    repo: str,
    pr_number: int,
    token: str | None = None,
    api_base_url: str = GITHUB_API_BASE_URL,
    opener: Callable[..., Any] | None = None,
) -> str:
    active_token = token or os.environ.get("GITHUB_TOKEN")
    _validate_pull_request_inputs(repo=repo, pr_number=pr_number, token=active_token)

    request = Request(
        f"{api_base_url.rstrip('/')}/repos/{repo}/pulls/{pr_number}",
        headers={
            "Accept": GITHUB_DIFF_ACCEPT,
            "Authorization": f"Bearer {active_token}",
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )
    active_opener = opener or urlopen

    try:
        with active_opener(request, timeout=30) as response:
            return response.read().decode("utf-8")
    except HTTPError as exc:
        raise GitHubIntegrationError(f"GitHub API request failed with HTTP {exc.code}") from exc
    except URLError as exc:
        raise GitHubIntegrationError(f"GitHub API request failed: {exc.reason}") from exc


def upsert_pull_request_comment(
    *,
    repo: str,
    pr_number: int,
    body: str,
    token: str | None = None,
    api_base_url: str = GITHUB_API_BASE_URL,
    opener: Callable[..., Any] | None = None,
    marker: str = AGENTREVIEW_COMMENT_MARKER,
) -> str:
    active_token = token or os.environ.get("GITHUB_TOKEN")
    _validate_pull_request_inputs(repo=repo, pr_number=pr_number, token=active_token)
    if not body.strip():
        raise GitHubIntegrationError("Comment body must not be empty")

    active_opener = opener or urlopen
    existing_comment = _find_existing_comment(
        repo=repo,
        pr_number=pr_number,
        token=active_token or "",
        api_base_url=api_base_url,
        opener=active_opener,
        marker=marker,
    )
    comment_body = _comment_body(body, marker=marker)
    if existing_comment is None:
        url = f"{api_base_url.rstrip('/')}/repos/{repo}/issues/{pr_number}/comments"
        method = "POST"
    else:
        url = f"{api_base_url.rstrip('/')}/repos/{repo}/issues/comments/{existing_comment['id']}"
        method = "PATCH"

    request = _json_request(url, token=active_token or "", method=method, payload={"body": comment_body})
    try:
        with active_opener(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise GitHubIntegrationError(f"GitHub API request failed with HTTP {exc.code}") from exc
    except (URLError, json.JSONDecodeError) as exc:
        raise GitHubIntegrationError(f"GitHub API request failed: {exc}") from exc

    html_url = payload.get("html_url")
    if not isinstance(html_url, str) or not html_url:
        raise GitHubIntegrationError("GitHub comment response did not include html_url")
    return html_url


def request_pull_request_reviewers(
    *,
    repo: str,
    pr_number: int,
    reviewers: list[str],
    team_reviewers: list[str],
    token: str | None = None,
    api_base_url: str = GITHUB_API_BASE_URL,
    opener: Callable[..., Any] | None = None,
) -> dict:
    _validate_repository_and_pr(repo=repo, pr_number=pr_number)
    reviewer_payload = _dedupe_case_insensitive(reviewers)
    team_reviewer_payload = _dedupe_case_insensitive(team_reviewers)
    if not reviewer_payload and not team_reviewer_payload:
        return {
            "requested": False,
            "reviewers": [],
            "team_reviewers": [],
            "message": "No GitHub reviewers to request.",
        }

    active_token = token or os.environ.get("GITHUB_TOKEN")
    _validate_pull_request_inputs(repo=repo, pr_number=pr_number, token=active_token)
    request = _json_request(
        f"{api_base_url.rstrip('/')}/repos/{repo}/pulls/{pr_number}/requested_reviewers",
        token=active_token or "",
        method="POST",
        payload={
            "reviewers": reviewer_payload,
            "team_reviewers": team_reviewer_payload,
        },
    )
    active_opener = opener or urlopen

    try:
        with active_opener(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise GitHubIntegrationError(_http_error_message(exc)) from exc
    except (URLError, json.JSONDecodeError) as exc:
        raise GitHubIntegrationError(f"GitHub API request failed: {exc}") from exc

    if not isinstance(payload, dict):
        raise GitHubIntegrationError("GitHub reviewer request response was not an object")
    return {
        "requested": True,
        "reviewers": reviewer_payload,
        "team_reviewers": team_reviewer_payload,
        "response": payload,
    }


def create_check_run(
    *,
    repo: str,
    head_sha: str,
    name: str,
    title: str,
    summary: str,
    text: str | None = None,
    conclusion: str,
    annotations: list[CheckRunAnnotation] | None = None,
    token: str | None = None,
    api_base_url: str = GITHUB_API_BASE_URL,
    opener: Callable[..., Any] | None = None,
) -> dict:
    active_token = token or os.environ.get("GITHUB_TOKEN")
    _validate_check_run_inputs(
        repo=repo,
        head_sha=head_sha,
        name=name,
        title=title,
        summary=summary,
        conclusion=conclusion,
        token=active_token,
        annotations=annotations or [],
    )
    output = {
        "title": title,
        "summary": summary,
    }
    if text is not None:
        output["text"] = text
    if annotations:
        output["annotations"] = [annotation.to_payload() for annotation in annotations]

    request = _json_request(
        f"{api_base_url.rstrip('/')}/repos/{repo}/check-runs",
        token=active_token or "",
        method="POST",
        payload={
            "name": name,
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": conclusion,
            "output": output,
        },
    )
    active_opener = opener or urlopen

    try:
        with active_opener(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise GitHubIntegrationError(_http_error_message(exc)) from exc
    except (URLError, json.JSONDecodeError) as exc:
        raise GitHubIntegrationError(f"GitHub API request failed: {exc}") from exc

    if not isinstance(payload, dict):
        raise GitHubIntegrationError("GitHub check run response was not an object")
    return payload


def create_or_update_check_run(**kwargs: Any) -> dict:
    return create_check_run(**kwargs)


def _find_existing_comment(
    *,
    repo: str,
    pr_number: int,
    token: str,
    api_base_url: str,
    opener: Callable[..., Any],
    marker: str,
) -> dict | None:
    request = _json_request(
        f"{api_base_url.rstrip('/')}/repos/{repo}/issues/{pr_number}/comments?per_page=100",
        token=token,
        method="GET",
    )
    try:
        with opener(request, timeout=30) as response:
            comments = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise GitHubIntegrationError(f"GitHub API request failed with HTTP {exc.code}") from exc
    except (URLError, json.JSONDecodeError) as exc:
        raise GitHubIntegrationError(f"GitHub API request failed: {exc}") from exc

    if not isinstance(comments, list):
        raise GitHubIntegrationError("GitHub comments response was not a list")
    for comment in comments:
        if isinstance(comment, dict) and marker in str(comment.get("body", "")) and comment.get("id") is not None:
            return comment
    return None


def _json_request(url: str, *, token: str, method: str, payload: dict | None = None) -> Request:
    data = None
    headers = {
        "Accept": GITHUB_JSON_ACCEPT,
        "Authorization": f"Bearer {token}",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    return Request(url, headers=headers, data=data, method=method)


def _comment_body(body: str, *, marker: str) -> str:
    return f"{marker}\n{body.strip()}\n"


def _validate_pull_request_inputs(*, repo: str, pr_number: int, token: str | None) -> None:
    _validate_repository_and_pr(repo=repo, pr_number=pr_number)
    if not token:
        raise MissingGitHubTokenError("GITHUB_TOKEN is required to access GitHub pull requests")


def _validate_repository_and_pr(*, repo: str, pr_number: int) -> None:
    _validate_repository(repo)
    if pr_number <= 0:
        raise GitHubIntegrationError("Pull request number must be greater than zero")


def _validate_check_run_inputs(
    *,
    repo: str,
    head_sha: str,
    name: str,
    title: str,
    summary: str,
    conclusion: str,
    token: str | None,
    annotations: list[CheckRunAnnotation],
) -> None:
    _validate_repository(repo)
    if not token:
        raise MissingGitHubTokenError("GITHUB_TOKEN is required to create GitHub check runs")
    if not head_sha.strip():
        raise GitHubIntegrationError("Check run head SHA must not be empty")
    if not name.strip():
        raise GitHubIntegrationError("Check run name must not be empty")
    if not title.strip():
        raise GitHubIntegrationError("Check run title must not be empty")
    if not summary.strip():
        raise GitHubIntegrationError("Check run summary must not be empty")
    if conclusion not in SUPPORTED_CHECK_CONCLUSIONS:
        raise GitHubIntegrationError("Check run conclusion must be success, neutral, or failure")
    for annotation in annotations:
        if annotation.annotation_level not in SUPPORTED_ANNOTATION_LEVELS:
            raise GitHubIntegrationError("Check annotation level must be notice, warning, or failure")
        if annotation.start_line <= 0 or annotation.end_line <= 0:
            raise GitHubIntegrationError("Check annotation line numbers must be greater than zero")


def _validate_repository(repo: str) -> None:
    if "/" not in repo or repo.count("/") != 1:
        raise GitHubIntegrationError("Repository must use the owner/name format")
    owner, name = repo.split("/", maxsplit=1)
    if not owner.strip() or not name.strip():
        raise GitHubIntegrationError("Repository must use the owner/name format")


def _dedupe_case_insensitive(values: list[str]) -> list[str]:
    deduped: dict[str, str] = {}
    for value in values:
        normalized = value.strip()
        if not normalized:
            continue
        deduped.setdefault(normalized.casefold(), normalized)
    return [deduped[key] for key in sorted(deduped)]


def _http_error_message(exc: HTTPError) -> str:
    detail = ""
    if exc.fp is not None:
        try:
            payload = json.loads(exc.fp.read().decode("utf-8"))
        except (AttributeError, json.JSONDecodeError, UnicodeDecodeError):
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("message"), str):
            detail = f": {payload['message']}"
    return f"GitHub API request failed with HTTP {exc.code}{detail}"
