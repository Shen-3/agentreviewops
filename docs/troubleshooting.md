# Troubleshooting

## GitHub token missing

`scan-pr`, `comment-pr`, Checks, and reviewer requests need `GITHUB_TOKEN` or the action `github-token` input. Use the workflow-provided `${{ github.token }}` with least-privilege permissions.

## Insufficient GitHub permissions

Comments and reviewer requests need `pull-requests: write`. Checks need `checks: write`. SARIF upload needs `security-events: write`.

## Fork pull request limitations

Fork PRs may not receive write tokens or repository secrets. Prefer `pull_request` for untrusted PRs and expect comments, Checks, reviewer requests, or SARIF upload to be unavailable when permissions are restricted.

## SARIF upload errors

Verify `security-events: write`, confirm the SARIF file exists, and check that the workflow uses `github/codeql-action/upload-sarif`.

## CODEOWNERS not found

Set `review_routing.codeowners.path` or pass `--codeowners-file`. Missing CODEOWNERS is not fatal, but routing may produce unconfigured review requirements.

## Unconfigured review requirements

Add CODEOWNERS entries or onboard repository users with GitHub login mappings in the self-hosted API/dashboard.

## Database migration errors

Run `uv run alembic upgrade head` with `AGENTREVIEW_DATABASE_URL` set to the target database. Check database connectivity and migration ordering.

## Dashboard cannot connect to API

Confirm the API `/health` endpoint is reachable, the dashboard API URL is correct, and `AGENTREVIEW_API_CORS_ORIGINS` includes the dashboard origin in production.

## API key rejected

Use `Authorization: Bearer <api-key>` or `X-AgentReview-API-Key`. Created keys are shown once; revoked keys and keys from another organization are rejected.

## Plugin timeout or error

Increase `timeout_seconds` only for trusted plugins that need more time. Package-discovered plugins run in an isolated child process with stripped environment and must return valid `RiskFinding` objects or dictionaries.
