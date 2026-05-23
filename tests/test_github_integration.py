from __future__ import annotations

from pathlib import Path
from urllib.error import HTTPError

from typer.testing import CliRunner

from agentreview.cli import app
from agentreview.integrations.github import (
    GITHUB_DIFF_ACCEPT,
    GitHubIntegrationError,
    MissingGitHubTokenError,
    fetch_pull_request_diff,
)


SAMPLE_DIFF = """diff --git a/README.md b/README.md
index 1111111..2222222 100644
--- a/README.md
+++ b/README.md
@@ -1 +1,2 @@
 # Project
+Updated docs
"""


class FakeResponse:
    def __init__(self, body: str) -> None:
        self.body = body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return self.body.encode("utf-8")


def test_fetch_pull_request_diff_uses_diff_media_type_and_token() -> None:
    captured = {}

    def fake_opener(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return FakeResponse(SAMPLE_DIFF)

    diff = fetch_pull_request_diff(
        repo="octo/example",
        pr_number=123,
        token="secret-token",
        opener=fake_opener,
    )

    assert diff == SAMPLE_DIFF
    assert captured["url"] == "https://api.github.com/repos/octo/example/pulls/123"
    assert captured["headers"]["Accept"] == GITHUB_DIFF_ACCEPT
    assert captured["headers"]["Authorization"] == "Bearer secret-token"
    assert captured["timeout"] == 30


def test_missing_github_token_fails_clearly(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    try:
        fetch_pull_request_diff(repo="octo/example", pr_number=123)
    except MissingGitHubTokenError as exc:
        assert "GITHUB_TOKEN is required" in str(exc)
    else:
        raise AssertionError("Expected MissingGitHubTokenError")


def test_github_http_error_does_not_include_token() -> None:
    def fake_opener(_request, timeout):
        assert timeout == 30
        raise HTTPError(
            url="https://api.github.com/repos/octo/example/pulls/123",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )

    try:
        fetch_pull_request_diff(
            repo="octo/example",
            pr_number=123,
            token="secret-token",
            opener=fake_opener,
        )
    except GitHubIntegrationError as exc:
        assert "HTTP 404" in str(exc)
        assert "secret-token" not in str(exc)
    else:
        raise AssertionError("Expected GitHubIntegrationError")


def test_scan_pr_writes_report_without_printing_token(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()
    output_path = tmp_path / "pr-report.md"
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    monkeypatch.setattr("agentreview.cli.fetch_pull_request_diff", lambda **_kwargs: SAMPLE_DIFF)

    result = runner.invoke(
        app,
        [
            "scan-pr",
            "--repo",
            "octo/example",
            "--pr",
            "123",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "GitHub PR: octo/example#123" in result.output
    assert "secret-token" not in result.output
    assert output_path.exists()


def test_scan_pr_missing_token_exits_clearly(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    result = runner.invoke(
        app,
        [
            "scan-pr",
            "--repo",
            "octo/example",
            "--pr",
            "123",
            "--output",
            str(tmp_path / "report.md"),
        ],
    )

    assert result.exit_code == 2
    assert "GITHUB_TOKEN is required" in result.output
