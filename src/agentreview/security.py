from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

REDACTED = "[REDACTED]"

DEFAULT_SENSITIVE_KEY_PARTS = {
    "token",
    "api_key",
    "authorization",
    "password",
    "secret",
    "credential",
}

_AUTHORIZATION_HEADER_RE = re.compile(r"(?i)\b(authorization\s*:\s*(?:bearer|basic)\s+)[^\s'\";,]+")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b((?:api[_-]?key|token|secret|password|credential)\s*[:=]\s*['\"]?)[^'\"\s,;]+"
)
_TOKEN_PATTERNS = [
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{10,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{8,}\b"),
    re.compile(r"\bghs_[A-Za-z0-9_]{8,}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\barok_[A-Za-z0-9_-]{16,}\b"),
]


def redact_secret(value: str | None) -> str:
    if value is None or value == "":
        return REDACTED
    if len(value) <= 8:
        return REDACTED
    return f"{value[:4]}...{REDACTED}...{value[-4:]}"


def redact_mapping(mapping: Mapping[str, Any], sensitive_keys: set[str] | None = None) -> dict:
    active_sensitive_keys = sensitive_keys or DEFAULT_SENSITIVE_KEY_PARTS
    return {
        key: (REDACTED if _is_sensitive_key(str(key), active_sensitive_keys) else _redact_value(value))
        for key, value in mapping.items()
    }


def redact_text(text: str) -> str:
    redacted = _AUTHORIZATION_HEADER_RE.sub(lambda match: f"{match.group(1)}{REDACTED}", text)
    redacted = _SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}{REDACTED}", redacted)
    for pattern in _TOKEN_PATTERNS:
        redacted = pattern.sub(REDACTED, redacted)
    return redacted


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return redact_mapping(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    return value


def _is_sensitive_key(key: str, sensitive_keys: set[str]) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(sensitive_key in normalized for sensitive_key in sensitive_keys)
