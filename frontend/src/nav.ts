export type Tab =
  | "overview"
  | "approvals"
  | "executions"
  | "actions"
  | "recovery"
  | "policies"
  | "integrations"
  | "team"
  | "billing"
  | "beta"
  | "audit"
  | "sandbox";

export const NAV: Array<{ key: Tab; label: string }> = [
  { key: "overview", label: "Overview" },
  { key: "approvals", label: "Approvals" },
  { key: "executions", label: "Executions" },
  { key: "actions", label: "Actions" },
  { key: "recovery", label: "Recovery" },
  { key: "policies", label: "Policies" },
  { key: "integrations", label: "Integrations" },
  { key: "team", label: "Team" },
  { key: "billing", label: "Billing & usage" },
  { key: "beta", label: "Beta readiness" },
  { key: "audit", label: "Audit log" },
];

export function tabTitle(tab: Tab): string {
  return ({
    overview: "Control overview",
    approvals: "Approval queue",
    executions: "Execution history",
    actions: "External actions",
    recovery: "Recovery console",
    policies: "Deterministic policies",
    integrations: "Connected systems",
    team: "Workspace team",
    billing: "Billing & usage",
    beta: "Private beta readiness",
    audit: "Audit evidence",
    sandbox: "Controlled demo sandbox",
  } as Record<Tab, string>)[tab];
}
