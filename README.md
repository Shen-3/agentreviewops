# AgentReviewOps

AgentReviewOps is an open-source quality gate for AI-generated pull requests.

It will analyze pull request diffs, detect high-risk changes, check whether tests were updated, apply policy-as-code, and generate a human review packet before merge.

Use it when your team uses Cursor, Copilot, Devin, Codex, Claude Code, or other coding agents and needs a repeatable way to decide what requires human attention.

## Current Status

This repository is at the CLI/API/dashboard foundation stage. It provides a Typer-based `agentreview` command that can scan a unified diff or GitHub pull request, apply deterministic risk rules and enabled analyzer plugins, optionally add an AI-authored summary, persist analysis runs and audit events through FastAPI, and manage the self-hosted review control plane from a React dashboard.

GitHub Action usage is documented for artifact-based reports, optional self-hosted dashboard submission, and GitHub PR comments. Multi-tenant auth foundations, package-discovered analyzer plugins, and an opt-in OpenAI-compatible AI provider exist; hosted deployment is intentionally not implemented yet.

## Quick Start

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/agentreview --help
.venv/bin/agentreview scan-diff --diff-file examples/sample.diff --config .agentreview.example.yml --output agentreview-report.md
.venv/bin/pytest
```

## CLI Usage

```bash
agentreview --help
agentreview scan-diff --diff-file examples/sample.diff --config .agentreview.example.yml --output agentreview-report.md
AGENTREVIEW_API_KEY=<api-key> agentreview submit-diff --diff-file examples/sample.diff --api-url http://127.0.0.1:8000 --repository owner/name --pr 123
GITHUB_TOKEN=<github-token> agentreview scan-pr --repo owner/name --pr 123 --output agentreview-report.md
GITHUB_TOKEN=<github-token> agentreview comment-pr --repo owner/name --pr 123 --report-file agentreview-report.md
```

Expected scan output includes the risk level, positive findings, and the report path.

`submit-diff` sends a unified diff to a self-hosted AgentReviewOps API and persists the result for the dashboard. The API key is read from `AGENTREVIEW_API_KEY` or `--api-key` and is not printed in command output.

`scan-pr` fetches the pull request diff from the GitHub API using `GITHUB_TOKEN`. The token is required at runtime and is not printed in command output.

`comment-pr` posts or updates the generated report as a GitHub pull request comment using a hidden AgentReviewOps marker, so repeated CI runs update the prior comment rather than creating duplicates.

## Example Report

The checked-in [example report](examples/report.md) shows the Markdown output generated from [examples/sample.diff](examples/sample.diff).

## API Usage

The FastAPI app lives at `agentreview_api.main:app`.

Implemented endpoints:

- `GET /health`
- `GET /api/auth/me`
- `GET /api/api-keys`
- `POST /api/api-keys`
- `PATCH /api/api-keys/{api_key_id}`
- `POST /api/api-keys/{api_key_id}/revoke`
- `GET /api/users`
- `POST /api/users`
- `PATCH /api/users/{user_id}`
- `DELETE /api/users/{user_id}`
- `GET /api/repositories`
- `POST /api/repositories`
- `POST /api/repositories/{repository_id}/memberships`
- `PATCH /api/repositories/{repository_id}/memberships/{user_id}`
- `DELETE /api/repositories/{repository_id}/memberships/{user_id}`
- `GET /api/audit-events`
- `GET /api/audit-events/export`
- `POST /api/retention/purge`
- `GET /api/policies`
- `POST /api/policies`
- `POST /api/analyze/diff`
- `GET /api/analysis-runs`
- `GET /api/analysis-runs/{analysis_run_id}`
- `GET /api/analysis-runs/{analysis_run_id}/report`

All `/api/*` endpoints require an AgentReviewOps API key in either header:

```text
Authorization: Bearer <api-key>
X-AgentReview-API-Key: <api-key>
```

`POST /api/analyze/diff` accepts JSON with a unified diff string:

```json
{
  "diff": "diff --git a/README.md b/README.md\n..."
}
```

The response includes a persisted analysis run ID scoped to the API key's organization, changed files, findings, risk score, risk level, and Markdown report content. If the analysis repository matches an onboarded repository with an enabled repository policy, that policy is applied first. Otherwise the latest enabled organization policy overrides the request-level config. Use the report endpoint to fetch the stored Markdown report later.

Save an organization policy with the same schema as `.agentreview.yml`:

```json
{
  "name": "Default review policy",
  "scope": "organization",
  "enabled": true,
  "config": {
    "version": 1,
    "critical_paths": ["auth/**", "payments/**", ".github/workflows/**"]
  }
}
```

Save a repository-scoped policy by first onboarding the repository, then passing its `repository_id`:

```json
{
  "name": "Checkout API review policy",
  "scope": "repository",
  "repository_id": "<repository-id>",
  "enabled": true,
  "config": {
    "version": 1,
    "critical_paths": ["auth/**", "payments/**"]
  }
}
```

Set `AGENTREVIEW_DATABASE_URL` to choose the database. SQLite is supported for local development and tests; production deployments should use a PostgreSQL URL.

Run database migrations with:

```bash
alembic upgrade head
```

Create the first self-hosted organization and one-time API key with:

```bash
agentreview admin bootstrap \
  --org-slug acme \
  --org-name "Acme Engineering" \
  --email reviewer@example.com \
  --api-key-name "Local CI"
```

The key is printed once and stored only as a hash. See [self-hosting docs](docs/self-hosting.md) for the current local deployment flow.

Issue additional organization API keys with `POST /api/api-keys`, list existing keys with `GET /api/api-keys`, update key names or roles with `PATCH /api/api-keys/{api_key_id}`, and revoke inactive keys with `POST /api/api-keys/{api_key_id}/revoke`. Created keys are returned once and are stored only as hashes. API key roles are `admin`, `ci`, and `read_only`: admin keys can manage governance settings, CI keys can submit analyses, and read-only keys can inspect existing data.

Create organization users with `POST /api/users`, update user roles with `PATCH /api/users/{user_id}`, then assign them to onboarded repositories with `POST /api/repositories/{repository_id}/memberships`. Repository membership roles are `owner`, `maintainer`, and `reviewer`; those assignments are returned in repository list responses and used as reviewer routing metadata during analysis. Update reviewer roles with `PATCH /api/repositories/{repository_id}/memberships/{user_id}`. Remove stale users with `DELETE /api/users/{user_id}` and remove stale reviewer assignments with `DELETE /api/repositories/{repository_id}/memberships/{user_id}`.

For a containerized local stack:

```bash
docker compose -f deploy/docker-compose.yml up --build
```

This starts PostgreSQL, the FastAPI API on `127.0.0.1:8000`, and the dashboard on `127.0.0.1:8080`.

## Web Dashboard

A React + TypeScript + Vite dashboard lives in `apps/web`.

Run it locally:

```bash
cd apps/web
npm install
npm run dev
```

Then open `http://127.0.0.1:5173`.

The dashboard can store an API key locally and sends it as a Bearer token for live API data. Without a key, it falls back to seeded demo data. It includes diff submission, analysis list, selected analysis detail, risk badges, findings table, report preview, user management, repository onboarding with reviewer routing assignment, organization and repository policy assignment, role-scoped API key management, audit history with JSON/CSV export, and loading/error/empty states.

## Sample Config

Start from the example config:

```bash
cp .agentreview.example.yml .agentreview.yml
```

The config defines initial risk thresholds, critical paths, test file patterns, agent detection hints, and rule toggles.

AI summaries are disabled by default:

```yaml
ai:
  enabled: false
  provider: null
  model: null
  base_url: null
  timeout_seconds: 15
  max_diff_chars: 12000
```

Enable AI summaries only when you explicitly want AgentReviewOps to send a redacted diff excerpt and deterministic findings to an external LLM provider. The supported provider values are `openai` and `openai-compatible`; both use a Chat Completions-compatible HTTP endpoint.

Required environment:

```bash
export AGENTREVIEW_OPENAI_API_KEY=<provider-api-key>
export AGENTREVIEW_OPENAI_MODEL=<model-name>
```

Optional environment:

```bash
export AGENTREVIEW_OPENAI_BASE_URL=https://api.openai.com/v1
```

You can also set `ai.model` and `ai.base_url` in `.agentreview.yml`. Secrets are read only from environment variables and are not written to reports.

Audit events are organization-scoped and available at `GET /api/audit-events`. Export filtered evidence with `GET /api/audit-events/export?format=json` or `format=csv`. AgentReviewOps records summary-only events for bootstrap, API key creation/revocation, user creation, repository onboarding, repository membership assignment, policy creation, and analysis creation, including policy source and reviewer routing counts for analyzed repositories. See [audit event docs](docs/audit-events.md).

Retention purges are available at `POST /api/retention/purge`. The endpoint defaults to dry-run mode and requires `confirm=true` for deletion, then records a `retention.purged` audit event with summary counts.

Analyzer plugins are disabled by default. A plugin must be enabled by ID and granted explicit permissions:

```yaml
plugins:
  - id: dependency-manifest
    enabled: true
    permissions:
      - read_diff
    timeout_seconds: 5
```

The built-in example plugin demonstrates the contract by flagging dependency manifests. Enabled plugins are loaded from the built-in registry and installed Python package entry points in the `agentreview.plugins` group. Plugin output is validated as `RiskFinding` data before it can affect risk scoring.

Third-party packages can expose analyzer plugins from `pyproject.toml`:

```toml
[project.entry-points."agentreview.plugins"]
my-analyzer = "my_package.plugins:MyAnalyzerPlugin"
```

## Security Note

AgentReviewOps is a review prioritization tool. It does not claim to prove that a pull request is secure or safe to merge.

The CLI runs locally without sending source code to external services.

## Contributing

Keep changes focused and testable. Public commands should be documented, and new behavior should include tests.
