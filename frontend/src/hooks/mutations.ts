import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { approvalsApi } from "@/api/approvals";
import { commercialApi, demoApi } from "@/api/commercial";
import { errorMessage } from "@/api/client";
import { opsApi } from "@/api/ops";
import { organizationsApi } from "@/api/organizations";
import { workspaceApi } from "@/api/workspace";
import { useWorkspace } from "@/features/auth/session";
import { useToast } from "@/components/ui/Toast";
import type {
  ApprovalDecisionRequest,
  GenericRestInput,
  RefundPolicyInput,
  Role,
  ShopifyInput,
  StripeInput,
  WebhookEndpointInput,
} from "@/types/api";
import { shortId } from "@/utils/format";

interface Options<R, V> {
  success?: (result: R, vars: V) => { title: string; description?: string } | null;
  errorTitle: string;
  /** Forms render the error inline; set false to avoid also raising a toast. */
  toastError?: boolean;
  /** Invalidate every query of the active workspace afterwards (default true). */
  invalidate?: boolean;
}

/**
 * Wraps a mutation with workspace scoping, cache invalidation and consistent
 * success/error feedback so pages don't repeat that logic.
 */
function useOrgMutation<V, R>(fn: (orgId: string, vars: V) => Promise<R>, options: Options<R, V>) {
  const { orgId } = useWorkspace();
  const queryClient = useQueryClient();
  const toast = useToast();
  return useMutation<R, Error, V>({
    mutationFn: (vars) => fn(orgId, vars),
    onSuccess: (result, vars) => {
      if (options.invalidate !== false) void queryClient.invalidateQueries({ queryKey: [orgId] });
      const message = options.success?.(result, vars);
      if (message) toast.success(message.title, message.description);
    },
    onError: (error) => {
      if (options.toastError !== false) toast.error(options.errorTitle, errorMessage(error));
    },
  });
}

// ── Approvals ───────────────────────────────────────────────────────────────
export const useDecideApproval = () =>
  useOrgMutation<{ id: string; body: ApprovalDecisionRequest }, { execution_id: string; status: string }>(
    (orgId, { id, body }) => approvalsApi.decide(orgId, id, body),
    {
      errorTitle: "Couldn't record the decision",
      toastError: false,
      success: (_r, { body }) => ({
        title: body.decision === "rejected" ? "Approval rejected" : body.decision === "modified" ? "Approved with changes" : "Approval submitted",
        description: body.decision === "rejected" ? "The action will not be executed." : "The workflow has resumed.",
      }),
    },
  );

// ── Executions & recovery ───────────────────────────────────────────────────
export const useRetryExecution = () =>
  useOrgMutation((orgId, id: string) => opsApi.retryExecution(orgId, id), {
    errorTitle: "Couldn't retry the execution",
    success: (r, id) => ({ title: "Retry requested", description: `Execution ${shortId(id)} is now ${r.status.replace(/_/g, " ")}.` }),
  });

export const useReconcileAction = () =>
  useOrgMutation((orgId, id: string) => opsApi.reconcileAction(orgId, id), {
    errorTitle: "Couldn't reconcile the action",
    success: (r) => ({ title: "Reconciliation complete", description: `Action is now ${r.status.replace(/_/g, " ")}.` }),
  });

export const useReplayEvent = () =>
  useOrgMutation((orgId, id: string) => opsApi.replayEvent(orgId, id), {
    errorTitle: "Couldn't replay the event",
    success: () => ({ title: "Event replayed" }),
  });

export const useRequeueOutbox = () =>
  useOrgMutation((orgId, id: string) => opsApi.requeueOutbox(orgId, id), {
    errorTitle: "Couldn't requeue the delivery",
    success: () => ({ title: "Delivery requeued" }),
  });

export const useSetLiveExecution = () =>
  useOrgMutation((orgId, enabled: boolean) => opsApi.setLiveExecution(orgId, enabled), {
    errorTitle: "Couldn't change live execution",
    toastError: false,
    success: (r) => ({ title: r.live_execution_enabled ? "Live execution enabled" : "Live execution disabled" }),
  });

// ── Policies & integrations ─────────────────────────────────────────────────
export const useSaveRefundPolicy = () =>
  useOrgMutation((orgId, input: RefundPolicyInput) => workspaceApi.saveRefundPolicy(orgId, input), {
    errorTitle: "Couldn't save the policy",
    toastError: false,
    success: () => ({ title: "Policy updated" }),
  });

