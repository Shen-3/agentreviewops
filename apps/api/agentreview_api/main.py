from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agentreview.ai import AIProviderConfigError, AIProviderRequestError
from agentreview.analysis import analyze_diff_text
from agentreview.models import AgentReviewConfig, DiffFile, RiskFinding, RiskLevel
from agentreview.plugins import PluginError
from agentreview_api.audit import (
    AUDIT_ACTION_ANALYSIS_CREATED,
    AUDIT_ACTION_API_KEY_CREATED,
    AUDIT_ACTION_API_KEY_REVOKED,
    AUDIT_ACTION_API_KEY_UPDATED,
    AUDIT_ACTION_POLICY_CREATED,
    AUDIT_ACTION_POLICY_UPDATED,
    AUDIT_ACTION_REPOSITORY_CREATED,
    AUDIT_ACTION_REPOSITORY_MEMBERSHIP_CREATED,
    AUDIT_ACTION_REPOSITORY_MEMBERSHIP_DELETED,
    AUDIT_ACTION_REPOSITORY_MEMBERSHIP_UPDATED,
    AUDIT_ACTION_RETENTION_PURGED,
    AUDIT_ACTION_USER_CREATED,
    AUDIT_ACTION_USER_DELETED,
    AUDIT_ACTION_USER_UPDATED,
)
from agentreview_api.auth import AuthContext, require_admin_api_key, require_analysis_api_key, require_api_key
from agentreview_api.db import PolicyRecord, RepositoryRecord, get_session
from agentreview_api.repository import (
    create_analysis_run,
    create_api_key,
    create_audit_event,
    create_policy,
    create_repository,
    create_repository_membership,
    create_user,
    count_retention_candidates,
    count_admin_users,
    delete_repository_membership,
    delete_user,
    get_analysis_run,
    get_api_key,
    get_enabled_policy,
    get_enabled_repository_policy,
    get_policy,
    get_repository,
    get_repository_by_identity,
    get_repository_membership,
    get_user,
    get_user_by_email,
    list_analysis_runs,
    list_api_keys,
    list_audit_events,
    list_policies,
    list_repositories,
    list_users,
    purge_retention_records,
    revoke_api_key,
    to_diff_files,
    to_risk_findings,
    update_api_key,
    update_policy,
    update_repository_membership,
    update_user,
)

app = FastAPI(
    title="AgentReviewOps API",
    version="0.1.0",
    summary="Analyze pull request diffs and generate review reports.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8080",
        "http://localhost:8080",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str
    service: str


class AnalyzeDiffRequest(BaseModel):
    diff: str = Field(min_length=1, description="Unified git diff text to analyze.")
    config: AgentReviewConfig | None = Field(default=None, description="Optional AgentReviewOps policy config.")
    repository: str | None = Field(default=None, description="Repository identifier such as owner/name.")
    pull_request_number: int | None = Field(default=None, ge=1, description="Pull request number, when available.")
    title: str | None = Field(default=None, description="Pull request or analysis title.")
    author: str | None = Field(default=None, description="Pull request author or agent account.")
    agent_name: str | None = Field(default=None, description="Detected or supplied AI agent name.")
    branch: str | None = Field(default=None, description="Source branch name.")


class AnalyzeDiffResponse(BaseModel):
    analysis_run_id: str
    created_at: datetime
    risk_score: int
    risk_level: RiskLevel
    findings: list[RiskFinding]
    changed_files: list[DiffFile]
    markdown: str


class AnalysisRunSummaryResponse(BaseModel):
    analysis_run_id: str
    created_at: datetime
    source: str
    repository: str | None
    pull_request_number: int | None
    title: str | None
    author: str | None
    agent_name: str | None
    branch: str | None
    risk_score: int
    risk_level: RiskLevel
    summary: str
    changed_file_count: int
    finding_count: int


class AnalysisReportResponse(BaseModel):
    analysis_run_id: str
    created_at: datetime
    risk_score: int
    risk_level: RiskLevel
    findings: list[RiskFinding]
    changed_files: list[DiffFile]
    markdown: str


class AuthMeResponse(BaseModel):
    organization_id: str
    api_key_id: str
    api_key_name: str
    api_key_role: str


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255, description="Human-readable API key name.")
    role: str = Field(default="admin", pattern="^(admin|ci|read_only)$")


