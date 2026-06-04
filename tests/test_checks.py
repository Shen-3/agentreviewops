from agentreview.analysis import AnalysisExecutionResult
from agentreview.checks import analysis_to_check_run_content
from agentreview.models import DiffFile, ReviewRequirement, RiskAnalysis, RiskFinding


def test_check_run_conclusion_is_failure_when_fail_on_threshold_matches() -> None:
    result = _analysis_result(
        risk_level="high",
        risk_score=70,
        findings=[
            RiskFinding(
                rule_id="critical-path-change",
                severity="high",
                title="Critical path changed",
                description="A critical file changed.",
                score_delta=30,
                file_path="auth/session.py",
                line_start=12,
            )
        ],
    )

    content = analysis_to_check_run_content(result, fail_on="high")

    assert content.conclusion == "failure"
    assert content.annotations[0].annotation_level == "failure"


def test_check_run_conclusion_is_neutral_for_findings_below_threshold() -> None:
    result = _analysis_result(
        risk_level="medium",
        risk_score=35,
        findings=[
            RiskFinding(
                rule_id="dependency-change",
                severity="medium",
                title="Dependency metadata changed",
                description="Dependency files changed.",
                score_delta=20,
                file_path="pyproject.toml",
                line_start=3,
                line_end=5,
            )
        ],
    )

    content = analysis_to_check_run_content(result, fail_on="high")

    assert content.conclusion == "neutral"
    assert content.annotations[0].annotation_level == "warning"
    assert content.annotations[0].end_line == 5


def test_check_run_conclusion_is_success_without_positive_findings() -> None:
    result = _analysis_result(
        risk_level="low",
        risk_score=0,
        findings=[
            RiskFinding(
                rule_id="small-focused-diff",
                severity="info",
                title="Small focused diff",
                description="The change set is small.",
                score_delta=-5,
            )
        ],
    )

    content = analysis_to_check_run_content(result, fail_on="never")

    assert content.conclusion == "success"
    assert content.annotations == []


def test_check_run_omits_annotations_without_locations_and_notes_summary() -> None:
    result = _analysis_result(
        risk_level="medium",
        risk_score=35,
        findings=[
            RiskFinding(
                rule_id="large-diff",
                severity="medium",
                title="Large diff",
                description="The change set is large.",
                score_delta=25,
            )
        ],
    )

    content = analysis_to_check_run_content(result, fail_on="high")

    assert content.annotations == []
    assert "omitted from check annotations because no file/line location was available" in content.summary


def test_check_run_caps_annotations_and_notes_omissions() -> None:
    findings = [
        RiskFinding(
            rule_id=f"generated-{index}",
            severity="low",
            title=f"Generated finding {index}",
            description="Generated test finding.",
            score_delta=1,
            file_path=f"src/file_{index}.py",
            line_start=1,
        )
        for index in range(4)
    ]
    result = _analysis_result(risk_level="low", risk_score=4, findings=findings)

    content = analysis_to_check_run_content(result, fail_on="high", annotation_limit=2)

    assert len(content.annotations) == 2
    assert all(annotation.annotation_level == "notice" for annotation in content.annotations)
    assert "2 finding(s) were omitted from check annotations because the annotation output is capped at 2" in content.summary


def _analysis_result(
    *,
    risk_level: str,
    risk_score: int,
    findings: list[RiskFinding],
) -> AnalysisExecutionResult:
    return AnalysisExecutionResult(
        changed_files=[DiffFile(path="auth/session.py", status="modified", additions=1, deletions=0)],
        analysis=RiskAnalysis(risk_level=risk_level, risk_score=risk_score, findings=findings),
        review_requirements=[
            ReviewRequirement(
                requirement_id="security-review",
                title="Security review",
                reason="Sensitive path changed.",
            )
        ],
        markdown="# AgentReviewOps Report\n",
    )
