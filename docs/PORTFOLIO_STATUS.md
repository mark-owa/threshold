# Project status

Reviewed on **2026-10-01** against source commit `99d6d03`.

## Available

- A local FastAPI/PostgreSQL refund demo with a React operator dashboard.
- Source, schema migrations, regression tests, deterministic evaluations, and CI.
- [Recorded screenshots and approval GIF](DEMO.md#existing-media) from September 19,
  with a source commit and machine-readable capture evidence.
- A business case that identifies the fictional data and mock effects.
- Architecture and reliability documentation covering demo and provider paths.

The root README now shows the existing media, names the actual source files, and
links dated verification evidence. Historical review and packaging instructions
are summarized in [HISTORY](HISTORY.md), rather than used as current project claims.
The existing deletions of `CHANGES.md` and `MERGE_NOTE.md` are preserved.

## Outstanding

| Work | Status |
| --- | --- |
| Python dependency audit | The October 1 run failed on PyJWT findings; remediation is pending. |
| Current dashboard captures | Existing media predates the latest dashboard; recapture pending. |
| Permanent narrated walkthrough | No permanent full-video link is committed. |
| TypeScript checking | Vite build passes; a real React type-check gate is not configured. |
| M8 deployment consolidation | Frozen runtime plus build overlays remain; current CI does not build that image. |
| Workflow engine structure | Policy, steps, actions, and recovery remain in `engine.py`. |
| Personal contribution detail | This repository acknowledges AI assistance; a more detailed owner-authored account is not inferred from the archive. |
| Provider and operations proof | Test-account flows and complete interruption/restore/alert drills remain subject to the documented evidence gaps. |

[VERIFICATION](VERIFICATION.md) distinguishes current source checks, hosted results,
recorded demo behavior, and historical staging reports. No customer deployment or
measured business outcome is claimed.
