from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from importlib.metadata import entry_points
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


def load_analyzer_plugins(entry_point_group: str = "agentreview.plugins") -> list[AnalyzerPlugin]:
    plugins = _builtin_plugins()
    plugins.extend(_entry_point_plugins(entry_point_group))
    _validate_unique_plugin_ids(plugins)
    return plugins


def run_analyzer_plugins(plugins: list[AnalyzerPlugin], context: AnalysisContext) -> list[RiskFinding]:
    findings: list[RiskFinding] = []
    plugin_config_by_id = {plugin.id: plugin for plugin in context.config.plugins if plugin.enabled}
    available_plugin_ids = {plugin.id for plugin in plugins}
    missing_plugin_ids = sorted(set(plugin_config_by_id) - available_plugin_ids)
    if missing_plugin_ids:
        missing = ", ".join(missing_plugin_ids)
        raise PluginError(f"Enabled plugin(s) not installed: {missing}")

    for plugin in plugins:
        plugin_config = plugin_config_by_id.get(plugin.id)
        if plugin_config is None:
            continue
        _validate_permissions(plugin, plugin_config)
        findings.extend(_run_plugin(plugin, context, plugin_config))

    return findings


def _builtin_plugins() -> list[AnalyzerPlugin]:
    from agentreview.example_plugins import DependencyManifestPlugin

    return [DependencyManifestPlugin()]


def _entry_point_plugins(entry_point_group: str) -> list[AnalyzerPlugin]:
    discovered = entry_points()
    if hasattr(discovered, "select"):
        selected = discovered.select(group=entry_point_group)
    elif isinstance(discovered, dict):
        selected = discovered.get(entry_point_group, [])
    else:
        selected = [
            entry_point
            for entry_point in discovered
            if getattr(entry_point, "group", entry_point_group) == entry_point_group
        ]

    plugins: list[AnalyzerPlugin] = []
    for entry_point in selected:
        try:
            plugins.append(
                _materialize_plugin(entry_point.load(), source=getattr(entry_point, "name", entry_point_group))
            )
        except Exception as exc:
            raise PluginError(
                f"Could not load analyzer plugin {getattr(entry_point, 'name', entry_point_group)}: {exc}"
            ) from exc
    return plugins


def _materialize_plugin(candidate, *, source: str) -> AnalyzerPlugin:
    plugin = candidate() if isinstance(candidate, type) else candidate
    if not hasattr(plugin, "analyze") and callable(plugin):
        plugin = plugin()

    _validate_plugin_shape(plugin, source=source)
    return plugin


def _validate_plugin_shape(plugin, *, source: str) -> None:
    plugin_id = getattr(plugin, "id", None)
    plugin_name = getattr(plugin, "name", None)
    permissions = getattr(plugin, "permissions", None)
    analyze = getattr(plugin, "analyze", None)
    if not isinstance(plugin_id, str) or not plugin_id.strip():
        raise PluginError(f"Analyzer plugin {source} must define a non-empty string id")
    if not isinstance(plugin_name, str) or not plugin_name.strip():
        raise PluginError(f"Analyzer plugin {plugin_id} must define a non-empty string name")
    if not isinstance(permissions, list) or any(
        not isinstance(permission, str) or not permission.strip() for permission in permissions
    ):
        raise PluginError(f"Analyzer plugin {plugin_id} must define permissions as a list of non-empty strings")
    if not callable(analyze):
        raise PluginError(f"Analyzer plugin {plugin_id} must define an analyze method")


def _validate_unique_plugin_ids(plugins: list[AnalyzerPlugin]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for plugin in plugins:
        if plugin.id in seen:
            duplicates.add(plugin.id)
        seen.add(plugin.id)
    if duplicates:
        raise PluginError(f"Duplicate analyzer plugin id(s): {', '.join(sorted(duplicates))}")


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
