from agentreview.ai import DiffSummaryRequest, DiffSummaryResult, generate_ai_summary, redact_secrets
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

    result = generate_ai_summary(provider=provider, analysis=analysis, changed_files=[], diff_text="token=secret", enabled=False)

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
