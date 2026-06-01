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


def test_composite_action_yaml_is_valid() -> None:
    action = yaml.safe_load((PROJECT_ROOT / "examples" / "github-action" / "action.yml").read_text(encoding="utf-8"))

    assert action["name"] == "AgentReviewOps scan-diff"
    assert action["runs"]["using"] == "composite"
    assert "diff-file" in action["inputs"]
    assert "api-url" in action["inputs"]
    assert "api-key" in action["inputs"]
    assert "github-comment" in action["inputs"]
    assert "github-token" in action["inputs"]
    assert 'python -m pip install -e "$GITHUB_ACTION_PATH"' in str(action["runs"]["steps"])
    assert "agentreview submit-diff" in str(action["runs"]["steps"])
    assert "agentreview comment-pr" in str(action["runs"]["steps"])


def test_github_action_docs_explain_artifact_flow() -> None:
    docs = (PROJECT_ROOT / "docs" / "github-action.md").read_text(encoding="utf-8")

    assert "agentreview scan-diff" in docs
    assert "agentreview submit-diff" in docs
    assert "agentreview comment-pr" in docs
    assert "Shen-3/agentreviewops/examples/github-action@main" in docs
    assert "$GITHUB_ACTION_PATH" in docs
    assert "actions/upload-artifact@v4" in docs
    assert "pull-requests: write" in docs
