import React from "react";
import { Empty, Metric } from "./common";
import type { BetaReadinessReport } from "../types";

interface BetaReadinessProps {
  report: BetaReadinessReport | null;
  isOwner: boolean;
  canAdmin: boolean;
  onToggle: (enabled: boolean) => void;
}

export function BetaReadiness({ report, isOwner, canAdmin, onToggle }: BetaReadinessProps) {
  if (!canAdmin) return <section className="panel"><Empty text="Owner or admin permission is required to inspect the private-beta gate." /></section>;
  if (!report) return <section className="panel"><Empty text="Beta readiness report unavailable." /></section>;
  const liveCheck = report.checks?.find((check) => check.key === "live_execution_switch");
  const liveEnabled = liveCheck?.level === "pass";
  return (
    <div className="stack">
      <section className="panel">
        <div className="section-title-row"><div><p className="eyebrow">Launch gate</p><h2>Private beta readiness</h2></div><span className={`status ${report.ready ? "success" : "failed"}`}>{report.ready ? "READY" : `${report.summary?.block ?? 0} BLOCKERS`}</span></div>
        <p className="muted">This page is a launch gate, not a marketing checklist. Runtime probes are performed again when live execution is enabled.</p>
        <div className="metric-grid">
          <Metric title="Passed" value={report.summary?.pass ?? 0} note="checks" />
          <Metric title="Warnings" value={report.summary?.warn ?? 0} note="checks" />
          <Metric title="Blockers" value={report.summary?.block ?? 0} note="checks" />
        </div>
        <div className="button-row">
          {liveEnabled ? <button className="danger" disabled={!canAdmin} onClick={() => onToggle(false)}>Disable live execution</button> : <button disabled={!isOwner} onClick={() => onToggle(true)}>Run gate + enable live execution</button>}
        </div>
        {!isOwner && !liveEnabled && <p className="permission-note">Only an owner may enable live provider execution. Owners and admins may disable it.</p>}
      </section>
      <section className="panel">
        <h3>Readiness checks</h3>
        <div className="table-list">
          {(report.checks ?? []).map((check) => <div className="table-row" key={check.key}>
            <div><strong>{check.title}</strong><small>{check.category} · {check.detail}</small></div>
            <span className={`status ${check.level === "pass" ? "success" : check.level === "warn" ? "pending" : "failed"}`}>{check.level.toUpperCase()}</span>
          </div>)}
        </div>
      </section>
    </div>
  );
}
