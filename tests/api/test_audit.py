from agentreview_api.audit import sanitize_audit_metadata


def test_sanitize_audit_metadata_drops_sensitive_keys_and_caps_size() -> None:
    metadata = sanitize_audit_metadata(
        {
            "repository": "platform/checkout-api",
            "token": "secret-token",
            "nested": {
                "password": "hunter2",
                "safe": "value",
            },
            "items": [{"secret": "hidden", "count": 1}],
        }
    )

    assert metadata == {
        "repository": "platform/checkout-api",
        "nested": {"safe": "value"},
        "items": [{"count": 1}],
    }

    large_metadata = sanitize_audit_metadata({"payload": "x" * 5000})

    assert large_metadata["truncated"] is True
    assert large_metadata["original_size_bytes"] > 4096
