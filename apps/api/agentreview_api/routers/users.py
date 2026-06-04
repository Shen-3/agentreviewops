from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from agentreview_api.audit import AUDIT_ACTION_USER_CREATED, AUDIT_ACTION_USER_DELETED, AUDIT_ACTION_USER_UPDATED
from agentreview_api.deps import AuthContext, get_session, require_admin_api_key, require_api_key
from agentreview_api.repository import (
    count_admin_users,
    create_audit_event,
    create_user,
    delete_user,
    get_user,
    get_user_by_email,
    list_users,
    update_user,
)
from agentreview_api.schemas.users import UserCreateRequest, UserResponse, UserUpdateRequest
from agentreview_api.services.repository_service import user_response

router = APIRouter()


@router.get("/api/users", response_model=list[UserResponse])
def get_users(
    auth: AuthContext = Depends(require_api_key), session: Session = Depends(get_session)
) -> list[UserResponse]:
    return [user_response(record) for record in list_users(session, organization_id=auth.organization_id)]


@router.post("/api/users", response_model=UserResponse)
def create_org_user(
    request: UserCreateRequest,
    auth: AuthContext = Depends(require_admin_api_key),
    session: Session = Depends(get_session),
) -> UserResponse:
    email = request.email.strip().lower()
    name = request.name.strip() if request.name and request.name.strip() else None
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="A valid user email is required")

    existing = get_user_by_email(session, email=email)
    if existing is not None:
        if existing.organization_id == auth.organization_id:
            raise HTTPException(status_code=409, detail="User already exists")
        raise HTTPException(status_code=409, detail="User email belongs to another organization")

    record = create_user(
        session,
        organization_id=auth.organization_id,
        email=email,
        name=name,
        role=request.role,
    )
    create_audit_event(
        session,
        organization_id=auth.organization_id,
        actor_type="api_key",
        actor_id=auth.api_key_id,
        action=AUDIT_ACTION_USER_CREATED,
        target_type="user",
        target_id=record.id,
        metadata={
            "user_role": record.role,
        },
    )
    return user_response(record)


@router.patch("/api/users/{user_id}", response_model=UserResponse)
def update_org_user(
    user_id: str,
    request: UserUpdateRequest,
    auth: AuthContext = Depends(require_admin_api_key),
    session: Session = Depends(get_session),
) -> UserResponse:
    record = get_user(session, organization_id=auth.organization_id, user_id=user_id)
    if record is None:
        raise HTTPException(status_code=404, detail="User not found")
    if (
        request.role == "reviewer"
        and record.role == "admin"
        and count_admin_users(session, organization_id=auth.organization_id) <= 1
    ):
        raise HTTPException(status_code=400, detail="Cannot demote the last organization admin")

    previous_role = record.role
    name = request.name.strip() if request.name is not None and request.name.strip() else record.name
    updated = update_user(session, record, name=name, role=request.role)
    create_audit_event(
        session,
        organization_id=auth.organization_id,
        actor_type="api_key",
        actor_id=auth.api_key_id,
        action=AUDIT_ACTION_USER_UPDATED,
        target_type="user",
        target_id=updated.id,
        metadata={
            "previous_role": previous_role,
            "user_role": updated.role,
        },
    )
    return user_response(updated)


@router.delete("/api/users/{user_id}", status_code=204)
def delete_org_user(
    user_id: str,
    auth: AuthContext = Depends(require_admin_api_key),
    session: Session = Depends(get_session),
) -> Response:
    record = get_user(session, organization_id=auth.organization_id, user_id=user_id)
    if record is None:
        raise HTTPException(status_code=404, detail="User not found")
    if record.role == "admin" and count_admin_users(session, organization_id=auth.organization_id) <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last organization admin")

    deleted_role = record.role
    delete_user(session, record)
    create_audit_event(
        session,
        organization_id=auth.organization_id,
        actor_type="api_key",
        actor_id=auth.api_key_id,
        action=AUDIT_ACTION_USER_DELETED,
        target_type="user",
        target_id=user_id,
        metadata={
            "user_role": deleted_role,
        },
    )
    return Response(status_code=204)
