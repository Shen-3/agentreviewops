# GitHub Action Usage

AgentReviewOps can run in GitHub Actions by scanning a prepared unified diff, uploading the generated Markdown report as an artifact, and optionally submitting the diff to a self-hosted AgentReviewOps API so it appears in the dashboard.

The project does not yet post PR comments. Keep API keys in GitHub Secrets and pass them through environment variables, not inline command output.

## Basic PR Workflow

Create a workflow such as `.github/workflows/agentreview.yml`:

```yaml
name: AgentReviewOps

"on":
  pull_request:

permissions:
  contents: read

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

      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: agentreview-report
          path: agentreview-report.md
```

## Composite Action Example

This repository also includes a local composite action at `examples/github-action/action.yml`.

After checking out the repository and preparing `agentreview.diff`, call it with artifact-only output:

```yaml
- name: Run AgentReviewOps composite action
  uses: ./examples/github-action
  with:
    diff-file: agentreview.diff
    config: .agentreview.example.yml
    output: agentreview-report.md
```

The composite action installs AgentReviewOps from the checked-out repository and runs `agentreview scan-diff`.

To also submit the analysis to a self-hosted dashboard, pass the optional API inputs:

```yaml
- name: Run AgentReviewOps composite action
  uses: ./examples/github-action
  with:
    diff-file: agentreview.diff
    config: .agentreview.example.yml
    output: agentreview-report.md
    api-url: ${{ vars.AGENTREVIEW_API_URL }}
    api-key: ${{ secrets.AGENTREVIEW_API_KEY }}
    repository: ${{ github.repository }}
    pr-number: ${{ github.event.pull_request.number }}
    title: ${{ github.event.pull_request.title }}
    author: ${{ github.actor }}
    branch: ${{ github.head_ref }}
```

## Report Handling

Use `actions/upload-artifact@v4` to retain `agentreview-report.md` for human review. Use `agentreview submit-diff` when you want the same analysis stored in the dashboard. A later GitHub PR integration can add direct PR comments.
