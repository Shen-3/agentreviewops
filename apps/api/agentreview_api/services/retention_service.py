from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from agentreview_api.audit import AUDIT_ACTION_RETENTION_PURGED
from agentreview_api.auth import AuthContext
from agentreview_api.repository import count_retention_candidates, create_audit_event, purge_retention_records
from agentreview_api.schemas.retention import RetentionPurgeRequest, RetentionPurgeResponse


def purge_retention_records_for_request(
    request: RetentionPurgeRequest,
    auth: AuthContext,
    session: Session,
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
