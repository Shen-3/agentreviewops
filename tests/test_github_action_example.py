from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).parents[1]


def test_tests_workflow_yaml_is_valid() -> None:
    workflow = yaml.safe_load((PROJECT_ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8"))

    assert workflow["name"] == "Tests"
    assert "python-test" in workflow["jobs"]
    assert "web-build" in workflow["jobs"]
    assert workflow["jobs"]["python-test"]["runs-on"] == "ubuntu-latest"
    assert workflow["jobs"]["web-build"]["runs-on"] == "ubuntu-latest"


def test_ci_workflow_yaml_is_valid() -> None:
    workflow = yaml.safe_load((PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))

    assert workflow["name"] == "CI"
    assert "quality" in workflow["jobs"]
    assert workflow["jobs"]["quality"]["runs-on"] == "ubuntu-latest"
    steps = str(workflow["jobs"]["quality"]["steps"])
    assert "astral-sh/setup-uv@v5" in steps
    assert "uv run pytest" in steps
    assert "pnpm/action-setup@v4" in steps
    assert "pnpm --filter agentreviewops-web build" in steps


def test_root_composite_action_yaml_is_valid() -> None:
    action = yaml.safe_load((PROJECT_ROOT / "action.yml").read_text(encoding="utf-8"))

    assert action["name"] == "AgentReviewOps"
    assert action["runs"]["using"] == "composite"
    assert "github-token" in action["inputs"]
    assert action["inputs"]["comment"]["default"] == "true"
    assert action["inputs"]["request-reviewers"]["default"] == "false"
    assert action["inputs"]["reviewer-request-mode"]["default"] == "users-and-teams"
    assert action["inputs"]["checks"]["default"] == "false"
    assert action["inputs"]["check-name"]["default"] == "AgentReviewOps"
    assert action["inputs"]["check-title"]["default"] == "AgentReviewOps policy gate"
    assert action["inputs"]["fail-on"]["default"] == "never"
    assert action["inputs"]["codeowners-file"]["default"] == ""
    assert "diff-file" in action["inputs"]
    assert "api-url" in action["inputs"]
    assert "api-key" in action["inputs"]
    steps = str(action["runs"]["steps"])
    assert 'python -m pip install -e "$GITHUB_ACTION_PATH"' in steps
    assert "git diff --no-ext-diff" in steps
    assert "agentreview scan-diff" in steps
    assert "--json-output" in steps
    assert "--checks" in steps
    assert "--head-sha" in steps
    assert "--check-name" in steps
    assert "agentreview request-reviewers" in steps
    assert "--reviewer-request-mode" in steps
    assert "--fail-on" in steps
    assert "--codeowners-file" in steps
    assert "agentreview submit-diff" in steps
    assert "agentreview comment-pr" in steps


def test_github_action_docs_explain_artifact_flow() -> None:
    docs = (PROJECT_ROOT / "docs" / "github-action.md").read_text(encoding="utf-8")

    assert "Shen-3/agentreviewops@main" in docs
    assert "fail-on: high" in docs
    assert "codeowners-file: .github/CODEOWNERS" in docs
    assert "Review Routing And CODEOWNERS" in docs
    assert "`--fail-on`" in docs
    assert "agentreview scan-diff" in docs
    assert "agentreview submit-diff" in docs
    assert "agentreview comment-pr" in docs
    assert "agentreview request-reviewers" in docs
    assert "request-reviewers: \"true\"" in docs
    assert "$GITHUB_ACTION_PATH" in docs
    assert "actions/checkout@v6" in docs
    assert "actions/setup-python@v6" in docs
    assert "actions/upload-artifact@v4" in docs
    assert "pull-requests: write" in docs
