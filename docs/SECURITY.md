# Security and trust boundaries

All demo and operator routes require a JWT. Organization membership scopes access
to business records; owner/admin/reviewer roles are required for decisions and
manual retries. Tokens are short-lived HS256 access tokens, with bcrypt password
hashing. There is no refresh or user-registration endpoint.

Incoming text and provider output are untrusted. Pydantic constrains provider
results; deterministic code controls policy and validates refund parameters before
mock execution, including after a reviewer modification. This does not prove that
a model extracted the right facts from the text or that the sender owns the order.
The demo is an operator tool, not a public customer refund endpoint.

`signature_verified` remains false for demo ingestion: no webhook signature was
checked. HMAC verification, API-key issuance, rate limiting, and payload-size
limits are not implemented. Schema support and unused configuration fields for
future features do not mean those protections are active.

Audit rows are appended by application code, but the database does not enforce
immutability. Raw requests and audit payloads can contain customer data, so use
fictional inputs for demonstrations. The coarse task-state endpoint requires
login but has no task-to-tenant ownership mapping; it returns only task ID/state.

`.env` and variants are ignored; `.env.example` and seeded credentials are public
local-demo placeholders. Never expose the default Compose setup to the internet.
It has no TLS and includes development tooling. Real deployment would require
strong secrets, restricted network exposure, and additional operational controls.
