from agentreview.github_reviewers import (
    filter_github_reviewer_request_plan,
    resolve_github_reviewer_request_plan,
)
from agentreview.models import ReviewRequirement, SuggestedReviewer


def test_resolve_github_reviewer_request_plan_splits_users_teams_and_skips() -> None:
    requirement = _requirement(
        [
            SuggestedReviewer(source="codeowners", identifier="@alice"),
            SuggestedReviewer(source="codeowners", identifier="@octo/security-team"),
            SuggestedReviewer(source="codeowners", identifier="@octo/security-team"),
            SuggestedReviewer(source="codeowners", identifier="security-team"),
            SuggestedReviewer(source="codeowners", identifier="owner@example.com"),
            SuggestedReviewer(source="repository_membership", identifier="maintainer@example.com", role="maintainer"),
            SuggestedReviewer(source="repository_membership", identifier="Engineering", role="reviewer"),
        ]
    )

    plan = resolve_github_reviewer_request_plan([requirement])

    assert plan.reviewers == ["alice"]
    assert plan.team_reviewers == ["security-team"]
    assert {(item.identifier, item.reason) for item in plan.skipped} == {
        ("security-team", "bare_identifier_not_requestable"),
        ("owner@example.com", "email_identifier_not_requestable"),
        ("maintainer@example.com", "email_identifier_not_requestable"),
        ("Engineering", "missing_github_login"),
    }


def test_resolve_github_reviewer_request_plan_excludes_pull_request_author() -> None:
    requirement = _requirement(
        [
            SuggestedReviewer(source="codeowners", identifier="@alice"),
            SuggestedReviewer(source="codeowners", identifier="@bob"),
        ]
    )

    plan = resolve_github_reviewer_request_plan([requirement], author="Alice")

    assert plan.reviewers == ["bob"]
    assert [(item.identifier, item.reason) for item in plan.skipped] == [("@alice", "pull_request_author")]


def test_filter_github_reviewer_request_plan_honors_request_mode() -> None:
    plan = resolve_github_reviewer_request_plan(
        [
            _requirement(
                [
                    SuggestedReviewer(source="codeowners", identifier="@alice"),
                    SuggestedReviewer(source="codeowners", identifier="@octo/security-team"),
                ]
            )
        ]
    )

    users_only = filter_github_reviewer_request_plan(plan, mode="users")
    teams_only = filter_github_reviewer_request_plan(plan, mode="teams")

    assert users_only.reviewers == ["alice"]
    assert users_only.team_reviewers == []
    assert teams_only.reviewers == []
    assert teams_only.team_reviewers == ["security-team"]


def _requirement(suggested_reviewers: list[SuggestedReviewer]) -> ReviewRequirement:
    return ReviewRequirement(
        requirement_id="security-review",
        title="Security review",
        reason="Sensitive change",
        suggested_reviewers=suggested_reviewers,
    )
