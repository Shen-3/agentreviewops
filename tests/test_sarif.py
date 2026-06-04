import json

from agentreview.analysis import AnalysisExecutionResult
from agentreview.models import DiffFile, RiskAnalysis, RiskFinding
from agentreview.sarif import SARIF_SCHEMA, analysis_to_sarif


def test_analysis_to_sarif_includes_schema_and_tool_metadata() -> None:
    sarif = analysis_to_sarif(_analysis_result(), information_uri="https://example.com/agentreviewops")

    assert sarif["version"] == "2.1.0"
    assert sarif["$schema"] == SARIF_SCHEMA
    driver = sarif["runs"][0]["tool"]["driver"]
    assert driver["name"] == "AgentReviewOps"
    assert driver["informationUri"] == "https://example.com/agentreviewops"


def test_analysis_to_sarif_generates_rules_and_results() -> None:
    sarif = analysis_to_sarif(_analysis_result())
    run = sarif["runs"][0]

    assert [rule["id"] for rule in run["tool"]["driver"]["rules"]] == [
        "dependency-change",
        "python-eval-exec",
    ]
    assert [result["ruleId"] for result in run["results"]] == [
        "python-eval-exec",
        "dependency-change",
    ]


def test_analysis_to_sarif_maps_severity_levels() -> None:
    sarif = analysis_to_sarif(_analysis_result())

    assert [result["level"] for result in sarif["runs"][0]["results"]] == ["error", "warning"]


def test_analysis_to_sarif_maps_locations_when_line_data_exists() -> None:
    sarif = analysis_to_sarif(_analysis_result(), checkout_uri="file:///workspace")
    location = sarif["runs"][0]["results"][0]["locations"][0]["physicalLocation"]

    assert sarif["runs"][0]["originalUriBaseIds"]["SRCROOT"]["uri"] == "file:///workspace/"
    assert location["artifactLocation"] == {
        "uri": "auth/session.py",
        "uriBaseId": "SRCROOT",
    }
    assert location["region"] == {
        "startLine": 12,
        "endLine": 14,
    }


def test_analysis_to_sarif_allows_results_without_locations() -> None:
    result = _analysis_result(
        findings=[
            RiskFinding(
                rule_id="large-diff",
                severity="low",
                title="Large diff",
                description="The change set is large.",
                score_delta=5,
            )
        ]
    )

    sarif = analysis_to_sarif(result)

    assert sarif["runs"][0]["results"][0]["level"] == "note"
    assert "locations" not in sarif["runs"][0]["results"][0]


def test_analysis_to_sarif_does_not_include_evidence_values() -> None:
    result = _analysis_result(
        findings=[
            RiskFinding(
                rule_id="secret-like-change",
                severity="high",
                title="Secret-like change",
                description="A sensitive pattern changed.",
                score_delta=30,
                file_path="settings.py",
                line_start=2,
                evidence={"matched_value": "super-secret-token"},
            )
        ]
    )

    sarif_text = json.dumps(analysis_to_sarif(result))

    assert "super-secret-token" not in sarif_text


def test_analysis_to_sarif_accepts_structured_json_payload() -> None:
    sarif = analysis_to_sarif(
        {
            "risk_score": 70,
            "risk_level": "high",
            "changed_files": [{"path": "auth/session.py"}],
            "findings": [
                {
                    "rule_id": "python-eval-exec",
                    "severity": "critical",
                    "title": "Dynamic execution",
                    "description": "Dynamic execution was introduced.",
                    "score_delta": 40,
                    "file_path": "auth/session.py",
                    "line_start": 12,
                }
            ],
        }
    )

    assert sarif["runs"][0]["results"][0]["ruleId"] == "python-eval-exec"
    assert sarif["runs"][0]["results"][0]["level"] == "error"


def _analysis_result(findings: list[RiskFinding] | None = None) -> AnalysisExecutionResult:
    return AnalysisExecutionResult(
        changed_files=[DiffFile(path="auth/session.py", status="modified", additions=3, deletions=0)],
        analysis=RiskAnalysis(
            risk_score=70,
            risk_level="high",
            findings=findings
            or [
                RiskFinding(
                    rule_id="python-eval-exec",
                    severity="critical",
                    title="Dynamic execution",
                    description="Dynamic execution was introduced.",
                    score_delta=40,
                    file_path="auth/session.py",
                    line_start=12,
                    line_end=14,
                ),
                RiskFinding(
                    rule_id="dependency-change",
                    severity="medium",
                    title="Dependency metadata changed",
                    description="Dependency metadata changed.",
                    score_delta=20,
                    file_path="pyproject.toml",
                    line_start=3,
                ),
            ],
        ),
        review_requirements=[],
        markdown="# AgentReviewOps Report\n",
    )
