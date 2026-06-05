# v0 readiness checklist

## Product

- [ ] README quickstart works
- [ ] `agentreview init` works
- [ ] GitHub Action local self-test passes
- [ ] Dogfooding workflow enabled

## Security

- [ ] Token logging audit complete
- [ ] Plugin sandbox hardening complete
- [ ] Fork PR threat model documented

## Testing

- [ ] Python tests pass
- [ ] Coverage threshold passes
- [ ] SQLite migration smoke passes
- [ ] PostgreSQL migration smoke passes
- [ ] Dashboard build/lint passes

## Release

- [ ] CHANGELOG updated
- [ ] SECURITY.md present
- [ ] CONTRIBUTING.md present
- [ ] LICENSE present
- [ ] Release tag plan documented

## Known limitations

- Hosted deployment is intentionally not implemented.
- GitHub App auth and OAuth are not implemented.
- External plugin sandboxing is limited to v0 child-process isolation and is not a full OS sandbox.
- Dashboard auth is API-key based.
- AgentReviewOps is not a SAST replacement.
- AgentReviewOps is not a human review replacement.
- Not all findings have line-level SARIF annotations.
