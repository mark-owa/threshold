import { request } from "./client";
import type {
  ActionDetail,
  ActionSummary,
  Approval,
  ApprovalStatus,
  AuditEntry,
  ExecutionDetail,
  ExecutionSummary,
  Metrics,
  ReadinessReport,
  Recovery,
} from "@/types/api";

export const opsApi = {
  metrics: (orgId: string) => request<Metrics>("/ops/metrics", { query: { org_id: orgId } }),

  executions: (orgId: string, limit = 100) =>
    request<ExecutionSummary[]>("/ops/executions", { query: { org_id: orgId, limit } }),

  execution: (orgId: string, id: string) =>
    request<ExecutionDetail>(`/ops/executions/${id}`, { query: { org_id: orgId } }),

  retryExecution: (orgId: string, id: string) =>
    request<{ id: string; status: string; error: string | null }>(`/ops/executions/${id}/retry`, {
      method: "POST",
      query: { org_id: orgId },
    }),

  approvals: (orgId: string, status: ApprovalStatus = "pending") =>
    request<Approval[]>("/ops/approvals", { query: { org_id: orgId, status } }),

  audit: (orgId: string, limit = 200) =>
    request<AuditEntry[]>("/ops/audit", { query: { org_id: orgId, limit } }),

  actions: (orgId: string, limit = 100) =>
    request<ActionSummary[]>("/ops/actions", { query: { org_id: orgId, limit } }),

  action: (orgId: string, id: string) =>
    request<ActionDetail>(`/ops/actions/${id}`, { query: { org_id: orgId } }),

  reconcileAction: (orgId: string, id: string) =>
    request<{ id: string; status: string; verified_at: string | null; next_retry_at: string | null; error: string | null }>(
      `/ops/actions/${id}/reconcile`,
      { method: "POST", query: { org_id: orgId } },
    ),

  recovery: (orgId: string, limit = 100) =>
    request<Recovery>("/ops/recovery", { query: { org_id: orgId, limit } }),

  replayEvent: (orgId: string, id: string) =>
    request<{ event_id: string; status: string }>(`/ops/events/${id}/replay`, {
      method: "POST",
      query: { org_id: orgId },
    }),

  requeueOutbox: (orgId: string, id: string) =>
    request<{ outbox_id: string; status: string }>(`/ops/outbox/${id}/requeue`, {
      method: "POST",
      query: { org_id: orgId },
    }),

  readiness: (orgId: string, probeRuntime: boolean) =>
    request<ReadinessReport>("/ops/beta-readiness", {
      query: { org_id: orgId, probe_runtime: probeRuntime },
    }),

  setLiveExecution: (orgId: string, enabled: boolean) =>
    request<{ organization_id: string; live_execution_enabled: boolean }>(
      "/ops/beta-readiness/live-execution",
      { method: "POST", query: { org_id: orgId }, body: { enabled } },
    ),
};
