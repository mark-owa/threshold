import React from "react";
import { Empty } from "./common";
import type { Approval, ApprovalDecision } from "../types";

interface ApprovalsProps {
  approvals: Approval[];
  onDecision: (approvalId: string, decision: ApprovalDecision) => void;
}

export function Approvals({ approvals, onDecision }: ApprovalsProps) {
  return <section className="panel"><div className="panel-head"><div><h2>Pending decisions</h2><p>AI-generated proposals stop here when deterministic policy requires human authority.</p></div></div>{approvals.length === 0 ? <Empty text="Nothing is waiting for review." /> : approvals.map((a) => <div className="approval-card" key={a.id}><div className="approval-top"><div><span className="kicker">PROPOSED ACTION</span><h3>{a.proposed_action?.action_type ?? "Action"}</h3></div><span className={`badge ${a.risk_level}`}>{a.risk_level} risk</span></div><p>{a.reason}</p><div className="evidence-grid"><div><span>Policy / risk context</span><pre>{JSON.stringify(a.risk_factors ?? [], null, 2)}</pre></div><div><span>Generated parameters</span><pre>{JSON.stringify(a.generated_parameters ?? {}, null, 2)}</pre></div></div><div className="approval-actions"><button className="primary" onClick={() => onDecision(a.id, "approved")}>Approve</button><button className="danger" onClick={() => onDecision(a.id, "rejected")}>Reject</button></div></div>)}</section>;
}
