# Frontend audit (pre-overhaul)

This audit was written before the dashboard was restructured. It records what
existed, what the backend supported, and the decisions that followed.
The checks below were reported with the uploaded source and were not repeated as
part of the GitHub import. Current results are in [VERIFICATION](VERIFICATION.md).

## 1. Architecture as found

- React 19 + TypeScript + Vite. **One 925-line `src/main.tsx`** containing the whole
  application, plus one 248-line `styles.css`.
- ~30 `useState` hooks in a single `App` component; a `refresh()` that fires 15
  requests in parallel on every action and swallows failures (`if (res.ok) … else set([])`).
- Navigation is a `useState<Tab>`; there is no URL routing, so nothing is linkable and
  the browser back button leaves the app.
- Almost every prop is `any`. TypeScript is installed but **there is no `tsconfig.json`**,
  so `vite build` never type-checks.
- The access token lives only in component state, so a page reload signs the user out.
- All feedback is a single `status` string rendered in a banner. No dialogs, toasts,
  skeletons, or per-page error states.

## 2. Pages that existed

Overview, Approvals, Executions (list + inspector), Actions, Recovery, Policies,
Integrations (Shopify / Stripe / generic REST / webhooks), Team, Billing & usage,
Beta readiness, Audit log, and a demo Sandbox (demo workspaces only).

## 3. Backend endpoints consumed (all preserved, none renamed)

Auth: `POST /auth/login|register|join`, `GET /auth/me`.
Organizations: `GET|POST /organizations`, members and invitations
(`GET|POST|PATCH|DELETE`).
Ops: `GET /ops/metrics|executions|executions/{id}|approvals|audit|actions|actions/{id}|recovery`,
`POST /ops/executions/{id}/retry`, `POST /ops/actions/{id}/reconcile`,
`POST /ops/events/{id}/replay`, `POST /ops/outbox/{id}/requeue`,
`GET /ops/beta-readiness`, `POST /ops/beta-readiness/live-execution`.
Approvals: `POST /approvals/{id}/decision`.
Workspace: `GET /workspace/onboarding|workflows|policies|integrations|webhook-endpoints`,
`PUT /workspace/refund-policy`, `PUT /workspace/integrations/{generic-rest|shopify|stripe}`,
`POST /workspace/shopify/orders/sync`, `POST|DELETE /workspace/webhook-endpoints`.
Commercial: `GET /commercial/status|plans`, `POST /commercial/checkout|portal`,
`GET /commercial/shopify/install`. Demo: `POST /demo/run`.

## 4. UX problems

- Dense JSON dumps (`<pre>`) as the primary way to explain an execution.
- Statuses rendered as raw enum strings with inconsistent styling.
- Approvals could only send a hard-coded note and could not use **modify-and-approve**,
  although the backend supports it (`decision: "modified"` + `modified_parameters`).
- No confirmation before approving/rejecting refunds, disabling webhooks, removing members.
- Errors reduced to "(status code)" strings; 403s were silently treated as "empty".
- Copy is written from the system's point of view ("Deterministic policy gate…").

## 5. Frontend / backend mismatches found

| Finding | Handling |
| --- | --- |
| Executions list has **no workflow name, trigger, or duration** | Joined client-side with `/workspace/workflows`; duration computed from `started_at`/`completed_at`. |
| Steps expose `latency_ms` but **no per-step timestamps or attempt numbers** | Timeline shows latency only. Attempts come from the linked action ledger (`/ops/actions/{id}`), which does record them. |
| Executions / audit endpoints have **no server-side filters or pagination** (`limit ≤ 100/200`) | Filters run client-side over the loaded window and the UI says so. |
| There is **no events-list endpoint** | No "Events" page. Failed/dead-letter events appear under Recovery, which is the only place the API exposes them. |
| Recovery lists failed events whose replay returns **409 if an execution already exists** | Replay is offered with an explanatory confirmation, and the backend's message is surfaced verbatim. |
| `estimated_hours_saved` in `/ops/metrics` is `automatic_runs × 0.25` — a fixed heuristic | Not shown as a headline metric. |
| Modified approval parameters **replace** the generated parameters wholesale (`engine.py`) | The modify form always submits the complete parameter set. |
| Stripe checkout returns to `/?billing=success|cancelled&org_id=…` | Root route preserves that query and lands on Billing. |
| Workflows are read-only in the API (no create/update) | Presented as read-only; no builder is faked. |
| Only the refund policy is editable; other policies are read-only | Others are listed read-only. |
| Local demo credentials were hard-coded into the login form's initial state | Now shown only when `VITE_SHOW_DEMO_CREDENTIALS=true` (dev + the local Docker build). |

