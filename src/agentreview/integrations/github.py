from __future__ import annotations

import os
import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_DIFF_ACCEPT = "application/vnd.github.v3.diff"
GITHUB_JSON_ACCEPT = "application/vnd.github+json"
AGENTREVIEW_COMMENT_MARKER = "<!-- agentreviewops-report -->"
USER_AGENT = "AgentReviewOps/0.1"


class GitHubIntegrationError(RuntimeError):
    """Raised when GitHub PR diff retrieval fails."""


class MissingGitHubTokenError(GitHubIntegrationError):
    """Raised when GITHUB_TOKEN is required but missing."""


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
    if not token:
        raise MissingGitHubTokenError("GITHUB_TOKEN is required to access GitHub pull requests")
    if "/" not in repo or repo.count("/") != 1:
        raise GitHubIntegrationError("Repository must use the owner/name format")
    if pr_number <= 0:
        raise GitHubIntegrationError("Pull request number must be greater than zero")
