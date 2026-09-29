from __future__ import annotations

import argparse
import json
import os

import httpx


def _must(response: httpx.Response, label: str) -> dict:
    if not response.is_success:
        raise RuntimeError(f"{label} failed: HTTP {response.status_code} {response.text[:400]}")
    body = response.json()
    return body if isinstance(body, dict) else {"data": body}


def main() -> int:
    parser = argparse.ArgumentParser(description="Non-destructive private-beta smoke test against a deployed Threshold instance.")
    parser.add_argument("--base-url", default=os.getenv("BETA_BASE_URL", ""))
    parser.add_argument("--email", default=os.getenv("BETA_OWNER_EMAIL", ""))
    parser.add_argument("--password", default=os.getenv("BETA_OWNER_PASSWORD", ""))
    parser.add_argument("--org-id", default=os.getenv("BETA_ORG_ID", ""))
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    if not all([args.base_url, args.email, args.password, args.org_id]):
        raise SystemExit("base URL, owner email/password, and org id are required")

    base = args.base_url.rstrip("/")
    evidence: dict[str, object] = {"base_url": base, "org_id": args.org_id, "checks": {}}
    with httpx.Client(timeout=15, follow_redirects=False) as client:
        evidence["checks"]["liveness"] = _must(client.get(f"{base}/health/live"), "liveness")
        ready = client.get(f"{base}/health/ready")
        evidence["checks"]["readiness"] = ready.json()
        if ready.status_code != 200:
            raise RuntimeError(f"service readiness failed: HTTP {ready.status_code} {ready.text[:400]}")

        auth = _must(
            client.post(
                f"{base}/api/v1/auth/login",
                json={"email": args.email, "password": args.password},
            ),
            "login",
        )
        token = auth.get("access_token")
        if not token:
            raise RuntimeError("login response did not contain access_token")
        headers = {"Authorization": f"Bearer {token}"}

        me = _must(client.get(f"{base}/api/v1/auth/me", headers=headers), "auth/me")
        evidence["checks"]["identity"] = {"email": me.get("email"), "user_id": me.get("user_id")}

        report = _must(
            client.get(
                f"{base}/api/v1/ops/beta-readiness",
                params={"org_id": args.org_id, "probe_runtime": "true"},
                headers=headers,
            ),
            "beta readiness",
        )
        evidence["checks"]["beta_readiness"] = report

    rendered = json.dumps(evidence, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")
    return 0 if report.get("ready") else 2


if __name__ == "__main__":
    raise SystemExit(main())
