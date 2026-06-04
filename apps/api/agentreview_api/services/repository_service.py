from __future__ import annotations

from agentreview.models import SuggestedReviewer
from agentreview_api.db import RepositoryRecord, UserRecord
from agentreview_api.schemas.repositories import RepositoryResponse, RepositoryReviewerResponse
from agentreview_api.schemas.users import UserResponse


def repository_response(record: RepositoryRecord) -> RepositoryResponse:
    return RepositoryResponse(
        repository_id=record.id,
        provider=record.provider,
        owner=record.owner,
        name=record.name,
        full_name=f"{record.owner}/{record.name}",
        default_branch=record.default_branch,
        visibility=record.visibility,
        reviewers=[
            RepositoryReviewerResponse(
                user_id=membership.user.id,
                email=membership.user.email,
                name=membership.user.name,
                role=membership.role,
            )
            for membership in sorted(record.memberships, key=lambda item: (item.role, item.user.email))
        ],
        created_at=record.created_at,
    )


def repository_reviewers_for_analysis(repository: RepositoryRecord | None) -> list[SuggestedReviewer]:
    if repository is None:
        return []
    return [
        SuggestedReviewer(
            source="repository_membership",
            identifier=membership.user.email,
            role=membership.role,
        )
        for membership in sorted(repository.memberships, key=lambda item: (item.role, item.user.email))
    ]


def user_response(record: UserRecord) -> UserResponse:
    return UserResponse(
        user_id=record.id,
        email=record.email,
        name=record.name,
        role=record.role,
        created_at=record.created_at,
    )
