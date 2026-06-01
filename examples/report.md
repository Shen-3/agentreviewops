# AgentReviewOps Report: HIGH risk (55/100)

## Merge recommendation

Human review required before merge.

## Why this requires attention

1 file(s) changed with 4 positive risk finding(s). The highest deterministic finding severity is HIGH; review the listed risk areas before merge.

## Findings table

| Severity | Rule | Score | File | Reason |
|---|---|---:|---|---|
| HIGH | critical-path-change | +20 | auth/session.py | auth/session.py matches a configured critical path. |
| HIGH | sensitive-area-change | +20 | auth/session.py | auth/session.py is in auth, security, or payments code. |
| MEDIUM | missing-tests | +15 | Change set | At least one source file changed, but no test files changed. |
| LOW | missing-docs | +5 | Change set | Source files changed without accompanying documentation updates. |
| INFO | small-focused-diff | -5 | Change set | Only one file changed and the diff is within the small-change threshold. |

## Changed files summary

| File | Status | + | - | Critical | Test |
|---|---|---:|---:|---|---|
| auth/session.py | modified | 3 | 1 | yes | no |

## Suggested human review checklist

- [ ] Verify adequate tests were added, or document why tests are not required.
- [ ] Get security or code owner review for the sensitive or critical-path changes.

## Policy Config Used

- Version: 1
- Fail level: high
- Large diff threshold: 20 files / 800 lines
- Critical paths: 10 configured
- Test patterns: tests/**, **/*test*, **/*spec*
- Enabled rules: require_tests_for_code_changes, flag_dependency_changes, flag_ci_changes, flag_auth_changes, flag_large_generated_files
