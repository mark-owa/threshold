from __future__ import annotations

import argparse
import json
from uuid import UUID

from app.db.session import SessionLocal
from app.services.beta_readiness import build_beta_readiness


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Threshold private-beta readiness for one workspace.")
    parser.add_argument("--org-id", required=True, help="Organization UUID")
    parser.add_argument("--no-runtime-probes", action="store_true", help="Skip Redis/Celery probes")
    parser.add_argument("--strict-warnings", action="store_true", help="Exit nonzero when warnings remain")
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = build_beta_readiness(
            db,
            UUID(args.org_id),
            probe_runtime=not args.no_runtime_probes,
        )
    finally:
        db.close()

    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")

    if report["summary"]["block"]:
        return 2
    if args.strict_warnings and report["summary"]["warn"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
