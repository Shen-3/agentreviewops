from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import PurePosixPath
import re

from agentreview.models import AddedDiffLine, AgentReviewConfig, DiffFile, RiskAnalysis, RiskFinding, RiskLevel

CODE_LANGUAGES = {
    "go",
    "javascript",
    "python",
    "ruby",
    "rust",
    "typescript",
}

DEPENDENCY_PATTERNS = [
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lockb",
    "pyproject.toml",
    "poetry.lock",
    "requirements*.txt",
    "uv.lock",
]

CI_PATTERNS = [
    ".github/workflows/**",
    ".gitlab-ci.yml",
    "circleci/**",
    ".circleci/**",
]

SENSITIVE_PATTERNS = [
    "auth/**",
    "security/**",
    "payments/**",
    "**/auth/**",
    "**/security/**",
    "**/payments/**",
]

DOC_PATTERNS = [
    "README*",
    "docs/**",
    "**/*.md",
    "**/*.mdx",
    "**/*.rst",
]

GENERATED_PATTERNS = [
    "**/*.min.js",
    "**/*.min.css",
    "**/generated/**",
    "**/__generated__/**",
]

MIGRATION_PATTERNS = [
    "**/migrations/**",
    "**/*migration*",
]

GITHUB_WORKFLOW_PATTERNS = [
    ".github/workflows/**",
]

WRITE_ALL_PERMISSIONS_RE = re.compile(r"^\s*permissions\s*:\s*['\"]?write-all['\"]?\s*(?:#.*)?$", re.IGNORECASE)
GITHUB_ACTION_USES_RE = re.compile(r"^\s*(?:-\s*)?uses\s*:\s*(?P<action>[^#\s]+)")
PYTHON_SUBPROCESS_SHELL_TRUE_RE = re.compile(r"\bshell\s*=\s*True\b")
PYTHON_EVAL_EXEC_RE = re.compile(r"(?<![\w.])(?:eval|exec)\s*\(")
PYTHON_UNSAFE_YAML_LOAD_RE = re.compile(r"(?<![\w.])yaml\.load\s*\(")


def analyze_risk(
    changed_files: list[DiffFile],
    config: AgentReviewConfig | None = None,
    plugin_findings: list[RiskFinding] | None = None,
) -> RiskAnalysis:
    active_config = config or AgentReviewConfig()
    findings: list[RiskFinding] = []

    _add_file_findings(changed_files, active_config, findings)
    _add_change_set_findings(changed_files, active_config, findings)
    if plugin_findings:
        findings.extend(plugin_findings)

    score = _clamp_score(sum(finding.score_delta for finding in findings))
    return RiskAnalysis(
        risk_score=score,
        risk_level=calculate_risk_level(score),
        findings=findings,
    )


def calculate_risk_level(score: int) -> RiskLevel:
    if score >= 75:
        return "block"
    if score >= 50:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def _add_file_findings(
    changed_files: list[DiffFile],
    config: AgentReviewConfig,
    findings: list[RiskFinding],
) -> None:
    for changed_file in changed_files:
        paths = _paths_for_file(changed_file)

        if changed_file.is_critical_file or _matches_any(paths, config.critical_paths):
            findings.append(
                RiskFinding(
                    rule_id="critical-path-change",
                    severity="high",
                    title="Critical path changed",
                    description=f"{changed_file.path} matches a configured critical path.",
                    score_delta=20,
                    file_path=changed_file.path,
                )
            )

        if config.rules.flag_dependency_changes and _matches_any(paths, DEPENDENCY_PATTERNS):
            findings.append(
                RiskFinding(
                    rule_id="dependency-change",
                    severity="medium",
                    title="Dependency file changed",
                    description=f"{changed_file.path} changes project dependency metadata.",
                    score_delta=15,
                    file_path=changed_file.path,
                )
            )

        if config.rules.flag_ci_changes and _matches_any(paths, CI_PATTERNS):
            findings.append(
                RiskFinding(
                    rule_id="ci-change",
                    severity="medium",
                    title="CI/CD workflow changed",
                    description=f"{changed_file.path} changes automation or release infrastructure.",
                    score_delta=15,
                    file_path=changed_file.path,
                )
            )

        if config.rules.flag_auth_changes and _matches_any(paths, SENSITIVE_PATTERNS):
            findings.append(
                RiskFinding(
                    rule_id="sensitive-area-change",
                    severity="high",
                    title="Sensitive product area changed",
                    description=f"{changed_file.path} is in auth, security, or payments code.",
                    score_delta=20,
                    file_path=changed_file.path,
                )
            )

        if config.rules.flag_large_generated_files and changed_file.status == "added" and _matches_any(paths, GENERATED_PATTERNS):
            findings.append(
                RiskFinding(
                    rule_id="generated-file-added",
                    severity="medium",
                    title="Generated or minified file added",
                    description=f"{changed_file.path} looks generated or minified and should be reviewed carefully.",
                    score_delta=10,
                    file_path=changed_file.path,
                )
            )

        if _matches_any(paths, MIGRATION_PATTERNS):
            findings.append(
                RiskFinding(
                    rule_id="database-migration-change",
                    severity="medium",
                    title="Database migration changed",
                    description=f"{changed_file.path} appears to modify database schema or migration history.",
                    score_delta=10,
                    file_path=changed_file.path,
                )
            )

        _add_added_line_findings(changed_file, findings)


