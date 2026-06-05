# Contributing

## Setup

```bash
uv sync --extra dev
pnpm install --frozen-lockfile
```

## Quality Gates

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=agentreview --cov=agentreview_api --cov-report=term-missing
uv run alembic upgrade head
pnpm --filter agentreviewops-web build
pnpm --filter agentreviewops-web lint
git diff --check
```

## Coding Style

Keep changes scoped and deterministic. Python code uses typed functions, Pydantic models for config/API shapes, and explicit domain errors. Dashboard changes should preserve the dense operational UI style and avoid adding heavy frontend libraries.

## Risk Rules

Add deterministic rules in `src/agentreview/risk.py`, include the rule ID in `BUILT_IN_RULE_IDS`, and add tests that prove both triggering and non-triggering behavior. Do not make LLM usage mandatory for deterministic rules.

## Policy Bundles

Update `src/agentreview/policy_bundles.py`, keep bundle IDs stable, and extend `tests/test_policy_bundles.py`. Bundle routing `rule_ids` must match `BUILT_IN_RULE_IDS` unless a documented pseudo-rule is intentionally added.

## API And Dashboard

API changes need route/service/schema tests under `tests/api/`. Dashboard changes must keep TypeScript types in sync and pass the filtered pnpm build and lint commands.

## Security Expectations

Do not put secrets in tests, fixtures, logs, reports, or screenshots. Use explicit redaction helpers for any new external output path. Treat plugin code, fork PRs, and CI tokens as security-sensitive surfaces.