export const useSaveGenericRest = () =>
  useOrgMutation((orgId, input: GenericRestInput) => workspaceApi.saveGenericRest(orgId, input), {
    errorTitle: "Couldn't save the integration",
    toastError: false,
    success: () => ({ title: "Integration saved", description: "Generic REST settings were updated." }),
  });

export const useSaveShopify = () =>
  useOrgMutation((orgId, input: ShopifyInput) => workspaceApi.saveShopify(orgId, input), {
    errorTitle: "Couldn't save the integration",
    toastError: false,
    success: () => ({ title: "Integration saved", description: "Shopify settings were updated." }),
  });

export const useSaveStripe = () =>
  useOrgMutation((orgId, input: StripeInput) => workspaceApi.saveStripe(orgId, input), {
    errorTitle: "Couldn't save the integration",
    toastError: false,
    success: () => ({ title: "Integration saved", description: "Stripe settings were updated." }),
  });

export const useSyncShopifyOrder = () =>
  useOrgMutation((orgId, orderNumber: string) => workspaceApi.syncShopifyOrder(orgId, orderNumber), {
    errorTitle: "Couldn't sync the order",
    toastError: false,
    invalidate: false,
    success: (r) => ({ title: "Order synced", description: `Order ${r.order_number} was fetched from Shopify.` }),
  });

export const useCreateWebhook = () =>
  useOrgMutation((orgId, input: WebhookEndpointInput) => workspaceApi.createWebhookEndpoint(orgId, input), {
    errorTitle: "Couldn't create the endpoint",
    toastError: false,
    success: (r) => ({ title: "Webhook endpoint created", description: r.name }),
  });

export const useDisableWebhook = () =>
  useOrgMutation((orgId, id: string) => workspaceApi.disableWebhookEndpoint(orgId, id), {
    errorTitle: "Couldn't disable the endpoint",
    toastError: false,
    success: () => ({ title: "Webhook endpoint disabled" }),
  });

// ── Team ────────────────────────────────────────────────────────────────────
export const useInviteMember = () =>
  useOrgMutation((orgId, input: { email: string; role: Role }) => organizationsApi.invite(orgId, input), {
    errorTitle: "Couldn't create the invitation",
    toastError: false,
    success: (r) => ({ title: "Invitation created", description: r.email }),
  });

export const useRevokeInvitation = () =>
  useOrgMutation((orgId, id: string) => organizationsApi.revokeInvitation(orgId, id), {
    errorTitle: "Couldn't revoke the invitation",
    success: () => ({ title: "Invitation revoked" }),
  });

export const useUpdateMemberRole = () =>
  useOrgMutation((orgId, v: { membershipId: string; role: Role }) => organizationsApi.updateMemberRole(orgId, v.membershipId, v.role), {
    errorTitle: "Couldn't change the role",
    success: (r) => ({ title: "Role updated", description: `${r.full_name} is now ${r.role}.` }),
  });

export const useRemoveMember = () =>
  useOrgMutation((orgId, membershipId: string) => organizationsApi.removeMember(orgId, membershipId), {
    errorTitle: "Couldn't remove the member",
    toastError: false,
    success: () => ({ title: "Member removed" }),
  });

// ── Billing & demo ──────────────────────────────────────────────────────────
export const useCheckout = () =>
  useOrgMutation((orgId, plan: string) => commercialApi.checkout(orgId, plan), {
    errorTitle: "Couldn't start checkout",
    invalidate: false,
  });

export const useBillingPortal = () =>
  useOrgMutation((orgId, _: void) => commercialApi.portal(orgId), {
    errorTitle: "Couldn't open the billing portal",
    invalidate: false,
  });

export function useRunDemo() {
  const navigate = useNavigate();
  return useOrgMutation((orgId, scenario: string) => demoApi.run(orgId, scenario), {
    errorTitle: "Couldn't run the scenario",
    success: (r) => {
      navigate(`/executions/${r.execution_id}`);
      return { title: "Scenario started", description: `Execution ${shortId(r.execution_id)} is ${r.status.replace(/_/g, " ")}.` };
    },
  });
}