class RepositoryCreateRequest(BaseModel):
    provider: str = Field(default="github", min_length=1, max_length=50, description="Source control provider.")
    owner: str = Field(min_length=1, max_length=255, description="Repository owner or namespace.")
    name: str = Field(min_length=1, max_length=255, description="Repository name.")
    default_branch: str | None = Field(default=None, max_length=255)
    visibility: str | None = Field(default=None, max_length=50)


class RepositoryReviewerResponse(BaseModel):
    user_id: str
    email: str
    name: str | None
    role: str


class RepositoryResponse(BaseModel):
    repository_id: str
    provider: str
    owner: str
    name: str
    full_name: str
    default_branch: str | None
    visibility: str | None
    reviewers: list[RepositoryReviewerResponse]
    created_at: datetime


class UserCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255, description="Organization user email.")
    name: str | None = Field(default=None, max_length=255)
    role: str = Field(default="reviewer", pattern="^(admin|reviewer)$")


class UserUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    role: str | None = Field(default=None, pattern="^(admin|reviewer)$")


class UserResponse(BaseModel):
    user_id: str
    email: str
    name: str | None
    role: str
    created_at: datetime


class RepositoryMembershipCreateRequest(BaseModel):
    user_id: str = Field(min_length=1)
    role: str = Field(default="reviewer", pattern="^(owner|maintainer|reviewer)$")


class RepositoryMembershipUpdateRequest(BaseModel):
    role: str = Field(pattern="^(owner|maintainer|reviewer)$")


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


class AuditEventResponse(BaseModel):
    audit_event_id: str
    created_at: datetime
    actor_type: str
    actor_id: str | None
    action: str
    target_type: str
    target_id: str | None
    metadata: dict


class RetentionPurgeRequest(BaseModel):
    older_than_days: int = Field(ge=1, le=3650, description="Delete records older than this many days.")
    include_analysis_runs: bool = Field(default=True, description="Include stored analysis reports and findings.")
    include_audit_events: bool = Field(default=False, description="Include audit events older than the cutoff.")
    dry_run: bool = Field(default=True, description="When true, only count matching records.")
    confirm: bool = Field(default=False, description="Must be true when dry_run is false.")


class RetentionPurgeResponse(BaseModel):
    cutoff: datetime
    older_than_days: int
    dry_run: bool
    include_analysis_runs: bool
    include_audit_events: bool
    analysis_run_count: int
    audit_event_count: int


@dataclass(frozen=True)
class PolicySelection:
    config: AgentReviewConfig
    source: str
    policy: PolicyRecord | None
    repository: RepositoryRecord | None


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="agentreview-api")


@app.get("/api/auth/me", response_model=AuthMeResponse)
def auth_me(auth: AuthContext = Depends(require_api_key)) -> AuthMeResponse:
    return AuthMeResponse(
        organization_id=auth.organization_id,
        api_key_id=auth.api_key_id,
        api_key_name=auth.api_key_name,
        api_key_role=auth.api_key_role,
    )


@app.get("/api/repositories", response_model=list[RepositoryResponse])
def get_repositories(auth: AuthContext = Depends(require_api_key), session: Session = Depends(get_session)) -> list[RepositoryResponse]:
    return [_repository_response(record) for record in list_repositories(session, organization_id=auth.organization_id)]


@app.post("/api/repositories", response_model=RepositoryResponse)
def create_org_repository(
    request: RepositoryCreateRequest,
    auth: AuthContext = Depends(require_admin_api_key),
    session: Session = Depends(get_session),
) -> RepositoryResponse:
    provider = request.provider.strip().lower()
    owner = request.owner.strip()
    name = request.name.strip()
    default_branch = request.default_branch.strip() if request.default_branch and request.default_branch.strip() else None
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
    return _repository_response(record)


