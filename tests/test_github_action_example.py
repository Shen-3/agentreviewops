from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).parents[1]


def test_tests_workflow_yaml_is_valid() -> None:
    workflow = yaml.safe_load((PROJECT_ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8"))

    assert workflow["name"] == "Tests"
    assert "test" in workflow["jobs"]
    assert workflow["jobs"]["test"]["runs-on"] == "ubuntu-latest"


def test_composite_action_yaml_is_valid() -> None:
    action = yaml.safe_load((PROJECT_ROOT / "examples" / "github-action" / "action.yml").read_text(encoding="utf-8"))

    assert action["name"] == "AgentReviewOps scan-diff"
    assert action["runs"]["using"] == "composite"
    assert "diff-file" in action["inputs"]


def test_github_action_docs_explain_artifact_flow() -> None:
    docs = (PROJECT_ROOT / "docs" / "github-action.md").read_text(encoding="utf-8")

    assert "agentreview scan-diff" in docs
    assert "actions/upload-artifact@v4" in docs
    assert "does not yet post PR comments" in docs
