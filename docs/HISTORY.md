# Development and review history

Threshold was developed locally and imported into this public repository.
Its Git history records publication and later maintenance, rather than every
original implementation step. AI assistance was used for source inspection,
documentation, and maintenance. This history does not attribute unsupported
individual contributions or claim customer deployments.

## Earlier local review

The original review reported 53 passing tests, 88% statement coverage, migration
and seeding checks, a frontend build, and browser interactions. The database was
PGlite's WebAssembly PostgreSQL engine exposed through a socket server; the local
frontend build used Node 24.

That environment did not verify native PostgreSQL concurrency, Docker/nginx,
Redis/Celery transport, process-kill recovery, or live model/provider APIs.
The project subsequently gained additional SaaS and provider code, so those
counts describe the earlier review only.

The original [review report](https://github.com/mark-owa/threshold/blob/99d6d033e41c66722172e59da59bb83d1d2d379c/REVIEW.md)
is preserved in Git history.

## 2026-09-16: documentation and fixture review

A presentation pass added the business case, demo script, architecture illustration,
and verification ledger. It reported parsing 53 Python files and checking
12 base classification fixtures, 8 adversarial-wording fixtures, and 5 extraction
fixtures against deterministic helpers.

These were fixture and syntax checks, not database, HTTP, browser, or live-model
tests. The then-pending publication and capture checklist has since been superseded.

## 2026-09-18 to 2026-09-19: staging reports and demo media

[Staging milestones](STAGING_MILESTONES.md) retain reported deployment, mock
execution, and Redis-interruption observations for the separate M8 runtime.
Incomplete milestone exit criteria remain visible.

The September 19 [capture evidence](assets/demo/capture-evidence.json) and its
successful Actions run support the committed demo screenshots and approval GIF.
That recording used mock payments and manual retry.

## 2026-09-29: source merge and frontend restructure

The dashboard was separated into an application shell, typed API helper, workspace
data/actions, navigation, and view components. The current file layout is documented
in [frontend/README](../frontend/README.md).

Earlier offline checks used handwritten React type stubs and isolated fixtures.
They do not establish compatibility with the real React types or current browser
behavior. The old verification notes also described `steps.py` and
`refund_rules.py`; those modules are absent from the committed source and are not
claimed as completed refactors.

## Hosted verification and current status

The September 29 CI run at `12bf94a` passed. The October 1 run at `99d6d03`
passed tests and frontend checks but failed the Python dependency audit.
[VERIFICATION](VERIFICATION.md) links the runs and explains their scope.

The packaging notes `CHANGES.md` and `MERGE_NOTE.md` were removed from main before
this documentation cleanup. Earlier versions remain available in Git history.

## 2026-10-01: current source import

The owner supplied `Threshold (4)(2).zip` as the intended GitHub version. It replaces
the canonical dashboard with React Router/TanStack Query pages and adds the optional
n8n/HubSpot final-outcome bridge. Existing license, billing timestamp migration,
regression tests, historical demo media, and deployment tooling are retained.
Documentation cleanup is reconciled with the imported implementation.

The M8 archive remains a separate historical deployment path. Importing canonical
source does not update that frozen runtime or establish current staging health.
The supplied September 30 packaging report is summarized in
[IMPORT_REPORT](IMPORT_REPORT.md); current verification is in
[VERIFICATION](VERIFICATION.md).
