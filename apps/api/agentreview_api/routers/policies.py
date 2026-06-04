from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from agentreview_api.audit import AUDIT_ACTION_POLICY_CREATED, AUDIT_ACTION_POLICY_UPDATED
from agentreview_api.deps import AuthContext, get_session, require_admin_api_key, require_api_key
from agentreview_api.repository import (
    create_audit_event,
    create_policy,
    get_policy,
    get_repository,
    list_policies,
    update_policy,
)
from agentreview_api.schemas.policies import PolicyCreateRequest, PolicyResponse, PolicyUpdateRequest
from agentreview_api.services.policy_service import compact_metadata, policy_response

router = APIRouter()


@router.get("/api/policies", response_model=list[PolicyResponse])
def get_policies(
    auth: AuthContext = Depends(require_api_key), session: Session = Depends(get_session)
) -> list[PolicyResponse]:
    return [policy_response(record) for record in list_policies(session, organization_id=auth.organization_id)]


@router.post("/api/policies", response_model=PolicyResponse)
def save_policy(
    request: PolicyCreateRequest,
    auth: AuthContext = Depends(require_admin_api_key),
    session: Session = Depends(get_session),
) -> PolicyResponse:
    repository = None
    if request.scope == "repository":
        if not request.repository_id:
            raise HTTPException(status_code=422, detail="repository_id is required for repository-scoped policies")
        repository = get_repository(session, organization_id=auth.organization_id, repository_id=request.repository_id)
        if repository is None:
            raise HTTPException(status_code=404, detail="Repository not found")
    elif request.repository_id is not None:
        raise HTTPException(status_code=422, detail="repository_id is only valid for repository-scoped policies")

    record = create_policy(
        session,
        organization_id=auth.organization_id,
        name=request.name,
        config=request.config,
        enabled=request.enabled,
        scope=request.scope,
        repository_id=repository.id if repository is not None else None,
    )
    create_audit_event(
        session,
        organization_id=auth.organization_id,
        actor_type="api_key",
        actor_id=auth.api_key_id,
        action=AUDIT_ACTION_POLICY_CREATED,
        target_type="policy",
        target_id=record.id,
        metadata=compact_metadata(
            {
                "policy_name": record.name,
                "enabled": record.enabled,
                "scope": record.scope,
                "repository": f"{repository.owner}/{repository.name}" if repository is not None else None,
            }
        ),
    )
    return policy_response(record)


@router.patch("/api/policies/{policy_id}", response_model=PolicyResponse)
def update_saved_policy(
    policy_id: str,
    request: PolicyUpdateRequest,
    auth: AuthContext = Depends(require_admin_api_key),
    session: Session = Depends(get_session),
) -> PolicyResponse:
    record = get_policy(session, organization_id=auth.organization_id, policy_id=policy_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    if request.name is None and request.config is None and request.enabled is None:
        raise HTTPException(status_code=400, detail="At least one policy field is required")
    if request.name is not None and not request.name.strip():
        raise HTTPException(status_code=422, detail="Policy name is required")

    previous_enabled = record.enabled
    updated = update_policy(
        session,
        record,
        name=request.name.strip() if request.name is not None else None,
        config=request.config,
        enabled=request.enabled,
    )
    create_audit_event(
        session,
        organization_id=auth.organization_id,
        actor_type="api_key",
        actor_id=auth.api_key_id,
        action=AUDIT_ACTION_POLICY_UPDATED,
        target_type="policy",
        target_id=updated.id,
        metadata=compact_metadata(
            {
                "policy_name": updated.name,
                "enabled": updated.enabled,
                "previous_enabled": previous_enabled,
                "scope": updated.scope,
                "repository": f"{updated.repository.owner}/{updated.repository.name}"
                if updated.repository is not None
                else None,
            }
        ),
    )
    return policy_response(updated)
