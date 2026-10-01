import type {
  ActionStatus,
  ApprovalStatus,
  EventProcessingStatus,
  InvitationStatus,
  OutboxStatus,
  RiskLevel,
  Role,
  StepStatus,
  StepType,
  WorkflowStatus,
} from "@/types/api";
import { humanize } from "./format";

export type Tone = "success" | "warning" | "danger" | "info" | "neutral";

export interface StatusView {
  label: string;
  tone: Tone;
}

/**
 * Tone for every backend enum. Labels are the backend value, humanised, so a
 * status is never silently renamed. Unknown values fall back to neutral.
 */
const WORKFLOW: Record<WorkflowStatus, Tone> = {
  completed: "success",
  running: "info",
  pending: "neutral",
  awaiting_approval: "warning",
  waiting_external: "info",
  failed: "danger",
  cancelled: "neutral",
};

const STEP: Record<StepStatus, Tone> = {
  succeeded: "success",
  running: "info",
  pending: "neutral",
  skipped: "neutral",
  awaiting_approval: "warning",
  failed: "danger",
};

const ACTION: Record<ActionStatus, Tone> = {
  succeeded: "success",
  executing: "info",
  pending: "neutral",
  retrying: "warning",
  unknown: "warning",
  failed: "danger",
  dead_letter: "danger",
  rolled_back: "neutral",
};

const APPROVAL: Record<ApprovalStatus, Tone> = {
  pending: "warning",
  approved: "success",
  modified: "info",
  rejected: "danger",
  escalated: "warning",
  expired: "neutral",
};

const RISK: Record<RiskLevel, Tone> = { low: "success", medium: "warning", high: "danger" };

const EVENT: Record<EventProcessingStatus, Tone> = {
  received: "neutral",
  processing: "info",
  normalized: "info",
  routed: "info",
  completed: "success",
  failed: "danger",
  dead_letter: "danger",
  duplicate: "neutral",
};

const OUTBOX: Record<OutboxStatus, Tone> = {
  pending: "neutral",
  processing: "info",
  sent: "success",
  failed: "danger",
  dead_letter: "danger",
};

const INVITATION: Record<InvitationStatus, Tone> = {
  pending: "warning",
  accepted: "success",
  expired: "neutral",
  revoked: "neutral",
};

function lookup<T extends string>(table: Record<T, Tone>, value: string): StatusView {
  return { label: humanize(value), tone: table[value as T] ?? "neutral" };
}

export const statusOf = {
  workflow: (v: string) => lookup(WORKFLOW, v),
  step: (v: string) => lookup(STEP, v),
  action: (v: string) => lookup(ACTION, v),
  approval: (v: string) => lookup(APPROVAL, v),
  risk: (v: string) => ({ ...lookup(RISK, v), label: `${humanize(v)} risk` }),
  event: (v: string) => lookup(EVENT, v),
  outbox: (v: string) => lookup(OUTBOX, v),
  invitation: (v: string) => lookup(INVITATION, v),
};

export type StatusKind = keyof typeof statusOf;

export const WORKFLOW_STATUSES = Object.keys(WORKFLOW) as WorkflowStatus[];

// ── Roles ───────────────────────────────────────────────────────────────────
export const ROLE_LABEL: Record<Role, string> = {
  owner: "Owner",
  admin: "Admin",
  reviewer: "Reviewer",
  viewer: "Viewer",
};

export const ROLE_DESCRIPTION: Record<Role, string> = {
  owner: "Full control, including billing and enabling live execution.",
  admin: "Manages team, policies, integrations, and recovery.",
  reviewer: "Approves or rejects actions and can retry failed work.",
  viewer: "Read-only access to executions, audit, and configuration.",
};

// ── Workflow step vocabulary ────────────────────────────────────────────────
/** Who or what decides at each step. Derived from the backend step type. */
export type StepActor = "ai" | "rules" | "human" | "external" | "system";

export interface StepMeta {
  title: string;
  actor: StepActor;
  description: string;
}

export const STEP_META: Record<StepType, StepMeta> = {
  ai_classify: {
    title: "Classify request",
    actor: "ai",
    description: "The AI model proposes a request category. It cannot take actions.",
  },
  ai_extract: {
    title: "Extract details",
    actor: "ai",
    description: "The AI model pulls structured fields out of the message.",
  },
  knowledge_lookup: {
    title: "Load policy",
    actor: "rules",
    description: "Fetches the workspace policy that applies to this category.",
  },
  business_rule: {
    title: "Check eligibility",
    actor: "rules",
    description: "Deterministic business rules verify the order and amount.",
  },
  risk_assessment: {
    title: "Assess risk",
    actor: "rules",
    description: "Deterministic thresholds decide whether a human must review.",
  },
  approval_gate: {
    title: "Approval gate",
    actor: "human",
    description: "Pauses for a reviewer when policy requires it.",
  },
  action_execute: {
    title: "Execute action",
    actor: "external",
    description: "Calls the external provider with a durable idempotency key.",
  },
  verification: {
    title: "Verify outcome",
    actor: "external",
    description: "Confirms the provider actually recorded the action.",
  },
  notification: {
    title: "Notify",
    actor: "system",
    description: "Records the outcome for the requester or team.",
  },
};

export const ACTOR_LABEL: Record<StepActor, string> = {
  ai: "AI",
  rules: "Deterministic",
  human: "Human",
  external: "External",
  system: "System",
};

export function stepMeta(type: string): StepMeta {
  return (
    STEP_META[type as StepType] ?? { title: humanize(type), actor: "system", description: "" }
  );
}

// ── Risk factors ────────────────────────────────────────────────────────────
const RISK_FACTOR_TEXT: Record<string, string> = {
  amount_exceeds_auto_approval_limit: "The amount is above the automatic approval limit.",
  amount_missing: "No refund amount could be determined from the request.",
  order_not_found: "The referenced order could not be found.",
  outside_refund_window: "The order is outside the refund window.",
  low_ai_confidence: "The AI model reported low confidence.",
  policy_failed: "The request did not satisfy the workspace policy.",
};

export function riskFactorText(factor: string): string {
  return RISK_FACTOR_TEXT[factor] ?? humanize(factor);
}

export function extractRiskFactors(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((v): v is string => typeof v === "string");
  if (value && typeof value === "object" && "factors" in value) {
    const factors = (value as { factors?: unknown }).factors;
    if (Array.isArray(factors)) return factors.filter((v): v is string => typeof v === "string");
  }
  return [];
}
