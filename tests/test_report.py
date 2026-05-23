from pathlib import Path

from agentreview.ai import DiffSummaryResult
from agentreview.config import load_config
from agentreview.gitdiff import parse_diff_file
from agentreview.report import generate_markdown_report
from agentreview.risk import analyze_risk


def test_report_snapshot_for_sample_diff() -> None:
    project_root = Path(__file__).parents[1]
    config = load_config(project_root / ".agentreview.example.yml")
    changed_files = parse_diff_file(project_root / "examples" / "sample.diff", config=config)
    analysis = analyze_risk(changed_files, config=config)

    report = generate_markdown_report(analysis, changed_files, config=config)

    assert report == (project_root / "examples" / "report.md").read_text(encoding="utf-8")


def test_report_includes_required_sections() -> None:
    project_root = Path(__file__).parents[1]
    config = load_config(project_root / ".agentreview.example.yml")
    changed_files = parse_diff_file(project_root / "examples" / "sample.diff", config=config)
    analysis = analyze_risk(changed_files, config=config)

    report = generate_markdown_report(analysis, changed_files, config=config)

    assert "# AgentReviewOps Report" in report
    assert "## Summary" in report
    assert "## Findings" in report
    assert "## Human Review Checklist" in report
    assert "## Changed Files" in report
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
