from __future__ import annotations

import contextlib
import io
import multiprocessing as mp
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from importlib.metadata import entry_points
from queue import Empty
from typing import Protocol

from pydantic import ValidationError

from agentreview.models import AgentReviewConfig, DiffFile, PluginConfig, RiskFinding, StrictConfigModel
from agentreview.security import redact_text


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


@dataclass(frozen=True)
class _LoadedAnalyzerPlugin:
    plugin: AnalyzerPlugin
    source: str
    isolated: bool = False

    @property
    def id(self) -> str:
        return self.plugin.id

    @property
    def name(self) -> str:
        return self.plugin.name

    @property
    def permissions(self) -> list[str]:
        return self.plugin.permissions

    def analyze(self, context: AnalysisContext) -> list[RiskFinding] | list[dict]:
        return self.plugin.analyze(context)


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
        source = getattr(entry_point, "name", entry_point_group)
        try:
            plugins.append(
                _LoadedAnalyzerPlugin(
                    plugin=_materialize_plugin(entry_point.load(), source=source),
                    source=source,
                    isolated=True,
                )
            )
        except Exception as exc:
            raise PluginError(f"Could not load analyzer plugin {source}: {redact_text(str(exc))}") from exc
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
    if isinstance(plugin, _LoadedAnalyzerPlugin) and plugin.isolated:
        return _run_plugin_in_subprocess(plugin.plugin, context, plugin_config)

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


def _run_plugin_in_subprocess(
    plugin: AnalyzerPlugin,
    context: AnalysisContext,
    plugin_config: PluginConfig,
) -> list[RiskFinding]:
    process_context = _plugin_process_context()
    result_queue = process_context.Queue(maxsize=1)
    process = process_context.Process(
        target=_plugin_worker,
        args=(plugin, _context_payload(context), _sanitized_plugin_environment(), result_queue),
    )
    try:
        process.start()
    except Exception as exc:
        raise PluginError(f"Plugin {plugin.id} could not start isolated subprocess: {redact_text(str(exc))}") from exc

    process.join(plugin_config.timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(1)
        if process.is_alive():
            process.kill()
            process.join(1)
        raise PluginError(f"Plugin {plugin.id} exceeded timeout of {plugin_config.timeout_seconds:g}s")

    try:
        payload = result_queue.get_nowait()
    except Empty as exc:
        raise PluginError(f"Plugin {plugin.id} exited without structured output") from exc

    if payload.get("status") != "success":
        raise PluginError(_format_subprocess_error(plugin.id, payload))

    try:
        return [RiskFinding.model_validate(finding) for finding in payload.get("findings", [])]
    except ValidationError as exc:
        raise PluginError(f"Plugin {plugin.id} returned invalid finding output: {exc}") from exc


def _plugin_worker(
    plugin: AnalyzerPlugin,
    context_payload: dict,
    environment: dict[str, str],
    result_queue,
) -> None:
    os.environ.clear()
    os.environ.update(environment)
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    try:
        context = AnalysisContext.model_validate(context_payload)
        with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
            raw_findings = plugin.analyze(context)
        findings = [RiskFinding.model_validate(finding).model_dump(mode="json") for finding in raw_findings]
        result_queue.put(
            {
                "status": "success",
                "findings": findings,
                "stdout": redact_text(stdout_buffer.getvalue()),
                "stderr": redact_text(stderr_buffer.getvalue()),
            }
        )
    except Exception as exc:
        result_queue.put(
            {
                "status": "error",
                "error_type": type(exc).__name__,
                "message": redact_text(str(exc)),
                "stdout": redact_text(stdout_buffer.getvalue()),
                "stderr": redact_text(stderr_buffer.getvalue()),
            }
        )


def _plugin_process_context() -> mp.context.BaseContext:
    if "fork" in mp.get_all_start_methods():
        return mp.get_context("fork")
    return mp.get_context()


def _context_payload(context: AnalysisContext) -> dict:
    return {
        "changed_files": [
            {
                **changed_file.model_dump(mode="json"),
                "added_lines": [line.model_dump(mode="json") for line in changed_file.added_lines],
            }
            for changed_file in context.changed_files
        ],
        "config": context.config.model_dump(mode="json"),
    }


def _sanitized_plugin_environment() -> dict[str, str]:
    allowed_keys = {"PATH", "PYTHONPATH", "PYTHONHOME", "TMPDIR", "TEMP", "TMP", "SYSTEMROOT", "WINDIR"}
    return {
        key: value for key, value in os.environ.items() if key in allowed_keys and not _looks_sensitive_env_key(key)
    }


def _looks_sensitive_env_key(key: str) -> bool:
    normalized = key.lower()
    return any(part in normalized for part in ("token", "api", "secret", "password", "credential"))


def _format_subprocess_error(plugin_id: str, payload: dict) -> str:
    error_type = str(payload.get("error_type") or "PluginError")
    message = str(payload.get("message") or "plugin failed")
    stderr = _truncate_plugin_output(str(payload.get("stderr") or ""))
    if stderr:
        return f"Plugin {plugin_id} failed in isolated subprocess: {error_type}: {message}; stderr: {stderr}"
    return f"Plugin {plugin_id} failed in isolated subprocess: {error_type}: {message}"


def _truncate_plugin_output(value: str, limit: int = 500) -> str:
    stripped = value.strip()
    if len(stripped) <= limit:
        return stripped
    return f"{stripped[:limit]}...[truncated]"