def _add_added_line_findings(changed_file: DiffFile, findings: list[RiskFinding]) -> None:
    if not changed_file.added_lines:
        return

    paths = _paths_for_file(changed_file)
    if _matches_any(paths, GITHUB_WORKFLOW_PATTERNS):
        _add_github_actions_findings(changed_file, findings)

    if changed_file.language == "python":
        _add_python_dangerous_pattern_findings(changed_file, findings)


def _add_github_actions_findings(changed_file: DiffFile, findings: list[RiskFinding]) -> None:
    for added_line in _actionable_added_lines(changed_file.added_lines, comment_prefix="#"):
        line = added_line.content
        if WRITE_ALL_PERMISSIONS_RE.search(line):
            findings.append(
                _line_finding(
                    rule_id="github-actions-write-all-permissions",
                    severity="high",
                    title="GitHub Actions workflow grants write-all permissions",
                    description="The workflow grants broad write-all token permissions.",
                    score_delta=20,
                    file_path=changed_file.path,
                    added_line=added_line,
                )
            )

        if "pull_request_target" in line:
            findings.append(
                _line_finding(
                    rule_id="github-actions-pull-request-target",
                    severity="high",
                    title="GitHub Actions workflow uses pull_request_target",
                    description="pull_request_target runs with elevated repository context and requires careful review.",
                    score_delta=20,
                    file_path=changed_file.path,
                    added_line=added_line,
                )
            )

        action_ref = _extract_github_action_reference(line)
        if action_ref is not None and _is_unpinned_or_moving_action_ref(action_ref):
            findings.append(
                _line_finding(
                    rule_id="github-actions-unpinned-action",
                    severity="medium",
                    title="GitHub Actions step uses an unpinned or moving action reference",
                    description="The workflow references an external action without a stable tag or commit SHA.",
                    score_delta=15,
                    file_path=changed_file.path,
                    added_line=added_line,
                    evidence_extra={"action": action_ref},
                )
            )


def _add_python_dangerous_pattern_findings(changed_file: DiffFile, findings: list[RiskFinding]) -> None:
    for added_line in _actionable_added_lines(changed_file.added_lines, comment_prefix="#"):
        line = added_line.content
        if PYTHON_SUBPROCESS_SHELL_TRUE_RE.search(line):
            findings.append(
                _line_finding(
                    rule_id="python-subprocess-shell-true",
                    severity="high",
                    title="Python subprocess call enables shell=True",
                    description="shell=True can execute shell metacharacters when inputs are not tightly controlled.",
                    score_delta=20,
                    file_path=changed_file.path,
                    added_line=added_line,
                )
            )

        if PYTHON_EVAL_EXEC_RE.search(line):
            findings.append(
                _line_finding(
                    rule_id="python-eval-exec",
                    severity="high",
                    title="Python eval or exec added",
                    description="eval and exec can execute attacker-controlled code if inputs are not trusted.",
                    score_delta=20,
                    file_path=changed_file.path,
                    added_line=added_line,
                )
            )

        if PYTHON_UNSAFE_YAML_LOAD_RE.search(line) and "SafeLoader" not in line:
            findings.append(
                _line_finding(
                    rule_id="python-unsafe-yaml-load",
                    severity="high",
                    title="Python yaml.load without SafeLoader added",
                    description="yaml.load without SafeLoader can construct unsafe Python objects from untrusted YAML.",
                    score_delta=20,
                    file_path=changed_file.path,
                    added_line=added_line,
                )
            )


def _actionable_added_lines(added_lines: list[AddedDiffLine], *, comment_prefix: str) -> list[AddedDiffLine]:
    return [
        added_line
        for added_line in added_lines
        if added_line.content.strip() and not added_line.content.lstrip().startswith(comment_prefix)
    ]


