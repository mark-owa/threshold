from pathlib import Path

ROOT = Path("/app")

REPLACEMENTS = [
    (
        "app/integrations/providers.py",
        '''    def execute_refund(self, integration, *, order_number, amount_usd, idempotency_key, payment_reference=None, currency="USD", **kwargs):
        if not payment_reference:
            return ProviderResult(status="failed", response={}, error="stripe_payment_reference_missing")
        validate_live_endpoint(f"{self.base_url}/v1/refunds")
        cents = int((amount_usd * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        form = {"amount": str(cents), "payment_intent": payment_reference, "reason": "requested_by_customer", "metadata[threshold_order_number]": order_number, "metadata[threshold_idempotency_key]": idempotency_key}
        timeout = float(integration.config.get("timeout_seconds", 10))
        try:
            with httpx.Client(timeout=timeout, follow_redirects=False) as client:
                response = client.post(f"{self.base_url}/v1/refunds", headers=self._headers(integration, idempotency_key), content=urlencode(form))
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            return ProviderResult(status="unknown", response={}, unknown=True, error=f"stripe_transport_unknown:{exc.__class__.__name__}")
        body = self._json(response)
        if 200 <= response.status_code < 300:
            refund_id = str(body.get("id") or "") or None
            status = str(body.get("status") or "").lower()
            verified = status == "succeeded"
            return ProviderResult(status="succeeded" if verified else "unknown", response=body, provider_operation_id=refund_id, verified=verified, unknown=not verified, error=None if verified else f"stripe_refund_status_{status or 'unknown'}")
        if response.status_code in {408, 409, 429} or response.status_code >= 500:
            return ProviderResult(status="retryable_failure", response=body, retryable=True, error=f"stripe_http_{response.status_code}")
        return ProviderResult(status="failed", response=body, error=f"stripe_http_{response.status_code}")
''',
        '''    def execute_refund(self, integration, *, order_number, amount_usd, idempotency_key, payment_reference=None, currency="USD", **kwargs):
        if not payment_reference:
            return ProviderResult(status="failed", response={}, error="stripe_payment_reference_missing")
        currency_code = str(currency or "USD").upper()
        if currency_code != "USD":
            return ProviderResult(status="failed", response={}, error="stripe_currency_unsupported")
        if str(payment_reference).startswith("pi_"):
            reference_field = "payment_intent"
        elif str(payment_reference).startswith("ch_"):
            reference_field = "charge"
        else:
            return ProviderResult(status="failed", response={}, error="stripe_payment_reference_invalid")
        validate_live_endpoint(f"{self.base_url}/v1/refunds")
        cents = int((amount_usd * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        form = {
            "amount": str(cents),
            reference_field: str(payment_reference),
            "reason": "requested_by_customer",
            "metadata[threshold_order_number]": order_number,
            "metadata[threshold_idempotency_key]": idempotency_key,
        }
        timeout = float(integration.config.get("timeout_seconds", 10))
        try:
            with httpx.Client(timeout=timeout, follow_redirects=False) as client:
                response = client.post(f"{self.base_url}/v1/refunds", headers=self._headers(integration, idempotency_key), content=urlencode(form))
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            return ProviderResult(status="unknown", response={}, unknown=True, error=f"stripe_transport_unknown:{exc.__class__.__name__}")
        body = self._json(response)
        if 200 <= response.status_code < 300:
            refund_id = str(body.get("id") or "") or None
            status = str(body.get("status") or "").lower()
            verified = status == "succeeded"
            return ProviderResult(status="succeeded" if verified else "unknown", response=body, provider_operation_id=refund_id, verified=verified, unknown=not verified, error=None if verified else f"stripe_refund_status_{status or 'unknown'}")
        # Stripe caches the first result for an idempotency key, including a 500.
        # Re-posting an ambiguous server response can therefore replay the same
        # failure forever. UNKNOWN requires reconciliation/operator review rather
        # than blindly issuing the side effect again.
        if response.status_code == 408 or response.status_code >= 500:
            return ProviderResult(status="unknown", response=body, unknown=True, error=f"stripe_http_unknown_{response.status_code}")
        if response.status_code in {409, 429}:
            return ProviderResult(status="retryable_failure", response=body, retryable=True, error=f"stripe_http_{response.status_code}")
        return ProviderResult(status="failed", response=body, error=f"stripe_http_{response.status_code}")
'''
    ),
    (
        "app/api/commercial.py",
        '''def _plan_from_price(price_id: str | None) -> str | None:
    if price_id and price_id == settings.STRIPE_STARTER_PRICE_ID:
        return "starter"
    if price_id and price_id == settings.STRIPE_BUSINESS_PRICE_ID:
        return "business"
    return None
''',
        '''def _plan_from_price(price_id: str | None) -> str | None:
    if price_id and price_id == settings.STRIPE_STARTER_PRICE_ID:
        return "starter"
    if price_id and price_id == settings.STRIPE_BUSINESS_PRICE_ID:
        return "business"
    return None


def _stripe_event_created(event: dict) -> int | None:
    value = event.get("created")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _stripe_subscription_event_is_stale(billing: BillingAccount, event: dict) -> bool:
    current = (billing.metadata_json or {}).get("stripe_subscription_event_created")
    incoming = _stripe_event_created(event)
    if incoming is None or current is None:
        return False
    try:
        return incoming < int(current)
    except (TypeError, ValueError):
        return False


def _remember_stripe_subscription_event(billing: BillingAccount, event: dict) -> None:
    incoming = _stripe_event_created(event)
    metadata = dict(billing.metadata_json or {})
    if incoming is not None:
        metadata["stripe_subscription_event_created"] = incoming
    event_id = str(event.get("id") or "")
    if event_id:
        metadata["stripe_subscription_event_id"] = event_id
    billing.metadata_json = metadata
'''
    ),
    (
        "app/api/commercial.py",
        '''        billing.customer_id = str(customer_id) if customer_id else billing.customer_id
        billing.subscription_id = str(subscription_id) if subscription_id else billing.subscription_id
        billing.subscription_status = "active"
''',
        '''        billing.customer_id = str(customer_id) if customer_id else billing.customer_id
        billing.subscription_id = str(subscription_id) if subscription_id else billing.subscription_id
        # Checkout completion proves the session finished, not the canonical
        # subscription state. customer.subscription.* events own that state.
'''
    ),
    (
        "app/api/commercial.py",
        '''        billing = get_or_create_billing_account(db, organization)
        subscription = obj
        first_item = (((obj.get("items") or {}).get("data") or [{}])[0])
''',
        '''        billing = get_or_create_billing_account(db, organization)
        if _stripe_subscription_event_is_stale(billing, event):
            db.commit()
            return {"received": True, "ignored": "stale_subscription_event"}
        subscription = obj
        first_item = (((obj.get("items") or {}).get("data") or [{}])[0])
'''
    ),
    (
        "app/api/commercial.py",
        '''        if event_type == "customer.subscription.deleted":
            organization.plan = "trial"
        elif resolved_plan:
            organization.plan = resolved_plan
        db.add(AuditLogEntry(organization_id=organization.id, workflow_execution_id=None, event_type="billing.subscription_synced", actor_type="system", actor_id=None, payload={"stripe_event_id": event.get("id"), "status": billing.subscription_status, "price_id": price_id, "plan": organization.plan}))
''',
        '''        if event_type == "customer.subscription.deleted":
            organization.plan = "trial"
        elif resolved_plan:
            organization.plan = resolved_plan
        _remember_stripe_subscription_event(billing, event)
        db.add(AuditLogEntry(organization_id=organization.id, workflow_execution_id=None, event_type="billing.subscription_synced", actor_type="system", actor_id=None, payload={"stripe_event_id": event.get("id"), "status": billing.subscription_status, "price_id": price_id, "plan": organization.plan}))
'''
    ),
]

for rel, old, new in REPLACEMENTS:
    path = ROOT / rel
    source = path.read_text()
    if old not in source:
        raise SystemExit(f"Expected source block not found in {rel}; refusing unsafe Stripe patch")
    path.write_text(source.replace(old, new, 1))

print("Stripe staging hardening patch applied")
