# Policy Bundles

Policy bundles are built-in AgentReviewOps config presets. They generate normal `.agentreview.yml` files, so teams can start from a deterministic preset and then edit the YAML without relying on hosted SaaS or external services.

## Bundles

| Bundle | Use when |
|---|---|
| `starter` | You want a safe default for most repositories with PR comments, standard critical paths, CODEOWNERS, and review routing. |
| `security` | The repository handles auth, security, payments, deployment, or other AppSec-sensitive code. |
| `github-actions` | Workflow and supply-chain controls are the main review concern. |
| `python` | The repository is a Python app, service, CLI, or library. |
| `dependency-governance` | Dependency manifests, lockfiles, and install paths need consistent maintainer review. |
| `ai-pr-strict` | AI-generated PRs should receive stricter human review before merge. |
| `enterprise-strict` | Conservative enterprise governance and broad owner routing are required. |

## Generate Setup Files

```bash
agentreview init --bundle starter
```

This writes:

- `.agentreview.yml`
- `.github/workflows/agentreview.yml`

Use `--force` to overwrite existing files. In CI or tests, add `--non-interactive` so existing files fail safely unless `--force` is present.

```bash
agentreview init \
  --bundle ai-pr-strict \
  --non-interactive \
  --force \
  --checks \
  --request-reviewers
```

## Inspect Bundles

```bash
agentreview bundles list
agentreview bundles show starter
```

`bundles show` prints the YAML config for the selected bundle.

## Example Config Excerpt

```yaml
version: 1
risk:
  fail_level: high
  large_diff:
    max_files: 25
    max_lines: 1000
critical_paths:
  - auth/**
  - security/**
  - payments/**
  - .github/workflows/**
review_routing:
  enabled: true
  codeowners:
    enabled: true
    path: null
```

The generated file also includes rule toggles, agent detection defaults, AI disabled by default, plugin defaults, and concrete review routing rules.

## Bundle Notes

`starter` keeps `fail_level: high` and moderate large-diff thresholds to avoid being overly strict on first adoption.

`security`, `github-actions`, `python`, and `dependency-governance` emphasize the paths and deterministic findings most relevant to their domain.

`ai-pr-strict` and `enterprise-strict` lower large-diff thresholds and route medium-or-higher risk to maintainers or owners. They are intended for teams that have already configured CODEOWNERS or repository memberships.

Reviewer requests only work for requestable GitHub identities. Repository members without `github_login` are still shown in reports by email, but the reviewer request resolver skips them as `missing_github_login`.