@app.post("/api/repositories/{repository_id}/memberships", response_model=RepositoryResponse)
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
    return _repository_response(refreshed)


@app.delete("/api/repositories/{repository_id}/memberships/{user_id}", response_model=RepositoryResponse)
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
    return _repository_response(refreshed)


@app.patch("/api/repositories/{repository_id}/memberships/{user_id}", response_model=RepositoryResponse)
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
    return _repository_response(refreshed)


@app.get("/api/users", response_model=list[UserResponse])
def get_users(auth: AuthContext = Depends(require_api_key), session: Session = Depends(get_session)) -> list[UserResponse]:
    return [_user_response(record) for record in list_users(session, organization_id=auth.organization_id)]


@app.post("/api/users", response_model=UserResponse)
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
    return _user_response(record)


@app.patch("/api/users/{user_id}", response_model=UserResponse)
def update_org_user(
    user_id: str,
    request: UserUpdateRequest,
    auth: AuthContext = Depends(require_admin_api_key),
    session: Session = Depends(get_session),
) -> UserResponse:
    record = get_user(session, organization_id=auth.organization_id, user_id=user_id)
    if record is None:
        raise HTTPException(status_code=404, detail="User not found")
    if request.role == "reviewer" and record.role == "admin" and count_admin_users(session, organization_id=auth.organization_id) <= 1:
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
    return _user_response(updated)


@app.delete("/api/users/{user_id}", status_code=204)
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


@app.get("/api/api-keys", response_model=list[ApiKeyResponse])
def get_api_keys(auth: AuthContext = Depends(require_api_key), session: Session = Depends(get_session)) -> list[ApiKeyResponse]:
    return [_api_key_response(record, auth=auth) for record in list_api_keys(session, organization_id=auth.organization_id)]


@app.post("/api/api-keys", response_model=ApiKeyCreateResponse)
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


@app.patch("/api/api-keys/{api_key_id}", response_model=ApiKeyResponse)
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


@app.post("/api/api-keys/{api_key_id}/revoke", response_model=ApiKeyResponse)
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


@app.get("/api/audit-events", response_model=list[AuditEventResponse])
def get_audit_events(
    limit: int = Query(default=100, ge=1, le=500),
    action: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    target_id: str | None = Query(default=None),
    actor_type: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    auth: AuthContext = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> list[AuditEventResponse]:
    return [
        _audit_event_response(record)
        for record in list_audit_events(
            session,
            organization_id=auth.organization_id,
            limit=limit,
            action=action,
            target_type=target_type,
            target_id=target_id,
            actor_type=actor_type,
            since=since,
            until=until,
        )
    ]


@app.get("/api/audit-events/export")
def export_audit_events(
    format: Literal["json", "csv"] = Query(default="json"),
    limit: int = Query(default=500, ge=1, le=500),
    action: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    target_id: str | None = Query(default=None),
    actor_type: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    auth: AuthContext = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> Response:
    events = [
        _audit_event_response(record)
        for record in list_audit_events(
            session,
            organization_id=auth.organization_id,
            limit=limit,
            action=action,
            target_type=target_type,
            target_id=target_id,
            actor_type=actor_type,
            since=since,
            until=until,
        )
    ]
    filename = f"agentreview-audit-events.{format}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    if format == "json":
        return JSONResponse(content=jsonable_encoder(events), headers=headers)

    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "audit_event_id",
            "created_at",
            "actor_type",
            "actor_id",
            "action",
            "target_type",
            "target_id",
            "metadata",
        ],
    )
    writer.writeheader()
    for event in events:
        writer.writerow(
            {
                "audit_event_id": event.audit_event_id,
                "created_at": event.created_at.isoformat(),
                "actor_type": event.actor_type,
                "actor_id": event.actor_id or "",
                "action": event.action,
                "target_type": event.target_type,
                "target_id": event.target_id or "",
                "metadata": json.dumps(event.metadata, sort_keys=True, separators=(",", ":")),
            }
        )
    return Response(content=output.getvalue(), media_type="text/csv", headers=headers)


