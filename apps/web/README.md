# AgentReviewOps Web Dashboard

This is a React + TypeScript + Vite dashboard for analysis runs, organization API keys, and audit events.

Run it locally from the repository root:

```bash
pnpm install
pnpm --filter agentreviewops-web dev
```

Then open the Vite URL, normally `http://127.0.0.1:5173`.

The app stores an AgentReviewOps API key in the browser and sends it as a Bearer token for live API data. Use session-only mode on shared machines, browser storage only on trusted devices, and clear the key when finished. Without a key, it falls back to demo data. With a live key, it reads `/api/auth/me` and disables mutation controls that the key role cannot use. Full OAuth or GitHub App browser auth is future work. It includes diff submission, analysis list, analysis detail, risk badge, findings table, report preview, user management with role updates, repository onboarding with reviewer routing assignment and role updates, organization and repository policy assignment, role-scoped API key management, audit history with action filtering and JSON/CSV export, and loading/error/empty states.
