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
    assert set(workflow["jobs"]) == {"python-quality", "postgres-migrations", "web-build"}
    assert workflow["jobs"]["python-quality"]["runs-on"] == "ubuntu-latest"
    assert workflow["jobs"]["postgres-migrations"]["runs-on"] == "ubuntu-latest"
    assert workflow["jobs"]["web-build"]["runs-on"] == "ubuntu-latest"

    python_steps = str(workflow["jobs"]["python-quality"]["steps"])
    assert "astral-sh/setup-uv@v5" in python_steps
    assert "uv run ruff check ." in python_steps
    assert "uv run ruff format --check ." in python_steps
    assert "uv run pytest --cov=agentreview --cov=agentreview_api --cov-report=term-missing" in python_steps
    assert "uv run alembic upgrade head" in python_steps
    assert "git diff --check" in python_steps

    postgres_job = workflow["jobs"]["postgres-migrations"]
    assert "postgres" in postgres_job["services"]
    assert "postgresql+psycopg://" in str(postgres_job["steps"])

    web_steps = str(workflow["jobs"]["web-build"]["steps"])
    assert "pnpm/action-setup@v4" in web_steps
    assert "pnpm --filter agentreviewops-web build" in web_steps
    assert "pnpm --filter agentreviewops-web lint" in web_steps


def test_root_composite_action_yaml_is_valid() -> None:
    action = yaml.safe_load((PROJECT_ROOT / "action.yml").read_text(encoding="utf-8"))

    assert action["name"] == "AgentReviewOps"
    assert action["author"] == "AgentReviewOps contributors"
    assert action["branding"]["icon"] == "shield"
    assert action["runs"]["using"] == "composite"
    assert "github-token" in action["inputs"]
    assert action["inputs"]["comment"]["default"] == "true"
    assert action["inputs"]["json-output"]["default"] == ""
    assert action["inputs"]["sarif-output"]["default"] == ""
    assert action["inputs"]["request-reviewers"]["default"] == "false"
    assert action["inputs"]["reviewer-request-mode"]["default"] == "users-and-teams"
    assert action["inputs"]["reviewer-request-failure-mode"]["default"] == "warn"
    assert action["inputs"]["checks"]["default"] == "false"
    assert action["inputs"]["check-name"]["default"] == "AgentReviewOps"
    assert action["inputs"]["check-title"]["default"] == "AgentReviewOps policy gate"
    assert action["inputs"]["fail-on"]["default"] == "never"
    assert action["inputs"]["codeowners-file"]["default"] == ""
    assert "diff-file" in action["inputs"]
    assert "api-url" in action["inputs"]
    assert "api-key" in action["inputs"]
    steps = str(action["runs"]["steps"])
    assert 'python -m pip install "$GITHUB_ACTION_PATH"' in steps
    assert "pip install -e" not in steps
    assert "git diff --no-ext-diff" in steps
    assert "agentreview scan-diff" in steps
    assert "--json-output" in steps
    assert "--checks" in steps
    assert "--sarif-output" in steps
    assert "--head-sha" in steps
    assert "--check-name" in steps
    assert "agentreview request-reviewers" in steps
    assert "--reviewer-request-mode" in steps
    assert "--reviewer-request-failure-mode" in steps
    assert "--fail-on" in steps
    assert "--codeowners-file" in steps
    assert "agentreview submit-diff" in steps
    assert "agentreview comment-pr" in steps


def test_action_self_test_workflow_is_read_only_and_uses_local_action() -> None:
    workflow = yaml.safe_load(
        (PROJECT_ROOT / ".github" / "workflows" / "action-self-test.yml").read_text(encoding="utf-8")
    )

    assert workflow["name"] == "Action Self Test"
    assert workflow["permissions"] == {"contents": "read"}
    steps = workflow["jobs"]["local-action"]["steps"]
    assert any(step.get("uses") == "./" for step in steps)
    steps_text = str(steps)
    assert "comment': 'false'" in steps_text
    assert "checks': 'false'" in steps_text
    assert "request-reviewers': 'false'" in steps_text
    assert "agentreview-self-test-report.json" in steps_text
    assert "agentreview-self-test.sarif.json" in steps_text
    assert "risk_score" in steps_text
    assert "risk_level" in steps_text
    assert "review_requirements" in steps_text
    assert "2.1.0" in steps_text


def test_github_action_docs_explain_artifact_flow() -> None:
    docs = (PROJECT_ROOT / "docs" / "github-action.md").read_text(encoding="utf-8")

    assert "Shen-3/agentreviewops@v0" in docs
    assert "Use `Shen-3/agentreviewops@main` only for development" in docs
    assert "fail-on: high" in docs
    assert "codeowners-file: .github/CODEOWNERS" in docs
    assert "Review Routing And CODEOWNERS" in docs
    assert "`--fail-on`" in docs
    assert "agentreview scan-diff" in docs
    assert "agentreview submit-diff" in docs
    assert "agentreview comment-pr" in docs
    assert "agentreview request-reviewers" in docs
    assert 'request-reviewers: "true"' in docs
    assert "$GITHUB_ACTION_PATH" in docs
    assert "actions/checkout@v6" in docs
    assert "actions/setup-python@v6" in docs
    assert "actions/upload-artifact@v4" in docs
    assert "pull-requests: write" in docs
    assert "checks: write" in docs
    assert "security-events: write" in docs


def test_release_docs_exist_and_document_validation() -> None:
    docs = (PROJECT_ROOT / "docs" / "release.md").read_text(encoding="utf-8")

    assert "uv sync --extra dev" in docs
    assert "uv run ruff check ." in docs
    assert "uv run ruff format --check ." in docs
    assert "uv run pytest --cov=agentreview --cov=agentreview_api --cov-report=term-missing" in docs
    assert "uv run alembic upgrade head" in docs
    assert "pnpm install --frozen-lockfile" in docs
    assert "pnpm --filter agentreviewops-web lint" in docs
    assert "git tag -a v0.x.y" in docs
    assert "git push origin -f v0" in docs


def test_docs_do_not_use_main_as_production_default() -> None:
    docs_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            PROJECT_ROOT / "README.md",
            PROJECT_ROOT / "docs" / "github-action.md",
            PROJECT_ROOT / "docs" / "sarif.md",
        ]
    )

    assert "uses: Shen-3/agentreviewops@main" not in docs_text
    assert "For production, pin to a release tag or a full commit SHA" in docs_text
