from __future__ import annotations

from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agentreview.gitdiff import parse_unified_diff
from agentreview.models import AgentReviewConfig, DiffFile, RiskFinding, RiskLevel
from agentreview.report import generate_markdown_report
from agentreview.risk import analyze_risk
from agentreview_api.auth import AuthContext, require_api_key
from agentreview_api.db import get_session
from agentreview_api.repository import (
    create_analysis_run,
    create_policy,
    get_analysis_run,
    get_enabled_policy,
    list_analysis_runs,
    list_policies,
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
