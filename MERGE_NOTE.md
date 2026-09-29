# Merge note

This package combines the full `Threshold (3)(20260929-142243)` project with the
`threshold_fixes_batch3_frontend` refactor bundle.

- Full backend, migrations, tests, Docker/Compose, scripts, and infrastructure are retained.
- The frontend refactor bundle is overlaid, including the split React source tree,
  updated frontend documentation, change log, and updated verification ledger.
- Relative frontend imports were checked after merge: no missing relative imports found.
- A full `npm ci && npm run build` was attempted in the packaging environment but
  dependency installation timed out, so a production frontend build is not claimed here.

Before publishing or deploying, run the repository's normal test/lint/build commands
on a machine with working dependency access.
