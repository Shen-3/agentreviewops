# Analyzer plugins

AgentReviewOps supports analyzer plugins for deterministic, repository-local checks that return `RiskFinding` objects. Plugins are optional and disabled unless explicitly configured.

## Minimal plugin contract

Plugins expose:

- `id`: stable plugin ID.
- `name`: human-readable name.
- `permissions`: declared permissions such as `read_diff`.
- `analyze(context)`: returns a list of `RiskFinding` objects or compatible dictionaries.

## v0 permission model

The v0 permission model is intentionally small:

- `read_diff`: plugin may inspect structured changed-file data supplied by AgentReviewOps.
- `read_file_paths`: reserved for plugins that only need file paths.
- Network access is not provided by AgentReviewOps and should be treated as unsupported by default.
- Environment access is denied by default for package-discovered plugins by stripping sensitive process environment before plugin execution.

External plugins receive structured analysis context, not GitHub tokens, AgentReviewOps API keys, provider keys, or raw process environment. Do not design plugins that require secrets.

## Isolation

Built-in plugins run in process. Package-discovered plugins run in a child process with a hard timeout and structured JSON-style result validation. Timeout, crashes, and invalid outputs fail the plugin run without hanging the scan.

This is not a full OS sandbox. Operators should only install plugins they trust and should run AgentReviewOps in an environment with least-privilege filesystem and network access.

## Configuration

```yaml
plugins:
  - id: dependency-manifest
    enabled: true
    permissions:
      - read_diff
    timeout_seconds: 5
```
