import time

import pytest

from agentreview.config import parse_config
from agentreview.example_plugins import DependencyManifestPlugin
from agentreview.models import DiffFile, RiskFinding
from agentreview.plugins import AnalysisContext, PluginError, run_analyzer_plugins
from agentreview.risk import analyze_risk


class CountingPlugin:
    id = "counting"
    name = "Counting Plugin"
    permissions = ["read_diff"]

    def __init__(self) -> None:
        self.calls = 0

    def analyze(self, context: AnalysisContext) -> list[RiskFinding]:
        self.calls += 1
        return [
            RiskFinding(
                rule_id="counting-plugin",
                severity="low",
                title="Counting plugin finding",
                description="Counting plugin was enabled.",
                score_delta=3,
            )
        ]


class InvalidOutputPlugin:
    id = "invalid-output"
    name = "Invalid Output Plugin"
    permissions = ["read_diff"]

    def analyze(self, context: AnalysisContext) -> list[dict]:
        return [{"rule_id": "missing-required-fields"}]


class SlowPlugin:
    id = "slow"
    name = "Slow Plugin"
    permissions = ["read_diff"]

    def analyze(self, context: AnalysisContext) -> list[RiskFinding]:
        time.sleep(0.2)
        return []


def test_disabled_plugin_does_nothing() -> None:
    plugin = CountingPlugin()
    config = parse_config({"version": 1})

    findings = run_analyzer_plugins([plugin], AnalysisContext(changed_files=[], config=config))

    assert findings == []
    assert plugin.calls == 0


def test_enabled_example_plugin_adds_validated_finding_to_analysis() -> None:
    config = parse_config(
        {
            "version": 1,
            "plugins": [
                {
                    "id": "dependency-manifest",
                    "enabled": True,
                    "permissions": ["read_diff"],
                }
            ],
        }
    )
    changed_files = [DiffFile(path="package.json", status="modified", additions=2, deletions=1)]

    plugin_findings = run_analyzer_plugins([DependencyManifestPlugin()], AnalysisContext(changed_files=changed_files, config=config))
    analysis = analyze_risk(changed_files, config=config, plugin_findings=plugin_findings)

    assert [finding.rule_id for finding in plugin_findings] == ["plugin-dependency-manifest"]
    assert "plugin-dependency-manifest" in [finding.rule_id for finding in analysis.findings]
    assert analysis.risk_score == 35


def test_enabled_plugin_requires_explicit_permissions() -> None:
    config = parse_config(
        {
            "version": 1,
            "plugins": [
                {
                    "id": "counting",
                    "enabled": True,
                    "permissions": [],
                }
            ],
        }
    )

    with pytest.raises(PluginError, match="requires explicit permission"):
        run_analyzer_plugins([CountingPlugin()], AnalysisContext(changed_files=[], config=config))


def test_plugin_timeout_fails_clearly() -> None:
    config = parse_config(
        {
            "version": 1,
            "plugins": [
                {
                    "id": "slow",
                    "enabled": True,
                    "permissions": ["read_diff"],
                    "timeout_seconds": 0.01,
                }
            ],
        }
    )

    with pytest.raises(PluginError, match="exceeded timeout"):
        run_analyzer_plugins([SlowPlugin()], AnalysisContext(changed_files=[], config=config))


def test_invalid_plugin_output_fails_validation() -> None:
    config = parse_config(
        {
            "version": 1,
            "plugins": [
                {
                    "id": "invalid-output",
                    "enabled": True,
                    "permissions": ["read_diff"],
                }
            ],
        }
    )

    with pytest.raises(PluginError, match="invalid finding output"):
        run_analyzer_plugins([InvalidOutputPlugin()], AnalysisContext(changed_files=[], config=config))
