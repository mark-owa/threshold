> Historical report. Statements, test counts, environment limits, and next steps
> describe the milestone or review recorded below. Current implementation and
> evidence are in [Scope](../SCOPE.md) and [Verification](../VERIFICATION.md).

# Source import history

The source supplied on October 1, 2026 was assembled on September 30 from a frontend
overhaul and an n8n bridge. Its bundled report stated that 73 frontend files were
preserved and 45 frontend API paths matched OpenAPI paths. Those are historical
packaging checks, not current browser or response-schema verification.

The supplied report recorded 96 passing backend tests and 41 PostgreSQL setup
errors. It reported successful lint, Mypy, frontend type/build checks, template
checks, and deterministic evaluation. It did not verify a running Compose stack,
authenticated browser navigation, or real n8n/HubSpot delivery.

The GitHub import retains the existing billing timestamp migration, license,
regression tests, historical media, and deployment tooling. Current canonical
source is under `backend/` and `frontend/`; `deploy/m8/` remains a historical frozen
runtime and does not automatically consume those sources.

Two existing workflow safeguards are retained: an open circuit defers manual
retry, and a disabled mock integration blocks execution rather than being replaced
with a new enabled integration. The existing lifecycle regression covers both.

The prior dashboard files are replaced by the routed frontend. Old capture
automation is removed because it targets the previous dashboard; its recordings
and original source remain available in Git history.

Current commands are in the root [README](../../README.md), n8n configuration is in
[N8N_INTEGRATION](../N8N_INTEGRATION.md), and dated results are in
[VERIFICATION](../VERIFICATION.md).
