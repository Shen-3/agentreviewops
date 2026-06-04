from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UserCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255, description="Organization user email.")
    name: str | None = Field(default=None, max_length=255)
    github_login: str | None = Field(default=None, max_length=255)
    role: str = Field(default="reviewer", pattern="^(admin|reviewer)$")


class UserUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    github_login: str | None = Field(default=None, max_length=255)
    role: str | None = Field(default=None, pattern="^(admin|reviewer)$")


class UserResponse(BaseModel):
    user_id: str
    email: str
    name: str | None
    github_login: str | None
    role: str
    created_at: datetime
