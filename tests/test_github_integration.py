from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError

from typer.testing import CliRunner

from agentreview.cli import app
from agentreview.integrations.github import (
    AGENTREVIEW_COMMENT_MARKER,
    GITHUB_DIFF_ACCEPT,
    GITHUB_JSON_ACCEPT,
    CheckRunAnnotation,
    GitHubIntegrationError,
    MissingGitHubTokenError,
    create_or_update_check_run,
    fetch_pull_request_diff,
    request_pull_request_reviewers,
    upsert_pull_request_comment,
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


def test_upsert_pull_request_comment_posts_when_no_existing_comment() -> None:
    calls = []

    def fake_opener(request, timeout):
        calls.append(
            {
                "url": request.full_url,
                "method": request.get_method(),
                "headers": dict(request.header_items()),
                "body": request.data.decode("utf-8") if request.data else "",
                "timeout": timeout,
            }
        )
        if request.get_method() == "GET":
            return FakeResponse("[]")
        return FakeResponse(json.dumps({"html_url": "https://github.com/octo/example/pull/123#issuecomment-1"}))

    comment_url = upsert_pull_request_comment(
        repo="octo/example",
        pr_number=123,
        body="# AgentReviewOps Report",
        token="secret-token",
        opener=fake_opener,
    )

    assert comment_url.endswith("#issuecomment-1")
    assert [call["method"] for call in calls] == ["GET", "POST"]
    assert calls[0]["headers"]["Accept"] == GITHUB_JSON_ACCEPT
    assert calls[0]["timeout"] == 30
    assert calls[1]["url"] == "https://api.github.com/repos/octo/example/issues/123/comments"
    assert calls[1]["headers"]["Authorization"] == "Bearer secret-token"
    posted_body = json.loads(calls[1]["body"])["body"]
    assert AGENTREVIEW_COMMENT_MARKER in posted_body
    assert "# AgentReviewOps Report" in posted_body


def test_upsert_pull_request_comment_patches_existing_agentreview_comment() -> None:
    calls = []

    def fake_opener(request, timeout):
        calls.append(
            {
                "url": request.full_url,
                "method": request.get_method(),
                "body": request.data.decode("utf-8") if request.data else "",
            }
        )
        if request.get_method() == "GET":
            return FakeResponse(json.dumps([{"id": 99, "body": f"{AGENTREVIEW_COMMENT_MARKER}\nold"}]))
        return FakeResponse(json.dumps({"html_url": "https://github.com/octo/example/pull/123#issuecomment-99"}))

    comment_url = upsert_pull_request_comment(
        repo="octo/example",
        pr_number=123,
        body="updated report",
        token="secret-token",
        opener=fake_opener,
    )

    assert comment_url.endswith("#issuecomment-99")
    assert [call["method"] for call in calls] == ["GET", "PATCH"]
    assert calls[1]["url"] == "https://api.github.com/repos/octo/example/issues/comments/99"
    assert "updated report" in json.loads(calls[1]["body"])["body"]


def test_request_pull_request_reviewers_posts_users_and_teams() -> None:
    calls = []

    def fake_opener(request, timeout):
        calls.append(
            {
                "url": request.full_url,
                "method": request.get_method(),
                "headers": dict(request.header_items()),
                "body": request.data.decode("utf-8") if request.data else "",
                "timeout": timeout,
            }
        )
        return FakeResponse(json.dumps({"requested_reviewers": [{"login": "alice"}]}))

    result = request_pull_request_reviewers(
        repo="octo/example",
        pr_number=123,
        reviewers=["alice", "alice"],
        team_reviewers=["security-team"],
        token="secret-token",
        opener=fake_opener,
    )

    assert result["requested"] is True
    assert result["reviewers"] == ["alice"]
    assert result["team_reviewers"] == ["security-team"]
    assert calls[0]["url"] == "https://api.github.com/repos/octo/example/pulls/123/requested_reviewers"
    assert calls[0]["method"] == "POST"
    assert calls[0]["headers"]["Accept"] == GITHUB_JSON_ACCEPT
    assert calls[0]["headers"]["Authorization"] == "Bearer secret-token"
    assert calls[0]["timeout"] == 30
    assert json.loads(calls[0]["body"]) == {
        "reviewers": ["alice"],
        "team_reviewers": ["security-team"],
    }


def test_request_pull_request_reviewers_noops_when_empty_without_token(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    result = request_pull_request_reviewers(
        repo="octo/example",
        pr_number=123,
        reviewers=[],
        team_reviewers=[],
    )

    assert result["requested"] is False
    assert result["message"] == "No GitHub reviewers to request."


def test_request_pull_request_reviewers_http_error_does_not_include_token() -> None:
    def fake_opener(_request, timeout):
        assert timeout == 30
        raise HTTPError(
            url="https://api.github.com/repos/octo/example/pulls/123/requested_reviewers",
            code=422,
            msg="Validation Failed",
            hdrs=None,
            fp=None,
        )

    try:
        request_pull_request_reviewers(
            repo="octo/example",
            pr_number=123,
            reviewers=["alice"],
            team_reviewers=[],
            token="secret-token",
            opener=fake_opener,
        )
    except GitHubIntegrationError as exc:
        assert "HTTP 422" in str(exc)
        assert "secret-token" not in str(exc)
    else:
        raise AssertionError("Expected GitHubIntegrationError")


def test_create_or_update_check_run_posts_completed_check_payload() -> None:
    calls = []

    def fake_opener(request, timeout):
        calls.append(
            {
                "url": request.full_url,
                "method": request.get_method(),
                "headers": dict(request.header_items()),
                "body": request.data.decode("utf-8") if request.data else "",
                "timeout": timeout,
            }
        )
        return FakeResponse(json.dumps({"html_url": "https://github.com/octo/example/runs/1"}))

    response = create_or_update_check_run(
        repo="octo/example",
        head_sha="abc123",
        name="AgentReviewOps",
        title="AgentReviewOps policy gate",
        summary="1 changed file, high risk.",
        text="Detailed findings.",
        conclusion="failure",
        annotations=[
            CheckRunAnnotation(
                path="auth/session.py",
                start_line=12,
                end_line=12,
                annotation_level="failure",
                message="A critical path changed.",
                title="Critical path changed",
                raw_details="Rule: critical-path-change",
            )
        ],
        token="secret-token",
        opener=fake_opener,
    )

    assert response["html_url"].endswith("/runs/1")
    assert calls[0]["url"] == "https://api.github.com/repos/octo/example/check-runs"
    assert calls[0]["method"] == "POST"
    assert calls[0]["headers"]["Accept"] == GITHUB_JSON_ACCEPT
    assert calls[0]["headers"]["Authorization"] == "Bearer secret-token"
    assert calls[0]["timeout"] == 30
    payload = json.loads(calls[0]["body"])
    assert payload["name"] == "AgentReviewOps"
    assert payload["head_sha"] == "abc123"
    assert payload["status"] == "completed"
    assert payload["conclusion"] == "failure"
    assert payload["output"]["title"] == "AgentReviewOps policy gate"
    assert payload["output"]["summary"] == "1 changed file, high risk."
    assert payload["output"]["text"] == "Detailed findings."
    assert payload["output"]["annotations"] == [
        {
            "path": "auth/session.py",
            "start_line": 12,
            "end_line": 12,
            "annotation_level": "failure",
            "message": "A critical path changed.",
            "title": "Critical path changed",
            "raw_details": "Rule: critical-path-change",
        }
    ]


def test_create_or_update_check_run_rejects_unsupported_conclusion() -> None:
    try:
        create_or_update_check_run(
            repo="octo/example",
            head_sha="abc123",
            name="AgentReviewOps",
            title="AgentReviewOps policy gate",
            summary="summary",
            conclusion="cancelled",
            token="secret-token",
        )
    except GitHubIntegrationError as exc:
        assert "success, neutral, or failure" in str(exc)
    else:
        raise AssertionError("Expected GitHubIntegrationError")


def test_scan_pr_writes_report_without_printing_token(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()
    output_path = tmp_path / "pr-report.md"
    json_output_path = tmp_path / "pr-report.json"
    sarif_output_path = tmp_path / "pr-report.sarif.json"
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
            "--json-output",
            str(json_output_path),
            "--sarif-output",
            str(sarif_output_path),
        ],
    )

    assert result.exit_code == 0
    assert "GitHub PR: octo/example#123" in result.output
    assert "secret-token" not in result.output
    assert output_path.exists()
    payload = json.loads(json_output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == "scan-pr"
    assert payload["changed_files"][0]["path"] == "README.md"
    sarif = json.loads(sarif_output_path.read_text(encoding="utf-8"))
    assert sarif["version"] == "2.1.0"
    assert sarif["runs"][0]["tool"]["driver"]["name"] == "AgentReviewOps"


def test_scan_pr_checks_requires_head_sha(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")

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
            "--checks",
        ],
    )

    assert result.exit_code == 2
    assert "--checks requires --head-sha" in result.output


def test_scan_pr_fail_on_high_exits_after_writing_report(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()
    project_root = Path(__file__).parents[1]
    output_path = tmp_path / "pr-report.md"
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    monkeypatch.setattr(
        "agentreview.cli.fetch_pull_request_diff",
        lambda **_kwargs: (project_root / "examples" / "sample.diff").read_text(encoding="utf-8"),
    )

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
            "--fail-on",
            "high",
        ],
    )

    assert result.exit_code == 1
    assert "GitHub PR: octo/example#123" in result.output
    assert "CI gate failed: risk HIGH" in result.output
    assert "secret-token" not in result.output
    assert output_path.exists()


