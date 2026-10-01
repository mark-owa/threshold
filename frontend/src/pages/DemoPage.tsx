import { Play } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Callout, PageHeader, Panel } from "@/components/ui/Layout";
import { useRunDemo } from "@/hooks/mutations";

/** Inputs mirror backend/app/api/demo.py; the workspace runs them through the real workflow engine. */
const SCENARIOS = [
  { key: "low_risk_refund", title: "Low-risk refund", text: "Please refund order #ORD-1002 for $65.00", note: "A typical refund request. Follow how policy evaluates it." },
  { key: "high_risk_refund", title: "High-risk refund", text: "Please refund order #ORD-1001 for $89.99", note: "Exercises the risk and approval path." },
  { key: "rejected_refund", title: "Refund likely to be rejected", text: "I want a refund for order #ORD-1001 for $150.00 because I changed my mind", note: "A large refund with a weak reason." },
  { key: "failed_refund", title: "Provider failure", text: "Please refund order #ORD-1002 for $65.00", note: "Simulates the provider failing once, to show retries and recovery." },
  { key: "support_inquiry", title: "Support inquiry", text: "My account has a problem and I need support", note: "A non-refund request." },
  { key: "lead_inquiry", title: "Sales lead", text: "I am interested and would like a quote for the premium plan", note: "A lead-capture request." },
];

export function DemoPage() {
  const run = useRunDemo();
  return (
    <>
      <PageHeader title="Scenarios" description="Send a sample event through the real workflow engine and follow it end to end." />
      <div className="section">
        <Callout tone="info">These run only in demo workspaces, against built-in mock providers. Each creates a real execution you can inspect.</Callout>
      </div>
      <div className="scenarios">
        {SCENARIOS.map((s) => (
          <Panel key={s.key} title={s.title} description={s.note}>
            <blockquote className="tl__quote">{s.text}</blockquote>
            <div className="plan-actions">
              <Button variant="primary" icon={<Play size={13} />} loading={run.isPending && run.variables === s.key} disabled={run.isPending} onClick={() => run.mutate(s.key)}>
                Run scenario
              </Button>
            </div>
          </Panel>
        ))}
      </div>
    </>
  );
}
