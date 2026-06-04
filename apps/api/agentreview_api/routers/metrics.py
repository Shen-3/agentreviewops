from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from agentreview_api.deps import AuthContext, get_session, require_api_key
from agentreview_api.schemas.metrics import (
    MetricsOverviewResponse,
    MetricsRepositoriesResponse,
    MetricsRoutingResponse,
    MetricsRulesResponse,
)
from agentreview_api.services.metrics_service import (
    get_overview_metrics,
    get_repository_metrics,
    get_routing_metrics,
    get_rule_metrics,
)

router = APIRouter()


@router.get("/api/metrics/overview", response_model=MetricsOverviewResponse)
def get_metrics_overview(
    days: int = Query(default=30, ge=1, le=365),
    repository: str | None = Query(default=None, min_length=1),
    auth: AuthContext = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> MetricsOverviewResponse:
    return get_overview_metrics(session, organization_id=auth.organization_id, days=days, repository=repository)


@router.get("/api/metrics/rules", response_model=MetricsRulesResponse)
def get_metrics_rules(
    days: int = Query(default=30, ge=1, le=365),
    repository: str | None = Query(default=None, min_length=1),
    auth: AuthContext = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> MetricsRulesResponse:
    return get_rule_metrics(session, organization_id=auth.organization_id, days=days, repository=repository)


@router.get("/api/metrics/routing", response_model=MetricsRoutingResponse)
def get_metrics_routing(
    days: int = Query(default=30, ge=1, le=365),
    repository: str | None = Query(default=None, min_length=1),
    auth: AuthContext = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> MetricsRoutingResponse:
    return get_routing_metrics(session, organization_id=auth.organization_id, days=days, repository=repository)


@router.get("/api/metrics/repositories", response_model=MetricsRepositoriesResponse)
def get_metrics_repositories(
    days: int = Query(default=30, ge=1, le=365),
    repository: str | None = Query(default=None, min_length=1),
    auth: AuthContext = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> MetricsRepositoriesResponse:
    return get_repository_metrics(session, organization_id=auth.organization_id, days=days, repository=repository)
