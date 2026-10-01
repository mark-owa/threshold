# Threshold Dashboard

React + TypeScript + Vite operator dashboard for the Threshold API.

## Local development

```bash
npm ci
npm run dev
```

Use `VITE_API_URL=http://localhost:8000 npm run dev` when running Vite locally.
The Docker dashboard uses the nginx same-origin proxy instead.

The dashboard covers: sign-in/registration/invitations, workflow metrics, the approval
queue, execution inspection (per-step inputs, outputs, latency), external actions and
recovery, refund policy and integration settings, team management, billing and usage,
and the private-beta launch gate.

The UI intentionally exposes the deterministic/AI boundary rather than presenting the system as an autonomous black box.

## Source layout

| File | Responsibility |
|---|---|
| `src/main.tsx` | Mounts `<App />` |
| `src/App.tsx` | Session and navigation state; composes the views |
| `src/types.ts` | Types for every API response and request body the dashboard uses |
| `src/api.ts` | Authenticated `fetch` helper and `parseResponse` |
| `src/workspaceData.ts` | Loads everything shown for one workspace into a single `WorkspaceData` object |
| `src/workspaceActions.ts` | Every operational action (approve, retry, save settings, invite, ...) |
| `src/nav.ts` | Tab names and titles |
| `src/components/` | One file per view, plus `AuthScreen` and `CreateWorkspacePanel`, which own their own form state |

`parseResponse` returns a discriminated union intended to require checking `ok`
before using the response body. That protection needs a real TypeScript type-check;
the current Vite build does not enforce it. API types are compile-time declarations,
and responses are not validated at runtime.

## Type-checking

`npm run build` runs Vite, which strips types without checking them, so a type error
does not fail the build. A `tsconfig.json` (strict mode) is included, but React 19 ships
no type declarations, so a one-time setup is needed before `tsc` can run:

```bash
npm install --save-dev @types/react @types/react-dom
npx tsc --noEmit
```

The first command updates `package.json` and `package-lock.json`; commit both (the
Docker build uses `npm ci`, which requires them to agree). Adding
`"typecheck": "tsc --noEmit"` to `scripts` and running it in CI is the natural next step.
