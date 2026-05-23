from __future__ import annotations

import os
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_DIFF_ACCEPT = "application/vnd.github.v3.diff"
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
    if not active_token:
        raise MissingGitHubTokenError("GITHUB_TOKEN is required to fetch pull request diffs")
    if "/" not in repo or repo.count("/") != 1:
        raise GitHubIntegrationError("Repository must use the owner/name format")
    if pr_number <= 0:
        raise GitHubIntegrationError("Pull request number must be greater than zero")

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
