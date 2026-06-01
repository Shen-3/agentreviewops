# Self-Hosting AgentReviewOps

This guide covers the current self-hosted path for the FastAPI backend and React dashboard.

## Docker Compose Quick Start

The compose stack runs PostgreSQL, the FastAPI API, and the built React dashboard:

```bash
cp .env.example .env
docker compose -f deploy/docker-compose.yml up --build
```

Then open:

- API health: `http://127.0.0.1:8000/health`
- Dashboard: `http://127.0.0.1:8080`

Compose healthchecks gate startup in order: PostgreSQL must be ready before migrations and the API start, and the dashboard waits for the API `/health` endpoint before serving traffic.

In another shell, bootstrap the first organization:

```bash
docker compose -f deploy/docker-compose.yml exec api agentreview admin bootstrap \
  --org-slug acme \
  --org-name "Acme Engineering" \
  --email reviewer@example.com \
  --user-name "Reviewer" \
  --api-key-name "Local CI"
```

Paste the printed API key into the dashboard.

The rest of this guide documents the local Python/Node path.

## 1. Install

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
cd apps/web
npm install
cd ../..
```

## 2. Choose a Database

For local evaluation, SQLite is enough:

```bash
export AGENTREVIEW_DATABASE_URL=sqlite:///./agentreview.db
```

For production-style deployments, use PostgreSQL:

```bash
export AGENTREVIEW_DATABASE_URL=postgresql+psycopg://agentreview:<password>@localhost:5432/agentreview
```

## 3. Run Migrations

```bash
.venv/bin/alembic upgrade head
```

## 4. Bootstrap the First Organization

```bash
.venv/bin/agentreview admin bootstrap \
  --org-slug acme \
  --org-name "Acme Engineering" \
  --email reviewer@example.com \
  --user-name "Reviewer" \
  --api-key-name "Local CI"
```

The command prints a one-time API key. Store it immediately. AgentReviewOps stores only a hash of the key.

## 5. Use the API

Pass the API key to protected endpoints:

```bash
curl -H "Authorization: Bearer $AGENTREVIEW_API_KEY" \
  http://127.0.0.1:8000/api/auth/me
```

API keys are role-scoped. Use `admin` keys for governance changes, `ci` keys for analysis submission from automation, and `read_only` keys for dashboards or evidence review that should not mutate state.

## 6. Use the Dashboard

```bash
cd apps/web
npm run dev
```

Open `http://127.0.0.1:5173` and paste the API key into the dashboard header. Without a key, the dashboard shows demo data.

## 7. Configure Policies

Create organization users from the dashboard or `POST /api/users`, then onboard repositories from the dashboard or `POST /api/repositories`. Assign users to repositories with the dashboard routing form or `POST /api/repositories/{repository_id}/memberships`. Update roles from the dashboard or the matching `PATCH` endpoints. Remove stale users or reviewer assignments from the same dashboard panels or with the matching `DELETE` endpoints. These governance endpoints require an admin API key.

Policies saved with `scope: "repository"` and a repository ID apply before organization policies when `POST /api/analyze/diff` receives a matching `repository` value such as `owner/name`. If no repository policy matches, AgentReviewOps uses the latest enabled organization policy, then request config, then defaults.

Repository list responses include assigned reviewers from repository memberships so analysis audit events can record routing counts and roles without storing raw diffs or reports.

## 8. Retention Purges

Use retention purges to remove old analysis reports and, when needed, old audit events for the authenticated organization. The endpoint is dry-run by default:

```bash
curl -X POST -H "Authorization: Bearer $AGENTREVIEW_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"older_than_days":90,"include_analysis_runs":true,"include_audit_events":false}' \
  http://127.0.0.1:8000/api/retention/purge
```

To actually delete matching records, set `dry_run` to `false` and `confirm` to `true`:

```bash
curl -X POST -H "Authorization: Bearer $AGENTREVIEW_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"older_than_days":90,"include_analysis_runs":true,"include_audit_events":true,"dry_run":false,"confirm":true}' \
  http://127.0.0.1:8000/api/retention/purge
```

Confirmed purges write a `retention.purged` audit event with cutoff and deletion counts.

## 9. Optional AI Summaries

AI summaries are off by default. To enable the OpenAI-compatible provider for local or self-hosted analysis, configure the provider in `.agentreview.yml` or an organization policy and pass secrets through environment variables:

```yaml
ai:
  enabled: true
  provider: openai
  model: "<model-name>"
```

```bash
export AGENTREVIEW_OPENAI_API_KEY=<provider-api-key>
export AGENTREVIEW_OPENAI_MODEL=<model-name>
export AGENTREVIEW_OPENAI_BASE_URL=https://api.openai.com/v1
```

AgentReviewOps sends deterministic findings and a redacted diff excerpt capped by `ai.max_diff_chars`. API keys and provider credentials are not stored in reports or audit events.
