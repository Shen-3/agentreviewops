# SARIF Export

AgentReviewOps can export deterministic findings as SARIF 2.1.0 for GitHub Code Scanning and other SARIF-compatible tooling.

Generate SARIF locally:

```bash
agentreview scan-diff \
  --diff-file agentreview.diff \
  --output agentreview-report.md \
  --sarif-output agentreview.sarif.json
```

Use SARIF in GitHub Actions:

After the first release, use `Shen-3/agentreviewops@v0` or pin to a full commit SHA. Use `@main` only for development or unreleased changes.

```yaml
name: AgentReviewOps SARIF

on:
  pull_request:

permissions:
  contents: read
  security-events: write

jobs:
  sarif:
    runs-on: ubuntu-latest
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

SARIF export does not upload results by itself. Use `github/codeql-action/upload-sarif@v3` or your platform's SARIF ingestion path.

Limitations:

- Not every finding has file and line data. Those findings are still included as SARIF results without physical locations.
- SARIF is an export format, not a replacement for PR comments or GitHub Check Runs.
- GitHub Code Scanning upload availability depends on repository, organization, plan, and settings.
- AgentReviewOps does not include raw diff content or finding evidence values in SARIF properties.
