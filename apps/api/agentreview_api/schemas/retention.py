from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


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
