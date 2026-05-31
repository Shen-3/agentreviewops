from __future__ import annotations

import csv
import json
from datetime import datetime
from io import StringIO
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agentreview.gitdiff import parse_unified_diff
from agentreview.models import AgentReviewConfig, DiffFile, RiskFinding, RiskLevel
from agentreview.report import generate_markdown_report
from agentreview.risk import analyze_risk
from agentreview_api.audit import (
    AUDIT_ACTION_ANALYSIS_CREATED,
    AUDIT_ACTION_API_KEY_CREATED,
    AUDIT_ACTION_API_KEY_REVOKED,
    AUDIT_ACTION_POLICY_CREATED,
)
from agentreview_api.auth import AuthContext, require_api_key
from agentreview_api.db import get_session
from agentreview_api.repository import (
    create_analysis_run,
    create_api_key,
    create_audit_event,
    create_policy,
    get_analysis_run,
    get_enabled_policy,
    list_analysis_runs,
    list_api_keys,
    list_audit_events,
    list_policies,
    revoke_api_key,
    to_diff_files,
    to_risk_findings,
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
    allow_methods=["GET", "POST"],
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


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255, description="Human-readable API key name.")


class ApiKeyResponse(BaseModel):
    api_key_id: str
    name: str
    key_prefix: str
    created_at: datetime
    revoked_at: datetime | None
    is_current: bool


class ApiKeyCreateResponse(ApiKeyResponse):
    api_key: str


class PolicyCreateRequest(BaseModel):
    name: str = Field(min_length=1, description="Human-readable policy name.")
    config: AgentReviewConfig
    enabled: bool = True
    scope: str = Field(default="organization", pattern="^organization$")


class PolicyResponse(BaseModel):
    policy_id: str
    name: str
    scope: str
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


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="agentreview-api")


@app.get("/api/auth/me", response_model=AuthMeResponse)
def auth_me(auth: AuthContext = Depends(require_api_key)) -> AuthMeResponse:
    return AuthMeResponse(
        organization_id=auth.organization_id,
        api_key_id=auth.api_key_id,
        api_key_name=auth.api_key_name,
    )


@app.get("/api/api-keys", response_model=list[ApiKeyResponse])
def get_api_keys(auth: AuthContext = Depends(require_api_key), session: Session = Depends(get_session)) -> list[ApiKeyResponse]:
    return [_api_key_response(record, auth=auth) for record in list_api_keys(session, organization_id=auth.organization_id)]


@app.post("/api/api-keys", response_model=ApiKeyCreateResponse)
def create_org_api_key(
    request: ApiKeyCreateRequest,
    auth: AuthContext = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> ApiKeyCreateResponse:
    normalized_name = request.name.strip()
    if not normalized_name:
        raise HTTPException(status_code=422, detail="API key name is required")

    record, secret = create_api_key(
        session,
        organization_id=auth.organization_id,
        name=normalized_name,
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
            "source": "api",
        },
    )
    return ApiKeyCreateResponse(
        **_api_key_response(record, auth=auth).model_dump(),
        api_key=secret,
    )


@app.post("/api/api-keys/{api_key_id}/revoke", response_model=ApiKeyResponse)
def revoke_org_api_key(
    api_key_id: str,
    auth: AuthContext = Depends(require_api_key),
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


@app.get("/api/policies", response_model=list[PolicyResponse])
def get_policies(auth: AuthContext = Depends(require_api_key), session: Session = Depends(get_session)) -> list[PolicyResponse]:
    return [_policy_response(record) for record in list_policies(session, organization_id=auth.organization_id)]


@app.post("/api/policies", response_model=PolicyResponse)
def save_policy(
    request: PolicyCreateRequest,
    auth: AuthContext = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> PolicyResponse:
    record = create_policy(
        session,
        organization_id=auth.organization_id,
        name=request.name,
        config=request.config,
        enabled=request.enabled,
        scope=request.scope,
    )
    create_audit_event(
        session,
        organization_id=auth.organization_id,
        actor_type="api_key",
        actor_id=auth.api_key_id,
        action=AUDIT_ACTION_POLICY_CREATED,
        target_type="policy",
        target_id=record.id,
        metadata={
            "policy_name": record.name,
            "enabled": record.enabled,
            "scope": record.scope,
        },
    )
    return _policy_response(record)


@app.post("/api/analyze/diff", response_model=AnalyzeDiffResponse)
def analyze_diff(
    request: AnalyzeDiffRequest,
    auth: AuthContext = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> AnalyzeDiffResponse:
    config = _resolve_analysis_config(request.config, auth, session)
    changed_files = parse_unified_diff(request.diff, config=config)
    analysis = analyze_risk(changed_files, config=config)
    markdown = generate_markdown_report(analysis, changed_files, config=config)
    record = create_analysis_run(
        session,
        changed_files=changed_files,
        analysis=analysis,
        markdown=markdown,
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
            "risk_level": analysis.risk_level,
            "risk_score": analysis.risk_score,
            "changed_file_count": len(changed_files),
            "finding_count": len(analysis.findings),
            "config_source": "organization_policy" if get_enabled_policy(session, organization_id=auth.organization_id) is not None else "request_or_default",
        },
    )

    return AnalyzeDiffResponse(
        analysis_run_id=record.id,
        created_at=record.created_at,
        risk_score=analysis.risk_score,
        risk_level=analysis.risk_level,
        findings=analysis.findings,
        changed_files=changed_files,
        markdown=markdown,
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


def _resolve_analysis_config(request_config: AgentReviewConfig | None, auth: AuthContext, session: Session) -> AgentReviewConfig:
    policy = get_enabled_policy(session, organization_id=auth.organization_id)
    if policy is not None:
        return AgentReviewConfig.model_validate(policy.config_json)
    return request_config or AgentReviewConfig()


def _policy_response(record) -> PolicyResponse:
    return PolicyResponse(
        policy_id=record.id,
        name=record.name,
        scope=record.scope,
        enabled=record.enabled,
        config=AgentReviewConfig.model_validate(record.config_json),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _api_key_response(record, *, auth: AuthContext) -> ApiKeyResponse:
    return ApiKeyResponse(
        api_key_id=record.id,
        name=record.name,
        key_prefix=record.key_prefix,
        created_at=record.created_at,
        revoked_at=record.revoked_at,
        is_current=record.id == auth.api_key_id,
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
