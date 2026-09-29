import React from "react";
import { Empty } from "./common";
import type { Recovery as RecoveryData } from "../types";

interface RecoveryProps {
  recovery: RecoveryData;
  canAdmin: boolean;
  onReplayEvent: (eventId: string) => void;
  onRequeueOutbox: (messageId: string) => void;
  onReconcile: (actionId: string) => void;
}

export function Recovery({ recovery, canAdmin, onReplayEvent, onRequeueOutbox, onReconcile }: RecoveryProps) {
  const events = recovery?.events ?? [];
  const outbox = recovery?.outbox ?? [];
  const actions = recovery?.actions ?? [];
  return <>
    <section className="panel"><div className="panel-head"><div><span className="kicker">RECOVERY</span><h2>Failed inbound events</h2><p>Replay is allowed only when no workflow execution exists, preventing duplicate business side effects.</p></div><span className="count">{events.length}</span></div>{events.length === 0 ? <Empty text="No failed or dead-letter inbound events." /> : events.map((e) => <div className="member-row" key={e.id}><div><strong>{e.external_id ?? e.id.slice(0, 12)}</strong><span>{e.status} · attempts {e.attempts}/{e.max_attempts} · {e.error ?? "no error"}</span></div><button className="outline" onClick={() => onReplayEvent(e.id)}>Replay safely</button></div>)}</section>
    <section className="panel"><div className="panel-head"><div><h2>Outbox delivery</h2><p>Stuck publisher leases recover automatically. Failed/dead messages can be explicitly requeued by workspace administrators.</p></div><span className="count">{outbox.length}</span></div>{outbox.length === 0 ? <Empty text="No outbox delivery failures." /> : outbox.map((m) => <div className="member-row" key={m.id}><div><strong>{m.topic}</strong><span>{m.status} · {m.aggregate_type} · attempts {m.attempts}/{m.max_attempts}</span></div>{canAdmin && (m.status === "failed" || m.status === "dead_letter") && <button className="outline" onClick={() => onRequeueOutbox(m.id)}>Requeue</button>}</div>)}</section>
    <section className="panel"><div className="panel-head"><div><h2>External action recovery</h2><p>UNKNOWN means Threshold cannot prove whether the provider side effect happened. Reconcile before retrying.</p></div><span className="count">{actions.length}</span></div>{actions.length === 0 ? <Empty text="No external actions require recovery." /> : actions.map((a) => <div className="member-row" key={a.id}><div><strong>{a.action_type} · {a.status}</strong><span>attempts {a.attempts}/{a.max_attempts} · {a.error ?? "no error"}</span></div>{a.status === "unknown" && <button className="outline" onClick={() => onReconcile(a.id)}>Reconcile</button>}</div>)}</section>
  </>;
}
