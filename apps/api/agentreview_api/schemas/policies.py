from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from agentreview.models import AgentReviewConfig


class PolicyCreateRequest(BaseModel):
    name: str = Field(min_length=1, description="Human-readable policy name.")
    config: AgentReviewConfig
    enabled: bool = True
    scope: str = Field(default="organization", pattern="^(organization|repository)$")
    repository_id: str | None = Field(default=None, description="Required when scope is repository.")


class PolicyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, description="Updated human-readable policy name.")
    config: AgentReviewConfig | None = None
    enabled: bool | None = None


class PolicyResponse(BaseModel):
    policy_id: str
    name: str
    scope: str
    repository_id: str | None
    repository_full_name: str | None
    enabled: bool
    config: AgentReviewConfig
    created_at: datetime
    updated_at: datetime
