# Development history

Threshold was developed locally and imported into this public repository. The Git
history records source imports and later maintenance. AI assistance was used for
source inspection, documentation, and maintenance. No customer deployment or
measured business outcome is inferred from that history.

| Period | Record |
| --- | --- |
| Earlier prototype | A local review reported 53 tests and 88% coverage using PGlite. It did not prove native PostgreSQL concurrency or Celery transport. The [original report](https://github.com/mark-owa/threshold/blob/99d6d033e41c66722172e59da59bb83d1d2d379c/REVIEW.md) remains in Git history. |
| September milestones | Workspaces, providers, delivery, billing, and hardening were added incrementally. [Milestone reports](history/README.md) retain their original scope and environment limitations. |
| September 18–19 | A separate M8 runtime was used for staging observations. The [staging report](history/STAGING_MILESTONES.md) includes incomplete exit criteria. |
| September 19 | A mock Docker demo was recorded with manual recovery. Its screenshots, GIF, and evidence remain under `docs/assets/demo/`. |
| October 1 | Canonical source gained the routed React dashboard and optional n8n/HubSpot final-outcome bridge. Existing billing migration and regression safeguards were retained. |

[Verification](VERIFICATION.md) records dated results for particular source versions.
[Scope](SCOPE.md) describes the current implementation. Historical environment
restrictions and deferred-feature lists do not describe the current application.
