from __future__ import annotations

from dataclasses import dataclass

from agentreview.ai import create_ai_provider, generate_ai_summary
from agentreview.gitdiff import parse_unified_diff
from agentreview.models import AgentReviewConfig, DiffFile, ReviewRequirement, RiskAnalysis, SuggestedReviewer
from agentreview.plugins import AnalysisContext, load_analyzer_plugins, run_analyzer_plugins
from agentreview.report import generate_markdown_report
from agentreview.risk import analyze_risk
from agentreview.routing import build_review_requirements


@dataclass(frozen=True)
class AnalysisExecutionResult:
    changed_files: list[DiffFile]
    analysis: RiskAnalysis
    review_requirements: list[ReviewRequirement]
    markdown: str


def analyze_diff_text(
    diff_text: str,
    *,
    config: AgentReviewConfig,
    repository_reviewers: list[SuggestedReviewer] | None = None,
    codeowners_text: str | None = None,
) -> AnalysisExecutionResult:
    changed_files = parse_unified_diff(diff_text, config=config)
    plugin_findings = []
    if any(plugin.enabled for plugin in config.plugins):
        plugin_findings = run_analyzer_plugins(
            load_analyzer_plugins(),
            AnalysisContext(changed_files=changed_files, config=config),
        )
    analysis = analyze_risk(changed_files, config=config, plugin_findings=plugin_findings)
    review_requirements = build_review_requirements(
        analysis=analysis,
        changed_files=changed_files,
        config=config,
        repository_reviewers=repository_reviewers,
        codeowners_text=codeowners_text,
    )
    provider = create_ai_provider(config.ai)
    ai_summary = None
    if provider is not None:
        ai_summary = generate_ai_summary(
            provider=provider,
            analysis=analysis,
            changed_files=changed_files,
            diff_text=diff_text,
            enabled=config.ai.enabled,
        )
    markdown = generate_markdown_report(
        analysis,
        changed_files,
        config=config,
        ai_summary=ai_summary,
        review_requirements=review_requirements,
    )
    return AnalysisExecutionResult(
        changed_files=changed_files,
        analysis=analysis,
        review_requirements=review_requirements,
        markdown=markdown,
    )
