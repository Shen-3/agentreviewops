# AgentReviewOps

AgentReviewOps is a policy-as-code risk gate for AI-generated pull requests. It classifies risky changes, routes or requires human review, comments on PRs, and preserves audit evidence before merge.

Use it when your team uses Cursor, Copilot, Devin, Codex, Claude Code, or other coding agents and needs deterministic governance before merge.

## Fastest Start

After the first release, use `Shen-3/agentreviewops@v0`; for local development use `@main`; for production pin to a release tag or full SHA.

Generate the default config and workflow:

```bash
agentreview init --bundle starter
```

### Minimal PR comment gate

```yaml
name: AgentReviewOps

on:
  pull_request:

permissions:
  contents: read
  pull-requests: write

jobs:
  agentreview:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: Shen-3/agentreviewops@v0
        with:
          github-token: ${{ github.token }}
          comment: "true"
          fail-on: high
```

### Recommended governance gate

Add `.agentreview.yml` and keep reviewer requests/checks opt-in:

```yaml
- uses: Shen-3/agentreviewops@v0
  with:
    github-token: ${{ github.token }}
    config: .agentreview.yml
    comment: "true"
    checks: "true"
    fail-on: high
    codeowners-file: .github/CODEOWNERS
```

### Advanced reviewer requests

```yaml
- uses: Shen-3/agentreviewops@v0
  with:
    github-token: ${{ github.token }}
    config: .agentreview.yml
    comment: "true"
    request-reviewers: "true"
    reviewer-request-mode: users-and-teams
    reviewer-request-failure-mode: warn
    fail-on: high
```

Reviewer requests need `pull-requests: write` and GitHub login mappings for repository members.

### Advanced SARIF / Code Scanning export

```yaml
permissions:
  contents: read
  pull-requests: write
  security-events: write

steps:
  - uses: Shen-3/agentreviewops@v0
    with:
      github-token: ${{ github.token }}
      sarif-output: agentreview.sarif.json

  - uses: github/codeql-action/upload-sarif@v3
    if: always()
    with:
      sarif_file: agentreview.sarif.json
```

### Self-hosted dashboard/API

```bash
cp .env.example .env
docker compose -f deploy/docker-compose.yml up --build
```

This starts PostgreSQL, the FastAPI API on `http://127.0.0.1:8000`, and the dashboard on `http://127.0.0.1:8080`.

## Policy Bundles

Built-in bundles provide deterministic starting points:

- `starter`
- `security`
- `github-actions`
- `python`
- `dependency-governance`
- `ai-pr-strict`
- `enterprise-strict`

Inspect and generate them:

```bash
agentreview bundles list
agentreview bundles show starter
agentreview init --bundle ai-pr-strict --checks --request-reviewers
```

See [policy bundle docs](docs/policy-bundles.md).

## Current Status

Current status: pre-v0 beta candidate. The CLI, GitHub Action, deterministic risk engine, review routing, JSON/SARIF/Checks outputs, self-hosted API/dashboard, governance metrics, policy bundles, and init onboarding are implemented. Hosted deployment is intentionally not implemented.

GitHub Action usage is the primary entrypoint for PR quality gates. Self-hosted API/dashboard submission, artifact-based reports, GitHub PR comments, GitHub Checks, reviewer requests, package-discovered analyzer plugins, and an opt-in OpenAI-compatible AI provider are supported.

Known limitations before a public v0 release are tracked in [docs/v0-readiness.md](docs/v0-readiness.md). AgentReviewOps is not a SAST replacement, not a human review replacement, does not implement hosted SaaS, and does not implement OAuth or GitHub App auth.

## Development

### Local CLI

Use `uv` for Python and `pnpm` for the dashboard:

```bash
uv sync --extra dev
uv run agentreview --help
uv run agentreview scan-diff --diff-file examples/sample.diff --config .agentreview.example.yml --output agentreview-report.md --fail-on never
uv run pytest
pnpm install
pnpm --filter agentreviewops-web dev
```

