# Changelog

All notable changes to AgentReviewOps are documented here.

## Unreleased

- Hardened secret redaction for JSON, SARIF, Markdown, Checks, and plugin error paths.
- Added isolated subprocess execution for package-discovered analyzer plugins.
- Added repo dogfooding configuration and workflow.
- Expanded release, security, contributing, CLI, plugin, troubleshooting, and v0 readiness docs.

## v0.1.0 - Proposed

- Typer CLI with `scan-diff`, `scan-pr`, `submit-diff`, `comment-pr`, `request-reviewers`, `bundles`, and `init`.
- Composite GitHub Action for pull request governance gates.
- Deterministic risk analysis for risky paths, dependency changes, CI changes, migrations, test gaps, and dangerous Python/GitHub Actions patterns.
- Review routing through CODEOWNERS, repository memberships, GitHub login mapping, and policy rules.
- Markdown, structured JSON, SARIF, GitHub Checks, PR comments, and reviewer request outputs.
- Built-in policy bundles for starter, security, GitHub Actions, Python, dependency governance, AI PR strict, and enterprise strict policies.
- FastAPI self-hosted API with SQLite/PostgreSQL migrations, API key auth, audit events, persisted analysis runs, and governance metrics.
- React dashboard for analysis review, governance metrics, policy management, repository/user setup, API keys, and audit exports.
- `agentreview init` onboarding for generating starter configs and GitHub Action workflows.