## 6. Information architecture

```
Overview
Workflows · Executions · Approvals
Operations   Actions · Recovery · Audit log
Platform     Integrations · Webhooks · Policies · Live execution (admin)
Workspace    Team · Billing · Settings
Demo         Scenarios (demo workspaces only)
```

Only pages backed by real endpoints are present.

## 7. Structure

```
src/
  app/         router, providers, route table
  api/         client (single fetch wrapper) + one module per API area
  types/       API types shared across the app
  hooks/       react-query reads and mutations
  features/    auth session, approvals/executions domain components
  components/  ui primitives + small shared pieces
  layouts/     app shell, sidebar, topbar, auth layout
  pages/       one file per route
  utils/       formatting, status mapping
  styles/      tokens + component + layout CSS
```

## 8. Unchanged

Every backend file. Every endpoint path and payload. The Dockerfile, nginx config, and
Compose topology (one build-arg was added to pass the demo-credentials hint).

## 9. Backend defects recorded during that review

The backend was intentionally left untouched. Two defects surfaced during end-to-end testing:

1. **Billing tables lack DB defaults for timestamps.** Migration `c6f8a012d4e6` creates
   `billing_accounts` and `usage_counters` with `created_at`/`updated_at` as `NOT NULL` and no
   server default, while the ORM model relies on `server_default=now()`. On a database built by
   `alembic upgrade head`, the first workflow run in a billing period fails with a
   `NotNullViolation` on `usage_counters` (this also breaks `make seed-history`). Tests likely
   miss it because they build the schema with `create_all`. Suggested fix: a new Alembic
   migration that runs `ALTER COLUMN … SET DEFAULT now()` on those four columns.
   **Import update:** existing GitHub migration `e8b0c234f6a8` is retained to apply
   these defaults. The defect describes the earlier eight-migration upload.
2. **Non-allowlisted integration hosts return 500, not 4xx.** `validate_live_endpoint()`
   (`integrations/providers.py`) raises a bare `ValueError` ("Integration host is not
   allowlisted", "INTEGRATION_ALLOWED_HOSTS must contain the provider host", and the HTTPS
   check). The Shopify, Stripe and generic-REST `PUT` handlers don't catch it, so the most
   common misconfiguration produces an unhandled 500. Suggested fix: catch `ValueError` around
   that call and raise `HTTPException(422, detail=str(exc))`. The forms already display a
   `detail` string if the API sends one.

## 10. Verification performed

Against the real backend (PostgreSQL 16, Redis, uvicorn) using headless Chromium:
sign-in (good/bad credentials), session restore on reload, expired and server-rejected tokens,
return-to-requested-page, all 15 routes, execution detail, retry, approve / reject /
modify-and-approve (confirmed the modified amount reached the provider request payload),
integrations forms (validation, secret masking), policy save + persistence, webhook create /
disable, invite → one-time token → join as viewer, viewer permission gating, workspace
creation and switching (tenant cache isolation), 404s, the Stripe `?billing=` return, and
1440 / 1366 / 390 px layouts. Console errors were limited to deliberate 401/404 responses and
finding 2 above. Not exercised: Stripe checkout/portal (needs Stripe configured), Shopify
OAuth install, and a real Shopify/Stripe provider.
