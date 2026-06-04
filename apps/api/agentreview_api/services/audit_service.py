from __future__ import annotations

import csv
import json
from io import StringIO

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response

from agentreview_api.db import AuditEventRecord
from agentreview_api.schemas.audit import AuditEventResponse


def audit_event_response(record: AuditEventRecord) -> AuditEventResponse:
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


def export_audit_events_response(events: list[AuditEventResponse], export_format: str) -> Response:
    filename = f"agentreview-audit-events.{export_format}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    if export_format == "json":
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
