import React from "react";
import { Empty } from "./common";
import type { ExternalAction } from "../types";

interface ActionsProps {
  actions: ExternalAction[];
  onReconcile: (actionId: string) => void;
}

export function Actions({ actions, onReconcile }: ActionsProps) {
  return <section className="panel"><div className="panel-head"><div><h2>External action ledger</h2><p>Provider effects are separate from workflow runs. Unknown outcomes are reconciled before any retry is allowed.</p></div><span className="count">{actions.length}</span></div>{actions.length === 0 ? <Empty text="No external actions yet." /> : actions.map((action) => <div className="member-row" key={action.id}><div><strong>{action.action_type} · {action.status}</strong><span>{action.id.slice(0, 8)} · attempts {action.attempt_count}/{action.max_attempts}{action.error ? ` · ${action.error}` : ""}</span></div><div className="member-actions">{action.verified_at && <span className="badge low">verified</span>}{action.status === "unknown" && <button className="primary" onClick={() => onReconcile(action.id)}>Reconcile</button>}{action.status === "retrying" && <span className="badge medium">safe retry queued</span>}</div></div>)}</section>;
}
