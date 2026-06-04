from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from agentreview_api.deps import AuthContext, get_session, require_analysis_api_key, require_api_key
from agentreview_api.repository import list_analysis_runs
from agentreview_api.schemas.analysis import (
    AnalysisReportResponse,
    AnalysisRunSummaryResponse,
    AnalyzeDiffRequest,
    AnalyzeDiffResponse,
)
from agentreview_api.services.analysis_service import (
    analysis_report_response,
    analysis_run_summary_response,
    analyze_and_persist_diff,
)

router = APIRouter()


@router.post("/api/analyze/diff", response_model=AnalyzeDiffResponse)
def analyze_diff(
    request: AnalyzeDiffRequest,
    auth: AuthContext = Depends(require_analysis_api_key),
    session: Session = Depends(get_session),
) -> AnalyzeDiffResponse:
    return analyze_and_persist_diff(request, auth, session)


@router.get("/api/analysis-runs", response_model=list[AnalysisRunSummaryResponse])
def list_runs(
    limit: int = Query(default=50, ge=1, le=200),
    auth: AuthContext = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> list[AnalysisRunSummaryResponse]:
    return [
        analysis_run_summary_response(record)
        for record in list_analysis_runs(session, organization_id=auth.organization_id, limit=limit)
    ]


@router.get("/api/analysis-runs/{analysis_run_id}", response_model=AnalysisReportResponse)
def get_analysis_run_detail(
    analysis_run_id: str,
    auth: AuthContext = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> AnalysisReportResponse:
    return analysis_report_response(analysis_run_id, auth, session)


@router.get("/api/analysis-runs/{analysis_run_id}/report", response_model=AnalysisReportResponse)
def get_report(
    analysis_run_id: str,
    auth: AuthContext = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> AnalysisReportResponse:
    return analysis_report_response(analysis_run_id, auth, session)
