from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from agentreview_api.deps import AuthContext, get_session, require_api_key
from agentreview_api.repository import list_audit_events
from agentreview_api.schemas.audit import AuditEventResponse
from agentreview_api.services.audit_service import audit_event_response, export_audit_events_response

router = APIRouter()


@router.get("/api/audit-events", response_model=list[AuditEventResponse])
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
        audit_event_response(record)
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


@router.get("/api/audit-events/export")
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
        audit_event_response(record)
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
    return export_audit_events_response(events, export_format=format)
