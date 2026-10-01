import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { commercialApi } from "@/api/commercial";
import { opsApi } from "@/api/ops";
import { organizationsApi } from "@/api/organizations";
import { workspaceApi } from "@/api/workspace";
import { useWorkspace } from "@/features/auth/session";
import type { ApprovalStatus } from "@/types/api";

const POLL_MS = 30_000;

/**
 * Every workspace-scoped query is keyed by org id first, so switching
 * workspaces can never show another tenant's cached data.
 */
function useOrgQuery<T>(key: unknown[], fn: (orgId: string) => Promise<T>, options: { enabled?: boolean; poll?: boolean; staleTime?: number } = {}): UseQueryResult<T> {
  const { orgId } = useWorkspace();
  return useQuery({
    queryKey: [orgId, ...key],
    queryFn: () => fn(orgId),
    enabled: options.enabled ?? true,
    refetchInterval: options.poll ? POLL_MS : false,
    staleTime: options.staleTime,
  });
}

export const useMetrics = () => useOrgQuery(["metrics"], (o) => opsApi.metrics(o), { poll: true });

export const useExecutions = (limit = 100) => useOrgQuery(["executions", limit], (o) => opsApi.executions(o, limit), { poll: true });

export const useExecution = (id: string) => useOrgQuery(["execution", id], (o) => opsApi.execution(o, id));

export function useApprovals(status: ApprovalStatus = "pending", enabled = true) {
  return useOrgQuery(["approvals", status], (o) => opsApi.approvals(o, status), { enabled, poll: status === "pending" });
}

export const useAudit = (limit = 200) => useOrgQuery(["audit", limit], (o) => opsApi.audit(o, limit));

export const useActions = (limit = 100) => useOrgQuery(["actions", limit], (o) => opsApi.actions(o, limit), { poll: true });

export const useAction = (id: string | null) => useOrgQuery(["action", id], (o) => opsApi.action(o, id as string), { enabled: !!id });

export const useRecovery = (enabled = true) => useOrgQuery(["recovery"], (o) => opsApi.recovery(o), { enabled, poll: true });

export const useReadiness = (probe: boolean, enabled = true) => useOrgQuery(["readiness", probe], (o) => opsApi.readiness(o, probe), { enabled });

export const useOnboarding = () => useOrgQuery(["onboarding"], (o) => workspaceApi.onboarding(o));

export const useWorkflows = () => useOrgQuery(["workflows"], (o) => workspaceApi.workflows(o), { staleTime: 60_000 });

export const usePolicies = () => useOrgQuery(["policies"], (o) => workspaceApi.policies(o));

export const useIntegrations = () => useOrgQuery(["integrations"], (o) => workspaceApi.integrations(o));

export const useWebhookEndpoints = () => useOrgQuery(["webhooks"], (o) => workspaceApi.webhookEndpoints(o));

export const useMembers = () => useOrgQuery(["members"], (o) => organizationsApi.members(o));

export const useInvitations = (enabled = true) => useOrgQuery(["invitations"], (o) => organizationsApi.invitations(o), { enabled });

export const useCommercialStatus = () => useOrgQuery(["commercial"], (o) => commercialApi.status(o));

export function usePlans() {
  return useQuery({ queryKey: ["plans"], queryFn: () => commercialApi.plans(), staleTime: 5 * 60_000 });
}
