import type { ApiRequest } from "./api";
import type {
  Approval,
  AuditEntry,
  BetaReadinessReport,
  CommercialStatus,
  ExecutionSummary,
  ExternalAction,
  Integration,
  Invitation,
  Member,
  Metrics,
  Onboarding,
  Policy,
  Recovery,
  WebhookEndpoint,
  WorkflowDefinition,
} from "./types";

// Everything the dashboard shows for one workspace, loaded together by refresh().
export interface WorkspaceData {
  metrics: Metrics | null;
  approvals: Approval[];
  executions: ExecutionSummary[];
  actions: ExternalAction[];
  recovery: Recovery;
  audit: AuditEntry[];
  policies: Policy[];
  integrations: Integration[];
  webhookEndpoints: WebhookEndpoint[];
  workflows: WorkflowDefinition[];
  onboarding: Onboarding | null;
  commercial: CommercialStatus | null;
  betaReadiness: BetaReadinessReport | null;
  members: Member[];
  invitations: Invitation[];
}

export const EMPTY_WORKSPACE_DATA: WorkspaceData = {
  metrics: null,
  approvals: [],
  executions: [],
  actions: [],
  recovery: { events: [], outbox: [], actions: [] },
  audit: [],
  policies: [],
  integrations: [],
  webhookEndpoints: [],
  workflows: [],
  onboarding: null,
  commercial: null,
  betaReadiness: null,
  members: [],
  invitations: [],
};

export interface LoadResult {
  data: WorkspaceData;
  unauthorized: boolean; // any request came back 401: the session has expired
  complete: boolean; // every request succeeded, or was refused as 403 (role-gated)
}

// Fetches every workspace slice in parallel. A slice that fails to load (for
// example a 403 for a role that cannot see it) falls back to its empty value
// rather than failing the whole refresh.
export async function loadWorkspaceData(
  request: ApiRequest,
  orgId: string,
  accessToken: string
): Promise<LoadResult> {
  const paths = [
    `/api/v1/ops/metrics?org_id=${orgId}`,
    `/api/v1/ops/approvals?org_id=${orgId}`,
    `/api/v1/ops/executions?org_id=${orgId}&limit=30`,
    `/api/v1/ops/actions?org_id=${orgId}&limit=50`,
    `/api/v1/ops/recovery?org_id=${orgId}&limit=50`,
    `/api/v1/ops/audit?org_id=${orgId}&limit=30`,
    `/api/v1/workspace/policies?org_id=${orgId}`,
    `/api/v1/workspace/integrations?org_id=${orgId}`,
    `/api/v1/workspace/webhook-endpoints?org_id=${orgId}`,
    `/api/v1/workspace/workflows?org_id=${orgId}`,
    `/api/v1/workspace/onboarding?org_id=${orgId}`,
    `/api/v1/commercial/status?org_id=${orgId}`,
    `/api/v1/ops/beta-readiness?org_id=${orgId}&probe_runtime=false`,
    `/api/v1/organizations/${orgId}/members`,
    `/api/v1/organizations/${orgId}/invitations`,
  ];
  const responses = await Promise.all(paths.map(path => request(path, {}, accessToken)));
  const unauthorized = responses.some(res => res.status === 401);
  const complete = responses.every(res => res.ok || res.status === 403);
  if (unauthorized) return { data: EMPTY_WORKSPACE_DATA, unauthorized, complete };

  const [m, a, e, ac, rc, au, p, i, wh, w, o, c, br, tm, inv] = responses;
  const slice = async <T>(res: Response, empty: T): Promise<T> =>
    res.ok ? ((await res.json()) as T) : empty;

  const data: WorkspaceData = {
    metrics: await slice<Metrics | null>(m, null),
    approvals: await slice<Approval[]>(a, []),
    executions: await slice<ExecutionSummary[]>(e, []),
    actions: await slice<ExternalAction[]>(ac, []),
    recovery: await slice<Recovery>(rc, EMPTY_WORKSPACE_DATA.recovery),
    audit: await slice<AuditEntry[]>(au, []),
    policies: await slice<Policy[]>(p, []),
    integrations: await slice<Integration[]>(i, []),
    webhookEndpoints: await slice<WebhookEndpoint[]>(wh, []),
    workflows: await slice<WorkflowDefinition[]>(w, []),
    onboarding: await slice<Onboarding | null>(o, null),
    commercial: await slice<CommercialStatus | null>(c, null),
    betaReadiness: await slice<BetaReadinessReport | null>(br, null),
    members: await slice<Member[]>(tm, []),
    invitations: await slice<Invitation[]>(inv, []),
  };
  return { data, unauthorized, complete };
}
