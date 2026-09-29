# Threshold -- batch 3 (frontend restructure)

Overwrite the matching paths. `frontend/src/styles.css` is untouched and not included.
`frontend/src/main.tsx` is REPLACED (915 lines -> 6); its contents now live in the new files.

## What changed
`main.tsx` was one 915-line file: an `App()` with 34 `useState` calls, 26 inline
handlers, and every API value typed `any`. It is now:

| File | Lines | Role |
|---|---|---|
| main.tsx | 6 | mounts <App /> |
| App.tsx | 242 | session + navigation state (10 useState), composes views |
| types.ts | ~390 | types for every API response/request body, from the backend serializers |
| api.ts | 47 | fetch helper, `parseResponse` (discriminated union) |
| workspaceData.ts | 115 | loads the 15 workspace slices into ONE `WorkspaceData` object |
| workspaceActions.ts | ~370 | all operational handlers; 11 of them share one `mutate()` |
| nav.ts | 44 | tab names/titles |
| components/*.tsx | 15 files | one per view; AuthScreen / CreateWorkspacePanel own their form state |

Also added `frontend/tsconfig.json` (strict) -- there was none, so nothing was ever
type-checked. `any` is gone from the application code; `parseResponse` is now a
discriminated union, so reading a response body without checking `ok` is a compile error.

## Deliberate behavior differences (everything else is unchanged)
1. Sign-in form fields now reset after sign-out (previously the typed email AND
   password stayed in memory in App state).
2. Login failures now show the API's message ("Invalid credentials") instead of a
   generic "Login failed (401)." (already true of batch 1's helper for other handlers).
3. Shopify "Sync order now": the "Synced #... Remaining refundable amount" message is now
   actually visible. Before, refresh() immediately overwrote it with "Workspace refreshed."
4. Removed a no-op line in the live-execution error path (`setBetaReadiness(c => ({...c,
   checks: c.checks}))` re-set state to identical content).
5. Closing the "New workspace" panel now discards half-typed fields (they used to persist
   in App state across open/close).
6. Typing in a form no longer re-renders the whole dashboard (state is local to the form).

## NOT included: package.json changes
`tsc` needs `@types/react` and `@types/react-dom` (React 19 ships no types). I did not add
them because the Dockerfile runs `npm ci`, which fails if package.json and
package-lock.json disagree, and I cannot regenerate the lockfile offline. On your machine:

    cd frontend
    npm install --save-dev @types/react @types/react-dom
    npx tsc --noEmit

Commit both package.json and package-lock.json. Expect the first real run to possibly
surface a few type errors my stub-based check could not (see below).

## How this was verified (no network, no Vite, no browser available)
- `tsc --noEmit`, strict mode, whole tree: 0 errors -- using hand-written stubs for
  react/react-dom that model change events like @types/react. Four planted bugs (wrong
  prop type, misspelled API field, bad enum literal, reading a body without `ok` check)
  were all rejected.
- 32 fixture renders of the 13 view components through BOTH the original and the new
  code, with real React 19.2.5 + a real esbuild: HTML identical byte for byte. Also
  rendered AuthScreen, CreateWorkspacePanel, and App (signed out). A planted missing
  `React` import was caught ("React is not defined"), which matters because this project has
  no vite.config, so JSX uses the classic transform and every .tsx file needs the import.
  (tsc did not catch that on its own.)
- 36 logic checks against a mocked API: parseResponse, the 15-request loader (403/500/401
  handling), and each action group (URLs, methods, bodies, status-message order, no-throw
  on network failure, demo-only guard, redirect handling).
- The real entry point bundles for the browser (esbuild, minified): 252 KB JS + CSS.

## NOT verified
- `npm ci && npm run build` with your real dependency tree (Vite 8, React 19.3).
- Anything in a real browser: layout, styling, click-through of each tab, redirects.
- Type-correctness against the real @types/react.
Do a build and click through every tab before relying on this.