def test_scan_pr_can_publish_comment(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()
    output_path = tmp_path / "pr-report.md"
    calls = []
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    monkeypatch.setattr("agentreview.cli.fetch_pull_request_diff", lambda **_kwargs: SAMPLE_DIFF)

    def fake_comment(**kwargs):
        calls.append(kwargs)
        return "https://github.com/octo/example/pull/123#issuecomment-1"

    monkeypatch.setattr("agentreview.cli.upsert_pull_request_comment", fake_comment)

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
            "--comment",
        ],
    )

    assert result.exit_code == 0
    assert "GitHub comment: https://github.com/octo/example/pull/123#issuecomment-1" in result.output
    assert calls[0]["repo"] == "octo/example"
    assert calls[0]["pr_number"] == 123
    assert calls[0]["body"].startswith("# AgentReviewOps Report")
    assert "secret-token" not in result.output


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


def test_comment_pr_posts_existing_report_without_printing_token(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()
    report_path = tmp_path / "agentreview-report.md"
    report_path.write_text("# AgentReviewOps Report\n", encoding="utf-8")
    calls = []
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")

    def fake_comment(**kwargs):
        calls.append(kwargs)
        return "https://github.com/octo/example/pull/123#issuecomment-1"

    monkeypatch.setattr("agentreview.cli.upsert_pull_request_comment", fake_comment)

    result = runner.invoke(
        app,
        [
            "comment-pr",
            "--repo",
            "octo/example",
            "--pr",
            "123",
            "--report-file",
            str(report_path),
        ],
    )

    assert result.exit_code == 0
    assert "GitHub PR: octo/example#123" in result.output
    assert "GitHub comment: https://github.com/octo/example/pull/123#issuecomment-1" in result.output
    assert calls[0]["body"] == "# AgentReviewOps Report\n"
    assert "secret-token" not in result.output