Run the API locally in another shell when developing against live dashboard data:

```bash
export AGENTREVIEW_DATABASE_URL=sqlite:///./agentreview.db
uv run alembic upgrade head
uv run uvicorn agentreview_api.main:app --reload --host 127.0.0.1 --port 8000
```

### Local Quality Gates

Run these checks before pushing changes:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=agentreview --cov=agentreview_api --cov-report=term-missing
uv run alembic upgrade head
pnpm --filter agentreviewops-web build
pnpm --filter agentreviewops-web lint
git diff --check
```

### Legacy/Manual Fallback

The classic editable install remains available if `uv` is not installed:

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/agentreview --help
.venv/bin/pytest
```

## CLI Usage

```bash
agentreview --help
agentreview bundles list
agentreview bundles show starter
agentreview init --bundle starter --non-interactive
agentreview scan-diff --diff-file examples/sample.diff --config .agentreview.example.yml --output agentreview-report.md --json-output agentreview-report.json --fail-on high --codeowners-file .github/CODEOWNERS
agentreview scan-diff --diff-file examples/sample.diff --output agentreview-report.md --sarif-output agentreview.sarif.json
GITHUB_TOKEN=<github-token> agentreview scan-diff --diff-file examples/sample.diff --output agentreview-report.md --checks --repo owner/name --head-sha <sha> --fail-on high
AGENTREVIEW_API_KEY=<api-key> agentreview submit-diff --diff-file examples/sample.diff --api-url http://127.0.0.1:8000 --repository owner/name --pr 123
GITHUB_TOKEN=<github-token> agentreview scan-pr --repo owner/name --pr 123 --head-sha <sha> --checks --output agentreview-report.md --json-output agentreview-report.json --fail-on high --codeowners-file .github/CODEOWNERS
GITHUB_TOKEN=<github-token> agentreview request-reviewers --repo owner/name --pr 123 --analysis-file agentreview-report.json
GITHUB_TOKEN=<github-token> agentreview comment-pr --repo owner/name --pr 123 --report-file agentreview-report.md
```

Expected scan output includes the risk level, positive findings, and the report path.

`--fail-on low|medium|high|block|never` controls whether scan commands fail CI after writing the report. The default is `never` for backward compatibility.

`--json-output` writes structured analysis JSON for `scan-diff` and `scan-pr`, including risk, decision, findings, changed files, review requirements, and metadata. The JSON is produced from structured analysis objects, not parsed from Markdown.

`--checks` publishes a completed GitHub Check Run using the Checks API. It maps `--fail-on` decisions to `failure`, findings below the failure threshold to `neutral`, and clean scans to `success`. Use checks alongside PR comments when you want branch protection to require the AgentReviewOps policy gate. Check annotations are emitted only for findings with file and line locations and are capped at 50 annotations.

`--sarif-output` writes SARIF 2.1.0 JSON for GitHub Code Scanning or other SARIF-compatible tools. SARIF is an export format, not a replacement for PR comments or checks. Not every deterministic finding has line-level location data, and GitHub Code Scanning availability depends on repository and organization settings.

`--codeowners-file` lets scan commands use an explicit CODEOWNERS file for human review routing. When omitted, AgentReviewOps looks for `.github/CODEOWNERS`, `CODEOWNERS`, then `docs/CODEOWNERS`; missing CODEOWNERS files are not an error unless you explicitly pass a missing path.

`submit-diff` sends a unified diff to a self-hosted AgentReviewOps API and persists the result for the dashboard. The API key is read from `AGENTREVIEW_API_KEY` or `--api-key` and is not printed in command output.

`scan-pr` fetches the pull request diff from the GitHub API using `GITHUB_TOKEN`. The token is required at runtime and is not printed in command output.

