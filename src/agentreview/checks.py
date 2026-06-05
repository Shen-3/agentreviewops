from __future__ import annotations

from dataclasses import dataclass

from agentreview.analysis import AnalysisExecutionResult
from agentreview.analysis_output import build_analysis_summary, should_fail_for_threshold
from agentreview.integrations.github import CheckRunAnnotation
from agentreview.models import RiskFinding
from agentreview.security import redact_text

CHECK_ANNOTATION_LIMIT = 50


@dataclass(frozen=True)
class CheckRunContent:
    conclusion: str
    summary: str
    text: str
    annotations: list[CheckRunAnnotation]


def analysis_to_check_run_content(
    result: AnalysisExecutionResult,
    *,
    fail_on: str,
    annotation_limit: int = CHECK_ANNOTATION_LIMIT,
) -> CheckRunContent:
    positive_findings = [finding for finding in result.analysis.findings if finding.score_delta > 0]
    annotations, missing_location_count, capped_count = _annotations_for_findings(
        positive_findings,
        annotation_limit=annotation_limit,
    )
    summary_lines = [
        build_analysis_summary(result),
        f"{len(positive_findings)} positive finding(s), {len(result.review_requirements)} review requirement(s).",
    ]
    if missing_location_count:
        summary_lines.append(
            f"{missing_location_count} finding(s) were omitted from check annotations because no file/line "
            "location was available."
        )
    if capped_count:
        summary_lines.append(
            f"{capped_count} finding(s) were omitted from check annotations because the annotation output is capped "
            f"at {annotation_limit}."
        )
    return CheckRunContent(
        conclusion=_check_conclusion(result, fail_on=fail_on, positive_findings=positive_findings),
        summary="\n".join(summary_lines),
        text=_check_text(result, positive_findings),
        annotations=annotations,
    )


def _check_conclusion(
    result: AnalysisExecutionResult,
    *,
    fail_on: str,
    positive_findings: list[RiskFinding],
) -> str:
    if should_fail_for_threshold(result.analysis.risk_level, fail_on):
        return "failure"
    if positive_findings:
        return "neutral"
    return "success"


def _annotations_for_findings(
    findings: list[RiskFinding],
    *,
    annotation_limit: int,
) -> tuple[list[CheckRunAnnotation], int, int]:
    annotations: list[CheckRunAnnotation] = []
    missing_location_count = 0
    capped_count = 0

    for finding in findings:
        if finding.file_path is None or finding.line_start is None:
            missing_location_count += 1
            continue
        if len(annotations) >= annotation_limit:
            capped_count += 1
            continue
        annotations.append(
            CheckRunAnnotation(
                path=finding.file_path,
                start_line=finding.line_start,
                end_line=finding.line_end or finding.line_start,
                annotation_level=_annotation_level(finding),
                message=redact_text(finding.description),
                title=redact_text(finding.title),
                raw_details=f"Rule: {finding.rule_id}; severity: {finding.severity}",
            )
        )

    return annotations, missing_location_count, capped_count


def _annotation_level(finding: RiskFinding) -> str:
    if finding.severity in {"critical", "high"}:
        return "failure"
    if finding.severity == "medium":
        return "warning"
    return "notice"


def _check_text(result: AnalysisExecutionResult, positive_findings: list[RiskFinding]) -> str:
    if not positive_findings:
        return "No positive deterministic risk findings were produced by the configured policy."

    lines = ["## Findings", ""]
    for finding in positive_findings:
        location = finding.file_path or "change set"
        if finding.line_start is not None:
            location = f"{location}:{finding.line_start}"
        lines.append(f"- {finding.severity.upper()} `{finding.rule_id}` at {location}: {redact_text(finding.title)}")

    if result.review_requirements:
        lines.extend(["", "## Required Human Review", ""])
        for requirement in result.review_requirements:
            lines.append(f"- {redact_text(requirement.title)}: {redact_text(requirement.reason)}")
    return "\n".join(lines)
