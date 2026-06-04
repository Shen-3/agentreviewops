from __future__ import annotations

from fastapi import APIRouter, Depends

from agentreview_api.deps import AuthContext, require_api_key
from agentreview_api.schemas.auth import AuthMeResponse

router = APIRouter()


@router.get("/api/auth/me", response_model=AuthMeResponse)
def auth_me(auth: AuthContext = Depends(require_api_key)) -> AuthMeResponse:
    return AuthMeResponse(
        organization_id=auth.organization_id,
        api_key_id=auth.api_key_id,
        api_key_name=auth.api_key_name,
        api_key_role=auth.api_key_role,
    )
