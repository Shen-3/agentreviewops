from __future__ import annotations

from agentreview.ai import DiffSummaryResult
from agentreview.models import AgentReviewConfig, DiffFile, ReviewRequirement, RiskAnalysis, RiskFinding, SuggestedReviewer


def generate_markdown_report(
    analysis: RiskAnalysis,
    changed_files: list[DiffFile],
    config: AgentReviewConfig | None = None,
    ai_summary: DiffSummaryResult | None = None,
    review_requirements: list[ReviewRequirement] | None = None,
) -> str:
    active_config = config or AgentReviewConfig()
    active_review_requirements = review_requirements or []
    sections = [
        f"# AgentReviewOps Report: {analysis.risk_level.upper()} risk ({analysis.risk_score}/100)",
        "",
        "## Merge recommendation",
        "",
        _build_merge_recommendation(analysis),
        "",
        _build_attention_summary(analysis, changed_files),
        "",
        "## Required human review",
        "",
        _build_review_requirements_table(active_review_requirements),
    ]
    if ai_summary is not None:
        sections.extend(["", "## AI Summary", "", _build_ai_summary(ai_summary)])

    sections.extend([
        "",
        "## Findings table",
        "",
        _build_findings_table(analysis.findings),
        "",
        "## Changed files summary",
        "",
        _build_changed_files_table(changed_files),
        "",
        "## Suggested human review checklist",
        "",
        _build_checklist(analysis.findings, active_review_requirements),
        "",
        "## Policy Config Used",
        "",
        _build_config_summary(active_config),
    ])
    return "\n".join(sections).rstrip() + "\n"


def _build_merge_recommendation(analysis: RiskAnalysis) -> str:
    recommendations = {
        "block": "Do not merge until required human review is complete.",
        "high": "Human review required before merge.",
        "medium": "Review recommended before merge.",
        "low": "No additional gate triggered by current policy.",
    }
    return recommendations[analysis.risk_level]


def _build_attention_summary(analysis: RiskAnalysis, changed_files: list[DiffFile]) -> str:
    heading = "Why this looks safe" if analysis.risk_level == "low" else "Why this requires attention"
    return f"## {heading}\n\n{_build_summary(analysis, changed_files)}"


def _build_summary(analysis: RiskAnalysis, changed_files: list[DiffFile]) -> str:
    if not changed_files:
        return "No changed files were detected in the supplied diff."

    positive_findings = [finding for finding in analysis.findings if finding.score_delta > 0]
    if not positive_findings:
        return f"{len(changed_files)} file(s) changed with no positive risk findings from the configured deterministic rules."

    highest_severity = _highest_positive_severity(positive_findings).upper()
    return (
        f"{len(changed_files)} file(s) changed with {len(positive_findings)} positive risk finding(s). "
        f"The highest deterministic finding severity is {highest_severity}; review the listed risk areas before merge."
    )


def _build_ai_summary(ai_summary: DiffSummaryResult) -> str:
    lines = [ai_summary.summary]
    if ai_summary.checklist:
        lines.extend(["", "### AI Checklist", ""])
        lines.extend(f"- [ ] {item}" for item in ai_summary.checklist)
    return "\n".join(lines)


def _build_findings_table(findings: list[RiskFinding]) -> str:
    lines = [
        "| Severity | Rule | Score | File | Reason |",
        "|---|---|---:|---|---|",
    ]
    if not findings:
        lines.append("| INFO | none | 0 | Change set | No findings produced by the configured rules. |")
        return "\n".join(lines)

    for finding in findings:
        score = _format_score_delta(finding.score_delta)
        lines.append(
            "| "
            f"{_escape_table_cell(finding.severity.upper())} | "
            f"{_escape_table_cell(finding.rule_id)} | "
            f"{score} | "
            f"{_escape_table_cell(finding.file_path or 'Change set')} | "
            f"{_escape_table_cell(finding.description)} |"
        )
    return "\n".join(lines)


def _build_review_requirements_table(review_requirements: list[ReviewRequirement]) -> str:
    if not review_requirements:
        return "No additional human review routing requirement was triggered by the current policy."

    lines = [
        "| Requirement | Reviewer source | Why |",
        "|---|---|---|",
    ]
    for requirement in review_requirements:
        lines.append(
            "| "
            f"{_escape_table_cell(requirement.title or requirement.requirement_id)} | "
            f"{_escape_table_cell(_format_reviewer_sources(requirement.suggested_reviewers))} | "
            f"{_escape_table_cell(_format_review_requirement_reason(requirement))} |"
        )
    return "\n".join(lines)


def _build_checklist(findings: list[RiskFinding], review_requirements: list[ReviewRequirement]) -> str:
    rule_ids = {finding.rule_id for finding in findings}
    items: list[str] = []

    if "missing-tests" in rule_ids:
        items.append("- [ ] Verify adequate tests were added, or document why tests are not required.")
    if {"critical-path-change", "sensitive-area-change"} & rule_ids:
        items.append("- [ ] Get security or code owner review for the sensitive or critical-path changes.")
    if "dependency-change" in rule_ids:
        items.append("- [ ] Review dependency changes for provenance, licensing, and lockfile consistency.")
    if "ci-change" in rule_ids:
        items.append("- [ ] Review CI/CD workflow changes for permission, secret, and release-control impact.")
    if "database-migration-change" in rule_ids:
        items.append("- [ ] Review migration order, backward compatibility, rollback behavior, and deployment timing.")
    if any(not requirement.suggested_reviewers for requirement in review_requirements):
        items.append("- [ ] Assign an appropriate reviewer for unconfigured review requirement(s).")
    if any(requirement.suggested_reviewers for requirement in review_requirements):
        items.append("- [ ] Confirm listed CODEOWNERS or repository reviewers approved the change.")

    high_or_medium_findings = [
        finding
        for finding in findings
        if finding.score_delta > 0 and finding.severity in {"medium", "high", "critical"}
    ]
    if not high_or_medium_findings:
        items.append("- [ ] Complete the normal code review and confirm the change matches the pull request intent.")
    elif not items:
        items.append("- [ ] Review the flagged high or medium findings with the relevant owner before merge.")

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


def _format_reviewer_sources(reviewers: list[SuggestedReviewer]) -> str:
    if not reviewers:
        return "Not configured"
    return ", ".join(_format_reviewer_source(reviewer) for reviewer in reviewers)


def _format_reviewer_source(reviewer: SuggestedReviewer) -> str:
    source_labels = {
        "codeowners": "CODEOWNERS",
        "repository_membership": "Repository membership",
    }
    return f"{source_labels.get(reviewer.source, reviewer.source)}: {reviewer.identifier}"


def _format_review_requirement_reason(requirement: ReviewRequirement) -> str:
    details: list[str] = []
    if requirement.matched_files:
        details.append(f"files: {', '.join(requirement.matched_files)}")
    if requirement.matched_rule_ids:
        details.append(f"rules: {', '.join(requirement.matched_rule_ids)}")
    if requirement.required_roles:
        details.append(f"roles: {', '.join(requirement.required_roles)}")
    if not details:
        return requirement.reason
    return f"{requirement.reason} ({'; '.join(details)})"


def _highest_positive_severity(findings: list[RiskFinding]) -> str:
    severity_order = {
        "info": 0,
        "low": 1,
        "medium": 2,
        "high": 3,
        "critical": 4,
    }
    return max(findings, key=lambda finding: severity_order[finding.severity]).severity


def _escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