`request-reviewers` reads the JSON created by `--json-output`, resolves review routing suggestions, and calls GitHub's requested reviewers API. CODEOWNERS `@username` entries become individual reviewers and `@org/team-slug` entries become team reviewers. Repository membership `@github-login` suggestions become individual reviewers; repository membership email suggestions are skipped with `missing_github_login`. Other email addresses are skipped with `email_identifier_not_requestable`. AgentReviewOps does not map emails to GitHub users automatically. Use `--reviewer-request-failure-mode warn` when reviewer request permission errors should not fail the command.

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
- `DELETE /api/repositories/{repository_id}`
- `POST /api/repositories/{repository_id}/memberships`
- `PATCH /api/repositories/{repository_id}/memberships/{user_id}`
- `DELETE /api/repositories/{repository_id}/memberships/{user_id}`
- `GET /api/audit-events`
- `GET /api/audit-events/export`
- `POST /api/retention/purge`
- `GET /api/metrics/overview`
- `GET /api/metrics/rules`
- `GET /api/metrics/routing`
- `GET /api/metrics/repositories`
- `GET /api/policies`
- `POST /api/policies`
- `PATCH /api/policies/{policy_id}`
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

The response includes a persisted analysis run ID scoped to the API key's organization, changed files, findings, review requirements, risk score, risk level, and Markdown report content. If the analysis repository matches an onboarded repository with an enabled repository policy, that policy is applied first. Otherwise the latest enabled organization policy overrides the request-level config. Use the report endpoint to fetch the stored Markdown report later.

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

Update a saved policy with `PATCH /api/policies/{policy_id}` to rename it, replace its config, or enable/disable it without deleting audit history. Disabled policies are ignored by future analysis configuration resolution.

Set `AGENTREVIEW_DATABASE_URL` to choose the database. SQLite is supported for local development and tests; production deployments should use a PostgreSQL URL.

Run database migrations with:

```bash
uv run alembic upgrade head
```

Create the first self-hosted organization and one-time API key with:

```bash
uv run agentreview admin bootstrap \
  --org-slug acme \
  --org-name "Acme Engineering" \
  --email reviewer@example.com \
  --api-key-name "Local CI"
```

The key is printed once and stored only as a hash. See [self-hosting docs](docs/self-hosting.md) for the current local deployment flow.

Issue additional organization API keys with `POST /api/api-keys`, list existing keys with `GET /api/api-keys`, update key names or roles with `PATCH /api/api-keys/{api_key_id}`, and revoke inactive keys with `POST /api/api-keys/{api_key_id}/revoke`. Created keys are returned once and are stored only as hashes. API key roles are `admin`, `ci`, and `read_only`: admin keys can manage governance settings, CI keys can submit analyses, and read-only keys can inspect existing data.

Create organization users with `POST /api/users`, update user roles with `PATCH /api/users/{user_id}`, then assign them to onboarded repositories with `POST /api/repositories/{repository_id}/memberships`. Users can include optional `github_login`; AgentReviewOps stores it without a leading `@`, preserves case, validates GitHub username syntax, and rejects duplicate logins within the same organization case-insensitively. No automatic email-to-GitHub mapping is performed. Repository membership roles are `owner`, `maintainer`, and `reviewer`; those assignments are returned in repository list responses and used as reviewer routing metadata during analysis. When `github_login` is set, repository membership suggestions use `@login` and can become GitHub reviewer requests. Without it, reports keep the member email for humans and reviewer requests skip the entry as `missing_github_login`. Update reviewer roles with `PATCH /api/repositories/{repository_id}/memberships/{user_id}`. Remove stale users with `DELETE /api/users/{user_id}`, remove stale reviewer assignments with `DELETE /api/repositories/{repository_id}/memberships/{user_id}`, and remove stale onboarded repositories with `DELETE /api/repositories/{repository_id}`.

Metrics endpoints are read-only, organization-scoped, and accept `days` from 1 to 365, defaulting to 30. They expose overview risk distribution and trends, top triggered rules and severity distribution, routing hit rate plus unconfigured requirements, and repository-level risk rows. Routing hit rate is `configured review requirements / total review requirements` and is `0` when no requirements exist.

