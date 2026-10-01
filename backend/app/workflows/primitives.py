"""Pure deterministic workflow primitives.

These functions perform no database or network I/O. They share the model enums
and can be tested without running PostgreSQL or Celery.
"""

from __future__ import annotations

import re

from app.models.enums import RequestCategory


def normalize_crm(value: object) -> dict:
    """Preserve only explicit CRM correlation. IDs remain strings."""
    if not isinstance(value, dict):
        raise ValueError("crm must be an object")
    allowed = {"provider", "portal_id", "ticket_id", "contact_id"}
    if set(value) - allowed or value.get("provider") != "hubspot":
        raise ValueError("crm must identify HubSpot using supported fields")
    for key in ("portal_id", "ticket_id"):
        if not isinstance(value.get(key), str) or not re.fullmatch(r"[0-9]{1,32}", value[key]):
            raise ValueError(f"crm.{key} must be a numeric ID string")
    if "contact_id" in value and (
        not isinstance(value["contact_id"], str)
        or not re.fullmatch(r"[0-9]{1,32}", value["contact_id"])
    ):
        raise ValueError("crm.contact_id must be a numeric ID string")
    return dict(value)


def normalize_payload(payload: dict) -> dict:
    text = payload.get("text") or payload.get("message") or payload.get("body") or ""
    if not isinstance(text, str):
        raise ValueError("Event text must be a string")
    for key in ("sender", "external_id"):
        value = payload.get(key)
        if value is not None and (not isinstance(value, str) or len(value) > 255):
            raise ValueError(f"{key} must be a string of at most 255 characters")
    return {
        **({"simulate_failure_once": True} if payload.get("simulate_failure_once") is True else {}),
        **({"crm": normalize_crm(payload["crm"])} if "crm" in payload else {}),
        "text": text.strip(),
        "sender": payload.get("sender"),
        "external_id": payload.get("external_id"),
    }


def classify_text(text: str) -> RequestCategory:
    lowered = text.lower()
    if any(
        word in lowered for word in ("refund", "money back", "charged twice", "charged me twice")
    ):
        return RequestCategory.REFUND_REQUEST
    if any(word in lowered for word in ("lead", "interested", "quote")):
        return RequestCategory.LEAD_INQUIRY
    if any(word in lowered for word in ("invoice", "order")):
        return RequestCategory.INVOICE_ORDER
    if any(word in lowered for word in ("problem", "broken", "issue", "support")):
        return RequestCategory.SUPPORT_REQUEST
    return RequestCategory.CUSTOMER_INQUIRY


def extract_refund(text: str) -> dict:
    order_match = re.search(r"(?:order|#)\s*[-:]?\s*([A-Za-z0-9-]+)", text, re.I)
    amount_match = re.search(
        r"([+-]?)\s*(?:\$|\busd\s*)\s*([+-]?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)"
        r"(?:\.[0-9]{1,2})?)(?![\w.,])",
        text,
        re.I,
    )
    result: dict[str, str | float | None] = {
        "order_number": order_match.group(1) if order_match else None
    }
    if amount_match:
        amount = float(amount_match.group(2).replace(",", ""))
        if amount_match.group(1) == "-":
            amount = -abs(amount)
        result["amount_usd"] = amount
    return result


def retry_delay_seconds(attempt: int, base: int = 2, cap: int = 60) -> int:
    """Return bounded exponential backoff with a one-second first retry."""
    if attempt <= 1:
        return 1
    return min(cap, base ** (attempt - 1))
