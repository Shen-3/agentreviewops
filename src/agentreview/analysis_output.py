from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentreview import __version__
from agentreview.analysis import AnalysisExecutionResult

RISK_LEVEL_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "block": 3,
}


def build_analysis_json_payload(
    result: AnalysisExecutionResult,
    *,
    fail_on: str,
    source: str,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build machine-readable analysis output from structured analysis objects."""
    return {
        "risk_score": result.analysis.risk_score,
        "risk_level": result.analysis.risk_level,
        "decision": {
            "fail_on": fail_on,
            "should_fail": should_fail_for_threshold(result.analysis.risk_level, fail_on),
        },
        "summary": build_analysis_summary(result),
        "findings": [finding.model_dump(mode="json") for finding in result.analysis.findings],
        "changed_files": [changed_file.model_dump(mode="json") for changed_file in result.changed_files],
        "review_requirements": [
            requirement.model_dump(mode="json")
            for requirement in result.review_requirements
        ],
        "metadata": {
            "generated_at": _format_timestamp(generated_at or datetime.now(timezone.utc)),
            "agentreview_version": __version__,
            "source": source,
        },
    }


def write_analysis_json_output(
    path: Path,
    result: AnalysisExecutionResult,
    *,
    fail_on: str,
    source: str,
) -> None:
    payload = build_analysis_json_payload(result, fail_on=fail_on, source=source)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def should_fail_for_threshold(risk_level: str, fail_on: str) -> bool:
    if fail_on == "never":
        return False
    return RISK_LEVEL_ORDER[str(risk_level)] >= RISK_LEVEL_ORDER[fail_on]


def build_analysis_summary(result: AnalysisExecutionResult) -> str:
    return (
        f"{len(result.changed_files)} changed file(s), "
        f"{result.analysis.risk_level} risk ({result.analysis.risk_score}/100)."
    )


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc).replace(microsecond=0)
    return value.isoformat().replace("+00:00", "Z")
