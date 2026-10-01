# Technical decisions

| Choice | Reason | Tradeoff |
| --- | --- | --- |
| Python policy checks after AI extraction | Refund authority depends on the order, amount, policy, and reviewer role. | Model output can fail validation; a confidence score does not authorize execution. |
| Synchronous demo, queued external actions | Mock scenarios return an inspectable result immediately. Persisted webhook intake and external intents use an outbox. | Demo requests wait for their steps. Manual retry still calls the provider directly; it needs separate live-path review. |
| Synchronous SQLAlchemy | The API and workers share a straightforward session model. | Database/provider latency can occupy a worker or request thread. |
| Policy rows with JSON rules | Refund thresholds and windows need direct lookup. | New policy behavior still needs Python support. |
| Ordered workflow and step records | Inputs, outputs, failures, and timing can be inspected per execution. | Approval continuation targets the refund flow; arbitrary mid-step restart is not implemented. |
| Event keys and action keys | Request delivery and business-action reuse have different identities. | Keys do not form a complete payment ledger or prove external exactly-once effects. |
| Outbox and provider reconciliation | Intent is persisted before worker delivery; ambiguous outcomes require inspection. | Database commits and external APIs cannot become one atomic transaction. |
| Signed n8n final outcomes | CRM receives the final result without executing the refund itself. | Delivery is at least once; the receiver needs duplicate-tolerant downstream automation. |
| Organization-scoped query keys | Dashboard reads and invalidation follow the selected workspace. | API authorization remains essential; a cache key is not an access-control mechanism. |
| Per-tab sessionStorage | Reload preserves the tab session and rejected/expired tokens clear it. | Browser script access remains possible; there is no refresh-token flow. |
| Direct backend pins and npm lockfile | Dependency changes are visible and frontend installs are reproducible. | Python transitive dependencies are not fully locked, and the current PyJWT pin fails audit. |

The canonical application is `backend/` plus `frontend/`. The legacy M8 image uses
a frozen runtime and overlays. See [Deployment](DEPLOYMENT.md) for that separation
and [Verification](VERIFICATION.md) for observed behavior.
