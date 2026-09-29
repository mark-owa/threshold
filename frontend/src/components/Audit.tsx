import React from "react";
import { Empty } from "./common";
import type { AuditEntry } from "../types";

interface AuditProps {
  audit: AuditEntry[];
}

export function Audit({ audit }: AuditProps) {
  return <section className="panel"><div className="panel-head"><div><h2>Operational evidence</h2><p>Append-only history for workflow activity and SaaS control-plane changes.</p></div></div>{audit.length === 0 ? <Empty text="No audit events yet." /> : audit.map((item) => <div className="audit-row" key={item.id}><div><strong>{item.event_type}</strong><span>{item.actor_type}</span></div><code>{item.execution_id?.slice(0, 8) ?? "control"}</code><small>{item.created_at ? new Date(item.created_at).toLocaleString() : ""}</small></div>)}</section>;
}
