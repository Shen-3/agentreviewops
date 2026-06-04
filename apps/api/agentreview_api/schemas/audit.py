from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AuditEventResponse(BaseModel):
    audit_event_id: str
    created_at: datetime
    actor_type: str
    actor_id: str | None
    action: str
    target_type: str
    target_id: str | None
    metadata: dict