def _line_finding(
    *,
    rule_id: str,
    severity: str,
    title: str,
    description: str,
    score_delta: int,
    file_path: str,
    added_line: AddedDiffLine,
    evidence_extra: dict | None = None,
) -> RiskFinding:
    evidence = {"line": added_line.content.strip()}
    if added_line.line_number is not None:
        evidence["line_number"] = added_line.line_number
    if evidence_extra:
        evidence.update(evidence_extra)
    return RiskFinding(
        rule_id=rule_id,
        severity=severity,
        title=title,
        description=description,
        score_delta=score_delta,
        file_path=file_path,
        line_start=added_line.line_number,
        line_end=added_line.line_number,
        evidence=evidence,
    )


def _extract_github_action_reference(line: str) -> str | None:
    match = GITHUB_ACTION_USES_RE.search(line)
    if match is None:
        return None
    action_ref = match.group("action").strip("'\"")
    if action_ref.startswith(("./", "../", "docker://")):
        return None
    return action_ref


def _is_unpinned_or_moving_action_ref(action_ref: str) -> bool:
    if "@" not in action_ref:
        return True
    ref = action_ref.rsplit("@", maxsplit=1)[1].lower()
    return ref in {"main", "master", "latest"}


def _add_change_set_findings(
    changed_files: list[DiffFile],
    config: AgentReviewConfig,
    findings: list[RiskFinding],
) -> None:
    total_lines = sum(file.additions + file.deletions for file in changed_files)
    production_files = [file for file in changed_files if _is_production_code(file)]
    test_files = [file for file in changed_files if file.is_test_file]
    docs_files = [file for file in changed_files if _is_docs_file(file)]

    if len(changed_files) > config.risk.large_diff.max_files or total_lines > config.risk.large_diff.max_lines:
        findings.append(
            RiskFinding(
                rule_id="large-diff",
                severity="medium",
                title="Large diff",
                description="The change exceeds configured file or line thresholds.",
                score_delta=10,
                evidence={
                    "files": len(changed_files),
                    "lines": total_lines,
                    "max_files": config.risk.large_diff.max_files,
                    "max_lines": config.risk.large_diff.max_lines,
                },
            )
        )

    if config.rules.require_tests_for_code_changes and production_files and not test_files:
        findings.append(
            RiskFinding(
                rule_id="missing-tests",
                severity="medium",
                title="Production code changed without tests",
                description="At least one source file changed, but no test files changed.",
                score_delta=15,
                evidence={"production_files": [file.path for file in production_files]},
            )
        )

    if production_files and not docs_files:
        findings.append(
            RiskFinding(
                rule_id="missing-docs",
                severity="low",
                title="Documentation absent for behavior change",
                description="Source files changed without accompanying documentation updates.",
                score_delta=5,
                evidence={"production_files": [file.path for file in production_files]},
            )
        )

    if test_files:
        findings.append(
            RiskFinding(
                rule_id="tests-updated",
                severity="info",
                title="Tests changed",
                description="Test files were added or updated with this change.",
                score_delta=-10,
                evidence={"test_files": [file.path for file in test_files]},
            )
        )

    if docs_files:
        findings.append(
            RiskFinding(
                rule_id="docs-updated",
                severity="info",
                title="Documentation changed",
                description="Documentation was updated with this change.",
                score_delta=-5,
                evidence={"docs_files": [file.path for file in docs_files]},
            )
        )

    if len(changed_files) == 1 and total_lines <= 20:
        findings.append(
            RiskFinding(
                rule_id="small-focused-diff",
                severity="info",
                title="Small focused diff",
                description="Only one file changed and the diff is within the small-change threshold.",
                score_delta=-5,
                evidence={"files": len(changed_files), "lines": total_lines},
            )
        )


def _is_production_code(changed_file: DiffFile) -> bool:
    return not changed_file.is_test_file and changed_file.language in CODE_LANGUAGES


def _is_docs_file(changed_file: DiffFile) -> bool:
    return _matches_any(_paths_for_file(changed_file), DOC_PATTERNS)


def _paths_for_file(changed_file: DiffFile) -> list[str]:
    paths = [changed_file.path]
    if changed_file.previous_path is not None:
        paths.append(changed_file.previous_path)
    return paths


def _matches_any(paths: list[str], patterns: list[str]) -> bool:
    return any(_matches_pattern(path, pattern) for path in paths for pattern in patterns)


def _matches_pattern(path: str, pattern: str) -> bool:
    normalized_path = path.strip("/")
    normalized_pattern = pattern.strip("/")
    if fnmatchcase(normalized_path, normalized_pattern):
        return True
    if normalized_pattern.startswith("**/"):
        return fnmatchcase(normalized_path, normalized_pattern[3:])
    return PurePosixPath(normalized_path).match(normalized_pattern)


def _clamp_score(score: int) -> int:
    return max(0, min(100, score))
