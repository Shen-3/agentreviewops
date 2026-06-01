from __future__ import annotations

import json
import os
import re
from typing import Protocol

import httpx
from pydantic import Field

from agentreview.models import AIConfig, DiffFile, RiskAnalysis, RiskFinding, StrictConfigModel


class AIProviderError(RuntimeError):
    """Raised when an enabled AI provider cannot produce a summary."""


class AIProviderConfigError(AIProviderError):
    """Raised when AI provider configuration is incomplete or unsupported."""


class AIProviderRequestError(AIProviderError):
    """Raised when an AI provider request fails."""


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


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 15.0,
        max_diff_chars: int = 12000,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_diff_chars = max_diff_chars

    def summarize_diff(self, request: DiffSummaryRequest) -> DiffSummaryResult:
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You summarize deterministic pull request risk analysis for a human reviewer. "
                        "Return compact JSON with string field summary and string array field checklist. "
                        "Do not include secrets, credentials, or raw sensitive values."
                    ),
                },
                {
                    "role": "user",
                    "content": _build_prompt(request, max_diff_chars=self.max_diff_chars),
                },
            ],
        }
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "agentreviewops-ai/0.1.0",
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise AIProviderRequestError(f"AI provider request failed: {exc}") from exc

        return _parse_provider_content(str(content))


def create_ai_provider(config: AIConfig) -> ReviewLLMProvider | None:
    if not config.enabled:
        return None

    provider = (config.provider or "").strip().lower()
    if provider not in {"openai", "openai-compatible"}:
        raise AIProviderConfigError("AI provider must be 'openai' or 'openai-compatible' when AI is enabled")

    api_key = os.environ.get("AGENTREVIEW_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise AIProviderConfigError("AGENTREVIEW_OPENAI_API_KEY or OPENAI_API_KEY is required when AI is enabled")

    model = config.model or os.environ.get("AGENTREVIEW_OPENAI_MODEL")
    if not model:
        raise AIProviderConfigError("AI model is required via ai.model or AGENTREVIEW_OPENAI_MODEL")

    base_url = config.base_url or os.environ.get("AGENTREVIEW_OPENAI_BASE_URL") or "https://api.openai.com/v1"
    return OpenAICompatibleProvider(
        api_key=api_key,
        model=model,
        base_url=base_url,
        timeout_seconds=config.timeout_seconds,
        max_diff_chars=config.max_diff_chars,
    )


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


def _build_prompt(request: DiffSummaryRequest, *, max_diff_chars: int) -> str:
    files = [
        {
            "path": changed_file.path,
            "status": changed_file.status,
            "additions": changed_file.additions,
            "deletions": changed_file.deletions,
            "language": changed_file.language,
            "is_test_file": changed_file.is_test_file,
            "is_critical_file": changed_file.is_critical_file,
        }
        for changed_file in request.changed_files
    ]
    findings = [
        {
            "rule_id": finding.rule_id,
            "severity": finding.severity,
            "title": finding.title,
            "description": finding.description,
            "file_path": finding.file_path,
            "score_delta": finding.score_delta,
        }
        for finding in request.findings
    ]
    diff_excerpt = request.redacted_diff or ""
    if len(diff_excerpt) > max_diff_chars:
        diff_excerpt = diff_excerpt[:max_diff_chars] + "\n[TRUNCATED]"

    return json.dumps(
        {
            "risk_score": request.risk_score,
            "risk_level": request.risk_level,
            "changed_files": files,
            "findings": findings,
            "redacted_diff_excerpt": diff_excerpt,
        },
        separators=(",", ":"),
    )


def _parse_provider_content(content: str) -> DiffSummaryResult:
    normalized = content.strip()
    if normalized.startswith("```"):
        normalized = normalized.strip("`").removeprefix("json").strip()

    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError:
        return DiffSummaryResult(summary=content.strip(), checklist=[])

    if not isinstance(parsed, dict):
        return DiffSummaryResult(summary=content.strip(), checklist=[])

    summary = parsed.get("summary")
    checklist = parsed.get("checklist", [])
    if not isinstance(summary, str) or not summary.strip():
        return DiffSummaryResult(summary=content.strip(), checklist=[])
    if not isinstance(checklist, list):
        checklist = []

    return DiffSummaryResult(
        summary=summary.strip(),
        checklist=[str(item).strip() for item in checklist if str(item).strip()],
    )


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
