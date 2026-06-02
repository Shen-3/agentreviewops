from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
import os
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DEFAULT_DATABASE_URL = "sqlite:///./agentreview.db"


class Base(DeclarativeBase):
    pass


class OrganizationRecord(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    users: Mapped[list[UserRecord]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    repositories: Mapped[list[RepositoryRecord]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    api_keys: Mapped[list[ApiKeyRecord]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    policies: Mapped[list[PolicyRecord]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    audit_events: Mapped[list[AuditEventRecord]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    analysis_runs: Mapped[list[AnalysisRunRecord]] = relationship(back_populates="organization")


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="admin", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    organization: Mapped[OrganizationRecord] = relationship(back_populates="users")
    repository_memberships: Mapped[list[RepositoryMembershipRecord]] = relationship(back_populates="user", cascade="all, delete-orphan")


class RepositoryRecord(Base):
    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("organization_id", "provider", "owner", "name", name="uq_repositories_identity"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_branch: Mapped[str | None] = mapped_column(String(255))
    visibility: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    organization: Mapped[OrganizationRecord] = relationship(back_populates="repositories")
    memberships: Mapped[list[RepositoryMembershipRecord]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    policies: Mapped[list[PolicyRecord]] = relationship(back_populates="repository", cascade="all, delete-orphan")


class RepositoryMembershipRecord(Base):
    __tablename__ = "repository_memberships"
    __table_args__ = (UniqueConstraint("repository_id", "user_id", name="uq_repository_memberships_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="maintainer", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    repository: Mapped[RepositoryRecord] = relationship(back_populates="memberships")
    user: Mapped[UserRecord] = relationship(back_populates="repository_memberships")


class ApiKeyRecord(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="admin", nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    organization: Mapped[OrganizationRecord] = relationship(back_populates="api_keys")


class PolicyRecord(Base):
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    repository_id: Mapped[str | None] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[str] = mapped_column(String(50), default="organization", nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    organization: Mapped[OrganizationRecord] = relationship(back_populates="policies")
    repository: Mapped[RepositoryRecord | None] = relationship(back_populates="policies")


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    organization: Mapped[OrganizationRecord] = relationship(back_populates="audit_events")


class AnalysisRunRecord(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="api", nullable=False)
    repository: Mapped[str | None] = mapped_column(String(255))
    pull_request_number: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(255))
    agent_name: Mapped[str | None] = mapped_column(String(100))
    branch: Mapped[str | None] = mapped_column(String(255))
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    review_requirements_json: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    changed_files: Mapped[list[ChangedFileRecord]] = relationship(
        back_populates="analysis_run",
        cascade="all, delete-orphan",
        order_by="ChangedFileRecord.id",
    )
    findings: Mapped[list[RiskFindingRecord]] = relationship(
        back_populates="analysis_run",
        cascade="all, delete-orphan",
        order_by="RiskFindingRecord.id",
    )
    organization: Mapped[OrganizationRecord | None] = relationship(back_populates="analysis_runs")


class ChangedFileRecord(Base):
    __tablename__ = "changed_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    previous_path: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    additions: Mapped[int] = mapped_column(Integer, nullable=False)
    deletions: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str | None] = mapped_column(String(50))
    is_test_file: Mapped[bool] = mapped_column(nullable=False)
    is_critical_file: Mapped[bool] = mapped_column(nullable=False)

    analysis_run: Mapped[AnalysisRunRecord] = relationship(back_populates="changed_files")


class RiskFindingRecord(Base):
    __tablename__ = "risk_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    score_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text)
    line_start: Mapped[int | None] = mapped_column(Integer)
    line_end: Mapped[int | None] = mapped_column(Integer)
    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    analysis_run: Mapped[AnalysisRunRecord] = relationship(back_populates="findings")


def get_database_url() -> str:
    return os.environ.get("AGENTREVIEW_DATABASE_URL", DEFAULT_DATABASE_URL)


def create_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    url = database_url or get_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, future=True)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


SessionLocal = create_session_factory()


def get_session() -> Generator[Session]:
    with SessionLocal() as session:
        yield session
