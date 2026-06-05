# GitHub Action Usage

The recommended GitHub Actions entrypoint is the root composite action. After the first release, use a stable release tag such as `Shen-3/agentreviewops@v0`. For production, pin to a release tag or a full commit SHA. Use `Shen-3/agentreviewops@main` only for development or testing unreleased changes.

The action installs AgentReviewOps from its own `$GITHUB_ACTION_PATH`, builds a pull request diff when `diff-file` is not provided, writes a Markdown report, optionally posts the report as a PR comment, optionally requests GitHub reviewers, optionally submits the analysis to a self-hosted AgentReviewOps API, and applies the configured CI failure threshold.

Keep API keys in GitHub Secrets. Do not echo GitHub tokens, AgentReviewOps API keys, or OpenAI-compatible provider keys from workflow steps.

The composite action installs the local package with `python -m pip install "$GITHUB_ACTION_PATH"` instead of editable install. It still resolves Python package dependencies at runtime; a future hardening step could publish a prebuilt Docker action or pinned wheel artifact.

## Minimal Setup

This is the smallest PR comment gate:

```yaml
name: AgentReviewOps

on:
  pull_request:

permissions:
  contents: read
  pull-requests: write
  checks: write
  security-events: write

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

## Generated Workflow

Generate a starter config and workflow:

```bash
agentreview init --bundle starter
```

The generated workflow uses `.agentreview.yml` and keeps advanced features disabled unless selected:

```yaml
name: AgentReviewOps

on:
  pull_request:

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      # Use a released tag or pin to a full commit SHA for production.
      - uses: Shen-3/agentreviewops@v0
        with:
          github-token: ${{ github.token }}
          config: .agentreview.yml
          comment: "true"
          fail-on: high
```

When `diff-file` is omitted on `pull_request` or `pull_request_target` events, the action reads the event payload, resolves the base/head SHAs, and writes a temporary unified diff before running `agentreview scan-diff`.

## Permissions By Feature

| Feature | Required permissions |
|---|---|
| PR comments | `contents: read`, `pull-requests: write` |
| GitHub Check Runs | `contents: read`, `checks: write` |
| Reviewer requests | `contents: read`, `pull-requests: write` |
| SARIF upload | `contents: read`, `security-events: write` |

Combine permissions when enabling multiple features.

## `fail-on`

`fail-on` maps directly to the CLI `--fail-on` option, which accepts `low|medium|high|block|never`.

- `never` always lets the scan command succeed unless there is a real read, config, plugin, AI provider, or API error.
- `high` fails CI for `high` and `block` risk.
- `medium` fails CI for `medium`, `high`, and `block` risk.
- `block` fails CI only for `block` risk.

The action still writes the report and runs configured comment/submission steps before the final CI failure is applied.

## GitHub Check Runs

Set `checks: "true"` to publish an AgentReviewOps GitHub Check Run. Checks are useful alongside PR comments when you want a branch protection rule to require the AgentReviewOps policy gate.

```yaml
- uses: Shen-3/agentreviewops@v0
  with:
    github-token: ${{ github.token }}
    comment: "true"
    checks: "true"
    check-name: AgentReviewOps
    check-title: AgentReviewOps policy gate
    fail-on: high
```

Workflows that publish check runs need:

```yaml
permissions:
  contents: read
  pull-requests: write
  checks: write
```

The check conclusion is `failure` when the configured `fail-on` threshold is met, `neutral` when findings exist below the failure threshold, and `success` when there are no positive deterministic findings. GitHub annotations are emitted only for findings with file and line locations, and the first implementation caps annotations at 50. Findings without line locations remain visible in the check summary/text and Markdown report.

## SARIF Export

Set `sarif-output` to write SARIF 2.1.0 output for GitHub Code Scanning or other SARIF-compatible tooling. The action writes the SARIF file but does not upload it automatically.

```yaml
permissions:
  contents: read
  security-events: write

steps:
  - uses: actions/checkout@v6
  - uses: Shen-3/agentreviewops@v0
    with:
      github-token: ${{ github.token }}
      sarif-output: agentreview.sarif.json
      fail-on: never
  - uses: github/codeql-action/upload-sarif@v3
    with:
      sarif_file: agentreview.sarif.json
```

Local generation:

```bash
agentreview scan-diff \
  --diff-file agentreview.diff \
  --output agentreview-report.md \
  --sarif-output agentreview.sarif.json
```

SARIF is an export format, not a replacement for PR comments/checks. Findings without file and line data are still included as SARIF results but do not have physical locations. GitHub Code Scanning upload behavior depends on repository and organization plan/settings.

## Review Routing And CODEOWNERS

AgentReviewOps can turn deterministic findings into required human review requirements. It can use policy rules, repository memberships, and CODEOWNERS.

Pass `codeowners-file` when your CODEOWNERS file lives in a non-standard path or you want explicit control:

```yaml
- uses: Shen-3/agentreviewops@v0
  with:
    github-token: ${{ github.token }}
    config: .agentreview.yml
    comment: "true"
    fail-on: high
    codeowners-file: .github/CODEOWNERS
```

When `codeowners-file` is omitted, the CLI looks for `.github/CODEOWNERS`, `CODEOWNERS`, then `docs/CODEOWNERS`. If no CODEOWNERS file exists, analysis still succeeds and any triggered requirement without a reviewer appears as `Not configured` in the report.

## Requesting GitHub Reviewers

Reviewer requests are disabled by default. Set `request-reviewers: "true"` to have the action write structured analysis JSON with `agentreview scan-diff --json-output` and then run `agentreview request-reviewers` against that file.

```yaml
- uses: Shen-3/agentreviewops@v0
  with:
    github-token: ${{ github.token }}
    config: .agentreview.yml
    comment: "true"
    checks: "true"
    request-reviewers: "true"
    reviewer-request-mode: users-and-teams
    reviewer-request-failure-mode: warn
    fail-on: high
    codeowners-file: .github/CODEOWNERS
