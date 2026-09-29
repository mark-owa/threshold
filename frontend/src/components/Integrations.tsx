import React, { useState } from "react";
import { Empty } from "./common";
import type { GenericRestInput, Integration, ShopifyInput, StripeInput, WebhookEndpointInput } from "../types";
import type { WebhookEndpoint as WebhookEndpointType } from "../types";
import { WebhookEndpoints } from "./WebhookEndpoints";

interface IntegrationsProps {
  integrations: Integration[];
  webhookEndpoints: WebhookEndpointType[];
  canEdit: boolean;
  isDemo: boolean;
  onSave: (values: GenericRestInput) => void;
  onSaveShopify: (values: ShopifyInput) => void;
  onSaveStripe: (values: StripeInput) => void;
  onSyncShopifyOrder: (orderNumber: string) => void;
  onCreateWebhook: (values: WebhookEndpointInput) => void;
  onDisableWebhook: (endpointId: string) => void;
}

export function Integrations({ integrations, webhookEndpoints, canEdit, isDemo, onSave, onSaveShopify, onSaveStripe, onSyncShopifyOrder, onCreateWebhook, onDisableWebhook }: IntegrationsProps) {
  const live = integrations.find((i) => i.provider === "generic_rest");
  const shopify = integrations.find((i) => i.provider === "shopify");
  const stripe = integrations.find((i) => i.provider === "stripe");
  const [baseUrl, setBaseUrl] = useState(live?.config?.base_url ?? "");
  const [refundPath, setRefundPath] = useState(live?.config?.refund_path ?? "/refunds");
  const [verifyPath, setVerifyPath] = useState(live?.config?.verify_path_template ?? "/refunds/{provider_operation_id}");
  const [reconcilePath, setReconcilePath] = useState(live?.config?.reconcile_path_template ?? "/refunds/by-idempotency/{idempotency_key}");
  const [credentialRef, setCredentialRef] = useState("");
  const [shopDomain, setShopDomain] = useState(shopify?.config?.shop_domain ?? "");
  const [shopCredentialRef, setShopCredentialRef] = useState("");
  const [shopWebhookRef, setShopWebhookRef] = useState(shopify?.config?.webhook_secret_ref ?? "");
  const [shopRefundEnabled, setShopRefundEnabled] = useState(Boolean(shopify?.config?.refund_enabled));
  const [stripeCredentialRef, setStripeCredentialRef] = useState("");
  const [stripeRefundEnabled, setStripeRefundEnabled] = useState(stripe?.config?.refund_enabled ?? true);
  const [syncOrder, setSyncOrder] = useState("");
  if (isDemo) return <section className="panel"><div className="panel-head"><div><h2>Demo integrations</h2><p>This workspace intentionally uses isolated mock providers. Live credentials cannot be attached to demo tenants.</p></div></div>{integrations.map((i) => <div className="integration-row" key={i.id}><div><strong>{i.provider.replaceAll("_", " ")}</strong><span>{i.is_enabled ? "Enabled" : "Disabled"}</span></div><span className={`health ${i.health}`}>{i.health.replaceAll("_", " ")}</span></div>)}</section>;
  return <>
    <section className="panel policy-editor"><div className="panel-head"><div><span className="kicker">ECOMMERCE SOURCE</span><h2>Shopify</h2><p>Shopify provides order/customer truth and can optionally execute refunds. Admin API tokens and webhook secrets stay outside the database behind secret references.</p></div><span className="badge neutral">2026-07 GraphQL</span></div>
      <div className="policy-form">
        <label className="span-2">Shop domain<input value={shopDomain} onChange={e => setShopDomain(e.target.value)} placeholder="merchant.myshopify.com" disabled={!canEdit} /></label>
        <label>Admin API credential ref<input value={shopCredentialRef} onChange={e => setShopCredentialRef(e.target.value)} placeholder={shopify?.credential_configured ? "Configured — enter ref to replace" : "SHOPIFY_ADMIN"} disabled={!canEdit} /></label>
        <label>Webhook secret ref<input value={shopWebhookRef} onChange={e => setShopWebhookRef(e.target.value)} placeholder="SHOPIFY_WEBHOOK" disabled={!canEdit} /></label>
        <label className="span-2"><input type="checkbox" checked={shopRefundEnabled} onChange={e => setShopRefundEnabled(e.target.checked)} disabled={!canEdit} /> Use Shopify as refund execution provider</label>
      </div>
      <button className="primary" disabled={!canEdit || !shopDomain || (!shopCredentialRef && !shopify?.credential_configured)} onClick={() => onSaveShopify({ shop_domain: shopDomain, credential_ref: shopCredentialRef || "SHOPIFY_ADMIN", webhook_secret_ref: shopWebhookRef || null, api_version: "2026-07", timeout_seconds: 10, refund_enabled: shopRefundEnabled, is_enabled: true })}>{shopify ? "Save Shopify" : "Connect Shopify"}</button>
      {shopify && <div className="team-invite-form"><input value={syncOrder} onChange={e => setSyncOrder(e.target.value)} placeholder="#1001" /><button className="outline" disabled={!syncOrder} onClick={() => onSyncShopifyOrder(syncOrder)}>Sync order now</button></div>}
      {shopify && <div className="policy-preview"><span>Shopify webhook</span><strong>/api/v1/webhooks/shopify/&lt;workspace-id&gt; · verify X-Shopify-Hmac-SHA256 · dedupe X-Shopify-Webhook-Id · order events hydrate the local policy cache through the outbox.</strong></div>}
    </section>

    <section className="panel policy-editor"><div className="panel-head"><div><span className="kicker">PAYMENT EXECUTION</span><h2>Stripe refunds</h2><p>Stripe refunds use PaymentIntent references, smallest-currency-unit amounts, provider idempotency keys, and retrieve-by-refund-ID verification.</p></div><span className="badge neutral">verified execution</span></div>
      <div className="policy-form">
        <label className="span-2">Stripe secret key reference<input value={stripeCredentialRef} onChange={e => setStripeCredentialRef(e.target.value)} placeholder={stripe?.credential_configured ? "Configured — enter ref to replace" : "STRIPE_SECRET"} disabled={!canEdit} /></label>
        <label className="span-2"><input type="checkbox" checked={stripeRefundEnabled} onChange={e => setStripeRefundEnabled(e.target.checked)} disabled={!canEdit} /> Use Stripe as refund execution provider</label>
      </div>
      <button className="primary" disabled={!canEdit || (!stripeCredentialRef && !stripe?.credential_configured)} onClick={() => onSaveStripe({ credential_ref: stripeCredentialRef || "STRIPE_SECRET", api_version: null, timeout_seconds: 10, refund_enabled: stripeRefundEnabled, is_enabled: true })}>{stripe ? "Save Stripe" : "Connect Stripe"}</button>
    </section>

    <section className="panel policy-editor"><div className="panel-head"><div><span className="kicker">CUSTOM PROVIDER</span><h2>Generic REST refund provider</h2><p>Retained for non-Shopify/Stripe deployments. Only one live integration should be marked as the refund execution provider.</p></div><span className="badge neutral">secret reference</span></div>
      <div className="policy-form">
        <label className="span-2">Provider base URL<input value={baseUrl} onChange={e => setBaseUrl(e.target.value)} placeholder="https://api.example.com" disabled={!canEdit} /></label>
        <label>Refund path<input value={refundPath} onChange={e => setRefundPath(e.target.value)} disabled={!canEdit} /></label>
        <label>Verify path<input value={verifyPath} onChange={e => setVerifyPath(e.target.value)} disabled={!canEdit} /></label>
        <label className="span-2">Reconcile by idempotency key<input value={reconcilePath} onChange={e => setReconcilePath(e.target.value)} disabled={!canEdit} /></label>
        <label className="span-2">Credential reference<input value={credentialRef} onChange={e => setCredentialRef(e.target.value)} placeholder={live?.credential_configured ? "Credential already configured — enter ref to replace" : "e.g. ACME_REFUND_API"} disabled={!canEdit} /></label>
      </div>
      <button className="primary" disabled={!canEdit || !baseUrl} onClick={() => onSave({ base_url: baseUrl, refund_path: refundPath, verify_path_template: verifyPath, reconcile_path_template: reconcilePath, credential_ref: credentialRef || null, timeout_seconds: 10, failure_threshold: 3, recovery_timeout_seconds: 30, is_enabled: true })}>{live ? "Save generic provider" : "Connect generic provider"}</button>
    </section>
    <section className="panel"><div className="panel-head"><div><h2>Integration registry</h2><p>Shopify can hydrate order truth while Stripe or Shopify can be the single refund execution boundary.</p></div></div>{integrations.length === 0 ? <Empty text="No external systems connected yet." /> : integrations.map((i) => <div className="integration-row" key={i.id}><div><strong>{i.provider.replaceAll("_", " ")}</strong><span>{i.is_enabled ? "Enabled" : "Disabled"} · credentials {i.credential_configured ? "referenced" : "not configured"}{i.config?.refund_enabled ? " · refund executor" : ""}</span></div><div><span className={`health ${i.health}`}>{i.health.replaceAll("_", " ")}</span><small>{i.consecutive_failures}/{i.failure_threshold} failures</small></div></div>)}</section>
    <WebhookEndpoints endpoints={webhookEndpoints} canEdit={canEdit} onCreate={onCreateWebhook} onDisable={onDisableWebhook} />
  </>;
}
