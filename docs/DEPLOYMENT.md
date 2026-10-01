# Local deployment

1. Copy `.env.example` to `.env`. Set a strong `SECRET_KEY` and `WEBHOOK_SIGNING_SECRET` for staging/production-like environments.
2. Run `docker compose up -d --build`.
3. Run `make migrate`.
4. Run `make seed` and `make seed-prompts`.
5. Open `http://localhost:5173` for the operator dashboard.
6. Use `make seed-history` to create realistic execution history.
7. Use `make test` for the PostgreSQL-backed test suite and `make eval` for deterministic AI-boundary evaluation.
8. Set `AI_PROVIDER=openai` or `AI_PROVIDER=anthropic` with a corresponding secret, then use `make eval-live` to compare provider-backed behavior with the deterministic baseline.

The frontend nginx container proxies `/api/*`, `/docs`, and `/openapi.json` to the backend service, keeping the browser on one origin in the Docker demo environment.

## Build sources

Local Compose selects `backend/Dockerfile.dev`; production Compose selects the
runtime-only backend image. Both build canonical `backend/` and `frontend/` source.

`deploy/m8/` is a legacy deployment snapshot retained for compatibility with the
previous staging setup. Its image extracts an archive and applies overlays. It
does not include subsequent canonical source changes, and current CI does not
build it. Treat a deployment from that directory as a different runtime until it
has been consolidated and verified. [Historical records](history/README.md) explain
the earlier staging observations.
