# Historical reports

These documents record earlier milestones, packaging reviews, and staging observations.
Their test counts and environment limitations apply to those records. Use
[Scope](../SCOPE.md), [Architecture](../ARCHITECTURE.md), and
[Verification](../VERIFICATION.md) for the current application.

| Record | Context |
| --- | --- |
| [SaaS build](SAAS_BUILD.md) | Workspaces, teams, and policies at Milestone 2. |
| [Milestone 3](SAAS_MILESTONE_3.md) | External-provider boundaries and reconciliation. |
| [Milestone 4](SAAS_MILESTONE_4.md) | Durable intake, action intents, and outbox. |
| [Milestone 5](SAAS_MILESTONE_5.md) | Shopify/Stripe ecommerce adapters. |
| [Milestone 6](SAAS_MILESTONE_6.md) | Trial, billing, and usage scaffolding. |
| [Milestone 7](SAAS_MILESTONE_7.md) | HTTP, authentication, and container hardening. |
| [Beta readiness report](BETA_READINESS_REPORT.md) | Earlier container-limited review. |
| [Frontend audit](FRONTEND_AUDIT.md) | Pre-overhaul findings and reported browser checks. |
| [Source import](IMPORT_REPORT.md) | September 30 archive and October 1 import. |
| [n8n inventory](N8N_CHANGED_FILES.md) | Archive merge inventory. |
| [n8n verification](N8N_VERIFICATION.md) | September 30 packaging checks. |
| [Staging milestones](STAGING_MILESTONES.md) | September M8 snapshot deployment reports. |

The separate `deploy/m8/` runtime is retained for deployment compatibility. Its
archive and overlays do not consume current `backend/` or `frontend/` source.
The dated staging observations do not establish current service health.