```

The workflow must grant:

```yaml
permissions:
  contents: read
  pull-requests: write
```

`reviewer-request-mode` accepts `users`, `teams`, or `users-and-teams`. `reviewer-request-failure-mode` accepts `warn` or `fail`; the action default is `warn`, so GitHub permission errors are printed but do not block comments, checks, or final `fail-on` handling. Set it to `fail` to preserve strict reviewer request failures. The action passes the pull request author to the CLI so AgentReviewOps does not request review from the PR author.

Resolution rules:

- CODEOWNERS `@username` becomes an individual GitHub reviewer named `username`.
- CODEOWNERS `@org/team-slug` becomes a GitHub team reviewer named `team-slug`.
- Bare CODEOWNERS identifiers are not guessed as teams.
- Email addresses are skipped with `email_identifier_not_requestable`.
- Repository membership `@github-login` suggestions become individual reviewers.
- Repository membership email suggestions are skipped with `missing_github_login`.
- Emails are not automatically mapped to GitHub users.

Manual equivalent:

```bash
agentreview scan-diff \
  --diff-file agentreview.diff \
  --config .agentreview.yml \
  --output agentreview-report.md \
  --json-output agentreview-report.json \
  --fail-on high \
  --codeowners-file .github/CODEOWNERS

GITHUB_TOKEN="${GITHUB_TOKEN}" agentreview request-reviewers \
  --repo owner/name \
  --pr 123 \
  --analysis-file agentreview-report.json \
  --reviewer-request-mode users-and-teams \
  --reviewer-request-failure-mode warn
```

## Reports And Artifacts

The action writes the Markdown report to `output`, which defaults to `agentreview-report.md`. The same file is used for the PR comment when `comment: "true"`. When `request-reviewers: "true"` is enabled, the action also writes a temporary structured JSON analysis file for reviewer resolution. When `sarif-output` is non-empty, the action writes SARIF to that path.

To retain the report as a workflow artifact, add an upload step after the action. Use `if: always()` if you want the artifact even when `fail-on` fails the job.

```yaml
- uses: actions/upload-artifact@v4
  if: always()
  with:
    name: agentreview-report
    path: agentreview-report.md
```

## Self-Hosted Dashboard Submission

Pass `api-url` and `api-key` to submit the same diff to a self-hosted AgentReviewOps API:

```yaml
- uses: Shen-3/agentreviewops@v0
  with:
    github-token: ${{ github.token }}
    config: .agentreview.yml
    comment: "true"
    fail-on: high
    codeowners-file: .github/CODEOWNERS
    api-url: ${{ vars.AGENTREVIEW_API_URL }}
    api-key: ${{ secrets.AGENTREVIEW_API_KEY }}
```

The action sends the API key through `AGENTREVIEW_API_KEY` and does not print it.

## Advanced Manual Fallback

Use the manual flow when you need full control over installation, diff construction, artifact upload, or command ordering.

```yaml
name: AgentReviewOps Manual

on:
  pull_request:

permissions:
  contents: read
  pull-requests: write

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
          cache: pip

      - name: Install AgentReviewOps
        run: python -m pip install -e "."

      - name: Build PR diff
        run: git diff --unified=3 "${{ github.event.pull_request.base.sha }}" "${{ github.event.pull_request.head.sha }}" > agentreview.diff

      - name: Run AgentReviewOps
        run: agentreview scan-diff --diff-file agentreview.diff --config .agentreview.yml --output agentreview-report.md --json-output agentreview-report.json --sarif-output agentreview.sarif.json --checks --repo "${{ github.repository }}" --head-sha "${{ github.event.pull_request.head.sha }}" --fail-on high --codeowners-file .github/CODEOWNERS

      - name: Request GitHub reviewers
        env:
          GITHUB_TOKEN: ${{ github.token }}
        run: |
          agentreview request-reviewers \
            --repo "${{ github.repository }}" \
            --pr "${{ github.event.pull_request.number }}" \
            --analysis-file agentreview-report.json \
            --author "${{ github.event.pull_request.user.login }}"

      - name: Submit to AgentReviewOps dashboard
        if: ${{ vars.AGENTREVIEW_API_URL != '' && secrets.AGENTREVIEW_API_KEY != '' }}
        env:
          AGENTREVIEW_API_KEY: ${{ secrets.AGENTREVIEW_API_KEY }}
        run: |
          agentreview submit-diff \
            --diff-file agentreview.diff \
            --config .agentreview.yml \
            --api-url "${{ vars.AGENTREVIEW_API_URL }}" \
            --repository "${{ github.repository }}" \
            --pr "${{ github.event.pull_request.number }}" \
            --title "${{ github.event.pull_request.title }}" \
            --author "${{ github.actor }}" \
            --branch "${{ github.head_ref }}"

      - name: Comment on pull request
        env:
          GITHUB_TOKEN: ${{ github.token }}
        run: |
          agentreview comment-pr \
            --repo "${{ github.repository }}" \
            --pr "${{ github.event.pull_request.number }}" \
            --report-file agentreview-report.md

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: agentreview-report
          path: agentreview-report.md
```

`agentreview comment-pr` posts or updates one AgentReviewOps PR comment using a hidden marker, so repeated workflow runs update the previous comment instead of adding duplicates.
