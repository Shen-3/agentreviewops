from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from agentreview_api.db import AnalysisRunRecord
from agentreview_api.schemas.metrics import (
    MetricsOverviewResponse,
    MetricsRepositoriesResponse,
    MetricsRepositoryRow,
    MetricsRoutingResponse,
    MetricsRulesResponse,
    MetricsRuleStat,
    MetricsTrendPoint,
    MetricsUnconfiguredRequirement,
)

RISK_LEVELS = ("low", "medium", "high", "block")
RISK_LEVEL_ORDER = {level: index for index, level in enumerate(RISK_LEVELS)}
FINDING_SEVERITIES = ("info", "low", "medium", "high", "critical")
UNKNOWN_REPOSITORY = "unknown"
UNKNOWN_AGENT = "unknown"


def get_overview_metrics(
    session: Session,
    *,
    organization_id: str,
    days: int,
    repository: str | None = None,
) -> MetricsOverviewResponse:
    generated_at = datetime.now(timezone.utc)
    runs = _list_metric_runs(
        session, organization_id=organization_id, days=days, repository=repository, now=generated_at
    )
    risk_distribution = Counter({level: 0 for level in RISK_LEVELS})
    risk_distribution.update(run.risk_level for run in runs)
    agent_counts = Counter(_normalized_agent(run.agent_name) for run in runs)

    return MetricsOverviewResponse(
        analysis_count=len(runs),
        risk_distribution=dict(risk_distribution),
        high_or_block_count=sum(1 for run in runs if run.risk_level in {"high", "block"}),
        average_risk_score=_average([run.risk_score for run in runs]),
        unique_repository_count=len({_normalized_repository(run.repository) for run in runs}),
        unique_agent_count=len({_normalized_agent(run.agent_name) for run in runs}),
        analysis_count_by_agent=dict(sorted(agent_counts.items())),
        recent_trend=_recent_trend(runs, days=days, now=generated_at),
        generated_at=generated_at,
    )


def get_rule_metrics(
    session: Session,
    *,
    organization_id: str,
    days: int,
    repository: str | None = None,
) -> MetricsRulesResponse:
    generated_at = datetime.now(timezone.utc)
    runs = _list_metric_runs(
        session, organization_id=organization_id, days=days, repository=repository, now=generated_at
    )
    findings = [finding for run in runs for finding in run.findings]
    severity_distribution = Counter({severity: 0 for severity in FINDING_SEVERITIES})
    severity_distribution.update(finding.severity for finding in findings)

    rule_counts: Counter[str] = Counter()
    score_deltas: dict[str, list[int]] = defaultdict(list)
    high_impact_counts: Counter[str] = Counter()
    high_impact_rule_ids: set[str] = set()
    for finding in findings:
        rule_counts[finding.rule_id] += 1
        score_deltas[finding.rule_id].append(finding.score_delta)
        if finding.severity in {"high", "critical"} or finding.score_delta >= 20:
            high_impact_counts[finding.rule_id] += 1
            high_impact_rule_ids.add(finding.rule_id)

    sorted_rule_ids = sorted(
        rule_counts,
        key=lambda rule_id: (
            -rule_counts[rule_id],
            -high_impact_counts[rule_id],
            -_average(score_deltas[rule_id]),
            rule_id,
        ),
    )
    top_rules = [
        MetricsRuleStat(
            rule_id=rule_id,
            finding_count=rule_counts[rule_id],
            average_score_delta=_average(score_deltas[rule_id]),
            high_impact_count=high_impact_counts[rule_id],
        )
        for rule_id in sorted_rule_ids[:10]
    ]

    return MetricsRulesResponse(
        total_finding_count=len(findings),
        severity_distribution=dict(severity_distribution),
        high_impact_rule_count=len(high_impact_rule_ids),
        top_rules=top_rules,
        generated_at=generated_at,
    )


