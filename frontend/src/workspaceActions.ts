import { CONNECTION_ERROR, jsonBody, parseResponse } from "./api";
import type { ApiRequest } from "./api";
import type { Tab } from "./nav";
import type {
  ApprovalDecision,
  ApprovalDecisionResponse,
  DemoRunResponse,
  ExecutionDetail,
  GenericRestInput,
  InvitationCreated,
  RefundPolicyInput,
  ShopifyInput,
  StatusResponse,
  StripeInput,
  SyncedOrder,
  WebhookEndpointInput,
} from "./types";

export interface ActionContext {
  request: ApiRequest;
  orgId: string;
  isDemo: boolean;
  setStatus: (message: string) => void;
  refresh: () => Promise<void>;
  setExecution: (execution: ExecutionDetail) => void;
  setActiveTab: (tab: Tab) => void;
  setLatestInviteToken: (token: string) => void;
}

interface Mutation {
  pending: string;
  path: string;
  method: "POST" | "PUT" | "PATCH" | "DELETE";
  payload?: unknown;
  failure: string; // "<failure> (<http status>)." is shown if the API gives no detail
  success: string;
  beforeRefresh?: () => void;
}

// Every operational action the dashboard can take on the active workspace.
// Each handler sets a status message, calls the API, and reports the outcome;
// none of them throws -- a network failure becomes a status message.
// (A plain factory, not a React hook: it holds no state of its own, so it is
// simply called on each render with the current session values.)
export function createWorkspaceActions(ctx: ActionContext) {
  const { request, orgId, isDemo, setStatus, refresh, setExecution, setActiveTab, setLatestInviteToken } = ctx;

  // The common shape: pending message -> call -> on failure show the API's
  // error -> on success refresh the workspace and confirm.
  async function mutate(m: Mutation) {
    try {
      setStatus(m.pending);
      const res = await request(m.path, {
        method: m.method,
        ...(m.payload === undefined ? {} : jsonBody(m.payload)),
      });
      const result = await parseResponse(res, `${m.failure} (${res.status}).`);
      if (!result.ok) return setStatus(result.errorMessage);
      m.beforeRefresh?.();
      await refresh();
      setStatus(m.success);
    } catch {
      setStatus(CONNECTION_ERROR);
    }
  }

  // --- Executions and approvals -------------------------------------------

  async function loadExecution(id: string) {
    try {
      const res = await request(`/api/v1/ops/executions/${id}?org_id=${orgId}`);
      const result = await parseResponse<ExecutionDetail>(res, `Execution lookup failed (${res.status}).`);
      if (!result.ok) return setStatus(result.errorMessage);
      setExecution(result.body);
      setActiveTab("executions");
    } catch {
      setStatus(CONNECTION_ERROR);
    }
  }

  async function retryExecution(id: string) {
    try {
      setStatus("Retrying failed action...");
      const res = await request(`/api/v1/ops/executions/${id}/retry?org_id=${orgId}`, { method: "POST" });
      const result = await parseResponse<StatusResponse>(res, `Retry failed (${res.status}).`);
      if (!result.ok) return setStatus(result.errorMessage);
      await refresh();
      await loadExecution(id);
      setStatus(`Retry finished: ${result.body.status}.`);
    } catch {
      setStatus(CONNECTION_ERROR);
    }
  }

  async function reconcileAction(actionId: string) {
    try {
      setStatus("Reconciling provider outcome without repeating the action...");
      const res = await request(`/api/v1/ops/actions/${actionId}/reconcile?org_id=${orgId}`, { method: "POST" });
      const result = await parseResponse<StatusResponse>(res, `Reconciliation failed (${res.status}).`);
      if (!result.ok) return setStatus(result.errorMessage);
      await refresh();
      setStatus(`Reconciliation finished: ${result.body.status}.`);
    } catch {
      setStatus(CONNECTION_ERROR);
    }
  }

  async function decideApproval(approvalId: string, decision: ApprovalDecision) {
    try {
      setStatus(`Recording ${decision} decision...`);
      const res = await request(`/api/v1/approvals/${approvalId}/decision?org_id=${orgId}`, {
        method: "POST",
        ...jsonBody({ decision, notes: "Decision recorded from Threshold operator dashboard." }),
      });
      const result = await parseResponse<ApprovalDecisionResponse>(res, `Approval decision failed (${res.status}).`);
      if (!result.ok) return setStatus(result.errorMessage);
      await refresh();
      await loadExecution(result.body.execution_id);
      setStatus(`Approval ${decision}. Execution is ${result.body.status}.`);
    } catch {
      setStatus(CONNECTION_ERROR);
    }
  }

  async function runScenario(scenario: string) {
    if (!isDemo) return setStatus("Demo scenarios are isolated to demo workspaces.");
    try {
      setStatus(`Running ${scenario.replaceAll("_", " ")}...`);
      const res = await request(`/api/v1/demo/run?org_id=${orgId}`, {
        method: "POST",
        ...jsonBody({ scenario }),
      });
      const result = await parseResponse<DemoRunResponse>(res, `Demo run failed (${res.status}).`);
      if (!result.ok) return setStatus(result.errorMessage);
      await refresh();
      await loadExecution(result.body.execution_id);
      setStatus(`${scenario.replaceAll("_", " ")} executed: ${result.body.status}.`);
    } catch {
      setStatus(CONNECTION_ERROR);
    }
  }

  // --- Configuration -------------------------------------------------------

  const saveRefundPolicy = (values: RefundPolicyInput) =>
    mutate({
      pending: "Saving deterministic refund policy...",
      path: `/api/v1/workspace/refund-policy?org_id=${orgId}`,
      method: "PUT",
      payload: values,
      failure: "Policy update failed",
      success: "Refund policy saved. Future refund runs will use these deterministic limits.",
    });

  const saveGenericRestIntegration = (values: GenericRestInput) =>
    mutate({
      pending: "Saving live refund integration...",
      path: `/api/v1/workspace/integrations/generic-rest?org_id=${orgId}`,
      method: "PUT",
      payload: values,
      failure: "Integration update failed",
      success: "Live refund integration saved. Provider calls will use durable idempotency and reconciliation.",
    });

  const saveShopifyIntegration = (values: ShopifyInput) =>
    mutate({
      pending: "Saving Shopify connection...",
      path: `/api/v1/workspace/integrations/shopify?org_id=${orgId}`,
      method: "PUT",
      payload: values,
      failure: "Shopify update failed",
      success: "Shopify connection saved. Configure the referenced Admin API and webhook secrets in deployment secrets.",
    });

  const saveStripeIntegration = (values: StripeInput) =>
    mutate({
      pending: "Saving Stripe connection...",
      path: `/api/v1/workspace/integrations/stripe?org_id=${orgId}`,
      method: "PUT",
      payload: values,
      failure: "Stripe update failed",
      success: "Stripe connection saved. Threshold will use Stripe only when it is marked as the refund execution provider.",
    });

  async function syncShopifyOrder(orderNumber: string) {
    try {
      setStatus(`Syncing Shopify order ${orderNumber}...`);
      const res = await request(
        `/api/v1/workspace/shopify/orders/sync?org_id=${orgId}&order_number=${encodeURIComponent(orderNumber)}`,
        { method: "POST" }
      );
      const result = await parseResponse<SyncedOrder>(res, `Order sync failed (${res.status}).`);
      if (!result.ok) return setStatus(result.errorMessage);
      const row = result.body;
      // Refresh first: refresh() sets its own status message, which used to
      // overwrite this one before it could be read.
      await refresh();
      setStatus(`Synced ${row.order_number}. Remaining refundable amount: ${row.refundable} ${row.currency}.`);
    } catch {
      setStatus(CONNECTION_ERROR);
    }
  }

  const createWebhookEndpoint = (values: WebhookEndpointInput) =>
    mutate({
      pending: "Creating signed webhook endpoint...",
      path: `/api/v1/workspace/webhook-endpoints?org_id=${orgId}`,
      method: "POST",
      payload: values,
      failure: "Webhook endpoint failed",
      success: "Signed webhook endpoint created. Configure its secret reference in deployment secrets.",
    });

  const disableWebhookEndpoint = (endpointId: string) =>
    mutate({
      pending: "Disabling webhook endpoint...",
      path: `/api/v1/workspace/webhook-endpoints/${endpointId}?org_id=${orgId}`,
      method: "DELETE",
      failure: "Webhook disable failed",
      success: "Webhook endpoint disabled.",
    });

  // --- Recovery -------------------------------------------------------------

  const replayEvent = (eventId: string) =>
    mutate({
      pending: "Queueing safe event replay...",
      path: `/api/v1/ops/events/${eventId}/replay?org_id=${orgId}`,
      method: "POST",
      failure: "Event replay failed",
      success: "Event replay queued through the durable outbox.",
    });

  const requeueOutbox = (messageId: string) =>
    mutate({
      pending: "Requeueing outbox delivery...",
      path: `/api/v1/ops/outbox/${messageId}/requeue?org_id=${orgId}`,
      method: "POST",
      failure: "Outbox requeue failed",
      success: "Outbox delivery reset to pending.",
    });

  // --- Team -----------------------------------------------------------------

  async function inviteMember(inviteEmail: string, role: string) {
    try {
      setStatus("Creating team invitation...");
      const res = await request(`/api/v1/organizations/${orgId}/invitations`, {
        method: "POST",
        ...jsonBody({ email: inviteEmail, role }),
      });
      const result = await parseResponse<InvitationCreated>(res, `Invitation failed (${res.status}).`);
      if (!result.ok) return setStatus(result.errorMessage);
      setLatestInviteToken(result.body.invitation_token);
      await refresh();
      setStatus(`Invitation created for ${result.body.email}. Copy the one-time token below.`);
    } catch {
      setStatus(CONNECTION_ERROR);
    }
  }

  const updateMemberRole = (membershipId: string, role: string) =>
    mutate({
      pending: "Updating member role...",
      path: `/api/v1/organizations/${orgId}/members/${membershipId}`,
      method: "PATCH",
      payload: { role },
      failure: "Role update failed",
      success: "Member role updated.",
    });

  const removeMember = (membershipId: string) =>
    mutate({
      pending: "Removing member...",
      path: `/api/v1/organizations/${orgId}/members/${membershipId}`,
      method: "DELETE",
      failure: "Member removal failed",
      success: "Member removed from the workspace.",
    });

  const revokeInvitation = (invitationId: string) =>
    mutate({
      pending: "Revoking invitation...",
      path: `/api/v1/organizations/${orgId}/invitations/${invitationId}`,
      method: "DELETE",
      failure: "Invitation revoke failed",
      success: "Invitation revoked.",
      beforeRefresh: () => setLatestInviteToken(""),
    });

  // --- Billing and launch gate ----------------------------------------------

  async function startCheckout(plan: string) {
    try {
      setStatus(`Starting ${plan} checkout...`);
      const res = await request(`/api/v1/commercial/checkout?org_id=${orgId}`, {
        method: "POST",
        ...jsonBody({ plan }),
      });
      const result = await parseResponse<{ checkout_url?: string }>(res, `Checkout failed (${res.status}).`);
      if (!result.ok) return setStatus(result.errorMessage);
      if (result.body.checkout_url) window.location.href = result.body.checkout_url;
    } catch {
      setStatus("Unable to start checkout.");
    }
  }

  async function openBillingPortal() {
    try {
      const res = await request(`/api/v1/commercial/portal?org_id=${orgId}`, { method: "POST" });
      const result = await parseResponse<{ url?: string }>(res, `Billing portal failed (${res.status}).`);
      if (!result.ok) return setStatus(result.errorMessage);
      if (result.body.url) window.location.href = result.body.url;
    } catch {
      setStatus("Unable to open billing portal.");
    }
  }

  async function startShopifyOAuth(shop: string) {
    try {
      setStatus("Preparing Shopify installation...");
      const res = await request(
        `/api/v1/commercial/shopify/install?org_id=${orgId}&shop=${encodeURIComponent(shop)}`
      );
      const result = await parseResponse<{ authorization_url?: string }>(res, `Shopify install failed (${res.status}).`);
      if (!result.ok) return setStatus(result.errorMessage);
      if (result.body.authorization_url) window.location.href = result.body.authorization_url;
    } catch {
      setStatus("Unable to start Shopify installation.");
    }
  }

  // Unlike the handlers above this one has no try/catch (it never did): a
  // network failure here rejects instead of setting a status message.
  async function setLiveExecution(enabled: boolean) {
    if (!orgId) return;
    setStatus(enabled ? "Running full beta readiness gate..." : "Disabling live execution...");
    const res = await request(`/api/v1/ops/beta-readiness/live-execution?org_id=${orgId}`, {
      method: "POST",
      ...jsonBody({ enabled }),
    });
    const result = await parseResponse(res, `Live execution change failed (${res.status}).`);
    if (!result.ok) return setStatus(result.errorMessage);
    await refresh();
    setStatus(enabled ? "Live execution enabled." : "Live execution disabled immediately.");
  }

  return {
    loadExecution,
    retryExecution,
    reconcileAction,
    decideApproval,
    runScenario,
    saveRefundPolicy,
    saveGenericRestIntegration,
    saveShopifyIntegration,
    saveStripeIntegration,
    syncShopifyOrder,
    createWebhookEndpoint,
    disableWebhookEndpoint,
    replayEvent,
    requeueOutbox,
    inviteMember,
    updateMemberRole,
    removeMember,
    revokeInvitation,
    startCheckout,
    openBillingPortal,
    startShopifyOAuth,
    setLiveExecution,
  };
}
