from pathlib import Path

from agentreview.config import parse_config
from agentreview.gitdiff import parse_unified_diff
from agentreview.models import AgentReviewConfig, RiskAnalysis, RiskFinding, SuggestedReviewer
from agentreview.risk import analyze_risk
from agentreview.routing import build_review_requirements, codeowners_for_path, load_codeowners_text, parse_codeowners


def test_path_rule_matches_changed_file() -> None:
    requirements = build_review_requirements(
        analysis=_analysis([]),
        changed_files=_changed_files("auth/session.py"),
        config=parse_config(
            {
                "version": 1,
                "review_routing": {
                    "rules": [
                        {
                            "id": "security-review",
                            "paths": ["auth/**"],
                            "reason": "Sensitive area changed.",
                        }
                    ]
                },
            }
        ),
    )

    assert requirements[0].requirement_id == "security-review"
    assert requirements[0].matched_files == ["auth/session.py"]


def test_rule_id_rule_matches_finding() -> None:
    requirements = build_review_requirements(
        analysis=_analysis([_finding("github-actions-write-all-permissions", file_path=".github/workflows/ci.yml")]),
        changed_files=_changed_files(".github/workflows/ci.yml"),
        config=parse_config(
            {
                "version": 1,
                "review_routing": {
                    "rules": [
                        {
                            "id": "ci-review",
                            "rule_ids": ["github-actions-write-all-permissions"],
                            "reason": "Workflow permissions changed.",
                        }
                    ]
                },
            }
        ),
    )

    assert requirements[0].matched_rule_ids == ["github-actions-write-all-permissions"]
    assert requirements[0].matched_files == [".github/workflows/ci.yml"]


def test_risk_level_rule_matches_block() -> None:
    requirements = build_review_requirements(
        analysis=RiskAnalysis(risk_score=80, risk_level="block", findings=[]),
        changed_files=[],
        config=parse_config(
            {
                "version": 1,
                "review_routing": {
                    "rules": [
                        {
                            "id": "block-risk-review",
                            "risk_levels": ["block"],
                            "reason": "Block risk.",
                        }
                    ]
                },
            }
        ),
    )

    assert requirements[0].requirement_id == "block-risk-review"


def test_codeowners_owner_is_suggested() -> None:
    requirements = build_review_requirements(
        analysis=_analysis([]),
        changed_files=_changed_files("auth/session.py"),
        config=AgentReviewConfig(),
        codeowners_text="auth/** @security-team\n",
    )

    reviewers = requirements[0].suggested_reviewers
    assert reviewers[0].source == "codeowners"
    assert reviewers[0].identifier == "@security-team"


def test_repository_membership_reviewer_is_suggested_by_role() -> None:
    requirements = build_review_requirements(
        analysis=_analysis([]),
        changed_files=_changed_files("auth/session.py"),
        config=AgentReviewConfig(),
        repository_reviewers=[
            SuggestedReviewer(source="repository_membership", identifier="alice@example.com", role="maintainer"),
            SuggestedReviewer(source="repository_membership", identifier="bob@example.com", role="reviewer"),
        ],
    )

    assert [reviewer.identifier for reviewer in requirements[0].suggested_reviewers] == ["alice@example.com"]


def test_no_reviewer_produces_empty_suggested_reviewers() -> None:
    requirements = build_review_requirements(
        analysis=_analysis([]),
        changed_files=_changed_files("auth/session.py"),
        config=AgentReviewConfig(),
    )

    assert requirements[0].suggested_reviewers == []


def test_duplicate_reviewers_are_deduplicated() -> None:
    requirements = build_review_requirements(
        analysis=_analysis([]),
        changed_files=_changed_files("auth/session.py"),
        config=AgentReviewConfig(),
        repository_reviewers=[
            SuggestedReviewer(source="repository_membership", identifier="alice@example.com", role="maintainer"),
            SuggestedReviewer(source="repository_membership", identifier="alice@example.com", role="maintainer"),
        ],
        codeowners_text="auth/** @security-team @security-team\n",
    )

    assert [(reviewer.source, reviewer.identifier, reviewer.role) for reviewer in requirements[0].suggested_reviewers] == [
        ("codeowners", "@security-team", None),
        ("repository_membership", "alice@example.com", "maintainer"),
    ]


def test_disabled_routing_returns_empty_list() -> None:
    config = parse_config({"version": 1, "review_routing": {"enabled": False}})

    requirements = build_review_requirements(
        analysis=_analysis([]),
        changed_files=_changed_files("auth/session.py"),
        config=config,
    )

    assert requirements == []


def test_codeowners_parser_ignores_comments_blank_and_malformed_lines() -> None:
    entries = parse_codeowners(
        """
# team ownership

malformed
auth/** @security-team
.github/workflows/** @platform-team user@example.com
*.py @backend-team
"""
    )

    assert [entry.pattern for entry in entries] == ["auth/**", ".github/workflows/**", "*.py"]
    assert codeowners_for_path("auth/session.py", entries) == ["@security-team", "@backend-team"]
    assert codeowners_for_path(".github/workflows/ci.yml", entries) == ["@platform-team", "user@example.com"]


def test_load_codeowners_text_uses_standard_search_order(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "CODEOWNERS").write_text("*.py @docs\n", encoding="utf-8")
    (tmp_path / "CODEOWNERS").write_text("*.py @root\n", encoding="utf-8")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "CODEOWNERS").write_text("*.py @github\n", encoding="utf-8")

    assert load_codeowners_text() == "*.py @github\n"


def _changed_files(path: str):
    diff_text = f"""diff --git a/{path} b/{path}
index 1111111..2222222 100644
--- a/{path}
+++ b/{path}
@@ -1 +1,2 @@
 old
+new
"""
    return parse_unified_diff(diff_text)


def _analysis(findings: list[RiskFinding]) -> RiskAnalysis:
    return RiskAnalysis(risk_score=50 if findings else 0, risk_level="high" if findings else "low", findings=findings)


def _finding(rule_id: str, *, file_path: str | None = None) -> RiskFinding:
    return RiskFinding(
        rule_id=rule_id,
        severity="high",
        title="Finding",
        description="Finding description.",
        score_delta=20,
        file_path=file_path,
    )
