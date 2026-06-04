from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from agentreview.models import AgentReviewConfig, DiffFile, ReviewRequirement, RiskFinding, RiskLevel


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
    review_requirements: list[ReviewRequirement]
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
    review_requirements: list[ReviewRequirement]
    markdown: str
