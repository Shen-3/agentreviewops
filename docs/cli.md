# CLI reference

AgentReviewOps commands are exposed through `agentreview`.

## `scan-diff`

Analyze a unified diff file and write a Markdown report.

```bash
agentreview scan-diff --diff-file examples/sample.diff --config .agentreview.yml --output agentreview-report.md --fail-on high
```

Common outputs:

```bash
agentreview scan-diff --diff-file examples/sample.diff --output report.md --json-output report.json --sarif-output report.sarif.json --fail-on never
```

## `scan-pr`

Fetch and analyze a GitHub pull request diff using `GITHUB_TOKEN`.

```bash
GITHUB_TOKEN=<token> agentreview scan-pr --repo owner/name --pr 123 --head-sha <sha> --checks --output report.md
```

## `submit-diff`

Submit a diff to a self-hosted AgentReviewOps API.

```bash
AGENTREVIEW_API_KEY=<api-key> agentreview submit-diff --diff-file examples/sample.diff --api-url http://127.0.0.1:8000 --repository owner/name --pr 123
```

## `comment-pr`

Post or update the AgentReviewOps Markdown report on a pull request.

```bash
GITHUB_TOKEN=<token> agentreview comment-pr --repo owner/name --pr 123 --report-file agentreview-report.md
```

## `request-reviewers`

Resolve review requirements from JSON output and request GitHub reviewers.

```bash
GITHUB_TOKEN=<token> agentreview request-reviewers --repo owner/name --pr 123 --analysis-file agentreview-report.json --reviewer-request-failure-mode warn
```

Use `--dry-run` to print the resolved request plan without calling GitHub.

## `bundles list`

List built-in policy bundles.

```bash
agentreview bundles list
```

## `bundles show`

Print a built-in bundle as YAML.

```bash
agentreview bundles show starter
```

## `init`

Generate an AgentReviewOps config and optional GitHub Actions workflow.

```bash
agentreview init --bundle starter --non-interactive --force
```

Useful options include `--checks`, `--request-reviewers`, `--sarif`, `--no-write-workflow`, `--config-path`, and `--workflow-path`.
