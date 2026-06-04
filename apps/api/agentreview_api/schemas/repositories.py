from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RepositoryCreateRequest(BaseModel):
    provider: str = Field(default="github", min_length=1, max_length=50, description="Source control provider.")
    owner: str = Field(min_length=1, max_length=255, description="Repository owner or namespace.")
    name: str = Field(min_length=1, max_length=255, description="Repository name.")
    default_branch: str | None = Field(default=None, max_length=255)
    visibility: str | None = Field(default=None, max_length=50)


class RepositoryReviewerResponse(BaseModel):
    user_id: str
    email: str
    name: str | None
    role: str


class RepositoryResponse(BaseModel):
    repository_id: str
    provider: str
    owner: str
    name: str
    full_name: str
    default_branch: str | None
    visibility: str | None
    reviewers: list[RepositoryReviewerResponse]
    created_at: datetime


class RepositoryMembershipCreateRequest(BaseModel):
    user_id: str = Field(min_length=1)
    role: str = Field(default="reviewer", pattern="^(owner|maintainer|reviewer)$")


class RepositoryMembershipUpdateRequest(BaseModel):
    role: str = Field(pattern="^(owner|maintainer|reviewer)$")
