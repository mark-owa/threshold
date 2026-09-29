// Shapes of the JSON the Threshold API returns, taken from the backend's route
// serializers (backend/app/api/*.py). They are compile-time claims only: the
// responses are not validated at runtime, so a backend change that alters a
// shape will not be caught until the field is read.

export type MemberRole = "owner" | "admin" | "reviewer" | "viewer";
export type RiskLevel = "low" | "medium" | "high";

export type ExecutionStatus =
  | "pending"
  | "running"
  | "awaiting_approval"
  | "waiting_external"
  | "completed"
  | "failed"
  | "cancelled";

export type ActionStatus =
  | "pending"
  | "executing"
  | "succeeded"
  | "failed"
  | "retrying"
  | "dead_letter"
  | "rolled_back"
  | "unknown";

export type ApprovalDecision = "approved" | "rejected";

// --- Session -------------------------------------------------------------

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  plan: string;
  role: MemberRole;
  is_active: boolean;
}

export interface CurrentUser {
  user_id: string;
  email: string;
  full_name: string;
  memberships: Array<Record<string, unknown>>;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface AuthWithWorkspaceResponse extends TokenResponse {
  organization_id: string;
  role?: MemberRole; // present on the invitation-join response only
}

// --- Operations ----------------------------------------------------------

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
  estimated_hours_saved: number;
}

export interface Approval {
  id: string;
  execution_id: string;
  status: string;
  risk_level: RiskLevel;
  risk_factors: unknown;
  reason: string;
  proposed_action: { action_type?: string } | null;
  generated_parameters: Record<string, unknown> | null;
  created_at: string;
}

export interface ExecutionSummary {
  id: string;
  status: ExecutionStatus;
  workflow_id: string;
  current_step: string | null;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
}

export interface StepRecord {
  id: string;
  step_key: string;
  step_type: string;
  status: string;
  latency_ms: number | null;
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  error: string | null;
}

export interface ExecutionDetail extends ExecutionSummary {
  context: Record<string, unknown>;
  steps: StepRecord[];
}

export interface ExternalAction {
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

export interface RecoveryEvent {
  id: string;
  external_id: string | null;
  status: string;
  attempts: number;
  max_attempts: number;
  next_retry_at: string | null;
  error: string | null;
  updated_at: string;
}

export interface RecoveryOutboxMessage {
  id: string;
  topic: string;
  aggregate_type: string;
  aggregate_id: string;
  status: string;
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
  outbox: RecoveryOutboxMessage[];
  actions: RecoveryAction[];
}

export interface AuditEntry {
  id: string;
  execution_id: string | null;
  event_type: string;
  actor_type: string;
  actor_id: string | null;
  payload: Record<string, unknown>;
  created_at: string | null;
}

// --- Workspace configuration ---------------------------------------------

export interface WorkflowDefinition {
  id: string;
  key: string;
  name: string;
  description: string | null;
  version: number;
  trigger_category: string;
  is_active: boolean;
  scope: string;
}

export interface PolicyRules {
  refund_window_days?: number;
  max_auto_refund_usd?: number;
  [rule: string]: unknown;
}

export interface Policy {
  id: string;
  category: string;
  title: string;
  content: string;
  structured_rules: PolicyRules | null;
  updated_at: string;
}

export interface IntegrationConfig {
  base_url?: string;
  refund_path?: string;
  verify_path_template?: string;
  reconcile_path_template?: string;
  shop_domain?: string;
  webhook_secret_ref?: string;
  refund_enabled?: boolean;
  [key: string]: unknown;
}

export interface Integration {
  id: string;
  provider: string;
  is_enabled: boolean;
  config: IntegrationConfig | null;
  credential_configured: boolean;
  health: string;
  consecutive_failures: number;
  failure_threshold: number;
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

export interface OnboardingStep {
  key: string;
  title: string;
  description: string;
  complete: boolean;
}

export interface Onboarding {
  organization_id: string;
  plan: string;
  role: MemberRole;
  steps: OnboardingStep[];
  completed_steps: number;
  total_steps: number;
  percent_complete: number;
  ready_for_live_execution: boolean;
}

export interface Member {
  membership_id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: MemberRole;
}

export interface Invitation {
  id: string;
  email: string;
  role: MemberRole;
  status: string;
  expires_at: string;
  accepted_at: string | null;
}

// --- Billing and launch gate ---------------------------------------------

export interface PlanLimits {
  workflow_executions: number | null;
  external_actions: number | null;
  team_members: number | null;
}

export interface CommercialStatus {
  plan: string;
  plan_definition: { name: string; limits: PlanLimits; features: string[] } | null;
  subscription_status: string;
  trial_ends_at: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  usage_period: string;
  usage: Record<string, number>;
  billing_configured: boolean;
  shopify_oauth_configured: boolean;
}

export type ReadinessLevel = "pass" | "warn" | "block";

export interface ReadinessCheck {
  key: string;
  title: string;
  level: ReadinessLevel;
  detail: string;
  category: string;
}

export interface BetaReadinessReport {
  ready: boolean;
  generated_at: string;
  summary: { pass: number; warn: number; block: number };
  checks: ReadinessCheck[];
}

// --- Request bodies the dashboard sends -----------------------------------

export interface RefundPolicyInput {
  title: string;
  content: string;
  refund_window_days: number;
  max_auto_refund_usd: number;
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

export interface WebhookEndpointInput {
  name: string;
  signing_secret_ref: string;
  allowed_clock_skew_seconds: number;
}

// --- Small mutation responses ---------------------------------------------

export interface StatusResponse {
  status: string;
}

export interface DemoRunResponse {
  execution_id: string;
  status: string;
}

export interface ApprovalDecisionResponse {
  approval_id: string;
  execution_id: string;
  status: string;
  reviewer_id: string;
}

export interface InvitationCreated {
  id: string;
  email: string;
  role: MemberRole;
  expires_at: string;
  invitation_token: string;
  delivery: string;
}

export interface SyncedOrder {
  id: string;
  order_number: string;
  external_order_id: string;
  currency: string;
  total: number;
  refunded: number;
  refundable: number;
  payment_reference_configured: boolean;
}
