from pathlib import Path

from agentreview.ai import DiffSummaryResult
from agentreview.config import load_config
from agentreview.gitdiff import parse_diff_file
from agentreview.models import ReviewRequirement, SuggestedReviewer
from agentreview.report import generate_markdown_report
from agentreview.risk import analyze_risk
from agentreview.routing import build_review_requirements


def test_report_snapshot_for_sample_diff() -> None:
    project_root = Path(__file__).parents[1]
    config = load_config(project_root / ".agentreview.example.yml")
    changed_files = parse_diff_file(project_root / "examples" / "sample.diff", config=config)
    analysis = analyze_risk(changed_files, config=config)
    review_requirements = build_review_requirements(analysis=analysis, changed_files=changed_files, config=config)

    report = generate_markdown_report(analysis, changed_files, config=config, review_requirements=review_requirements)

    assert report == (project_root / "examples" / "report.md").read_text(encoding="utf-8")


def test_report_includes_required_sections() -> None:
    project_root = Path(__file__).parents[1]
    config = load_config(project_root / ".agentreview.example.yml")
    changed_files = parse_diff_file(project_root / "examples" / "sample.diff", config=config)
    analysis = analyze_risk(changed_files, config=config)

    report = generate_markdown_report(analysis, changed_files, config=config)

    assert "# AgentReviewOps Report: HIGH risk (55/100)" in report
    assert "## Merge recommendation" in report
    assert "Human review required before merge." in report
    assert "## Why this requires attention" in report
    assert "## Required human review" in report
    assert "## Findings table" in report
    assert "## Changed files summary" in report
    assert "## Suggested human review checklist" in report
    assert "## Policy Config Used" in report


def test_report_includes_ai_summary_when_provided() -> None:
    project_root = Path(__file__).parents[1]
    config = load_config(project_root / ".agentreview.example.yml")
    changed_files = parse_diff_file(project_root / "examples" / "sample.diff", config=config)
    analysis = analyze_risk(changed_files, config=config)
    ai_summary = DiffSummaryResult(summary="AI summary from a fake provider.", checklist=["Check auth owner review."])

    report = generate_markdown_report(analysis, changed_files, config=config, ai_summary=ai_summary)

    assert "## AI Summary" in report
    assert "AI summary from a fake provider." in report
    assert "- [ ] Check auth owner review." in report


def test_report_includes_required_review_sources_and_gaps() -> None:
    project_root = Path(__file__).parents[1]
    config = load_config(project_root / ".agentreview.example.yml")
    changed_files = parse_diff_file(project_root / "examples" / "sample.diff", config=config)
    analysis = analyze_risk(changed_files, config=config)
    requirements = [
        ReviewRequirement(
            requirement_id="security-review",
            title="Security review",
            reason="Sensitive area changed.",
            matched_files=["auth/session.py"],
            matched_rule_ids=["critical-path-change"],
            required_roles=["maintainer"],
            suggested_reviewers=[
                SuggestedReviewer(source="codeowners", identifier="@security-team"),
                SuggestedReviewer(source="repository_membership", identifier="alice@example.com", role="maintainer"),
            ],
        ),
        ReviewRequirement(
            requirement_id="owner-review",
            title="Owner review",
            reason="Risk level BLOCK.",
            required_roles=["owner"],
        ),
    ]

    report = generate_markdown_report(analysis, changed_files, config=config, review_requirements=requirements)

    assert "## Required human review" in report
    assert "CODEOWNERS: @security-team" in report
    assert "Repository membership: alice@example.com" in report
    assert "Not configured" in report
    assert "- [ ] Assign an appropriate reviewer for unconfigured review requirement(s)." in report
    assert "- [ ] Confirm listed CODEOWNERS or repository reviewers approved the change." in report
