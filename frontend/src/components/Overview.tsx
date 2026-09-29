import React from "react";
import { Empty, Metric } from "./common";
import type { Approval, ExecutionSummary, Metrics, Onboarding, WorkflowDefinition } from "../types";
import type { Tab } from "../nav";

interface OverviewProps {
  metrics: Metrics | null;
  workflows: WorkflowDefinition[];
  approvals: Approval[];
  executions: ExecutionSummary[];
  onboarding: Onboarding | null;
  onExecution: (id: string) => void;
  onNavigate: (tab: Tab) => void;
}

export function Overview({ metrics, workflows, approvals, executions, onboarding, onExecution, onNavigate }: OverviewProps) {
  return <>
    {onboarding && onboarding.plan !== "demo" && <section className="panel onboarding-panel">
      <div className="panel-head"><div><span className="kicker">SAAS ONBOARDING</span><h2>Prepare this workspace for live execution</h2><p>{onboarding.completed_steps}/{onboarding.total_steps} setup steps complete.</p></div><strong className="progress-number">{onboarding.percent_complete}%</strong></div>
      <div className="progress-track"><div style={{ width: `${onboarding.percent_complete}%` }} /></div>
      <div className="onboarding-list">{onboarding.steps.map((step) => <button key={step.key} className={`onboarding-step ${step.complete ? "done" : ""}`} onClick={() => step.key === "refund_policy" ? onNavigate("policies") : step.key === "team" ? onNavigate("team") : step.key === "integration" ? onNavigate("integrations") : undefined}><span className="checkmark">{step.complete ? "✓" : "○"}</span><div><strong>{step.title}</strong><small>{step.description}</small></div></button>)}</div>
    </section>}
    <section className="metrics-grid">
      <Metric title="Executions" value={metrics?.total_executions ?? "—"} note="All workflow runs" />
      <Metric title="Automation rate" value={metrics ? `${metrics.automation_rate_percent}%` : "—"} note="Completed without approval" />
      <Metric title="Awaiting approval" value={metrics?.awaiting_approval ?? "—"} note="Human decisions pending" />
      <Metric title="Failed" value={metrics?.failed ?? "—"} note="Needs operational attention" />
      <Metric title="Hours saved" value={metrics ? `${metrics.estimated_hours_saved}h` : "—"} note="Current estimate" />
    </section>
    <section className="split-grid">
      <div className="panel"><div className="panel-head"><div><h2>Active workflows</h2><p>Configured control paths available to this workspace.</p></div><span className="count">{workflows.filter((w) => w.is_active).length}</span></div>{workflows.length === 0 ? <Empty text="No workflows configured yet." /> : workflows.slice(0, 6).map((w) => <div className="list-row" key={w.id}><div><strong>{w.name}</strong><span>{w.trigger_category.replaceAll("_", " ")}</span></div><span className="badge neutral">v{w.version}</span></div>)}</div>
      <div className="panel"><div className="panel-head"><div><h2>Approval pressure</h2><p>Actions waiting for an authorized reviewer.</p></div><span className="count">{approvals.length}</span></div>{approvals.length === 0 ? <Empty text="No pending approvals." /> : approvals.slice(0, 5).map((a) => <div className="list-row" key={a.id}><div><strong>{a.proposed_action?.action_type ?? "Action"}</strong><span>{a.reason}</span></div><span className={`badge ${a.risk_level}`}>{a.risk_level}</span></div>)}</div>
    </section>
    <section className="panel"><div className="panel-head"><div><h2>Recent executions</h2><p>Every run stays inspectable down to its recorded steps.</p></div></div>{executions.length === 0 ? <Empty text="No executions yet." /> : executions.slice(0, 8).map((e) => <button className="execution-row" key={e.id} onClick={() => onExecution(e.id)}><code>{e.id.slice(0, 8)}</code><strong>{e.status}</strong><span>{e.current_step ?? "complete"}</span><small>{e.error ?? "No recorded error"}</small></button>)}</section>
  </>;
}
