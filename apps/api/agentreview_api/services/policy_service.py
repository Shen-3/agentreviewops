from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from agentreview.models import AgentReviewConfig
from agentreview_api.auth import AuthContext
from agentreview_api.db import PolicyRecord, RepositoryRecord
from agentreview_api.repository import (
    get_enabled_policy,
    get_enabled_repository_policy,
    get_repository_by_identity,
)
from agentreview_api.schemas.policies import PolicyResponse


@dataclass(frozen=True)
class PolicySelection:
    config: AgentReviewConfig
    source: str
    policy: PolicyRecord | None
    repository: RepositoryRecord | None


def resolve_analysis_config(
    repository_name: str | None,
    request_config: AgentReviewConfig | None,
    auth: AuthContext,
    session: Session,
) -> PolicySelection:
    repository = find_repository_for_analysis(repository_name, auth, session)
    if repository is not None:
        repository_policy = get_enabled_repository_policy(
            session,
            organization_id=auth.organization_id,
            repository_id=repository.id,
        )
        if repository_policy is not None:
            return PolicySelection(
                config=AgentReviewConfig.model_validate(repository_policy.config_json),
                source="repository_policy",
                policy=repository_policy,
                repository=repository,
            )

    organization_policy = get_enabled_policy(session, organization_id=auth.organization_id)
    if organization_policy is not None:
        return PolicySelection(
            config=AgentReviewConfig.model_validate(organization_policy.config_json),
            source="organization_policy",
            policy=organization_policy,
            repository=repository,
        )

    if request_config is not None:
        return PolicySelection(config=request_config, source="request_config", policy=None, repository=repository)
    return PolicySelection(config=AgentReviewConfig(), source="default", policy=None, repository=repository)


def find_repository_for_analysis(
    repository_name: str | None, auth: AuthContext, session: Session
) -> RepositoryRecord | None:
    identity = parse_repository_identity(repository_name)
    if identity is None:
        return None
    provider, owner, name = identity
    return get_repository_by_identity(
        session,
        organization_id=auth.organization_id,
        provider=provider,
        owner=owner,
        name=name,
    )


def parse_repository_identity(repository_name: str | None) -> tuple[str, str, str] | None:
    if repository_name is None:
        return None
    normalized = repository_name.strip().rstrip("/")
    if not normalized:
        return None
    if normalized.startswith("https://github.com/"):
        normalized = normalized.removeprefix("https://github.com/")
    elif normalized.startswith("git@github.com:"):
        normalized = normalized.removeprefix("git@github.com:")
    elif "://" in normalized:
        return None
    if normalized.endswith(".git"):
        normalized = normalized[:-4]

    provider = "github"
    if ":" in normalized:
        provider_candidate, repository_path = normalized.split(":", 1)
        if provider_candidate and "/" in repository_path:
            provider = provider_candidate.strip().lower()
            normalized = repository_path

    owner_name = normalized.split("/")
    if len(owner_name) != 2 or not owner_name[0].strip() or not owner_name[1].strip():
        return None
    return provider, owner_name[0].strip(), owner_name[1].strip()


def policy_response(record: PolicyRecord) -> PolicyResponse:
    return PolicyResponse(
        policy_id=record.id,
        name=record.name,
        scope=record.scope,
        repository_id=record.repository_id,
        repository_full_name=f"{record.repository.owner}/{record.repository.name}"
        if record.repository is not None
        else None,
        enabled=record.enabled,
        config=AgentReviewConfig.model_validate(record.config_json),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def compact_metadata(metadata: dict) -> dict:
    return {key: value for key, value in metadata.items() if value is not None}
