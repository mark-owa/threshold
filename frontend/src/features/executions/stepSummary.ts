import type { JsonObject, StepExecution } from "@/types/api";
import { formatCurrency, formatPercent, humanize } from "@/utils/format";
import { extractRiskFactors, riskFactorText } from "@/utils/status";

function obj(value: unknown): JsonObject | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as JsonObject) : null;
}

/**
 * One line explaining what a step decided, derived from its real output. Falls
 * back to a generic key/value preview so unknown outputs are never hidden.
 */
export function summarizeStep(step: StepExecution): string | null {
  const out = step.output ?? {};
  switch (step.step_type) {
    case "ai_classify": {
      const confidence = typeof out.ai_confidence === "number" ? ` · ${formatPercent(Math.round(out.ai_confidence * 100))} confidence` : "";
      return out.category ? `Classified as ${humanize(String(out.category)).toLowerCase()}${confidence}` : null;
    }
    case "ai_extract": {
      const extracted = obj(out.extracted);
      if (!extracted) return null;
      const parts: string[] = [];
      if (extracted.order_number) parts.push(`Order ${extracted.order_number}`);
      if (typeof extracted.amount_usd === "number") parts.push(formatCurrency(extracted.amount_usd));
      return parts.length ? `Extracted ${parts.join(" · ")}` : "Extracted fields from the message";
    }
    case "knowledge_lookup": {
      const policy = obj(out.policy);
      const title = out.policy_title ? String(out.policy_title) : "Policy";
      if (!policy) return title;
      const bits: string[] = [];
      if (typeof policy.refund_window_days === "number") bits.push(`${policy.refund_window_days}-day window`);
      if (typeof policy.max_auto_refund_usd === "number") bits.push(`auto-approves up to ${formatCurrency(policy.max_auto_refund_usd)}`);
      return bits.length ? `${title}: ${bits.join(", ")}` : title;
    }
    case "business_rule": {
      const rule = obj(out.rule_result);
      if (!rule) return null;
      const reason = rule.reason ? humanize(String(rule.reason)) : "Evaluated";
      return rule.allowed === false ? `Not allowed: ${reason.toLowerCase()}` : rule.allowed === true ? `Allowed: ${reason.toLowerCase()}` : reason;
    }
    case "risk_assessment": {
      const level = out.risk_level ? String(out.risk_level) : null;
      const factors = extractRiskFactors(out.risk_factors);
      if (!level) return null;
      return factors.length ? `${humanize(level)} risk: ${factors.map(riskFactorText).join(" ").replace(/\.$/, "")}` : `${humanize(level)} risk, no risk factors`;
    }
    case "approval_gate":
      if (out.approval_required === true) return step.status === "awaiting_approval" ? "Waiting for a reviewer" : "A reviewer decision was required";
      if (out.approval_required === false) return "No approval required";
      return null;
    case "notification": {
      const n = obj(out.notification);
      return n ? `Notification ${String(n.status ?? "recorded")}${n.recipient ? ` to ${n.recipient}` : ""}` : null;
    }
    default: {
      const preview = Object.entries(out)
        .filter(([, v]) => ["string", "number", "boolean"].includes(typeof v))
        .slice(0, 3)
        .map(([k, v]) => `${humanize(k)}: ${v}`);
      return preview.length ? preview.join(" · ") : null;
    }
  }
}
