/**
 * Types mirroring the Threshold FastAPI responses. Enum values are the exact
 * strings the backend emits (see backend/app/models/enums.py); nothing is
 * renamed or reinterpreted on the client.
 */

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };

// ── Identity & tenancy ──────────────────────────────────────────────────────
export type Role = "owner" | "admin" | "reviewer" | "viewer";

export interface Me {
  user_id: string;
  email: string;
  full_name: string;
  memberships: { organization_id: string; role: Role }[];
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  plan: string;
  role: Role;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}
export interface RegisterResponse extends TokenResponse {
  organization_id: string;
}
export interface JoinResponse extends TokenResponse {
  organization_id: string;
  role: Role;
}

// ── Enums ───────────────────────────────────────────────────────────────────
export type WorkflowStatus =
  | "pending"
  | "running"
  | "awaiting_approval"
  | "waiting_external"
  | "completed"
  | "failed"
  | "cancelled";

export type StepType =
  | "ai_classify"
  | "ai_extract"
  | "knowledge_lookup"
  | "business_rule"
  | "risk_assessment"
  | "approval_gate"
  | "action_execute"
  | "verification"
  | "notification";

export type StepStatus =
  | "pending"
  | "running"
  | "succeeded"
  | "failed"
  | "skipped"
  | "awaiting_approval";

export type RiskLevel = "low" | "medium" | "high";

export type ApprovalStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "modified"
  | "escalated"
  | "expired";

export type ActionStatus =
  | "pending"
  | "executing"
  | "succeeded"
  | "failed"
  | "retrying"
  | "dead_letter"
  | "rolled_back"
  | "unknown";

export type EventProcessingStatus =
  | "received"
  | "processing"
  | "normalized"
  | "routed"
  | "completed"
  | "failed"
  | "dead_letter"
  | "duplicate";

export type OutboxStatus = "pending" | "processing" | "sent" | "failed" | "dead_letter";

export type IntegrationProvider =
  | "mock_email"
  | "mock_crm"
  | "mock_slack"
  | "mock_payments"
  | "generic_rest"
  | "shopify"
  | "stripe";

export type InvitationStatus = "pending" | "accepted" | "expired" | "revoked";

// ── Ops ─────────────────────────────────────────────────────────────────────
export interface Metrics {
  total_executions: number;
  completed: number;
  failed: number;
  awaiting_approval: number;
  waiting_external: number;
  automation_rate_percent: number;
  approval_rate_percent: number;
  workflow_success_rate_percent: number;
  average_step_latency_ms: number;
  estimated_ai_cost_usd: number;
  /** A fixed heuristic (automatic runs × 0.25h). Deliberately not surfaced as a KPI. */
  estimated_hours_saved: number;
}

export interface ExecutionSummary {
  id: string;
  status: WorkflowStatus;
  workflow_id: string;
  current_step: string | null;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
}

export interface StepExecution {
  id: string;
  step_key: string;
  step_type: StepType;
  status: StepStatus;
  latency_ms: number | null;
  input: JsonObject | null;
  output: JsonObject | null;
  error: string | null;
}

export interface ExecutionContext {
  event?: { text?: string; sender?: string; external_id?: string | null; [key: string]: JsonValue | undefined };
  category?: string;
  ai_confidence?: number;
  ai_rationale?: string;
  risk_level?: RiskLevel;
  risk_factors?: string[];
  approval_required?: boolean;
  [key: string]: unknown;
}

export interface ExecutionDetail extends ExecutionSummary {
  context: ExecutionContext;
  steps: StepExecution[];
}

export interface Approval {
  id: string;
  execution_id: string;
  status: ApprovalStatus;
  risk_level: RiskLevel;
  risk_factors: { factors?: string[] } | JsonValue[] | null;
  reason: string;
  proposed_action: { action_type?: string; [key: string]: JsonValue | undefined } | null;
  generated_parameters: JsonObject | null;
  created_at: string;
}

export interface ApprovalDecisionRequest {
  decision: "approved" | "rejected" | "modified";
  notes?: string | null;
  modified_parameters?: JsonObject | null;
}
export interface ApprovalDecisionResult {
  approval_id: string;
  execution_id: string;
  status: WorkflowStatus;
  reviewer_id: string;
}

export interface AuditEntry {
  id: string;
  execution_id: string | null;
  event_type: string;
  actor_type: string;
  actor_id: string | null;
  payload: JsonObject | null;
  created_at: string;
}

export interface ActionSummary {
  id: string;
  execution_id: string;
  action_type: string;
  status: ActionStatus;
  attempt_count: number;
  max_attempts: number;
  verified_at: string | null;
  next_retry_at: string | null;
  error: string | null;
  created_at: string;
}