def get_routing_metrics(
    session: Session,
    *,
    organization_id: str,
    days: int,
    repository: str | None = None,
) -> MetricsRoutingResponse:
    generated_at = datetime.now(timezone.utc)
    runs = _list_metric_runs(
        session, organization_id=organization_id, days=days, repository=repository, now=generated_at
    )
    requirements = [requirement for run in runs for requirement in _review_requirements(run)]
    configured = [requirement for requirement in requirements if requirement.get("suggested_reviewers")]
    unconfigured = [requirement for requirement in requirements if not requirement.get("suggested_reviewers")]

    reviewer_sources: Counter[str] = Counter()
    required_roles: Counter[str] = Counter()
    unconfigured_keys: Counter[tuple[str, str]] = Counter()
    for requirement in requirements:
        for reviewer in _list_dicts(requirement.get("suggested_reviewers")):
            source = reviewer.get("source")
            if isinstance(source, str) and source:
                reviewer_sources[source] += 1
        for role in requirement.get("required_roles") or []:
            if isinstance(role, str) and role:
                required_roles[role] += 1
    for requirement in unconfigured:
        requirement_id = _text_value(requirement.get("requirement_id"), "unknown")
        title = _text_value(requirement.get("title"), requirement_id)
        unconfigured_keys[(requirement_id, title)] += 1

    return MetricsRoutingResponse(
        total_review_requirement_count=len(requirements),
        unconfigured_review_requirement_count=len(unconfigured),
        configured_review_requirement_count=len(configured),
        routing_hit_rate=round(len(configured) / len(requirements), 4) if requirements else 0.0,
        reviewer_source_distribution=dict(sorted(reviewer_sources.items())),
        required_role_distribution=dict(sorted(required_roles.items())),
        top_unconfigured_requirements=[
            MetricsUnconfiguredRequirement(requirement_id=key[0], title=key[1], count=count)
            for key, count in unconfigured_keys.most_common(10)
        ],
        generated_at=generated_at,
    )


def get_repository_metrics(
    session: Session,
    *,
    organization_id: str,
    days: int,
    repository: str | None = None,
) -> MetricsRepositoriesResponse:
    generated_at = datetime.now(timezone.utc)
    runs = _list_metric_runs(
        session, organization_id=organization_id, days=days, repository=repository, now=generated_at
    )
    grouped_runs: dict[str, list[AnalysisRunRecord]] = defaultdict(list)
    for run in runs:
        grouped_runs[_normalized_repository(run.repository)].append(run)

    rows: list[MetricsRepositoryRow] = []
    for repository_name, repository_runs in grouped_runs.items():
        rule_counts = Counter(finding.rule_id for run in repository_runs for finding in run.findings)
        unconfigured_count = sum(
            1
            for run in repository_runs
            for requirement in _review_requirements(run)
            if not requirement.get("suggested_reviewers")
        )
        rows.append(
            MetricsRepositoryRow(
                repository=repository_name,
                analysis_count=len(repository_runs),
                average_risk_score=_average([run.risk_score for run in repository_runs]),
                high_or_block_count=sum(1 for run in repository_runs if run.risk_level in {"high", "block"}),
                last_analysis_time=max(_as_utc(run.created_at) for run in repository_runs),
                top_risk_level=max(
                    (run.risk_level for run in repository_runs), key=lambda level: RISK_LEVEL_ORDER[level]
                ),
                unconfigured_review_requirement_count=unconfigured_count,
                top_triggered_rule_ids=[rule_id for rule_id, _ in rule_counts.most_common(5)],
            )
        )

    rows.sort(key=lambda row: (row.high_or_block_count, row.analysis_count, row.repository), reverse=True)
    return MetricsRepositoriesResponse(repositories=rows, generated_at=generated_at)


def _list_metric_runs(
    session: Session,
    *,
    organization_id: str,
    days: int,
    repository: str | None,
    now: datetime,
) -> list[AnalysisRunRecord]:
    since = now - timedelta(days=days)
    statement = (
        select(AnalysisRunRecord)
        .where(
            AnalysisRunRecord.organization_id == organization_id,
            AnalysisRunRecord.created_at >= since,
        )
        .options(selectinload(AnalysisRunRecord.findings))
    )
    if repository:
        statement = statement.where(AnalysisRunRecord.repository == repository)
    statement = statement.order_by(AnalysisRunRecord.created_at.desc())
    return list(session.scalars(statement).all())


def _recent_trend(runs: list[AnalysisRunRecord], *, days: int, now: datetime) -> list[MetricsTrendPoint]:
    start_date = now.date() - timedelta(days=days - 1)
    counts = Counter(_as_utc(run.created_at).date().isoformat() for run in runs)
    return [
        MetricsTrendPoint(
            date=(start_date + timedelta(days=offset)).isoformat(),
            analysis_count=counts[(start_date + timedelta(days=offset)).isoformat()],
        )
        for offset in range(days)
    ]


def _review_requirements(run: AnalysisRunRecord) -> list[dict[str, Any]]:
    return _list_dicts(run.review_requirements_json)


def _list_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _normalized_repository(value: str | None) -> str:
    return value.strip() if value and value.strip() else UNKNOWN_REPOSITORY


def _normalized_agent(value: str | None) -> str:
    return value.strip() if value and value.strip() else UNKNOWN_AGENT


def _text_value(value: object, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return fallback


def _average(values: list[int]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
