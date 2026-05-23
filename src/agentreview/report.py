from __future__ import annotations

from agentreview.ai import DiffSummaryResult
from agentreview.models import AgentReviewConfig, DiffFile, RiskAnalysis, RiskFinding


def generate_markdown_report(
    analysis: RiskAnalysis,
    changed_files: list[DiffFile],
    config: AgentReviewConfig | None = None,
    ai_summary: DiffSummaryResult | None = None,
) -> str:
    active_config = config or AgentReviewConfig()
    sections = [
        "# AgentReviewOps Report",
        "",
        f"Risk: {analysis.risk_level.upper()} ({analysis.risk_score}/100)",
        "",
        "## Summary",
        "",
        _build_summary(analysis, changed_files),
    ]
    if ai_summary is not None:
        sections.extend(["", "## AI Summary", "", _build_ai_summary(ai_summary)])

    sections.extend([
        "",
        "## Findings",
        "",
        _build_findings_table(analysis.findings),
        "",
        "## Human Review Checklist",
        "",
        _build_checklist(analysis.findings),
        "",
        "## Changed Files",
        "",
        _build_changed_files_table(changed_files),
        "",
        "## Policy Config Used",
        "",
        _build_config_summary(active_config),
    ])
    return "\n".join(sections).rstrip() + "\n"


def _build_summary(analysis: RiskAnalysis, changed_files: list[DiffFile]) -> str:
    if not changed_files:
        return "No changed files were detected in the supplied diff."

    positive_findings = [finding for finding in analysis.findings if finding.score_delta > 0]
    if not positive_findings:
        return f"{len(changed_files)} file(s) changed with no positive risk findings from the configured deterministic rules."

    return (
        f"{len(changed_files)} file(s) changed with {len(positive_findings)} positive risk finding(s). "
        f"Review the {analysis.risk_level.upper()} risk areas before merge."
    )


def _build_ai_summary(ai_summary: DiffSummaryResult) -> str:
    lines = [ai_summary.summary]
    if ai_summary.checklist:
        lines.extend(["", "### AI Checklist", ""])
        lines.extend(f"- [ ] {item}" for item in ai_summary.checklist)
    return "\n".join(lines)


def _build_findings_table(findings: list[RiskFinding]) -> str:
    lines = [
        "| Severity | Rule | File | Reason |",
        "|---|---|---|---|",
    ]
    if not findings:
        lines.append("| INFO | none | Change set | No findings produced by the configured rules. |")
        return "\n".join(lines)

    for finding in findings:
        score = _format_score_delta(finding.score_delta)
        lines.append(
            "| "
            f"{_escape_table_cell(finding.severity.upper())} | "
            f"{_escape_table_cell(finding.rule_id)} | "
            f"{_escape_table_cell(finding.file_path or 'Change set')} | "
            f"{_escape_table_cell(finding.description)} Score {score}. |"
        )
    return "\n".join(lines)


def _build_checklist(findings: list[RiskFinding]) -> str:
    checklist_by_rule = {
        "critical-path-change": "Verify critical-path changes are intentional and scoped.",
        "dependency-change": "Confirm dependency changes are intentional and trusted.",
        "ci-change": "Confirm CI/CD changes do not weaken build, test, or release controls.",
        "sensitive-area-change": "Review auth, security, or payments behavior with a human owner.",
        "missing-tests": "Require tests for changed behavior or document why tests are not needed.",
        "large-diff": "Split review by subsystem and inspect the highest-risk files first.",
        "generated-file-added": "Confirm generated or minified artifacts come from a trusted source.",
        "database-migration-change": "Verify migration order, rollback behavior, and compatibility.",
        "missing-docs": "Confirm whether behavior changes require documentation updates.",
    }
    items: list[str] = []
    seen: set[str] = set()
    for finding in findings:
        item = checklist_by_rule.get(finding.rule_id)
        if item is not None and item not in seen:
            seen.add(item)
            items.append(f"- [ ] {item}")

    if not items:
        return "- [ ] Confirm the change matches the pull request intent."
    return "\n".join(items)


def _build_changed_files_table(changed_files: list[DiffFile]) -> str:
    lines = [
        "| File | Status | + | - | Critical | Test |",
        "|---|---|---:|---:|---|---|",
    ]
    if not changed_files:
        lines.append("| none | none | 0 | 0 | no | no |")
        return "\n".join(lines)

    for changed_file in changed_files:
        lines.append(
            "| "
            f"{_escape_table_cell(_format_changed_path(changed_file))} | "
            f"{changed_file.status} | "
            f"{changed_file.additions} | "
            f"{changed_file.deletions} | "
            f"{_format_bool(changed_file.is_critical_file)} | "
            f"{_format_bool(changed_file.is_test_file)} |"
        )
    return "\n".join(lines)


def _build_config_summary(config: AgentReviewConfig) -> str:
    enabled_rules = [
        name
        for name, enabled in config.rules.model_dump().items()
        if enabled
    ]
    return "\n".join(
        [
            f"- Version: {config.version}",
            f"- Fail level: {config.risk.fail_level}",
            f"- Large diff threshold: {config.risk.large_diff.max_files} files / {config.risk.large_diff.max_lines} lines",
            f"- Critical paths: {len(config.critical_paths)} configured",
            f"- Test patterns: {', '.join(config.test_patterns)}",
            f"- Enabled rules: {', '.join(enabled_rules) if enabled_rules else 'none'}",
        ]
    )


def _format_changed_path(changed_file: DiffFile) -> str:
    if changed_file.previous_path and changed_file.previous_path != changed_file.path:
        return f"{changed_file.previous_path} -> {changed_file.path}"
    return changed_file.path


def _format_bool(value: bool) -> str:
    return "yes" if value else "no"


def _format_score_delta(score_delta: int) -> str:
    if score_delta > 0:
        return f"+{score_delta}"
    return str(score_delta)


def _escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
