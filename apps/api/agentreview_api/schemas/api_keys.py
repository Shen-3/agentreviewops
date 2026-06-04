from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255, description="Human-readable API key name.")
    role: str = Field(default="admin", pattern="^(admin|ci|read_only)$")


class ApiKeyResponse(BaseModel):
    api_key_id: str
    name: str
    role: str
    key_prefix: str
    created_at: datetime
    revoked_at: datetime | None
    is_current: bool


class ApiKeyCreateResponse(ApiKeyResponse):
    api_key: str


class ApiKeyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    role: str | None = Field(default=None, pattern="^(admin|ci|read_only)$")
