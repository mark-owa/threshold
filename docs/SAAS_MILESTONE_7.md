# SaaS Milestone 7 — Production and Security Hardening

Milestone 7 freezes feature expansion and hardens the private-beta boundary.

## Activated protections

- Redis-backed fixed-window rate limits for API, auth, and webhook endpoints.
- Request body ceiling (`MAX_REQUEST_BODY_BYTES`) plus Nginx `client_max_body_size`.
- Security response headers, HSTS in staging/production, and no-store auth responses.
- JWT issuer, audience, iat, nbf, and jti validation in addition to expiry and subject.
- Production startup rejects weak runtime secrets, wildcard CORS, and non-HTTPS public app URLs.
- Stripe billing webhook receipts are transactionally deduplicated by provider/event id and payload hash.
- Shopify OAuth state uses a persisted single-use nonce in addition to signed/expiring state.
- Backend production container installs production dependencies only and runs as a non-root user.
- CI runs migrations, tests with a coverage floor, Python dependency audit, npm audit, frontend build, and Compose validation.
- Backup, catalog verification, and isolated restore-drill scripts are present.
- Production preflight rejects development secrets/configuration before Compose launch.

## Important topology assumption

`TRUST_PROXY_HEADERS=true` is safe only when the backend is not directly exposed and the trusted reverse proxy overwrites `X-Real-IP`. The supplied production Compose follows this topology: only Nginx publishes a host port; the backend remains on the internal Compose network.

## Remaining private-beta requirements

Code hardening does not substitute for operational proof. Before real customer money or personal data is enabled, run the full CI suite with PostgreSQL/Redis/Celery, validate live Stripe test-mode and Shopify development-store flows, connect a real secret manager, configure TLS at the ingress/load balancer, perform backup restore drills, and establish alerting/on-call ownership.
