from agentreview.security import REDACTED, redact_mapping, redact_secret, redact_text


def test_redact_secret_fully_redacts_short_values() -> None:
    assert redact_secret("short") == REDACTED
    assert redact_secret(None) == REDACTED


def test_redact_secret_keeps_only_small_prefix_and_suffix_for_long_values() -> None:
    redacted = redact_secret("abcdefghijklmnopqrstuvwxyz")

    assert redacted == f"abcd...{REDACTED}...wxyz"


def test_redact_mapping_redacts_sensitive_keys_recursively() -> None:
    payload = {
        "repository": "platform/checkout-api",
        "headers": {"Authorization": "Bearer secret-token-value"},
        "items": [{"api_key": "arok_secret_value", "count": 1}],
    }

    redacted = redact_mapping(payload)

    assert redacted["repository"] == "platform/checkout-api"
    assert redacted["headers"]["Authorization"] == REDACTED
    assert redacted["items"][0]["api_key"] == REDACTED
    assert redacted["items"][0]["count"] == 1


def test_redact_text_removes_common_secret_patterns() -> None:
    github_token = "github_pat_" + "1234567890abcdef"
    openai_token = "sk-" + "abcdefghijklmnopqrstuvwxyz"
    text = f"Authorization: Bearer {github_token}\nOPENAI_API_KEY={openai_token}\npassword=hunter2\nplain text stays"

    redacted = redact_text(text)

    assert github_token not in redacted
    assert openai_token not in redacted
    assert "hunter2" not in redacted
    assert "plain text stays" in redacted
