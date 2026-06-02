# GitHub Action Usage

The recommended GitHub Actions entrypoint is the root composite action:

```yaml
- uses: Shen-3/agentreviewops@main
  with:
    github-token: ${{ github.token }}
    config: .agentreview.yml
    comment: "true"
    fail-on: high
    codeowners-file: .github/CODEOWNERS
```

The action installs AgentReviewOps from its own `$GITHUB_ACTION_PATH`, builds a pull request diff when `diff-file` is not provided, writes a Markdown report, optionally posts the report as a PR comment, optionally submits the analysis to a self-hosted AgentReviewOps API, and applies the configured CI failure threshold.

Keep API keys in GitHub Secrets. Do not echo GitHub tokens, AgentReviewOps API keys, or OpenAI-compatible provider keys from workflow steps.

## Recommended Workflow

Create `.github/workflows/agentreview.yml`:

```yaml
name: AgentReviewOps

on:
  pull_request:

permissions:
  contents: read
  pull-requests: write

jobs:
  review-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0

      - uses: Shen-3/agentreviewops@main
        with:
          github-token: ${{ github.token }}
          config: .agentreview.yml
          comment: "true"
          fail-on: high
          codeowners-file: .github/CODEOWNERS
```

When `diff-file` is omitted on `pull_request` or `pull_request_target` events, the action reads the event payload, resolves the base/head SHAs, and writes a temporary unified diff before running `agentreview scan-diff`.

## `fail-on`

`fail-on` maps directly to the CLI `--fail-on` option, which accepts `low|medium|high|block|never`.

- `never` always lets the scan command succeed unless there is a real read, config, plugin, AI provider, or API error.
- `high` fails CI for `high` and `block` risk.
- `medium` fails CI for `medium`, `high`, and `block` risk.
- `block` fails CI only for `block` risk.

The action still writes the report and runs configured comment/submission steps before the final CI failure is applied.

## Review Routing And CODEOWNERS

AgentReviewOps can turn deterministic findings into required human review requirements. It can use policy rules, repository memberships, and CODEOWNERS.

Pass `codeowners-file` when your CODEOWNERS file lives in a non-standard path or you want explicit control:

```yaml
- uses: Shen-3/agentreviewops@main
  with:
    github-token: ${{ github.token }}
    config: .agentreview.yml
    comment: "true"
    fail-on: high
    codeowners-file: .github/CODEOWNERS
```

When `codeowners-file` is omitted, the CLI looks for `.github/CODEOWNERS`, `CODEOWNERS`, then `docs/CODEOWNERS`. If no CODEOWNERS file exists, analysis still succeeds and any triggered requirement without a reviewer appears as `Not configured` in the report.

## Reports And Artifacts

The action writes the Markdown report to `output`, which defaults to `agentreview-report.md`. The same file is used for the PR comment when `comment: "true"`.

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
- uses: Shen-3/agentreviewops@main
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
        run: agentreview scan-diff --diff-file agentreview.diff --config .agentreview.yml --output agentreview-report.md --fail-on high --codeowners-file .github/CODEOWNERS

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
