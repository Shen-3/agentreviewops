import pytest

from agentreview.ai import (
    AIProviderConfigError,
    DiffSummaryRequest,
    DiffSummaryResult,
    OpenAICompatibleProvider,
    create_ai_provider,
    generate_ai_summary,
    redact_secrets,
)
from agentreview.config import parse_config
from agentreview.models import DiffFile, RiskAnalysis


class FakeProvider:
    def __init__(self) -> None:
        self.requests: list[DiffSummaryRequest] = []

    def summarize_diff(self, request: DiffSummaryRequest) -> DiffSummaryResult:
        self.requests.append(request)
        return DiffSummaryResult(
            summary=f"Fake summary for {len(request.changed_files)} file(s).",
            checklist=["Check the deterministic findings first."],
        )


def test_ai_summary_disabled_does_not_call_provider() -> None:
    provider = FakeProvider()
    analysis = RiskAnalysis(risk_score=0, risk_level="low")

    result = generate_ai_summary(
        provider=provider, analysis=analysis, changed_files=[], diff_text="token=secret", enabled=False
    )

    assert result is None
    assert provider.requests == []


def test_fake_provider_receives_redacted_request_when_enabled() -> None:
    provider = FakeProvider()
    analysis = RiskAnalysis(risk_score=25, risk_level="medium")
    changed_files = [DiffFile(path="src/app.py", status="modified", additions=2, deletions=1, language="python")]
    github_token = "github_pat_" + "1234567890"
    openai_token = "sk-" + "abcdefghijklmnopqrstuvwxyz"

    result = generate_ai_summary(
        provider=provider,
        analysis=analysis,
        changed_files=changed_files,
        diff_text=f"token={github_token}\nOPENAI_API_KEY={openai_token}",
        enabled=True,
    )

    assert result is not None
    assert result.summary == "Fake summary for 1 file(s)."
    assert len(provider.requests) == 1
    assert github_token not in (provider.requests[0].redacted_diff or "")
    assert openai_token not in (provider.requests[0].redacted_diff or "")
    assert "[REDACTED]" in (provider.requests[0].redacted_diff or "")


def test_redact_secrets_handles_common_token_shapes() -> None:
    github_token = "ghp_" + "1234567890"
    redacted = redact_secrets(f"password=hunter2 secret:abc {github_token}")

    assert "hunter2" not in redacted
    assert "abc" not in redacted
    assert github_token not in redacted
    assert redacted.count("[REDACTED]") == 3


def test_create_ai_provider_requires_explicit_key_and_model(monkeypatch) -> None:
    config = parse_config({"version": 1, "ai": {"enabled": True, "provider": "openai"}})
    monkeypatch.delenv("AGENTREVIEW_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(AIProviderConfigError, match="API_KEY"):
        create_ai_provider(config.ai)

    monkeypatch.setenv("AGENTREVIEW_OPENAI_API_KEY", "test-key")
    with pytest.raises(AIProviderConfigError, match="model"):
        create_ai_provider(config.ai)


def test_openai_compatible_provider_posts_redacted_analysis(monkeypatch) -> None:
    captured = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"summary":"Review auth behavior and missing tests.",'
                                '"checklist":["Confirm owner review.","Add tests."]}'
                            )
                        }
                    }
                ]
            }

    def fake_post(url, *, json, headers, timeout):
        captured.update({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return Response()

    monkeypatch.setattr("agentreview.ai.httpx.post", fake_post)
    provider = OpenAICompatibleProvider(
        api_key="test-api-key",
        model="review-model",
        base_url="https://llm.example/v1",
        timeout_seconds=3,
        max_diff_chars=80,
    )
    request = DiffSummaryRequest(
        risk_score=55,
        risk_level="high",
        changed_files=[
            DiffFile(path="auth/session.py", status="modified", additions=3, deletions=1, language="python")
        ],
        findings=[],
        redacted_diff="OPENAI_API_KEY=[REDACTED]\n" + ("x" * 200),
    )

    result = provider.summarize_diff(request)

    assert result.summary == "Review auth behavior and missing tests."
    assert result.checklist == ["Confirm owner review.", "Add tests."]
    assert captured["url"] == "https://llm.example/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-api-key"
    assert captured["json"]["model"] == "review-model"
    assert "test-api-key" not in captured["json"]["messages"][1]["content"]
    assert "[TRUNCATED]" in captured["json"]["messages"][1]["content"]
