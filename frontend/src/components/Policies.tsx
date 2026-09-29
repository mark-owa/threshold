import React, { useState } from "react";
import { Empty } from "./common";
import type { Policy, RefundPolicyInput } from "../types";

interface PoliciesProps {
  policies: Policy[];
  canEdit: boolean;
  onSave: (values: RefundPolicyInput) => void;
}

export function Policies({ policies, canEdit, onSave }: PoliciesProps) {
  const existing = policies.find((p) => p.category === "refund_request");
  const [title, setTitle] = useState(existing?.title ?? "Refund policy");
  const [content, setContent] = useState(existing?.content ?? "Refunds are eligible only inside the configured window and within the order total.");
  const [windowDays, setWindowDays] = useState(String(existing?.structured_rules?.refund_window_days ?? 30));
  const [autoLimit, setAutoLimit] = useState(String(existing?.structured_rules?.max_auto_refund_usd ?? 50));

  return <>
    <section className="panel policy-editor"><div className="panel-head"><div><span className="kicker">REFUND CONTROL</span><h2>Editable deterministic policy</h2><p>These values feed Threshold's existing business-rule and risk-assessment steps. The model cannot override them.</p></div><span className="badge neutral">server enforced</span></div>
      <div className="policy-form">
        <label>Policy title<input value={title} onChange={e => setTitle(e.target.value)} disabled={!canEdit} /></label>
        <label className="span-2">Human-readable policy<textarea value={content} onChange={e => setContent(e.target.value)} disabled={!canEdit} /></label>
        <label>Refund window (days)<input type="number" min="1" max="365" value={windowDays} onChange={e => setWindowDays(e.target.value)} disabled={!canEdit} /></label>
        <label>Automatic refund limit (USD)<input type="number" min="0" step="0.01" value={autoLimit} onChange={e => setAutoLimit(e.target.value)} disabled={!canEdit} /></label>
      </div>
      <div className="policy-preview"><span>Behavior</span><strong>Eligible refunds at or below ${autoLimit || "0"} may pass automatically. Larger eligible refunds require human approval. Requests outside {windowDays || "0"} days fail the deterministic eligibility gate.</strong></div>
      <button className="primary" disabled={!canEdit} onClick={() => onSave({ title, content, refund_window_days: Number(windowDays), max_auto_refund_usd: Number(autoLimit) })}>{existing ? "Save policy changes" : "Create refund policy"}</button>
      {!canEdit && <p className="permission-note">Only workspace owners and admins can edit deterministic policy.</p>}
    </section>
    <section className="panel"><div className="panel-head"><div><h2>Policy registry</h2><p>Current policy records scoped to this workspace.</p></div></div>{policies.length === 0 ? <Empty text="No workspace policies configured yet." /> : policies.map((p) => <article className="policy-card" key={p.id}><div className="policy-head"><div><span className="kicker">{p.category.replaceAll("_", " ")}</span><h3>{p.title}</h3></div><span className="badge neutral">deterministic</span></div><p>{p.content}</p><div className="rule-grid">{Object.entries(p.structured_rules ?? {}).map(([key, value]) => <div key={key}><span>{key.replaceAll("_", " ")}</span><strong>{String(value)}</strong></div>)}</div></article>)}</section>
  </>;
}
