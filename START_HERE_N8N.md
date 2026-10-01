# Start here: Threshold + n8n + HubSpot

Threshold includes an optional n8n/HubSpot bridge alongside the routed dashboard.
It keeps refund policy, approvals, and action execution in Threshold. n8n submits
a request and synchronizes its final outcome to an **existing dedicated test ticket**
in HubSpot. Use fictional data and mock refunds throughout this setup.

## What to do first (Windows)

1. Open the repository root. Preserve an existing `.env` when configuring the demo.
2. Start Docker Desktop.
3. Open PowerShell in the extracted `Threshold` folder (the one containing `docker-compose.yml`).
4. Run this block. It preserves `.env` if one already exists:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.seed_demo_org
```

Open **http://localhost:5173**. For this local seeded demo, use
`owner@acme-demo.example.com` / `demo1234`. Run a low-risk mock refund before
connecting external tools. Keep public demo credentials confined to the local demo.

Then run the new integration tests against the disposable test database:

```powershell
docker compose exec backend pytest tests/test_n8n_bridge.py tests/test_n8n_http_delivery.py tests/unit/test_n8n_outcomes.py -q
```

**Next:** follow [the integration guide](docs/N8N_INTEGRATION.md), starting with
secret setup and endpoint registration. The n8n workflow JSON files are under
`integrations/n8n/`.

## What is ready, and what still needs your environment

- Backend implementation, focused tests, two inactive n8n exports, and this setup guide are included.
- CI passed 177 tests against PostgreSQL 16 on 2026-10-01, including bridge persistence
  tests. Backend lint/types, frontend audit/type/build, the 16-check template harness,
  and production Compose syntax also passed. The Python dependency audit reported zero findings.
- A separate Docker/Chromium capture verified the dashboard's stated mock refund,
  approval, and manual recovery flows. Worker and Beat were absent from that capture.
- A real n8n → Threshold → HubSpot round trip is still unverified. Account credentials,
  reachable endpoints, installed n8n node compatibility, and worker delivery must be
  checked in the environment used for that run.

See [current verification](docs/VERIFICATION.md) for dated evidence. Earlier packaging
checks are in [history](docs/history/README.md). Before submitting a refund, complete
the [HubSpot API preflight](docs/N8N_INTEGRATION.md#hubspot-api-preflight) using the
same credential that will update the fictional ticket.

n8n Cloud cannot reach `localhost` on your laptop. For the intake workflow, use
an HTTPS development endpoint reachable from n8n, or run n8n locally on a network
that can reach Threshold. For a first Cloud demo, expose only the signed webhook
route through a development proxy/tunnel; do not expose the entire seeded dashboard
and its demo login. Do not remove signature verification to solve connectivity.
