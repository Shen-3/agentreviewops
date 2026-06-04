from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agentreview_api.deps import AuthContext, get_session, require_admin_api_key
from agentreview_api.schemas.retention import RetentionPurgeRequest, RetentionPurgeResponse
from agentreview_api.services.retention_service import purge_retention_records_for_request

router = APIRouter()


@router.post("/api/retention/purge", response_model=RetentionPurgeResponse)
def purge_retention(
    request: RetentionPurgeRequest,
    auth: AuthContext = Depends(require_admin_api_key),
    session: Session = Depends(get_session),
) -> RetentionPurgeResponse:
    return purge_retention_records_for_request(request, auth, session)
