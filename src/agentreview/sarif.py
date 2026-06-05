from __future__ import annotations

from typing import Any

from agentreview.analysis import AnalysisExecutionResult
from agentreview.security import redact_mapping, redact_text

SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
SARIF_VERSION = "2.1.0"


def analysis_to_sarif(
    analysis_result: AnalysisExecutionResult | dict,
    *,
    tool_name: str = "AgentReviewOps",
    information_uri: str | None = None,
    repo_uri: str | None = None,
    checkout_uri: str | None = None,
) -> dict:
    normalized = _normalize_analysis_result(analysis_result)
    rules = _sarif_rules(normalized["findings"])
    run: dict[str, Any] = {
        "tool": {
            "driver": {
                "name": tool_name,
                "rules": rules,
            }
        },
        "results": [
            _sarif_result(
                finding,
                risk_level=normalized["risk_level"],
                risk_score=normalized["risk_score"],
                checkout_uri=checkout_uri,
            )
            for finding in normalized["findings"]
        ],
        "properties": {
            "riskLevel": normalized["risk_level"],
            "riskScore": normalized["risk_score"],
            "changedFileCount": len(normalized["changed_files"]),
        },
    }
    if information_uri is not None:
        run["tool"]["driver"]["informationUri"] = information_uri
    if repo_uri is not None:
        run["versionControlProvenance"] = [{"repositoryUri": repo_uri}]
    if checkout_uri is not None:
        run["originalUriBaseIds"] = {
            "SRCROOT": {
                "uri": _directory_uri(checkout_uri),
            }
        }
    return {
        "version": SARIF_VERSION,
        "$schema": SARIF_SCHEMA,
        "runs": [run],
    }


def _normalize_analysis_result(analysis_result: AnalysisExecutionResult | dict) -> dict[str, Any]:
    if isinstance(analysis_result, AnalysisExecutionResult):
        return {
            "risk_score": analysis_result.analysis.risk_score,
            "risk_level": analysis_result.analysis.risk_level,
            "findings": [
                redact_mapping(finding.model_dump(mode="json")) for finding in analysis_result.analysis.findings
            ],
            "changed_files": [changed_file.model_dump(mode="json") for changed_file in analysis_result.changed_files],
        }
    return {
        "risk_score": int(analysis_result.get("risk_score", 0)),
        "risk_level": str(analysis_result.get("risk_level", "low")),
        "findings": [
            redact_mapping(finding) if isinstance(finding, dict) else finding
            for finding in list(analysis_result.get("findings") or [])
        ],
        "changed_files": list(analysis_result.get("changed_files") or []),
    }


def _sarif_rules(findings: list[dict]) -> list[dict]:
    rules_by_id: dict[str, dict] = {}
    for finding in findings:
        rule_id = str(finding.get("rule_id") or "agentreview-finding")
        rules_by_id.setdefault(
            rule_id,
            {
                "id": rule_id,
                "name": rule_id,
                "shortDescription": {
                    "text": redact_text(str(finding.get("title") or rule_id)),
                },
                "help": {
                    "text": redact_text(str(finding.get("description") or finding.get("title") or rule_id)),
                },
                "properties": {
                    "category": "agentreviewops",
                },
            },
        )
    return [rules_by_id[rule_id] for rule_id in sorted(rules_by_id)]


def _sarif_result(
    finding: dict,
    *,
    risk_level: str,
    risk_score: int,
    checkout_uri: str | None,
) -> dict:
    rule_id = str(finding.get("rule_id") or "agentreview-finding")
    result = {
        "ruleId": rule_id,
        "level": _sarif_level(str(finding.get("severity") or "info")),
        "message": {
            "text": redact_text(str(finding.get("description") or finding.get("title") or rule_id)),
        },
        "properties": {
            "riskLevel": risk_level,
            "riskScore": risk_score,
            "severity": str(finding.get("severity") or "info"),
            "scoreDelta": int(finding.get("score_delta") or 0),
            "source": "agentreviewops",
        },
    }
    location = _sarif_location(finding, checkout_uri=checkout_uri)
    if location is not None:
        result["locations"] = [location]
    return result


def _sarif_location(finding: dict, *, checkout_uri: str | None) -> dict | None:
    file_path = finding.get("file_path")
    line_start = finding.get("line_start")
    if not file_path or line_start is None:
        return None
    region = {"startLine": int(line_start)}
    line_end = finding.get("line_end")
    if line_end is not None:
        region["endLine"] = int(line_end)
    artifact_location = {"uri": str(file_path)}
    if checkout_uri is not None:
        artifact_location["uriBaseId"] = "SRCROOT"
    return {
        "physicalLocation": {
            "artifactLocation": artifact_location,
            "region": region,
        }
    }


def _sarif_level(severity: str) -> str:
    if severity in {"critical", "high", "block", "blocking"}:
        return "error"
    if severity == "medium":
        return "warning"
    return "note"


def _directory_uri(value: str) -> str:
    return value if value.endswith("/") else f"{value}/"
