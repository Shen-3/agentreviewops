# Security Policy

## Supported Versions

AgentReviewOps is preparing for a self-hosted open-source v0 release. Until a stable v0 tag exists, security fixes target the default branch and the next tagged v0 release.

## Reporting Vulnerabilities

Please use GitHub Security Advisories for private vulnerability reports. Do not open public issues for suspected vulnerabilities that include exploit details or secrets.

## Security Expectations

AgentReviewOps handles diffs, reports, SARIF, API keys, GitHub tokens, and optional OpenAI-compatible provider keys. Tokens and API keys must not be committed, logged, copied into reports, or echoed from workflows. Created AgentReviewOps API keys are returned once and stored only as hashes.

Self-hosted operators are responsible for database access, TLS termination, network exposure, backup handling, and least-privilege API key issuance.

External analyzer plugins execute untrusted code risk. v0 isolates package-discovered plugins in a child process with a timeout and stripped environment, but this is not a full OS sandbox. Run only plugins you trust and do not give plugins secrets.

For GitHub Actions, prefer `pull_request` for untrusted external pull requests. Do not use `pull_request_target` with write tokens or repository secrets unless you fully understand the fork PR risk.
