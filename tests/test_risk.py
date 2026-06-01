from agentreview.config import parse_config
from agentreview.gitdiff import parse_unified_diff
from agentreview.models import DiffFile
from agentreview.risk import analyze_risk, calculate_risk_level


def test_auth_change_without_tests_is_high_risk() -> None:
    changed_files = [
        DiffFile(
            path="auth/session.py",
            status="modified",
            additions=24,
            deletions=3,
            language="python",
            is_critical_file=True,
        )
    ]

    analysis = analyze_risk(changed_files)

    assert analysis.risk_score == 60
    assert analysis.risk_level == "high"
    assert _rule_ids(analysis) == [
        "critical-path-change",
        "sensitive-area-change",
        "missing-tests",
        "missing-docs",
    ]


def test_docs_only_change_is_low_risk() -> None:
    changed_files = [
        DiffFile(
            path="README.md",
            status="modified",
            additions=2,
            deletions=1,
            language="markdown",
        )
    ]

    analysis = analyze_risk(changed_files)

    assert analysis.risk_score == 0
    assert analysis.risk_level == "low"
    assert _rule_ids(analysis) == ["docs-updated", "small-focused-diff"]


def test_dependency_change_is_medium_risk_with_default_config() -> None:
    changed_files = [
        DiffFile(
            path="pyproject.toml",
            status="modified",
            additions=6,
            deletions=2,
            is_critical_file=True,
        )
    ]

    analysis = analyze_risk(changed_files)

    assert analysis.risk_score == 30
    assert analysis.risk_level == "medium"
    assert _rule_ids(analysis) == [
        "critical-path-change",
        "dependency-change",
        "small-focused-diff",
    ]


def test_source_change_with_tests_reduces_score() -> None:
    changed_files = [
        DiffFile(
            path="src/agentreview/cli.py",
            status="modified",
            additions=12,
            deletions=4,
            language="python",
        ),
        DiffFile(
            path="tests/test_cli.py",
            status="modified",
            additions=8,
            deletions=1,
            language="python",
            is_test_file=True,
        ),
    ]

    analysis = analyze_risk(changed_files)

    assert analysis.risk_score == 0
    assert analysis.risk_level == "low"
    assert _rule_ids(analysis) == ["missing-docs", "tests-updated"]


def test_large_diff_uses_configured_thresholds() -> None:
    config = parse_config(
        {
            "version": 1,
            "risk": {
                "large_diff": {
                    "max_files": 1,
                    "max_lines": 10,
                }
            },
        }
    )
    changed_files = [
        DiffFile(
            path="src/agentreview/config.py",
            status="modified",
            additions=9,
            deletions=3,
            language="python",
        )
    ]

    analysis = analyze_risk(changed_files, config=config)

    assert "large-diff" in _rule_ids(analysis)
    assert analysis.risk_score == 25
    assert analysis.risk_level == "medium"


def test_rule_toggles_disable_configured_findings() -> None:
    config = parse_config(
        {
            "version": 1,
            "rules": {
                "require_tests_for_code_changes": False,
                "flag_dependency_changes": False,
                "flag_ci_changes": True,
                "flag_auth_changes": False,
                "flag_large_generated_files": True,
            },
        }
    )
    changed_files = [
        DiffFile(
            path="auth/session.py",
            status="modified",
            additions=5,
            deletions=1,
            language="python",
            is_critical_file=True,
        ),
        DiffFile(
            path="pyproject.toml",
            status="modified",
            additions=2,
            deletions=1,
            is_critical_file=True,
        ),
    ]

    analysis = analyze_risk(changed_files, config=config)

    assert "missing-tests" not in _rule_ids(analysis)
    assert "dependency-change" not in _rule_ids(analysis)
    assert "sensitive-area-change" not in _rule_ids(analysis)
    assert analysis.risk_score == 45
    assert analysis.risk_level == "medium"


def test_github_actions_write_all_permissions_rule() -> None:
    analysis = _analysis_for_added_lines(
        ".github/workflows/agentreview.yml",
        ["permissions: write-all"],
    )

    finding = _finding_by_rule(analysis, "github-actions-write-all-permissions")
    assert finding.severity == "high"
    assert finding.score_delta == 20
    assert finding.file_path == ".github/workflows/agentreview.yml"
    assert finding.evidence["line"] == "permissions: write-all"


def test_github_actions_pull_request_target_rule() -> None:
    analysis = _analysis_for_added_lines(
        ".github/workflows/agentreview.yml",
        ["on:", "  pull_request_target:"],
    )

    finding = _finding_by_rule(analysis, "github-actions-pull-request-target")
    assert finding.severity == "high"
    assert finding.score_delta == 20
    assert finding.file_path == ".github/workflows/agentreview.yml"


def test_github_actions_unpinned_action_rule() -> None:
    analysis = _analysis_for_added_lines(
        ".github/workflows/agentreview.yml",
        ["jobs:", "  test:", "    steps:", "      - uses: actions/checkout@main"],
    )

    finding = _finding_by_rule(analysis, "github-actions-unpinned-action")
    assert finding.severity == "medium"
    assert finding.score_delta == 15
    assert finding.evidence["action"] == "actions/checkout@main"


def test_python_subprocess_shell_true_rule() -> None:
    analysis = _analysis_for_added_lines(
        "src/agentreview/runner.py",
        ["subprocess.run(command, shell=True)"],
    )

    finding = _finding_by_rule(analysis, "python-subprocess-shell-true")
    assert finding.severity == "high"
    assert finding.score_delta == 20
    assert finding.line_start == 1


def test_python_eval_exec_rule() -> None:
    analysis = _analysis_for_added_lines(
        "src/agentreview/runner.py",
        ["result = eval(user_input)"],
    )

    finding = _finding_by_rule(analysis, "python-eval-exec")
    assert finding.severity == "high"
    assert finding.score_delta == 20
    assert finding.evidence["line"] == "result = eval(user_input)"


def test_python_unsafe_yaml_load_rule() -> None:
    analysis = _analysis_for_added_lines(
        "src/agentreview/config_loader.py",
        ["config = yaml.load(raw_config)"],
    )

    finding = _finding_by_rule(analysis, "python-unsafe-yaml-load")
    assert finding.severity == "high"
    assert finding.score_delta == 20


def test_python_yaml_load_with_safe_loader_is_not_flagged() -> None:
    analysis = _analysis_for_added_lines(
        "src/agentreview/config_loader.py",
        ["config = yaml.load(raw_config, Loader=yaml.SafeLoader)"],
    )

    assert "python-unsafe-yaml-load" not in _rule_ids(analysis)


def test_calculate_risk_level_boundaries() -> None:
    assert calculate_risk_level(0) == "low"
    assert calculate_risk_level(24) == "low"
    assert calculate_risk_level(25) == "medium"
    assert calculate_risk_level(50) == "high"
    assert calculate_risk_level(75) == "block"
    assert calculate_risk_level(100) == "block"


def _rule_ids(analysis) -> list[str]:
    return [finding.rule_id for finding in analysis.findings]


def _finding_by_rule(analysis, rule_id: str):
    for finding in analysis.findings:
        if finding.rule_id == rule_id:
            return finding
    raise AssertionError(f"Expected finding {rule_id}")


def _analysis_for_added_lines(path: str, added_lines: list[str]):
    added_body = "\n".join(f"+{line}" for line in added_lines)
    diff_text = f"""diff --git a/{path} b/{path}
index 1111111..2222222 100644
--- a/{path}
+++ b/{path}
@@ -0,0 +1,{len(added_lines)} @@
{added_body}
"""
    return analyze_risk(parse_unified_diff(diff_text))
