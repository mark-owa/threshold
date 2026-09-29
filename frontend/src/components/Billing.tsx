import React, { useState } from "react";
import { Empty, Metric } from "./common";
import type { CommercialStatus, PlanLimits } from "../types";

interface BillingProps {
  commercial: CommercialStatus | null;
  isOwner: boolean;
  onCheckout: (plan: string) => void;
  onPortal: () => void;
  onShopifyOAuth: (shop: string) => void;
}

export function Billing({ commercial, isOwner, onCheckout, onPortal, onShopifyOAuth }: BillingProps) {
  const [shop, setShop] = useState("");
  if (!commercial) return <section className="panel"><Empty text="Billing state unavailable." /></section>;
  const limits: Partial<PlanLimits> = commercial.plan_definition?.limits ?? {};
  const usage: Record<string, number> = commercial.usage ?? {};
  return <>
    <section className="panel"><div className="panel-head"><div><span className="kicker">COMMERCIAL</span><h2>{commercial.plan_definition?.name ?? commercial.plan} plan</h2><p>Subscription status: {commercial.subscription_status}. Usage resets by calendar month in this milestone.</p></div><span className="badge neutral">{commercial.plan}</span></div>
      <div className="metrics-grid">
        <Metric title="Workflow executions" value={usage.workflow_executions ?? 0} note={limits.workflow_executions == null ? "unlimited" : `of ${limits.workflow_executions}`} />
        <Metric title="External actions" value={usage.external_actions ?? 0} note={limits.external_actions == null ? "unlimited" : `of ${limits.external_actions}`} />
        <Metric title="Team limit" value={limits.team_members ?? "∞"} note="members" />
      </div>
      {commercial.trial_ends_at && <div className="policy-preview"><span>Trial ends</span><strong>{new Date(commercial.trial_ends_at).toLocaleString()}</strong></div>}
      {isOwner && <div className="inline-form"><button className="primary" disabled={!commercial.billing_configured} onClick={() => onCheckout("starter")}>Choose Starter</button><button className="outline" disabled={!commercial.billing_configured} onClick={() => onCheckout("business")}>Choose Business</button><button className="outline" onClick={onPortal}>Manage billing</button></div>}
      {!commercial.billing_configured && <p className="permission-note">Stripe Billing is intentionally fail-closed until server-side billing credentials and Price IDs are configured.</p>}
    </section>
    <section className="panel"><div className="panel-head"><div><span className="kicker">SHOPIFY INSTALL</span><h2>Merchant OAuth</h2><p>Starts Shopify's authorization flow. Threshold will refuse the callback unless a server-side secret-vault sink is configured for the resulting merchant token.</p></div></div>
      <div className="inline-form"><input value={shop} onChange={e => setShop(e.target.value)} placeholder="store.myshopify.com" /><button className="primary" disabled={!commercial.shopify_oauth_configured || !shop} onClick={() => onShopifyOAuth(shop)}>Install Shopify</button></div>
      {!commercial.shopify_oauth_configured && <p className="permission-note">Shopify client credentials are not configured on this deployment.</p>}
    </section>
  </>;
}