@app.post("/api/retention/purge", response_model=RetentionPurgeResponse)
def purge_retention(
    request: RetentionPurgeRequest,
    auth: AuthContext = Depends(require_admin_api_key),
    session: Session = Depends(get_session),
) -> RetentionPurgeResponse:
    if not request.include_analysis_runs and not request.include_audit_events:
        raise HTTPException(status_code=422, detail="At least one retention target must be enabled")
    if not request.dry_run and not request.confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to run a non-dry-run retention purge")

    cutoff = datetime.now(timezone.utc) - timedelta(days=request.older_than_days)
    if request.dry_run:
        candidate_analysis_count, candidate_audit_count = count_retention_candidates(
            session,
            organization_id=auth.organization_id,
            before=cutoff,
        )
        return RetentionPurgeResponse(
            cutoff=cutoff,
            older_than_days=request.older_than_days,
            dry_run=True,
            include_analysis_runs=request.include_analysis_runs,
            include_audit_events=request.include_audit_events,
            analysis_run_count=candidate_analysis_count if request.include_analysis_runs else 0,
            audit_event_count=candidate_audit_count if request.include_audit_events else 0,
        )

    analysis_count, audit_count = purge_retention_records(
        session,
        organization_id=auth.organization_id,
        before=cutoff,
        include_analysis_runs=request.include_analysis_runs,
        include_audit_events=request.include_audit_events,
    )
    create_audit_event(
        session,
        organization_id=auth.organization_id,
        actor_type="api_key",
        actor_id=auth.api_key_id,
        action=AUDIT_ACTION_RETENTION_PURGED,
        target_type="organization",
        target_id=auth.organization_id,
        metadata={
            "older_than_days": request.older_than_days,
            "cutoff": cutoff.isoformat(),
            "include_analysis_runs": request.include_analysis_runs,
            "include_audit_events": request.include_audit_events,
            "analysis_run_count": analysis_count,
            "audit_event_count": audit_count,
        },
    )
    return RetentionPurgeResponse(
        cutoff=cutoff,
        older_than_days=request.older_than_days,
        dry_run=False,
        include_analysis_runs=request.include_analysis_runs,
        include_audit_events=request.include_audit_events,
        analysis_run_count=analysis_count,
        audit_event_count=audit_count,
    )


@app.get("/api/policies", response_model=list[PolicyResponse])
def get_policies(auth: AuthContext = Depends(require_api_key), session: Session = Depends(get_session)) -> list[PolicyResponse]:
    return [_policy_response(record) for record in list_policies(session, organization_id=auth.organization_id)]


@app.post("/api/policies", response_model=PolicyResponse)
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
        metadata=_compact_metadata(
            {
                "policy_name": record.name,
                "enabled": record.enabled,
                "scope": record.scope,
                "repository": f"{repository.owner}/{repository.name}" if repository is not None else None,
            }
        ),
    )
    return _policy_response(record)


@app.patch("/api/policies/{policy_id}", response_model=PolicyResponse)
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
        metadata=_compact_metadata(
            {
                "policy_name": updated.name,
                "enabled": updated.enabled,
                "previous_enabled": previous_enabled,
                "scope": updated.scope,
                "repository": f"{updated.repository.owner}/{updated.repository.name}" if updated.repository is not None else None,
            }
        ),
    )
    return _policy_response(updated)