export interface ActionAttempt {
  id: string;
  attempt_number: number;
  operation: string;
  provider: string;
  provider_operation_id: string | null;
  outcome: string;
  response_payload: JsonObject | null;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface ActionDetail {
  id: string;
  execution_id: string;
  action_type: string;
  status: ActionStatus;
  idempotency_key: string;
  request_payload: JsonObject | null;
  response_payload: JsonObject | null;
  verified_at: string | null;
  error: string | null;
  attempts: ActionAttempt[];
}

export interface RecoveryEvent {
  id: string;
  external_id: string | null;
  status: EventProcessingStatus;
  attempts: number;
  max_attempts: number;
  next_retry_at: string | null;
  error: string | null;
  updated_at: string;
}
export interface RecoveryOutbox {
  id: string;
  topic: string;
  aggregate_type: string;
  aggregate_id: string;
  status: OutboxStatus;
  attempts: number;
  max_attempts: number;
  available_at: string | null;
  locked_at: string | null;
  error: string | null;
  updated_at: string;
}
export interface RecoveryAction {
  id: string;
  action_type: string;
  status: ActionStatus;
  attempts: number;
  max_attempts: number;
  next_retry_at: string | null;
  locked_at: string | null;
  error: string | null;
  updated_at: string;
}
export interface Recovery {
  events: RecoveryEvent[];
  outbox: RecoveryOutbox[];
  actions: RecoveryAction[];
}

export type ReadinessLevel = "pass" | "warn" | "block";
export interface ReadinessCheck {
  key: string;
  title: string;
  level: ReadinessLevel;
  detail: string;
  category: string;
}
export interface ReadinessReport {
  ready: boolean;
  generated_at: string;
  organization_id: string;
  summary: { pass: number; warn: number; block: number };
  checks: ReadinessCheck[];
}

// ── Workspace configuration ─────────────────────────────────────────────────
export interface WorkflowDefinition {
  id: string;
  key: string;
  name: string;
  description: string | null;
  version: number;
  trigger_category: string;
  is_active: boolean;
  scope: "workspace" | "template";
}

export interface Policy {
  id: string;
  category: string;
  title: string;
  content: string;
  structured_rules: JsonObject | null;
  updated_at: string | null;
}

export interface RefundPolicyInput {
  title: string;
  content: string;
  refund_window_days: number;
  max_auto_refund_usd: number;
}

export interface Integration {
  id: string;
  provider: IntegrationProvider;
  is_enabled: boolean;
  config: JsonObject | null;
  credential_configured: boolean;
  health: "available" | "circuit_open";
  consecutive_failures: number;
  failure_threshold: number;
}

export interface GenericRestInput {
  base_url: string;
  refund_path: string;
  verify_path_template: string;
  reconcile_path_template: string;
  credential_ref: string | null;
  timeout_seconds: number;
  failure_threshold: number;
  recovery_timeout_seconds: number;
  is_enabled: boolean;
}
export interface ShopifyInput {
  shop_domain: string;
  credential_ref: string;
  webhook_secret_ref: string | null;
  api_version: string;
  timeout_seconds: number;
  refund_enabled: boolean;
  is_enabled: boolean;
}
export interface StripeInput {
  credential_ref: string;
  api_version: string | null;
  timeout_seconds: number;
  refund_enabled: boolean;
  is_enabled: boolean;
}

export interface ShopifyOrderSync {
  id: string;
  order_number: string;
  external_order_id: string;
  currency: string;
  total: number;
  refunded: number;
  refundable: number;
  payment_reference_configured: boolean;
}

export interface WebhookEndpoint {
  id: string;
  name: string;
  endpoint_key: string;
  path: string;
  signing_secret_ref: string;
  is_active: boolean;
  allowed_clock_skew_seconds: number;
  created_at: string;
}
export interface WebhookEndpointInput {
  name: string;
  signing_secret_ref: string;
  allowed_clock_skew_seconds: number;
}

export interface OnboardingStep {
  key: string;
  title: string;
  complete: boolean;
  description: string;
}
export interface Onboarding {
  organization_id: string;
  plan: string;
  role: Role;
  steps: OnboardingStep[];
  completed_steps: number;
  total_steps: number;
  percent_complete: number;
  ready_for_live_execution: boolean;
}

// ── Team ────────────────────────────────────────────────────────────────────
export interface Member {
  membership_id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: Role;
}
export interface Invitation {
  id: string;
  email: string;
  role: Role;
  status: InvitationStatus;
  expires_at: string;
  accepted_at: string | null;
}
export interface CreatedInvitation {
  id: string;
  email: string;
  role: Role;
  expires_at: string;
  invitation_token: string;
  delivery: string;
}

// ── Commercial ──────────────────────────────────────────────────────────────
export interface PlanDefinition {
  name: string;
  monthly_price_usd: number | null;
  limits: {
    workflow_executions: number | null;
    external_actions: number | null;
    team_members: number | null;
  };
  features: string[];
}
export interface CommercialStatus {
  plan: string;
  plan_definition: PlanDefinition | null;
  subscription_status: string;
  trial_ends_at: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  usage_period: string;
  usage: Record<string, number>;
  billing_configured: boolean;
  shopify_oauth_configured: boolean;
}

export interface DemoRunResult {
  execution_id: string;
  status: WorkflowStatus;
  scenario: string;
}
