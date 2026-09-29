"""Local, non-production provider simulator for failure-path validation.

Order-number conventions:
- contains RETRY-ONCE: first POST returns 503, next POST with same idempotency key succeeds.
- contains HARD-FAIL: returns 422.
- contains UNKNOWN-RECOVER: persists the refund, then sleeps long enough for a short client timeout;
  reconciliation can still discover the committed provider operation.
"""

from __future__ import annotations

import os
import time
import uuid

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Threshold Provider Simulator")
TOKEN = os.getenv("PROVIDER_SIMULATOR_TOKEN", "local-simulator-token")
UNKNOWN_DELAY = float(os.getenv("PROVIDER_SIMULATOR_UNKNOWN_DELAY_SECONDS", "2"))
_refunds: dict[str, dict] = {}
_attempts: dict[str, int] = {}


class RefundRequest(BaseModel):
    order_number: str
    amount_usd: float


def _auth(authorization: str | None) -> None:
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="invalid simulator credential")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/refunds")
def refunds(
    request: RefundRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    _auth(authorization)
    if idempotency_key in _refunds:
        return _refunds[idempotency_key]
    count = _attempts.get(idempotency_key, 0) + 1
    _attempts[idempotency_key] = count
    if "HARD-FAIL" in request.order_number:
        raise HTTPException(status_code=422, detail="simulated permanent provider rejection")
    if "RETRY-ONCE" in request.order_number and count == 1:
        raise HTTPException(status_code=503, detail="simulated transient outage")

    result = {
        "id": f"sim_rf_{uuid.uuid4().hex[:12]}",
        "refund_id": None,
        "order_number": request.order_number,
        "amount_usd": request.amount_usd,
        "status": "succeeded",
        "idempotency_key": idempotency_key,
    }
    result["refund_id"] = result["id"]
    _refunds[idempotency_key] = result
    if "UNKNOWN-RECOVER" in request.order_number:
        time.sleep(UNKNOWN_DELAY)
    return result


@app.get("/refunds/{provider_operation_id}")
def refund_by_id(
    provider_operation_id: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    _auth(authorization)
    for value in _refunds.values():
        if value["id"] == provider_operation_id:
            return value
    raise HTTPException(status_code=404, detail="not found")


@app.get("/refunds/by-idempotency/{idempotency_key:path}")
def refund_by_key(
    idempotency_key: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    _auth(authorization)
    value = _refunds.get(idempotency_key)
    if not value:
        raise HTTPException(status_code=404, detail="not found")
    return value
