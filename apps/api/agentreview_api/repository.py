from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from agentreview.models import AgentReviewConfig, DiffFile, ReviewRequirement, RiskAnalysis, RiskFinding
from agentreview_api.audit import sanitize_audit_metadata
from agentreview_api.auth import generate_api_key, hash_api_key, key_prefix
from agentreview_api.db import (
    AnalysisRunRecord,
    ApiKeyRecord,
    AuditEventRecord,
    ChangedFileRecord,
    OrganizationRecord,
    PolicyRecord,
    RepositoryMembershipRecord,
    RepositoryRecord,
    RiskFindingRecord,
    UserRecord,
)


def create_organization(session: Session, *, slug: str, name: str) -> OrganizationRecord:
    record = OrganizationRecord(slug=slug, name=name)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def create_user(
    session: Session,
    *,
    organization_id: str,
    email: str,
    name: str | None = None,
    github_login: str | None = None,
    role: str = "admin",
) -> UserRecord:
    record = UserRecord(
        organization_id=organization_id,
        email=email,
        name=name,
        github_login=github_login,
        role=role,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def list_users(session: Session, *, organization_id: str) -> list[UserRecord]:
    statement = select(UserRecord).where(UserRecord.organization_id == organization_id).order_by(UserRecord.email)
    return list(session.scalars(statement).all())


def get_user(session: Session, *, organization_id: str, user_id: str) -> UserRecord | None:
    statement = select(UserRecord).where(
        UserRecord.organization_id == organization_id,
        UserRecord.id == user_id,
    )
    return session.scalar(statement)


def get_user_by_email(session: Session, *, email: str) -> UserRecord | None:
    statement = select(UserRecord).where(UserRecord.email == email)
    return session.scalar(statement)


def get_user_by_github_login(
    session: Session,
    *,
    organization_id: str,
    github_login: str,
    exclude_user_id: str | None = None,
) -> UserRecord | None:
    statement = select(UserRecord).where(
        UserRecord.organization_id == organization_id,
        func.lower(UserRecord.github_login) == github_login.lower(),
    )
    if exclude_user_id is not None:
        statement = statement.where(UserRecord.id != exclude_user_id)
    return session.scalar(statement)


def count_admin_users(session: Session, *, organization_id: str) -> int:
    count = session.scalar(
        select(func.count())
        .select_from(UserRecord)
        .where(
            UserRecord.organization_id == organization_id,
            UserRecord.role == "admin",
        )
    )
    return int(count or 0)


def delete_user(session: Session, record: UserRecord) -> None:
    session.delete(record)
    session.commit()


def update_user(
    session: Session,
    record: UserRecord,
    *,
    name: str | None = None,
    github_login: str | None = None,
    github_login_provided: bool = False,
    role: str | None = None,
) -> UserRecord:
    if name is not None:
        record.name = name
    if github_login_provided:
        record.github_login = github_login
    if role is not None:
        record.role = role
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def create_repository(
    session: Session,
    *,
    organization_id: str,
    provider: str,
    owner: str,
    name: str,
    default_branch: str | None = None,
    visibility: str | None = None,
) -> RepositoryRecord:
    record = RepositoryRecord(
        organization_id=organization_id,
        provider=provider,
        owner=owner,
        name=name,
        default_branch=default_branch,
        visibility=visibility,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def get_repository_by_identity(
    session: Session,
    *,
    organization_id: str,
    provider: str,
    owner: str,
    name: str,
) -> RepositoryRecord | None:
    statement = select(RepositoryRecord).where(
        RepositoryRecord.organization_id == organization_id,
        RepositoryRecord.provider == provider,
        RepositoryRecord.owner == owner,
        RepositoryRecord.name == name,
    )
    return session.scalar(statement)


def get_repository(session: Session, *, organization_id: str, repository_id: str) -> RepositoryRecord | None:
    statement = (
        select(RepositoryRecord)
        .where(
            RepositoryRecord.organization_id == organization_id,
            RepositoryRecord.id == repository_id,
        )
        .options(selectinload(RepositoryRecord.memberships).selectinload(RepositoryMembershipRecord.user))
        .execution_options(populate_existing=True)
    )
    return session.scalar(statement)


def list_repositories(session: Session, *, organization_id: str) -> list[RepositoryRecord]:
    statement = (
        select(RepositoryRecord)
        .where(RepositoryRecord.organization_id == organization_id)
        .options(selectinload(RepositoryRecord.memberships).selectinload(RepositoryMembershipRecord.user))
        .order_by(RepositoryRecord.provider, RepositoryRecord.owner, RepositoryRecord.name)
    )
    return list(session.scalars(statement).all())


def delete_repository(session: Session, record: RepositoryRecord) -> None:
    session.delete(record)
    session.commit()


def create_repository_membership(
    session: Session,
    *,
    repository_id: str,
    user_id: str,
    role: str = "maintainer",
) -> RepositoryMembershipRecord:
    record = RepositoryMembershipRecord(repository_id=repository_id, user_id=user_id, role=role)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def get_repository_membership(
    session: Session,
    *,
    repository_id: str,
    user_id: str,
) -> RepositoryMembershipRecord | None:
    statement = select(RepositoryMembershipRecord).where(
        RepositoryMembershipRecord.repository_id == repository_id,
        RepositoryMembershipRecord.user_id == user_id,
    )
    return session.scalar(statement)


def delete_repository_membership(session: Session, record: RepositoryMembershipRecord) -> None:
    session.delete(record)
    session.commit()


def update_repository_membership(
    session: Session,
    record: RepositoryMembershipRecord,
    *,
    role: str,
) -> RepositoryMembershipRecord:
    record.role = role
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def create_api_key(
    session: Session,
    *,
    organization_id: str,
    name: str,
    role: str = "admin",
    secret: str | None = None,
) -> tuple[ApiKeyRecord, str]:
    api_key = secret or generate_api_key()
    record = ApiKeyRecord(
        organization_id=organization_id,
        name=name,
        role=role,
        key_prefix=key_prefix(api_key),
        key_hash=hash_api_key(api_key),
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record, api_key


def list_api_keys(session: Session, *, organization_id: str) -> list[ApiKeyRecord]:
    statement = (
        select(ApiKeyRecord)
        .where(ApiKeyRecord.organization_id == organization_id)
        .order_by(ApiKeyRecord.created_at.desc())
    )
    return list(session.scalars(statement).all())


def get_api_key(session: Session, *, organization_id: str, api_key_id: str) -> ApiKeyRecord | None:
    statement = select(ApiKeyRecord).where(
        ApiKeyRecord.organization_id == organization_id,
        ApiKeyRecord.id == api_key_id,
    )
    return session.scalar(statement)


def revoke_api_key(session: Session, *, organization_id: str, api_key_id: str) -> ApiKeyRecord | None:
    record = get_api_key(session, organization_id=organization_id, api_key_id=api_key_id)
    if record is None:
        return None
    if record.revoked_at is None:
        record.revoked_at = datetime.now(timezone.utc)
        session.add(record)
        session.commit()
        session.refresh(record)
    return record


def update_api_key(
    session: Session,
    record: ApiKeyRecord,
    *,
    name: str | None = None,
    role: str | None = None,
) -> ApiKeyRecord:
    if name is not None:
        record.name = name
    if role is not None:
        record.role = role
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def create_audit_event(
    session: Session,
    *,
    organization_id: str,
    actor_type: str,
    actor_id: str | None,
    action: str,
    target_type: str,
    target_id: str | None,
    metadata: dict | None = None,
) -> AuditEventRecord:
    record = AuditEventRecord(
        organization_id=organization_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_json=sanitize_audit_metadata(metadata),
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def list_audit_events(
    session: Session,
    *,
    organization_id: str,
    limit: int = 100,
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    actor_type: str | None = None,
    since=None,
    until=None,
) -> list[AuditEventRecord]:
    statement = select(AuditEventRecord).where(AuditEventRecord.organization_id == organization_id)
    if action is not None:
        statement = statement.where(AuditEventRecord.action == action)
    if target_type is not None:
        statement = statement.where(AuditEventRecord.target_type == target_type)
    if target_id is not None:
        statement = statement.where(AuditEventRecord.target_id == target_id)
    if actor_type is not None:
        statement = statement.where(AuditEventRecord.actor_type == actor_type)
    if since is not None:
        statement = statement.where(AuditEventRecord.created_at >= since)
    if until is not None:
        statement = statement.where(AuditEventRecord.created_at <= until)
    statement = statement.order_by(AuditEventRecord.created_at.desc()).limit(limit)
    return list(session.scalars(statement).all())


def create_policy(
    session: Session,
    *,
    organization_id: str,
    name: str,
    config: AgentReviewConfig,
    enabled: bool = True,
    scope: str = "organization",
    repository_id: str | None = None,
) -> PolicyRecord:
    record = PolicyRecord(
        organization_id=organization_id,
        repository_id=repository_id,
        name=name,
        scope=scope,
        config_json=config.model_dump(mode="json"),
        enabled=enabled,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def list_policies(session: Session, *, organization_id: str) -> list[PolicyRecord]:
    statement = (
        select(PolicyRecord)
        .where(PolicyRecord.organization_id == organization_id)
        .options(selectinload(PolicyRecord.repository))
        .order_by(PolicyRecord.created_at.desc())
    )
    return list(session.scalars(statement).all())


def get_policy(session: Session, *, organization_id: str, policy_id: str) -> PolicyRecord | None:
    statement = (
        select(PolicyRecord)
        .where(
            PolicyRecord.organization_id == organization_id,
            PolicyRecord.id == policy_id,
        )
        .options(selectinload(PolicyRecord.repository))
    )
    return session.scalar(statement)


def update_policy(
    session: Session,
    record: PolicyRecord,
    *,
    name: str | None = None,
    config: AgentReviewConfig | None = None,
    enabled: bool | None = None,
) -> PolicyRecord:
    if name is not None:
        record.name = name
    if config is not None:
        record.config_json = config.model_dump(mode="json")
    if enabled is not None:
        record.enabled = enabled
    record.updated_at = datetime.now(timezone.utc)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def get_enabled_policy(session: Session, *, organization_id: str) -> PolicyRecord | None:
    statement = (
        select(PolicyRecord)
        .where(
            PolicyRecord.organization_id == organization_id,
            PolicyRecord.scope == "organization",
            PolicyRecord.repository_id.is_(None),
            PolicyRecord.enabled.is_(True),
        )
        .order_by(PolicyRecord.created_at.desc())
        .limit(1)
    )
    return session.scalar(statement)


def get_enabled_repository_policy(
    session: Session,
    *,
    organization_id: str,
    repository_id: str,
) -> PolicyRecord | None:
    statement = (
        select(PolicyRecord)
        .where(
            PolicyRecord.organization_id == organization_id,
            PolicyRecord.repository_id == repository_id,
            PolicyRecord.scope == "repository",
            PolicyRecord.enabled.is_(True),
        )
        .options(selectinload(PolicyRecord.repository))
        .order_by(PolicyRecord.created_at.desc())
        .limit(1)
    )
    return session.scalar(statement)


def create_analysis_run(
    session: Session,
    *,
    changed_files: list[DiffFile],
    analysis: RiskAnalysis,
    review_requirements: list[ReviewRequirement],
    markdown: str,
    config: AgentReviewConfig,
    source: str = "api",
    organization_id: str | None = None,
    repository: str | None = None,
    pull_request_number: int | None = None,
    title: str | None = None,
    author: str | None = None,
    agent_name: str | None = None,
    branch: str | None = None,
) -> AnalysisRunRecord:
    record = AnalysisRunRecord(
        organization_id=organization_id,
        source=source,
        repository=repository,
        pull_request_number=pull_request_number,
        title=title,
        author=author,
        agent_name=agent_name,
        branch=branch,
        risk_score=analysis.risk_score,
        risk_level=analysis.risk_level,
        summary=_build_summary(changed_files, analysis),
        markdown=markdown,
        config_json=config.model_dump(mode="json"),
        review_requirements_json=[requirement.model_dump(mode="json") for requirement in review_requirements],
        changed_files=[
            ChangedFileRecord(
                path=file.path,
                previous_path=file.previous_path,
                status=file.status,
                additions=file.additions,
                deletions=file.deletions,
                language=file.language,
                is_test_file=file.is_test_file,
                is_critical_file=file.is_critical_file,
            )
            for file in changed_files
        ],
        findings=[
            RiskFindingRecord(
                rule_id=finding.rule_id,
                severity=finding.severity,
                title=finding.title,
                description=finding.description,
                score_delta=finding.score_delta,
                file_path=finding.file_path,
                line_start=finding.line_start,
                line_end=finding.line_end,
                evidence_json=finding.evidence,
            )
            for finding in analysis.findings
        ],
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def list_analysis_runs(
    session: Session, *, organization_id: str | None = None, limit: int = 50
) -> list[AnalysisRunRecord]:
    statement = select(AnalysisRunRecord).options(
        selectinload(AnalysisRunRecord.changed_files),
        selectinload(AnalysisRunRecord.findings),
    )
    if organization_id is not None:
        statement = statement.where(AnalysisRunRecord.organization_id == organization_id)
    statement = statement.order_by(AnalysisRunRecord.created_at.desc()).limit(limit)
    return list(session.scalars(statement).all())


def get_analysis_run(
    session: Session, analysis_run_id: str, *, organization_id: str | None = None
) -> AnalysisRunRecord | None:
    statement = (
        select(AnalysisRunRecord)
        .where(AnalysisRunRecord.id == analysis_run_id)
        .options(
            selectinload(AnalysisRunRecord.changed_files),
            selectinload(AnalysisRunRecord.findings),
        )
    )
    if organization_id is not None:
        statement = statement.where(AnalysisRunRecord.organization_id == organization_id)
    return session.scalar(statement)


def count_retention_candidates(session: Session, *, organization_id: str, before: datetime) -> tuple[int, int]:
    analysis_count = session.scalar(
        select(func.count())
        .select_from(AnalysisRunRecord)
        .where(
            AnalysisRunRecord.organization_id == organization_id,
            AnalysisRunRecord.created_at < before,
        )
    )
    audit_count = session.scalar(
        select(func.count())
        .select_from(AuditEventRecord)
        .where(
            AuditEventRecord.organization_id == organization_id,
            AuditEventRecord.created_at < before,
        )
    )
    return int(analysis_count or 0), int(audit_count or 0)


def purge_retention_records(
    session: Session,
    *,
    organization_id: str,
    before: datetime,
    include_analysis_runs: bool,
    include_audit_events: bool,
) -> tuple[int, int]:
    analysis_count = 0
    audit_count = 0

    if include_analysis_runs:
        analysis_runs = list(
            session.scalars(
                select(AnalysisRunRecord)
                .where(
                    AnalysisRunRecord.organization_id == organization_id,
                    AnalysisRunRecord.created_at < before,
                )
                .options(
                    selectinload(AnalysisRunRecord.changed_files),
                    selectinload(AnalysisRunRecord.findings),
                )
            ).all()
        )
        analysis_count = len(analysis_runs)
        for record in analysis_runs:
            session.delete(record)

    if include_audit_events:
        audit_events = list(
            session.scalars(
                select(AuditEventRecord).where(
                    AuditEventRecord.organization_id == organization_id,
                    AuditEventRecord.created_at < before,
                )
            ).all()
        )
        audit_count = len(audit_events)
        for record in audit_events:
            session.delete(record)

    session.commit()
    return analysis_count, audit_count


def to_diff_files(record: AnalysisRunRecord) -> list[DiffFile]:
    return [
        DiffFile(
            path=file.path,
            previous_path=file.previous_path,
            status=file.status,
            additions=file.additions,
            deletions=file.deletions,
            language=file.language,
            is_test_file=file.is_test_file,
            is_critical_file=file.is_critical_file,
        )
        for file in record.changed_files
    ]


def to_risk_findings(record: AnalysisRunRecord) -> list[RiskFinding]:
    return [
        RiskFinding(
            rule_id=finding.rule_id,
            severity=finding.severity,
            title=finding.title,
            description=finding.description,
            score_delta=finding.score_delta,
            file_path=finding.file_path,
            line_start=finding.line_start,
            line_end=finding.line_end,
            evidence=finding.evidence_json,
        )
        for finding in record.findings
    ]


def to_review_requirements(record: AnalysisRunRecord) -> list[ReviewRequirement]:
    return [ReviewRequirement.model_validate(requirement) for requirement in (record.review_requirements_json or [])]


def _build_summary(changed_files: list[DiffFile], analysis: RiskAnalysis) -> str:
    return f"{len(changed_files)} changed file(s), {analysis.risk_level} risk ({analysis.risk_score}/100)."
