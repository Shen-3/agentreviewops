# AgentReviewOps Web Dashboard

This is a React + TypeScript + Vite read-only dashboard for analysis runs.

Run it locally:

```bash
npm install
npm run dev
```

Then open the Vite URL, normally `http://127.0.0.1:5173`.

The app stores an AgentReviewOps API key locally when supplied and sends it as a Bearer token for live API data. Without a key, it falls back to demo data. It includes the Request 11 views: analysis list, analysis detail, risk badge, findings table, report preview, and loading/error/empty states.
