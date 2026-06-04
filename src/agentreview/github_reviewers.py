from __future__ import annotations

import re
from dataclasses import dataclass

from agentreview.models import ReviewRequirement, SuggestedReviewer

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
GITHUB_LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
GITHUB_TEAM_SLUG_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]*$")


@dataclass(frozen=True)
class SkippedReviewer:
    identifier: str
    reason: str
    source: str


@dataclass(frozen=True)
class GitHubReviewerRequestPlan:
    reviewers: list[str]
    team_reviewers: list[str]
    skipped: list[SkippedReviewer]


def resolve_github_reviewer_request_plan(
    review_requirements: list[ReviewRequirement],
    *,
    author: str | None = None,
) -> GitHubReviewerRequestPlan:
    reviewers: dict[str, str] = {}
    team_reviewers: dict[str, str] = {}
    skipped: dict[tuple[str, str, str], SkippedReviewer] = {}
    author_key = _author_key(author)

    for requirement in review_requirements:
        for suggested_reviewer in requirement.suggested_reviewers:
            resolved = _resolve_suggested_reviewer(suggested_reviewer)
            if resolved[0] == "skip":
                _add_skipped(skipped, suggested_reviewer, resolved[1])
                continue

            reviewer_type, reviewer_value = resolved
            reviewer_key = reviewer_value.casefold()
            if reviewer_type == "user" and reviewer_key == author_key:
                _add_skipped(skipped, suggested_reviewer, "pull_request_author")
                continue
            if reviewer_type == "user":
                reviewers.setdefault(reviewer_key, reviewer_value)
            else:
                team_reviewers.setdefault(reviewer_key, reviewer_value)

    return GitHubReviewerRequestPlan(
        reviewers=sorted(reviewers.values(), key=lambda value: value.casefold()),
        team_reviewers=sorted(team_reviewers.values(), key=lambda value: value.casefold()),
        skipped=sorted(
            skipped.values(),
            key=lambda item: (item.identifier.casefold(), item.reason, item.source.casefold()),
        ),
    )


def filter_github_reviewer_request_plan(
    plan: GitHubReviewerRequestPlan,
    *,
    mode: str,
) -> GitHubReviewerRequestPlan:
    if mode == "users":
        return GitHubReviewerRequestPlan(reviewers=plan.reviewers, team_reviewers=[], skipped=plan.skipped)
    if mode == "teams":
        return GitHubReviewerRequestPlan(reviewers=[], team_reviewers=plan.team_reviewers, skipped=plan.skipped)
    return plan


def _resolve_suggested_reviewer(suggested_reviewer: SuggestedReviewer) -> tuple[str, str]:
    identifier = suggested_reviewer.identifier.strip()
    if suggested_reviewer.source == "repository_membership" and _is_email(identifier):
        return "skip", "missing_github_login"
    if _is_email(identifier):
        return "skip", "email_identifier_not_requestable"

    if identifier.startswith("@"):
        github_identifier = identifier[1:].strip()
        if "/" in github_identifier:
            owner, team_slug = github_identifier.split("/", maxsplit=1)
            if owner and team_slug and GITHUB_TEAM_SLUG_RE.fullmatch(team_slug):
                return "team", team_slug
            return "skip", "invalid_github_team_identifier"
        if GITHUB_LOGIN_RE.fullmatch(github_identifier):
            return "user", github_identifier
        return "skip", "invalid_github_login_identifier"

    if suggested_reviewer.source == "repository_membership":
        return "skip", "missing_github_login"
    return "skip", "bare_identifier_not_requestable"


def _add_skipped(
    skipped: dict[tuple[str, str, str], SkippedReviewer],
    suggested_reviewer: SuggestedReviewer,
    reason: str,
) -> None:
    key = (suggested_reviewer.identifier, reason, suggested_reviewer.source)
    skipped.setdefault(
        key,
        SkippedReviewer(
            identifier=suggested_reviewer.identifier,
            reason=reason,
            source=suggested_reviewer.source,
        ),
    )


def _author_key(author: str | None) -> str | None:
    if author is None:
        return None
    normalized = author.strip()
    if normalized.startswith("@"):
        normalized = normalized[1:]
    return normalized.casefold() or None


def _is_email(identifier: str) -> bool:
    return EMAIL_RE.fullmatch(identifier) is not None
