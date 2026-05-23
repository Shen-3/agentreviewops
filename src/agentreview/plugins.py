from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Protocol

from pydantic import ValidationError

from agentreview.models import AgentReviewConfig, DiffFile, PluginConfig, RiskFinding, StrictConfigModel


class PluginError(RuntimeError):
    """Raised when a configured analyzer plugin cannot run safely."""


class AnalysisContext(StrictConfigModel):
    changed_files: list[DiffFile]
    config: AgentReviewConfig


class AnalyzerPlugin(Protocol):
    id: str
    name: str
    permissions: list[str]

    def analyze(self, context: AnalysisContext) -> list[RiskFinding] | list[dict]:
        """Return validated risk findings for the supplied analysis context."""


def run_analyzer_plugins(plugins: list[AnalyzerPlugin], context: AnalysisContext) -> list[RiskFinding]:
    findings: list[RiskFinding] = []
    plugin_config_by_id = {plugin.id: plugin for plugin in context.config.plugins if plugin.enabled}

    for plugin in plugins:
        plugin_config = plugin_config_by_id.get(plugin.id)
        if plugin_config is None:
            continue
        _validate_permissions(plugin, plugin_config)
        findings.extend(_run_plugin(plugin, context, plugin_config))

    return findings


def _validate_permissions(plugin: AnalyzerPlugin, plugin_config: PluginConfig) -> None:
    missing_permissions = sorted(set(plugin.permissions) - set(plugin_config.permissions))
    if missing_permissions:
        missing = ", ".join(missing_permissions)
        raise PluginError(f"Plugin {plugin.id} requires explicit permission(s): {missing}")


def _run_plugin(plugin: AnalyzerPlugin, context: AnalysisContext, plugin_config: PluginConfig) -> list[RiskFinding]:
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(plugin.analyze, context)
    try:
        raw_findings = future.result(timeout=plugin_config.timeout_seconds)
    except TimeoutError as exc:
        raise PluginError(f"Plugin {plugin.id} exceeded timeout of {plugin_config.timeout_seconds:g}s") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    try:
        return [RiskFinding.model_validate(finding) for finding in raw_findings]
    except ValidationError as exc:
        raise PluginError(f"Plugin {plugin.id} returned invalid finding output: {exc}") from exc
