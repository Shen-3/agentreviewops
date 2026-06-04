from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from agentreview.models import FindingSeverity, RiskLevel


class MetricsTrendPoint(BaseModel):
    date: str
    analysis_count: int


class MetricsOverviewResponse(BaseModel):
    analysis_count: int
    risk_distribution: dict[RiskLevel, int]
    high_or_block_count: int
    average_risk_score: float
    unique_repository_count: int
    unique_agent_count: int
    analysis_count_by_agent: dict[str, int]
    recent_trend: list[MetricsTrendPoint]
    generated_at: datetime


class MetricsRuleStat(BaseModel):
    rule_id: str
    finding_count: int
    average_score_delta: float
    high_impact_count: int


class MetricsRulesResponse(BaseModel):
    total_finding_count: int
    severity_distribution: dict[FindingSeverity, int]
    high_impact_rule_count: int
    top_rules: list[MetricsRuleStat]
    generated_at: datetime


class MetricsUnconfiguredRequirement(BaseModel):
    requirement_id: str
    title: str
    count: int


class MetricsRoutingResponse(BaseModel):
    total_review_requirement_count: int
    unconfigured_review_requirement_count: int
    configured_review_requirement_count: int
    routing_hit_rate: float
    reviewer_source_distribution: dict[str, int]
    required_role_distribution: dict[str, int]
    top_unconfigured_requirements: list[MetricsUnconfiguredRequirement]
    generated_at: datetime


class MetricsRepositoryRow(BaseModel):
    repository: str
    analysis_count: int
    average_risk_score: float
    high_or_block_count: int
    last_analysis_time: datetime
    top_risk_level: RiskLevel
    unconfigured_review_requirement_count: int
    top_triggered_rule_ids: list[str]


class MetricsRepositoriesResponse(BaseModel):
    repositories: list[MetricsRepositoryRow]
    generated_at: datetime
