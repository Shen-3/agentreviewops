from __future__ import annotations

import re
from typing import Protocol

from pydantic import Field

from agentreview.models import DiffFile, RiskAnalysis, RiskFinding, StrictConfigModel


class DiffSummaryRequest(StrictConfigModel):
    risk_score: int = Field(ge=0, le=100)
    risk_level: str
    changed_files: list[DiffFile]
    findings: list[RiskFinding]
    redacted_diff: str | None = None


class DiffSummaryResult(StrictConfigModel):
    summary: str
    checklist: list[str] = Field(default_factory=list)


class ReviewLLMProvider(Protocol):
    def summarize_diff(self, request: DiffSummaryRequest) -> DiffSummaryResult:
        """Return an optional AI-authored summary for an already analyzed diff."""


def generate_ai_summary(
    *,
    provider: ReviewLLMProvider,
    analysis: RiskAnalysis,
    changed_files: list[DiffFile],
    diff_text: str | None = None,
    enabled: bool = False,
) -> DiffSummaryResult | None:
    if not enabled:
        return None

    request = DiffSummaryRequest(
        risk_score=analysis.risk_score,
        risk_level=analysis.risk_level,
        changed_files=changed_files,
        findings=analysis.findings,
        redacted_diff=redact_secrets(diff_text) if diff_text is not None else None,
    )
    return provider.summarize_diff(request)


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern, replacement in _TOKEN_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    redacted = _ASSIGNMENT_PATTERN.sub(lambda match: f"{match.group(1)}=[REDACTED]", redacted)
    return redacted


_TOKEN_PATTERNS = [
    (re.compile(r"github_pat_[A-Za-z0-9_]+"), "github_pat_[REDACTED]"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]+"), "gh_[REDACTED]"),
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "sk-[REDACTED]"),
]
_ASSIGNMENT_PATTERN = re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s]+")
