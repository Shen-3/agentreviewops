from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from agentreview_api.db import ApiKeyRecord, get_session

API_KEY_PREFIX_LENGTH = 16


@dataclass(frozen=True)
class AuthContext:
    organization_id: str
    api_key_id: str
    api_key_name: str


def generate_api_key() -> str:
    return f"arok_{secrets.token_urlsafe(32)}"


def hash_api_key(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def key_prefix(secret: str) -> str:
    return secret[:API_KEY_PREFIX_LENGTH]


def authenticate_api_key(session: Session, secret: str) -> AuthContext | None:
    if not secret:
        return None

    record = session.scalar(
        select(ApiKeyRecord).where(
            ApiKeyRecord.key_prefix == key_prefix(secret),
            ApiKeyRecord.revoked_at.is_(None),
        )
    )
    if record is None:
        return None

    if not hmac.compare_digest(record.key_hash, hash_api_key(secret)):
        return None

    return AuthContext(
        organization_id=record.organization_id,
        api_key_id=record.id,
        api_key_name=record.name,
    )


def require_api_key(
    authorization: Annotated[str | None, Header()] = None,
    x_agentreview_api_key: Annotated[str | None, Header(alias="X-AgentReview-API-Key")] = None,
    session: Session = Depends(get_session),
) -> AuthContext:
    secret = _extract_api_key(authorization=authorization, x_agentreview_api_key=x_agentreview_api_key)
    auth = authenticate_api_key(session, secret or "")
    if auth is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid AgentReviewOps API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth


def _extract_api_key(*, authorization: str | None, x_agentreview_api_key: str | None) -> str | None:
    if x_agentreview_api_key:
        return x_agentreview_api_key.strip()
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()
