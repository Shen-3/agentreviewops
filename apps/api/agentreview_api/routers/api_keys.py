from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from agentreview_api.audit import (
    AUDIT_ACTION_API_KEY_CREATED,
    AUDIT_ACTION_API_KEY_REVOKED,
    AUDIT_ACTION_API_KEY_UPDATED,
)
from agentreview_api.db import ApiKeyRecord
from agentreview_api.deps import AuthContext, get_session, require_admin_api_key, require_api_key
from agentreview_api.repository import (
    create_api_key,
    create_audit_event,
    get_api_key,
    list_api_keys,
    revoke_api_key,
    update_api_key,
)
from agentreview_api.schemas.api_keys import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    ApiKeyUpdateRequest,
)

router = APIRouter()


@router.get("/api/api-keys", response_model=list[ApiKeyResponse])
def get_api_keys(
    auth: AuthContext = Depends(require_api_key), session: Session = Depends(get_session)
) -> list[ApiKeyResponse]:
    return [
        _api_key_response(record, auth=auth) for record in list_api_keys(session, organization_id=auth.organization_id)
    ]


@router.post("/api/api-keys", response_model=ApiKeyCreateResponse)
def create_org_api_key(
    request: ApiKeyCreateRequest,
    auth: AuthContext = Depends(require_admin_api_key),
    session: Session = Depends(get_session),
) -> ApiKeyCreateResponse:
    normalized_name = request.name.strip()
    if not normalized_name:
        raise HTTPException(status_code=422, detail="API key name is required")

    record, secret = create_api_key(
        session,
        organization_id=auth.organization_id,
        name=normalized_name,
        role=request.role,
    )
    create_audit_event(
        session,
        organization_id=auth.organization_id,
        actor_type="api_key",
        actor_id=auth.api_key_id,
        action=AUDIT_ACTION_API_KEY_CREATED,
        target_type="api_key",
        target_id=record.id,
        metadata={
            "api_key_name": record.name,
            "api_key_role": record.role,
            "source": "api",
        },
    )
    return ApiKeyCreateResponse(
        **_api_key_response(record, auth=auth).model_dump(),
        api_key=secret,
    )


@router.patch("/api/api-keys/{api_key_id}", response_model=ApiKeyResponse)
def update_org_api_key(
    api_key_id: str,
    request: ApiKeyUpdateRequest,
    auth: AuthContext = Depends(require_admin_api_key),
    session: Session = Depends(get_session),
) -> ApiKeyResponse:
    record = get_api_key(session, organization_id=auth.organization_id, api_key_id=api_key_id)
    if record is None:
        raise HTTPException(status_code=404, detail="API key not found")
    if record.revoked_at is not None:
        raise HTTPException(status_code=400, detail="Cannot update a revoked API key")
    if record.id == auth.api_key_id and request.role is not None and request.role != "admin":
        raise HTTPException(status_code=400, detail="Cannot change the current admin API key to a non-admin role")

    previous_role = record.role
    name = request.name.strip() if request.name is not None and request.name.strip() else record.name
    updated = update_api_key(session, record, name=name, role=request.role)
    create_audit_event(
        session,
        organization_id=auth.organization_id,
        actor_type="api_key",
        actor_id=auth.api_key_id,
        action=AUDIT_ACTION_API_KEY_UPDATED,
        target_type="api_key",
        target_id=updated.id,
        metadata={
            "api_key_name": updated.name,
            "previous_role": previous_role,
            "api_key_role": updated.role,
        },
    )
    return _api_key_response(updated, auth=auth)


@router.post("/api/api-keys/{api_key_id}/revoke", response_model=ApiKeyResponse)
def revoke_org_api_key(
    api_key_id: str,
    auth: AuthContext = Depends(require_admin_api_key),
    session: Session = Depends(get_session),
) -> ApiKeyResponse:
    if api_key_id == auth.api_key_id:
        raise HTTPException(status_code=400, detail="Cannot revoke the API key used for this request")

    record = revoke_api_key(session, organization_id=auth.organization_id, api_key_id=api_key_id)
    if record is None:
        raise HTTPException(status_code=404, detail="API key not found")

    create_audit_event(
        session,
        organization_id=auth.organization_id,
        actor_type="api_key",
        actor_id=auth.api_key_id,
        action=AUDIT_ACTION_API_KEY_REVOKED,
        target_type="api_key",
        target_id=record.id,
        metadata={
            "api_key_name": record.name,
        },
    )
    return _api_key_response(record, auth=auth)


def _api_key_response(record: ApiKeyRecord, *, auth: AuthContext) -> ApiKeyResponse:
    return ApiKeyResponse(
        api_key_id=record.id,
        name=record.name,
        role=record.role,
        key_prefix=record.key_prefix,
        created_at=record.created_at,
        revoked_at=record.revoked_at,
        is_current=record.id == auth.api_key_id,
    )