## Review routing

AgentReviewOps can turn deterministic findings into required human review requirements. It can use policy rules, repository memberships, and CODEOWNERS.

Routing does not change the risk score and does not request GitHub reviewers automatically. If a routing rule triggers but no reviewer can be found, the report shows `Not configured` so the governance gap is visible.

Example policy:

```yaml
review_routing:
  enabled: true
  codeowners:
    enabled: true
  rules:
    - id: security-review
      paths: ["auth/**", "security/**"]
      rule_ids: ["sensitive-area-change", "python-eval-exec"]
      require_roles: ["maintainer", "owner"]
      reason: "Sensitive area changed."
```

Supported repository membership roles for routing are `owner`, `maintainer`, and `reviewer`. The minimal CODEOWNERS parser supports common whitespace-separated entries such as:

```text
auth/** @security-team
.github/workflows/** @platform-team @devops
*.py @backend-team
```

For a containerized local stack:

```bash
docker compose -f deploy/docker-compose.yml up --build
```

This starts PostgreSQL, the FastAPI API on `127.0.0.1:8000`, and the dashboard on `127.0.0.1:8080`.

## Web Dashboard

A React + TypeScript + Vite dashboard lives in `apps/web`.

Run it locally:

```bash
pnpm install
pnpm --filter agentreviewops-web dev
```

Then open `http://127.0.0.1:5173`.

The dashboard sends the supplied API key as a Bearer token for live API data. Session-only storage is the default; browser storage keeps the key after the tab closes and should be used only on trusted devices. Clear the key from the header when finished. Without a key, the dashboard falls back to seeded demo data. With a live key, it reads `/api/auth/me` and enables only the actions allowed by that key role: admin keys manage governance and submit analyses, CI keys submit analyses, and read-only keys inspect existing data and export audit evidence. Full OAuth or GitHub App browser auth is future work. The dashboard includes diff submission, governance metrics, analysis list, selected analysis detail, risk badges, findings table, report preview, user management with GitHub login mapping, repository onboarding with reviewer routing assignment, organization and repository policy assignment, role-scoped API key management, audit history with JSON/CSV export, and loading/error/empty states.

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

The built-in example plugin demonstrates the contract by flagging dependency manifests. Enabled plugins are loaded from the built-in registry and installed Python package entry points in the `agentreview.plugins` group. Plugin output is validated as `RiskFinding` data before it can affect risk scoring. Package-discovered plugins run in an isolated child process with a timeout and stripped environment, but this is not a full OS sandbox. See [plugin docs](docs/plugins.md).

Third-party packages can expose analyzer plugins from `pyproject.toml`:

```toml
[project.entry-points."agentreview.plugins"]
my-analyzer = "my_package.plugins:MyAnalyzerPlugin"
```

## Security Note

AgentReviewOps is a review prioritization tool. It does not claim to prove that a pull request is secure or safe to merge.

The CLI runs locally without sending source code to external services.

Use `pull_request`, not `pull_request_target`, for untrusted external PRs unless you fully understand the fork PR token and secret exposure risk. Do not expose write tokens, repository secrets, GitHub tokens, AgentReviewOps API keys, or OpenAI-compatible provider keys to untrusted code. See [SECURITY.md](SECURITY.md) and [GitHub Action docs](docs/github-action.md).

## Contributing

Keep changes focused and testable. Public commands should be documented, and new behavior should include tests. Run the local quality gates before opening or updating a pull request.

### Backend Structure

The FastAPI backend is composed from `apps/api/agentreview_api/main.py`. Request and response models live in `schemas/`, route handlers live in `routers/`, and non-trivial policy, analysis, audit, repository, and retention logic lives in `services/`. Keep endpoint paths, auth dependencies, and response payloads stable when moving code between these modules.
