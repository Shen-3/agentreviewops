# GitHub Action Usage

AgentReviewOps can run in GitHub Actions by scanning a prepared unified diff, uploading the generated Markdown report as an artifact, optionally submitting the diff to a self-hosted AgentReviewOps API so it appears in the dashboard, and optionally posting or updating a pull request comment.

Keep API keys in GitHub Secrets and pass them through environment variables, not inline command output.

## Basic PR Workflow

Create a workflow such as `.github/workflows/agentreview.yml`:

```yaml
name: AgentReviewOps

"on":
  pull_request:

permissions:
  contents: read
  pull-requests: write

jobs:
  scan:
    runs-on: ubuntu-latest
    env:
      AGENTREVIEW_API_KEY: ${{ secrets.AGENTREVIEW_API_KEY }}

    steps:
      - name: Check out repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install AgentReviewOps
        run: python -m pip install -e "."

      - name: Build PR diff
        run: git diff --unified=0 "origin/${{ github.base_ref }}" HEAD > agentreview.diff

      - name: Run AgentReviewOps
        run: agentreview scan-diff --diff-file agentreview.diff --config .agentreview.example.yml --output agentreview-report.md

      - name: Submit to AgentReviewOps dashboard
        if: ${{ env.AGENTREVIEW_API_KEY != '' }}
        run: |
          agentreview submit-diff \
            --diff-file agentreview.diff \
            --config .agentreview.example.yml \
            --api-url "${{ vars.AGENTREVIEW_API_URL }}" \
            --repository "${{ github.repository }}" \
            --pr "${{ github.event.pull_request.number }}" \
            --title "${{ github.event.pull_request.title }}" \
            --author "${{ github.actor }}" \
            --branch "${{ github.head_ref }}"

      - name: Comment on pull request
        run: |
          agentreview comment-pr \
            --repo "${{ github.repository }}" \
            --pr "${{ github.event.pull_request.number }}" \
            --report-file agentreview-report.md
        env:
          GITHUB_TOKEN: ${{ github.token }}

      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: agentreview-report
          path: agentreview-report.md
```

## Composite Action Example

This repository also includes a local composite action at `examples/github-action/action.yml`.

In a consuming repository, set up Python first, check out the repository you want to scan, prepare `agentreview.diff`, then call the action with artifact-only output:

```yaml
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: "3.12"

- name: Check out repository
  uses: actions/checkout@v4
  with:
    fetch-depth: 0

- name: Build PR diff
  run: git diff --unified=0 "origin/${{ github.base_ref }}" HEAD > agentreview.diff

- name: Run AgentReviewOps composite action
  uses: Shen-3/agentreviewops/examples/github-action@main
  with:
    diff-file: agentreview.diff
    config: .agentreview.yml
    output: agentreview-report.md
```

The composite action installs AgentReviewOps from its own `$GITHUB_ACTION_PATH`, not from the consuming repository, then runs `agentreview scan-diff`.

To also submit the analysis to a self-hosted dashboard, pass the optional API inputs:

```yaml
- name: Run AgentReviewOps composite action
  uses: Shen-3/agentreviewops/examples/github-action@main
  with:
    diff-file: agentreview.diff
    config: .agentreview.yml
    output: agentreview-report.md
    api-url: ${{ vars.AGENTREVIEW_API_URL }}
    api-key: ${{ secrets.AGENTREVIEW_API_KEY }}
    repository: ${{ github.repository }}
    pr-number: ${{ github.event.pull_request.number }}
    title: ${{ github.event.pull_request.title }}
    author: ${{ github.actor }}
    branch: ${{ github.head_ref }}
    github-comment: "true"
    github-token: ${{ github.token }}
```

## PR Comments

`agentreview comment-pr` posts or updates one AgentReviewOps PR comment using a hidden marker, so repeated workflow runs update the prior comment instead of adding duplicate review packets.

Use `agentreview scan-pr --comment` when you want the CLI to fetch the diff, generate the report, and publish the PR comment in one command.

## Report Handling

Use `actions/upload-artifact@v4` to retain `agentreview-report.md` for human review. Use `agentreview submit-diff` when you want the same analysis stored in the dashboard.
