# Threshold dashboard

React 19 + TypeScript + Vite. Talks to the FastAPI backend under `/api/v1`.

```bash
npm ci
npm run dev        # http://localhost:5173 (set VITE_API_URL if the API is on another origin)
npm run typecheck  # strict tsc, no emit
npm run build      # typecheck + production build
```

## Configuration

| Variable | Purpose |
| --- | --- |
| `VITE_API_URL` | API origin. Leave empty to use same-origin (the nginx image proxies `/api`). |
| `VITE_SHOW_DEMO_CREDENTIALS` | `true` shows a "Fill credentials" helper for the seeded demo user. On in `npm run dev` and the local `docker-compose.yml`; **off** in production builds. |

## Structure

```
src/
  app/         router (App.tsx) and providers
  api/         client.ts is the only place that calls fetch; one module per API area
  types/       API types mirroring backend responses and enums
  hooks/       react-query reads (queries.ts) and mutations with toasts (mutations.ts)
  features/    auth session + domain components (executions, integrations)
  components/  ui primitives (Button, Dialog, Fields, Badge, Menu, JsonViewer, Toast…)
  layouts/     AppShell, Sidebar, AuthLayout, nav config
  pages/       one file per route
  utils/       formatting and the status/step vocabulary
  styles/      design tokens + CSS
```

## Conventions

- **Workspace scoping.** Workspace query keys include the organization ID. Mutations
  invalidate that workspace's queries. The API enforces tenant access; cache keys are
  a UI isolation mechanism, not an authorization boundary.
- **Roles.** `useWorkspace()` exposes `canManage` (owner/admin) and `canReview`
  (owner/admin/reviewer), mirroring the checks the API enforces. The UI hides or disables
  controls; the backend remains the authority.
- **Statuses** come from `utils/status.ts`. Labels are the backend enum value, humanised;
  the UI never renames or reinterprets a state.
- **No fabricated data.** Where the API doesn't expose something (per-step timestamps, an
  events list, workflow editing), the UI says so instead of inventing it.
- **Sessions.** The access token lives in `sessionStorage` (per tab) and is never rendered.
  There is no refresh flow in the API, so an expired or rejected token signs the user out
  with a notice and returns them to the page they asked for after signing in.
- Dialogs and drawers use the native `<dialog>` element (focus trap, Escape, focus return).
