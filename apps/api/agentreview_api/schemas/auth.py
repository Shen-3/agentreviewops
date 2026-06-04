from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


class AuthMeResponse(BaseModel):
    organization_id: str
    api_key_id: str
    api_key_name: str
    api_key_role: str
