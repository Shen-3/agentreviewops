import os
import time

import pytest

from agentreview.config import parse_config
from agentreview.example_plugins import DependencyManifestPlugin
from agentreview.models import DiffFile, RiskFinding
from agentreview.plugins import AnalysisContext, PluginError, load_analyzer_plugins, run_analyzer_plugins
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


class CrashPlugin:
    id = "crash"
    name = "Crash Plugin"
    permissions = ["read_diff"]

    def analyze(self, context: AnalysisContext) -> list[RiskFinding]:
        print("token=ghp_1234567890")
        raise RuntimeError("plugin failed with token=ghp_1234567890")


class EnvEchoPlugin:
    id = "env-echo"
    name = "Environment Echo Plugin"
    permissions = ["read_diff"]

    def analyze(self, context: AnalysisContext) -> list[RiskFinding]:
        return [
            RiskFinding(
                rule_id="env-echo",
                severity="low",
                title="Environment echo",
                description="Reports whether sensitive environment reached the plugin.",
                score_delta=1,
                evidence={"github_token": os.environ.get("GITHUB_TOKEN", "missing")},
            )
        ]


class FakeEntryPoint:
    def __init__(self, plugin_class=CountingPlugin, name: str = "counting") -> None:
        self._plugin_class = plugin_class
        self.name = name

    def load(self):
        return self._plugin_class


def test_disabled_plugin_does_nothing() -> None:
    plugin = CountingPlugin()
    config = parse_config({"version": 1})

    findings = run_analyzer_plugins([plugin], AnalysisContext(changed_files=[], config=config))

    assert findings == []
    assert plugin.calls == 0


def test_load_analyzer_plugins_includes_builtin_plugin() -> None:
    plugins = load_analyzer_plugins()

    assert "dependency-manifest" in {plugin.id for plugin in plugins}


def test_load_analyzer_plugins_discovers_entry_points(monkeypatch) -> None:
    monkeypatch.setattr("agentreview.plugins.entry_points", lambda: [FakeEntryPoint()])

    plugins = load_analyzer_plugins()

    assert {"dependency-manifest", "counting"} == {plugin.id for plugin in plugins}


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

    plugin_findings = run_analyzer_plugins(
        [DependencyManifestPlugin()], AnalysisContext(changed_files=changed_files, config=config)
    )
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


def test_enabled_missing_plugin_fails_clearly() -> None:
    config = parse_config(
        {
            "version": 1,
            "plugins": [
                {
                    "id": "missing",
                    "enabled": True,
                    "permissions": ["read_diff"],
                }
            ],
        }
    )

    with pytest.raises(PluginError, match="Enabled plugin\\(s\\) not installed: missing"):
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


def test_entry_point_plugin_runs_in_isolated_subprocess(monkeypatch) -> None:
    monkeypatch.setattr("agentreview.plugins.entry_points", lambda: [FakeEntryPoint(CountingPlugin, "counting")])
    plugins = load_analyzer_plugins()
    config = parse_config(
        {
            "version": 1,
            "plugins": [
                {
                    "id": "counting",
                    "enabled": True,
                    "permissions": ["read_diff"],
                }
            ],
        }
    )

    findings = run_analyzer_plugins(plugins, AnalysisContext(changed_files=[], config=config))

    assert [finding.rule_id for finding in findings] == ["counting-plugin"]


def test_entry_point_plugin_timeout_is_killed(monkeypatch) -> None:
    monkeypatch.setattr("agentreview.plugins.entry_points", lambda: [FakeEntryPoint(SlowPlugin, "slow")])
    plugins = load_analyzer_plugins()
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
        run_analyzer_plugins(plugins, AnalysisContext(changed_files=[], config=config))


def test_entry_point_plugin_crash_is_redacted(monkeypatch) -> None:
    monkeypatch.setattr("agentreview.plugins.entry_points", lambda: [FakeEntryPoint(CrashPlugin, "crash")])
    plugins = load_analyzer_plugins()
    config = parse_config(
        {
            "version": 1,
            "plugins": [
                {
                    "id": "crash",
                    "enabled": True,
                    "permissions": ["read_diff"],
                }
            ],
        }
    )

    with pytest.raises(PluginError) as exc_info:
        run_analyzer_plugins(plugins, AnalysisContext(changed_files=[], config=config))

    assert "failed in isolated subprocess" in str(exc_info.value)
    assert "ghp_1234567890" not in str(exc_info.value)


def test_entry_point_plugin_does_not_inherit_sensitive_environment(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_1234567890")
    monkeypatch.setattr("agentreview.plugins.entry_points", lambda: [FakeEntryPoint(EnvEchoPlugin, "env-echo")])
    plugins = load_analyzer_plugins()
    config = parse_config(
        {
            "version": 1,
            "plugins": [
                {
                    "id": "env-echo",
                    "enabled": True,
                    "permissions": ["read_diff"],
                }
            ],
        }
    )

    findings = run_analyzer_plugins(plugins, AnalysisContext(changed_files=[], config=config))

    assert findings[0].evidence == {"github_token": "missing"}