@app.post("/api/analyze/diff", response_model=AnalyzeDiffResponse)
def analyze_diff(
    request: AnalyzeDiffRequest,
    auth: AuthContext = Depends(require_analysis_api_key),
    session: Session = Depends(get_session),
) -> AnalyzeDiffResponse:
    policy_selection = _resolve_analysis_config(request.repository, request.config, auth, session)
    config = policy_selection.config
    try:
        result = analyze_diff_text(request.diff, config=config)
    except PluginError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AIProviderConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AIProviderRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    record = create_analysis_run(
        session,
        changed_files=result.changed_files,
        analysis=result.analysis,
        markdown=result.markdown,
        config=config,
        source="api",
        organization_id=auth.organization_id,
        repository=request.repository,
        pull_request_number=request.pull_request_number,
        title=request.title,
        author=request.author,
        agent_name=request.agent_name,
        branch=request.branch,
    )
    create_audit_event(
        session,
        organization_id=auth.organization_id,
        actor_type="api_key",
        actor_id=auth.api_key_id,
        action=AUDIT_ACTION_ANALYSIS_CREATED,
        target_type="analysis_run",
        target_id=record.id,
        metadata={
            "repository": request.repository,
            "pull_request_number": request.pull_request_number,
            "agent_name": request.agent_name,
            "branch": request.branch,
            "risk_level": result.analysis.risk_level,
            "risk_score": result.analysis.risk_score,
            "changed_file_count": len(result.changed_files),
            "finding_count": len(result.analysis.findings),
            "config_source": policy_selection.source,
            "policy_id": policy_selection.policy.id if policy_selection.policy is not None else None,
            "policy_name": policy_selection.policy.name if policy_selection.policy is not None else None,
            "repository_id": policy_selection.repository.id if policy_selection.repository is not None else None,
            "routed_reviewer_count": len(policy_selection.repository.memberships) if policy_selection.repository is not None else 0,
            "routed_reviewer_roles": sorted({membership.role for membership in policy_selection.repository.memberships})
            if policy_selection.repository is not None
            else [],
        },
    )

    return AnalyzeDiffResponse(
        analysis_run_id=record.id,
        created_at=record.created_at,
        risk_score=result.analysis.risk_score,
        risk_level=result.analysis.risk_level,
        findings=result.analysis.findings,
        changed_files=result.changed_files,
        markdown=result.markdown,
    )


