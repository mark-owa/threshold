import React, { useState } from "react";
import { Empty } from "./common";
import type { WebhookEndpoint as WebhookEndpointType, WebhookEndpointInput } from "../types";

interface WebhookEndpointsProps {
  endpoints: WebhookEndpointType[];
  canEdit: boolean;
  onCreate: (values: WebhookEndpointInput) => void;
  onDisable: (endpointId: string) => void;
}

export function WebhookEndpoints({ endpoints, canEdit, onCreate, onDisable }: WebhookEndpointsProps) {
  const [name, setName] = useState("Operations webhook");
  const [secretRef, setSecretRef] = useState("");
  return <section className="panel"><div className="panel-head"><div><span className="kicker">DURABLE INGRESS</span><h2>Signed inbound webhooks</h2><p>Deliveries are HMAC verified, deduplicated by provider event ID, committed to the database, then handed to workers through the transactional outbox.</p></div><span className="badge neutral">at-least-once safe</span></div>
    {canEdit && <div className="team-invite-form"><input value={name} onChange={e => setName(e.target.value)} placeholder="Endpoint name" /><input value={secretRef} onChange={e => setSecretRef(e.target.value)} placeholder="Signing secret ref, e.g. SHOPIFY_WEBHOOK" /><button className="primary" disabled={!secretRef} onClick={() => onCreate({ name, signing_secret_ref: secretRef, allowed_clock_skew_seconds: 300 })}>Create endpoint</button></div>}
    <div className="policy-preview"><span>Signature contract</span><strong>X-Threshold-Event-Id + X-Threshold-Timestamp + X-Threshold-Signature (HMAC-SHA256 of timestamp.body). Secret resolves from THRESHOLD_WEBHOOK_SECRET__&lt;REF&gt;.</strong></div>
    {endpoints.length === 0 ? <Empty text="No inbound webhook endpoints configured." /> : endpoints.map((ep) => <div className="member-row" key={ep.id}><div><strong>{ep.name}</strong><span>{ep.path} · secret ref {ep.signing_secret_ref}</span></div><div className="member-actions"><span className={`badge ${ep.is_active ? "low" : "neutral"}`}>{ep.is_active ? "active" : "disabled"}</span>{canEdit && ep.is_active && <button className="outline danger-outline" onClick={() => onDisable(ep.id)}>Disable</button>}</div></div>)}
  </section>;
}
