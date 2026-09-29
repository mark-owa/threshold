import React from "react";

interface SandboxProps {
  onRun: (scenario: string) => void;
}

export function Sandbox({ onRun }: SandboxProps) {
  const scenarios = [
    ["low_risk_refund", "Low-risk refund", "Automatically passes policy and executes."],
    ["high_risk_refund", "High-risk refund", "Stops at the human approval boundary."],
    ["rejected_refund", "Policy failure", "Demonstrates deterministic rejection."],
    ["failed_refund", "Failure + retry", "Exercises retry and idempotency behavior."],
    ["support_inquiry", "Support inquiry", "Routes a support request."],
    ["lead_inquiry", "Lead inquiry", "Routes a sales lead."],
  ];
  return <><section className="sandbox-banner"><div><span className="kicker">ISOLATED DEMO WORKSPACE</span><h2>Seeded scenarios cannot run inside customer trial workspaces.</h2><p>This preserves the portfolio/demo experience without treating mock integrations as production capability.</p></div></section><section className="scenario-grid">{scenarios.map(([key, name, description]) => <button className="scenario-card" key={key} onClick={() => onRun(key)}><span className="scenario-arrow">→</span><strong>{name}</strong><p>{description}</p></button>)}</section></>;
}
