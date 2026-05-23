# GitHub Action Usage

AgentReviewOps can run in GitHub Actions today by scanning a prepared unified diff and uploading the generated Markdown report as an artifact.

The project does not yet post PR comments or fetch pull request diffs through the GitHub API. Those capabilities are planned after the local CLI workflow is stable.

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

      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: agentreview-report
          path: agentreview-report.md
```

## Composite Action Example

This repository also includes a local composite action at `examples/github-action/action.yml`.

After checking out the repository and preparing `agentreview.diff`, call it with:

```yaml
- name: Run AgentReviewOps composite action
  uses: ./examples/github-action
  with:
    diff-file: agentreview.diff
    config: .agentreview.example.yml
    output: agentreview-report.md
```

The composite action installs AgentReviewOps from the checked-out repository and runs `agentreview scan-diff`.

## Report Handling

Use `actions/upload-artifact@v4` to retain `agentreview-report.md` for human review. A later GitHub PR integration can add direct PR comments once the project has token handling and API tests.
