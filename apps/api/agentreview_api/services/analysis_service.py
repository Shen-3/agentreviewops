from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from agentreview.ai import AIProviderConfigError, AIProviderRequestError
from agentreview.analysis import analyze_diff_text
from agentreview.models import ReviewRequirement
from agentreview.plugins import PluginError
from agentreview_api.audit import AUDIT_ACTION_ANALYSIS_CREATED
from agentreview_api.auth import AuthContext
from agentreview_api.db import AnalysisRunRecord
from agentreview_api.repository import (
    create_analysis_run,
    create_audit_event,
    get_analysis_run,
    to_diff_files,
    to_review_requirements,
    to_risk_findings,
)
from agentreview_api.schemas.analysis import (
    AnalysisReportResponse,
    AnalysisRunSummaryResponse,
    AnalyzeDiffRequest,
    AnalyzeDiffResponse,
)
from agentreview_api.services.policy_service import resolve_analysis_config
from agentreview_api.services.repository_service import repository_reviewers_for_analysis


def analyze_and_persist_diff(
    request: AnalyzeDiffRequest,
    auth: AuthContext,
    session: Session,
) -> AnalyzeDiffResponse:
    policy_selection = resolve_analysis_config(request.repository, request.config, auth, session)
    config = policy_selection.config
    repository_reviewers = repository_reviewers_for_analysis(policy_selection.repository)
    try:
        result = analyze_diff_text(
            request.diff,
            config=config,
            repository_reviewers=repository_reviewers,
        )
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
        review_requirements=result.review_requirements,
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
            "review_requirement_count": len(result.review_requirements),
            "unconfigured_review_requirement_count": unconfigured_review_requirement_count(result.review_requirements),
            "reviewer_sources": reviewer_sources(result.review_requirements),
            "required_roles": required_roles(result.review_requirements),
            "config_source": policy_selection.source,
            "policy_id": policy_selection.policy.id if policy_selection.policy is not None else None,
            "policy_name": policy_selection.policy.name if policy_selection.policy is not None else None,
            "repository_id": policy_selection.repository.id if policy_selection.repository is not None else None,
            "routed_reviewer_count": len(policy_selection.repository.memberships)
            if policy_selection.repository is not None
            else 0,
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
        review_requirements=result.review_requirements,
        markdown=result.markdown,
    )


def analysis_run_summary_response(record: AnalysisRunRecord) -> AnalysisRunSummaryResponse:
    return AnalysisRunSummaryResponse(
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


def analysis_report_response(
    analysis_run_id: str,
    auth: AuthContext,
    session: Session,
) -> AnalysisReportResponse:
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
        review_requirements=to_review_requirements(record),
        markdown=record.markdown,
    )


def unconfigured_review_requirement_count(review_requirements: list[ReviewRequirement]) -> int:
    return sum(1 for requirement in review_requirements if not requirement.suggested_reviewers)


def reviewer_sources(review_requirements: list[ReviewRequirement]) -> list[str]:
    return sorted(
        {reviewer.source for requirement in review_requirements for reviewer in requirement.suggested_reviewers}
    )


def required_roles(review_requirements: list[ReviewRequirement]) -> list[str]:
    return sorted({role for requirement in review_requirements for role in requirement.required_roles})
