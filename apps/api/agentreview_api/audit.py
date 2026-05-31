from __future__ import annotations

import json
from typing import Any

AUDIT_ACTION_ANALYSIS_CREATED = "analysis.created"
AUDIT_ACTION_API_KEY_CREATED = "api_key.created"
AUDIT_ACTION_API_KEY_REVOKED = "api_key.revoked"
AUDIT_ACTION_ORGANIZATION_BOOTSTRAPPED = "organization.bootstrapped"
AUDIT_ACTION_POLICY_CREATED = "policy.created"

MAX_METADATA_BYTES = 4096

_SENSITIVE_KEY_NAMES = {
    "api_key",
    "api_key_secret",
    "authorization",
    "key_hash",
    "password",
    "secret",
    "token",
}
_SENSITIVE_KEY_SUFFIXES = ("_hash", "_password", "_secret", "_token")


def sanitize_audit_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {}

    sanitized = _sanitize_value(metadata)
    if not isinstance(sanitized, dict):
        return {}

    encoded = json.dumps(sanitized, sort_keys=True, separators=(",", ":"), default=str)
    if len(encoded.encode("utf-8")) <= MAX_METADATA_BYTES:
        return sanitized

    return {
        "truncated": True,
        "original_size_bytes": len(encoded.encode("utf-8")),
    }


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, child in value.items():
            normalized_key = str(key)
            if _is_sensitive_key(normalized_key):
                continue
            sanitized_child = _sanitize_value(child)
            if sanitized_child is not None:
                output[normalized_key] = sanitized_child
        return output

    if isinstance(value, list):
        output = []
        for item in value:
            sanitized_item = _sanitize_value(item)
            if sanitized_item is not None:
                output.append(sanitized_item)
        return output

    if isinstance(value, str | int | float | bool) or value is None:
        return value

    return str(value)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return normalized in _SENSITIVE_KEY_NAMES or normalized.endswith(_SENSITIVE_KEY_SUFFIXES)
