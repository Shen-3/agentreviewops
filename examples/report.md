# AgentReviewOps Report

Risk: HIGH (55/100)

## Summary

1 file(s) changed with 4 positive risk finding(s). Review the HIGH risk areas before merge.

## Findings

| Severity | Rule | File | Reason |
|---|---|---|---|
| HIGH | critical-path-change | auth/session.py | auth/session.py matches a configured critical path. Score +20. |
| HIGH | sensitive-area-change | auth/session.py | auth/session.py is in auth, security, or payments code. Score +20. |
| MEDIUM | missing-tests | Change set | At least one source file changed, but no test files changed. Score +15. |
| LOW | missing-docs | Change set | Source files changed without accompanying documentation updates. Score +5. |
| INFO | small-focused-diff | Change set | Only one file changed and the diff is within the small-change threshold. Score -5. |

## Human Review Checklist

- [ ] Verify critical-path changes are intentional and scoped.
- [ ] Review auth, security, or payments behavior with a human owner.
- [ ] Require tests for changed behavior or document why tests are not needed.
- [ ] Confirm whether behavior changes require documentation updates.

## Changed Files

| File | Status | + | - | Critical | Test |
|---|---|---:|---:|---|---|
| auth/session.py | modified | 3 | 1 | yes | no |

## Policy Config Used

- Version: 1
- Fail level: high
- Large diff threshold: 20 files / 800 lines
- Critical paths: 10 configured
- Test patterns: tests/**, **/*test*, **/*spec*
- Enabled rules: require_tests_for_code_changes, flag_dependency_changes, flag_ci_changes, flag_auth_changes, flag_large_generated_files
