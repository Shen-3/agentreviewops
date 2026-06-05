import json
from pathlib import Path

from agentreview.analysis import AnalysisExecutionResult
from agentreview.analysis_output import build_analysis_json_payload, write_analysis_json_output
from agentreview.models import DiffFile, RiskAnalysis, RiskFinding


def test_analysis_json_payload_redacts_secret_like_finding_evidence() -> None:
    payload = build_analysis_json_payload(
        _analysis_result(),
        fail_on="high",
        source="test",
    )

    payload_text = json.dumps(payload)

    assert "ghp_1234567890" not in payload_text
    assert "hunter2" not in payload_text
    assert "[REDACTED]" in payload_text


def test_write_analysis_json_output_redacts_secret_like_finding_evidence(tmp_path: Path) -> None:
    output_path = tmp_path / "analysis.json"

    write_analysis_json_output(output_path, _analysis_result(), fail_on="high", source="test")

    payload_text = output_path.read_text(encoding="utf-8")
    assert "ghp_1234567890" not in payload_text
    assert "hunter2" not in payload_text


def _analysis_result() -> AnalysisExecutionResult:
    return AnalysisExecutionResult(
        changed_files=[DiffFile(path="settings.py", status="modified", additions=1, deletions=0)],
        analysis=RiskAnalysis(
            risk_score=60,
            risk_level="high",
            findings=[
                RiskFinding(
                    rule_id="secret-like-change",
                    severity="high",
                    title="Token changed",
                    description="A line changed with token=ghp_1234567890.",
                    score_delta=30,
                    file_path="settings.py",
                    line_start=1,
                    evidence={"password": "hunter2", "line": "token=ghp_1234567890"},
                )
            ],
        ),
        review_requirements=[],
        markdown="# AgentReviewOps Report\n",
    )
