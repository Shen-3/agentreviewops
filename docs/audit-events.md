# Audit Events

AgentReviewOps records organization-scoped audit events for governance actions.

Current write events:

- `organization.bootstrapped`
- `api_key.created`
- `api_key.revoked`
- `policy.created`
- `analysis.created`

Protected endpoint:

```text
GET /api/audit-events
GET /api/audit-events/export
```

Supported query parameters:

- `limit`
- `action`
- `target_type`
- `target_id`
- `actor_type`
- `since`
- `until`

All audit reads are scoped to the authenticated API key's organization. Normal API keys cannot read global audit events.

Audit metadata is summary-only. It is sanitized before storage and must not contain raw diffs, Markdown reports, API key secrets, key hashes, full policy config, LLM prompts, or LLM outputs.

Example:

```bash
curl -H "Authorization: Bearer $AGENTREVIEW_API_KEY" \
  "http://127.0.0.1:8000/api/audit-events?action=analysis.created&limit=20"
```

## Export

`GET /api/audit-events/export` accepts the same filters and returns attachment-ready JSON or CSV:

```bash
curl -H "Authorization: Bearer $AGENTREVIEW_API_KEY" \
  "http://127.0.0.1:8000/api/audit-events/export?format=csv&action=policy.created" \
  -o agentreview-audit-events.csv
```

CSV exports use stable columns and store sanitized metadata as compact JSON in the `metadata` column.
