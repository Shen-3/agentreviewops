from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from agentreview_api.audit import (
    AUDIT_ACTION_REPOSITORY_CREATED,
    AUDIT_ACTION_REPOSITORY_DELETED,
    AUDIT_ACTION_REPOSITORY_MEMBERSHIP_CREATED,
    AUDIT_ACTION_REPOSITORY_MEMBERSHIP_DELETED,
    AUDIT_ACTION_REPOSITORY_MEMBERSHIP_UPDATED,
)
from agentreview_api.deps import AuthContext, get_session, require_admin_api_key, require_api_key
from agentreview_api.repository import (
    create_audit_event,
    create_repository,
    create_repository_membership,
    delete_repository,
    delete_repository_membership,
    get_repository,
    get_repository_by_identity,
    get_repository_membership,
    get_user,
    list_repositories,
    update_repository_membership,
)
from agentreview_api.schemas.repositories import (
    RepositoryCreateRequest,
    RepositoryMembershipCreateRequest,
    RepositoryMembershipUpdateRequest,
    RepositoryResponse,
)
from agentreview_api.services.repository_service import repository_response

router = APIRouter()


@router.get("/api/repositories", response_model=list[RepositoryResponse])
def get_repositories(
    auth: AuthContext = Depends(require_api_key), session: Session = Depends(get_session)
) -> list[RepositoryResponse]:
    return [repository_response(record) for record in list_repositories(session, organization_id=auth.organization_id)]


@router.post("/api/repositories", response_model=RepositoryResponse)
def create_org_repository(
    request: RepositoryCreateRequest,
    auth: AuthContext = Depends(require_admin_api_key),
    session: Session = Depends(get_session),
) -> RepositoryResponse:
    provider = request.provider.strip().lower()
    owner = request.owner.strip()
    name = request.name.strip()
    default_branch = (
        request.default_branch.strip() if request.default_branch and request.default_branch.strip() else None
    )
    visibility = request.visibility.strip().lower() if request.visibility and request.visibility.strip() else None
    if not provider or not owner or not name:
        raise HTTPException(status_code=422, detail="Repository provider, owner, and name are required")

    existing = get_repository_by_identity(
        session,
        organization_id=auth.organization_id,
        provider=provider,
        owner=owner,
        name=name,
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Repository already exists")

    record = create_repository(
        session,
        organization_id=auth.organization_id,
        provider=provider,
        owner=owner,
        name=name,
        default_branch=default_branch,
        visibility=visibility,
    )
    create_audit_event(
        session,
        organization_id=auth.organization_id,
        actor_type="api_key",
        actor_id=auth.api_key_id,
        action=AUDIT_ACTION_REPOSITORY_CREATED,
        target_type="repository",
        target_id=record.id,
        metadata={
            "provider": record.provider,
            "owner": record.owner,
            "name": record.name,
            "default_branch": record.default_branch,
            "visibility": record.visibility,
        },
    )
    return repository_response(record)


@router.delete("/api/repositories/{repository_id}", status_code=204)
def delete_org_repository(
    repository_id: str,
    auth: AuthContext = Depends(require_admin_api_key),
    session: Session = Depends(get_session),
) -> Response:
    repository = get_repository(session, organization_id=auth.organization_id, repository_id=repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    metadata = {
        "provider": repository.provider,
        "owner": repository.owner,
        "name": repository.name,
        "repository": f"{repository.owner}/{repository.name}",
    }
    delete_repository(session, repository)
    create_audit_event(
        session,
        organization_id=auth.organization_id,
        actor_type="api_key",
        actor_id=auth.api_key_id,
        action=AUDIT_ACTION_REPOSITORY_DELETED,
        target_type="repository",
        target_id=repository_id,
        metadata=metadata,
    )
    return Response(status_code=204)


@router.post("/api/repositories/{repository_id}/memberships", response_model=RepositoryResponse)
def assign_repository_membership(
    repository_id: str,
    request: RepositoryMembershipCreateRequest,
    auth: AuthContext = Depends(require_admin_api_key),
    session: Session = Depends(get_session),
) -> RepositoryResponse:
    repository = get_repository(session, organization_id=auth.organization_id, repository_id=repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    user = get_user(session, organization_id=auth.organization_id, user_id=request.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    existing = get_repository_membership(session, repository_id=repository.id, user_id=user.id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="User is already assigned to this repository")

    membership = create_repository_membership(
        session,
        repository_id=repository.id,
        user_id=user.id,
        role=request.role,
    )
    create_audit_event(
        session,
        organization_id=auth.organization_id,
        actor_type="api_key",
        actor_id=auth.api_key_id,
        action=AUDIT_ACTION_REPOSITORY_MEMBERSHIP_CREATED,
        target_type="repository",
        target_id=repository.id,
        metadata={
            "repository": f"{repository.owner}/{repository.name}",
            "user_id": user.id,
            "membership_id": membership.id,
            "membership_role": membership.role,
        },
    )
    refreshed = get_repository(session, organization_id=auth.organization_id, repository_id=repository.id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repository_response(refreshed)


@router.delete("/api/repositories/{repository_id}/memberships/{user_id}", response_model=RepositoryResponse)
def remove_repository_membership(
    repository_id: str,
    user_id: str,
    auth: AuthContext = Depends(require_admin_api_key),
    session: Session = Depends(get_session),
) -> RepositoryResponse:
    repository = get_repository(session, organization_id=auth.organization_id, repository_id=repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    membership = get_repository_membership(session, repository_id=repository.id, user_id=user_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Repository membership not found")

    membership_role = membership.role
    membership_id = membership.id
    delete_repository_membership(session, membership)
    create_audit_event(
        session,
        organization_id=auth.organization_id,
        actor_type="api_key",
        actor_id=auth.api_key_id,
        action=AUDIT_ACTION_REPOSITORY_MEMBERSHIP_DELETED,
        target_type="repository",
        target_id=repository.id,
        metadata={
            "repository": f"{repository.owner}/{repository.name}",
            "user_id": user_id,
            "membership_id": membership_id,
            "membership_role": membership_role,
        },
    )
    refreshed = get_repository(session, organization_id=auth.organization_id, repository_id=repository.id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repository_response(refreshed)


@router.patch("/api/repositories/{repository_id}/memberships/{user_id}", response_model=RepositoryResponse)
def update_repository_membership_role(
    repository_id: str,
    user_id: str,
    request: RepositoryMembershipUpdateRequest,
    auth: AuthContext = Depends(require_admin_api_key),
    session: Session = Depends(get_session),
) -> RepositoryResponse:
    repository = get_repository(session, organization_id=auth.organization_id, repository_id=repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    membership = get_repository_membership(session, repository_id=repository.id, user_id=user_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Repository membership not found")

    previous_role = membership.role
    updated = update_repository_membership(session, membership, role=request.role)
    create_audit_event(
        session,
        organization_id=auth.organization_id,
        actor_type="api_key",
        actor_id=auth.api_key_id,
        action=AUDIT_ACTION_REPOSITORY_MEMBERSHIP_UPDATED,
        target_type="repository",
        target_id=repository.id,
        metadata={
            "repository": f"{repository.owner}/{repository.name}",
            "user_id": user_id,
            "membership_id": updated.id,
            "previous_role": previous_role,
            "membership_role": updated.role,
        },
    )
    refreshed = get_repository(session, organization_id=auth.organization_id, repository_id=repository.id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repository_response(refreshed)
