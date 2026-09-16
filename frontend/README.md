# Threshold Dashboard

React + TypeScript + Vite operator dashboard for the Threshold API.

## Local development

```bash
npm ci
npm run dev
```

Use `VITE_API_URL=http://localhost:8000 npm run dev` when running Vite locally.
The Docker dashboard uses the nginx same-origin proxy instead.

The dashboard currently focuses on the operator's most useful views:

- authentication
- workflow metrics
- pending approval queue
- execution inspection
- per-step outputs and latency

The UI intentionally exposes the deterministic/AI boundary rather than presenting the system as an autonomous black box.
