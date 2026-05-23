from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from agentreview_api.audit import AUDIT_ACTION_API_KEY_CREATED, AUDIT_ACTION_ORGANIZATION_BOOTSTRAPPED
from agentreview_api.db import OrganizationRecord, UserRecord
from agentreview_api.repository import create_api_key, create_audit_event, create_organization, create_user


class BootstrapError(RuntimeError):
    """Raised when the first self-hosted account cannot be bootstrapped."""


@dataclass(frozen=True)
class BootstrapResult:
    organization_id: str
    organization_slug: str
    user_id: str
    user_email: str
    api_key_id: str
    api_key_name: str
    api_key_secret: str


def bootstrap_account(
    session: Session,
    *,
    org_slug: str,
    org_name: str,
    email: str,
    user_name: str | None,
    api_key_name: str,
) -> BootstrapResult:
    normalized_slug = org_slug.strip()
    normalized_email = email.strip().lower()
    if not normalized_slug:
        raise BootstrapError("Organization slug is required")
    if not normalized_email:
        raise BootstrapError("User email is required")

    organization = _get_or_create_organization(session, slug=normalized_slug, name=org_name.strip() or normalized_slug)
    user = _get_or_create_user(session, organization_id=organization.id, email=normalized_email, name=user_name)
    api_key, secret = create_api_key(session, organization_id=organization.id, name=api_key_name.strip() or "Bootstrap key")
    create_audit_event(
        session,
        organization_id=organization.id,
        actor_type="system",
        actor_id=None,
        action=AUDIT_ACTION_ORGANIZATION_BOOTSTRAPPED,
        target_type="organization",
        target_id=organization.id,
        metadata={
            "source": "bootstrap",
        },
    )
    create_audit_event(
        session,
        organization_id=organization.id,
        actor_type="system",
        actor_id=None,
        action=AUDIT_ACTION_API_KEY_CREATED,
        target_type="api_key",
        target_id=api_key.id,
        metadata={
            "api_key_name": api_key.name,
            "source": "bootstrap",
        },
    )

    return BootstrapResult(
        organization_id=organization.id,
        organization_slug=organization.slug,
        user_id=user.id,
        user_email=user.email,
        api_key_id=api_key.id,
        api_key_name=api_key.name,
        api_key_secret=secret,
    )


def _get_or_create_organization(session: Session, *, slug: str, name: str) -> OrganizationRecord:
    existing = session.scalar(select(OrganizationRecord).where(OrganizationRecord.slug == slug))
    if existing is not None:
        return existing
    return create_organization(session, slug=slug, name=name)


def _get_or_create_user(session: Session, *, organization_id: str, email: str, name: str | None) -> UserRecord:
    existing = session.scalar(select(UserRecord).where(UserRecord.email == email))
    if existing is not None:
        if existing.organization_id != organization_id:
            raise BootstrapError(f"User {email} already belongs to another organization")
        return existing
    return create_user(session, organization_id=organization_id, email=email, name=name, role="admin")
