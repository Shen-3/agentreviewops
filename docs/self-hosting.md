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

## 6. Use the Dashboard

```bash
cd apps/web
npm run dev
```

Open `http://127.0.0.1:5173` and paste the API key into the dashboard header. Without a key, the dashboard shows demo data.