@app.get("/api/analysis-runs", response_model=list[AnalysisRunSummaryResponse])
def list_runs(
    limit: int = Query(default=50, ge=1, le=200),
    auth: AuthContext = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> list[AnalysisRunSummaryResponse]:
    return [
        AnalysisRunSummaryResponse(
            analysis_run_id=record.id,
            created_at=record.created_at,
            source=record.source,
            repository=record.repository,
            pull_request_number=record.pull_request_number,
            title=record.title,
            author=record.author,
            agent_name=record.agent_name,
            branch=record.branch,
            risk_score=record.risk_score,
            risk_level=record.risk_level,
            summary=record.summary,
            changed_file_count=len(record.changed_files),
            finding_count=len(record.findings),
        )
        for record in list_analysis_runs(session, organization_id=auth.organization_id, limit=limit)
    ]


@app.get("/api/analysis-runs/{analysis_run_id}", response_model=AnalysisReportResponse)
def get_analysis_run_detail(
    analysis_run_id: str,
    auth: AuthContext = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> AnalysisReportResponse:
    return _get_analysis_report_response(analysis_run_id, auth, session)


@app.get("/api/analysis-runs/{analysis_run_id}/report", response_model=AnalysisReportResponse)
def get_report(
    analysis_run_id: str,
    auth: AuthContext = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> AnalysisReportResponse:
    return _get_analysis_report_response(analysis_run_id, auth, session)


def _get_analysis_report_response(analysis_run_id: str, auth: AuthContext, session: Session) -> AnalysisReportResponse:
    record = get_analysis_run(session, analysis_run_id, organization_id=auth.organization_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    return AnalysisReportResponse(
        analysis_run_id=record.id,
        created_at=record.created_at,
        risk_score=record.risk_score,
        risk_level=record.risk_level,
        findings=to_risk_findings(record),
        changed_files=to_diff_files(record),
        markdown=record.markdown,
    )


def _resolve_analysis_config(
    repository_name: str | None,
    request_config: AgentReviewConfig | None,
    auth: AuthContext,
    session: Session,
) -> PolicySelection:
    repository = _find_repository_for_analysis(repository_name, auth, session)
    if repository is not None:
        repository_policy = get_enabled_repository_policy(
            session,
            organization_id=auth.organization_id,
            repository_id=repository.id,
        )
        if repository_policy is not None:
            return PolicySelection(
                config=AgentReviewConfig.model_validate(repository_policy.config_json),
                source="repository_policy",
                policy=repository_policy,
                repository=repository,
            )

    organization_policy = get_enabled_policy(session, organization_id=auth.organization_id)
    if organization_policy is not None:
        return PolicySelection(
            config=AgentReviewConfig.model_validate(organization_policy.config_json),
            source="organization_policy",
            policy=organization_policy,
            repository=repository,
        )

    if request_config is not None:
        return PolicySelection(config=request_config, source="request_config", policy=None, repository=repository)
    return PolicySelection(config=AgentReviewConfig(), source="default", policy=None, repository=repository)


def _find_repository_for_analysis(repository_name: str | None, auth: AuthContext, session: Session) -> RepositoryRecord | None:
    identity = _parse_repository_identity(repository_name)
    if identity is None:
        return None
    provider, owner, name = identity
    return get_repository_by_identity(
        session,
        organization_id=auth.organization_id,
        provider=provider,
        owner=owner,
        name=name,
    )


def _parse_repository_identity(repository_name: str | None) -> tuple[str, str, str] | None:
    if repository_name is None:
        return None
    normalized = repository_name.strip().rstrip("/")
    if not normalized:
        return None
    if normalized.startswith("https://github.com/"):
        normalized = normalized.removeprefix("https://github.com/")
    elif normalized.startswith("git@github.com:"):
        normalized = normalized.removeprefix("git@github.com:")
    elif "://" in normalized:
        return None
    if normalized.endswith(".git"):
        normalized = normalized[:-4]

    provider = "github"
    if ":" in normalized:
        provider_candidate, repository_path = normalized.split(":", 1)
        if provider_candidate and "/" in repository_path:
            provider = provider_candidate.strip().lower()
            normalized = repository_path

    owner_name = normalized.split("/")
    if len(owner_name) != 2 or not owner_name[0].strip() or not owner_name[1].strip():
        return None
    return provider, owner_name[0].strip(), owner_name[1].strip()


def _policy_response(record) -> PolicyResponse:
    return PolicyResponse(
        policy_id=record.id,
        name=record.name,
        scope=record.scope,
        repository_id=record.repository_id,
        repository_full_name=f"{record.repository.owner}/{record.repository.name}" if record.repository is not None else None,
        enabled=record.enabled,
        config=AgentReviewConfig.model_validate(record.config_json),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _api_key_response(record, *, auth: AuthContext) -> ApiKeyResponse:
    return ApiKeyResponse(
        api_key_id=record.id,
        name=record.name,
        role=record.role,
        key_prefix=record.key_prefix,
        created_at=record.created_at,
        revoked_at=record.revoked_at,
        is_current=record.id == auth.api_key_id,
    )


def _user_response(record) -> UserResponse:
    return UserResponse(
        user_id=record.id,
        email=record.email,
        name=record.name,
        role=record.role,
        created_at=record.created_at,
    )


def _repository_response(record) -> RepositoryResponse:
    return RepositoryResponse(
        repository_id=record.id,
        provider=record.provider,
        owner=record.owner,
        name=record.name,
        full_name=f"{record.owner}/{record.name}",
        default_branch=record.default_branch,
        visibility=record.visibility,
        reviewers=[
            RepositoryReviewerResponse(
                user_id=membership.user.id,
                email=membership.user.email,
                name=membership.user.name,
                role=membership.role,
            )
            for membership in sorted(record.memberships, key=lambda item: (item.role, item.user.email))
        ],
        created_at=record.created_at,
    )


def _audit_event_response(record) -> AuditEventResponse:
    return AuditEventResponse(
        audit_event_id=record.id,
        created_at=record.created_at,
        actor_type=record.actor_type,
        actor_id=record.actor_id,
        action=record.action,
        target_type=record.target_type,
        target_id=record.target_id,
        metadata=record.metadata_json,
    )


def _compact_metadata(metadata: dict) -> dict:
    return {key: value for key, value in metadata.items() if value is not None}
