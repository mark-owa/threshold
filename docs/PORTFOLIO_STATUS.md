# Project status

Updated on **2026-10-01** for the owner-supplied frontend/n8n source import.

## Available

- FastAPI/PostgreSQL refund workflow, policy checks, and operator review.
- Routed React/TypeScript dashboard with TanStack Query and typed API calls.
- Signed webhook intake and optional n8n/HubSpot final-outcome bridge.
- Existing billing timestamp migration, regression tests, and CI: 162 tests passed
  on PostgreSQL 16 in the candidate import run, with 72.29% coverage.
- Historical September 19 screenshots/GIF with source and capture evidence.
- Documentation distinguishing mock behavior, source mechanisms, and verified results.

## Outstanding

| Work | Status |
| --- | --- |
| Python dependency audit | PyJWT 2.13.0 still reports 13 findings; remediation pending. |
| Current dashboard captures | Historical media predates the imported routed dashboard. |
| Permanent narrated walkthrough | No permanent full-video link is committed. |
| M8 runtime consolidation | Historical archive/overlays remain separate from canonical source. |
| Workflow engine structure | Policy, steps, actions, and recovery remain in `engine.py`. |
| n8n/provider/operations proof | Real-account delivery and interruption/restore/alert drills remain pending. |

[VERIFICATION](VERIFICATION.md) records check results and their environment.
No customer deployment or measured business outcome is claimed.
