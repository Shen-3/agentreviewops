# Release Checklist

AgentReviewOps is distributed primarily as a GitHub composite action and Python package source tree. Releases should be predictable, tagged, and easy to roll back.

## Versioning

- Use `v0.x.y` while the project is pre-1.0.
- Reserve `v1.x.y` for the first stable compatibility commitment.
- Keep `pyproject.toml` and `src/agentreview/__init__.py` versions aligned.
- Document user-visible CLI, action input, API, and report format changes in release notes.

## Pre-Release Validation

Run the full local validation suite:

```bash
uv sync --extra dev
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=agentreview --cov=agentreview_api --cov-report=term-missing
uv run alembic upgrade head
pnpm install --frozen-lockfile
pnpm --filter agentreviewops-web build
pnpm --filter agentreviewops-web lint
git diff --check
```

Verify action examples in `README.md`, `docs/github-action.md`, and `docs/sarif.md`.

Confirm `CHANGELOG.md`, `SECURITY.md`, `CONTRIBUTING.md`, and `docs/v0-readiness.md` are current. Review README, GitHub Action, self-hosting, policy bundle, plugin, CLI, troubleshooting, and release docs before tagging.

## Test The Local Action

Before tagging, run the action self-test workflow on the release candidate branch:

```bash
gh workflow run action-self-test.yml --ref <branch-or-sha>
gh run list --workflow action-self-test.yml --limit 5
```

The workflow must exercise `uses: ./` with comments, checks, and reviewer requests disabled, and verify Markdown, JSON, and SARIF output files exist.

Also confirm `.github/workflows/agentreview.yml` runs on a pull request and publishes Markdown, JSON, and SARIF artifacts while comments and Checks are enabled.

## Create A Release Tag

1. Create a release branch if needed:

   ```bash
   git switch -c release/v0.x.y
   ```

2. Commit release-note and version updates.
3. Tag the exact commit:

   ```bash
   git tag -a v0.x.y -m "AgentReviewOps v0.x.y"
   git push origin v0.x.y
   ```

4. Update the major/minor alias after validation:

   ```bash
   git tag -f v0 v0.x.y
   git push origin -f v0
   ```

Use `v1` instead of `v0` after the first stable release.

## Marketplace Notes

Draft GitHub release notes with:

- Summary of new action inputs and CLI flags.
- Upgrade notes for workflow permissions.
- Known limitations for Checks API annotations and SARIF upload.
- Recommended pinning guidance: release tag for normal use, full commit SHA for maximum immutability.

## Rollback

If a release is bad:

1. Move the `v0` or `v1` alias back to the last known-good release tag.
2. Publish a GitHub release note describing the rollback and affected versions.
3. Open a follow-up issue with failing validation evidence.
4. Avoid deleting immutable version tags unless a secret was exposed.
