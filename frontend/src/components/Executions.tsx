import React from "react";
import { Empty } from "./common";
import type { ExecutionDetail, ExecutionSummary } from "../types";

interface ExecutionsProps {
  executions: ExecutionSummary[];
  execution: ExecutionDetail | null;
  onSelect: (id: string) => void;
  onRetry: (id: string) => void;
}

export function Executions({ executions, execution, onSelect, onRetry }: ExecutionsProps) {
  return <div className="execution-layout"><section className="panel execution-list"><div className="panel-head"><div><h2>Executions</h2><p>Select a run to inspect its control path.</p></div></div>{executions.length === 0 ? <Empty text="No executions yet." /> : executions.map((e) => <button className={`execution-row compact-row ${execution?.id === e.id ? "selected" : ""}`} key={e.id} onClick={() => onSelect(e.id)}><code>{e.id.slice(0, 8)}</code><strong>{e.status}</strong><span>{e.current_step ?? "complete"}</span></button>)}</section><section className="panel inspector"><div className="panel-head"><div><h2>Execution inspector</h2><p>Recorded inputs, outputs, latency, and failures.</p></div></div>{execution ? <div className="timeline"><div className="execution-summary"><div><span>Execution</span><code>{execution.id}</code></div><span className={`badge ${execution.status}`}>{execution.status}</span></div>{execution.status === "failed" && <div className="warning-action"><div><strong>Execution failed</strong><span>The retry path reuses the existing action idempotency key.</span></div><button onClick={() => onRetry(execution.id)}>Retry</button></div>}{execution.steps.map((s) => <div className={`step ${s.status}`} key={s.id}><div className="dot"/><div className="step-main"><strong>{s.step_key}</strong><span>{s.step_type}</span><small>{s.status}</small></div><div className="latency">{s.latency_ms ?? 0}ms</div><pre>{JSON.stringify({ input: s.input ?? {}, output: s.output ?? {}, error: s.error }, null, 2)}</pre></div>)}</div> : <Empty text="Select an execution to inspect it." />}</section></div>;
}
