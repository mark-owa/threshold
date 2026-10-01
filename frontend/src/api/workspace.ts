import { request } from "./client";
import type {
  GenericRestInput,
  Integration,
  Onboarding,
  Policy,
  RefundPolicyInput,
  ShopifyInput,
  ShopifyOrderSync,
  StripeInput,
  WebhookEndpoint,
  WebhookEndpointInput,
  WorkflowDefinition,
} from "@/types/api";

export const workspaceApi = {
  onboarding: (orgId: string) => request<Onboarding>("/workspace/onboarding", { query: { org_id: orgId } }),

  workflows: (orgId: string) => request<WorkflowDefinition[]>("/workspace/workflows", { query: { org_id: orgId } }),

  policies: (orgId: string) => request<Policy[]>("/workspace/policies", { query: { org_id: orgId } }),

  saveRefundPolicy: (orgId: string, input: RefundPolicyInput) =>
    request<Policy>("/workspace/refund-policy", { method: "PUT", query: { org_id: orgId }, body: input }),

  integrations: (orgId: string) => request<Integration[]>("/workspace/integrations", { query: { org_id: orgId } }),

  saveGenericRest: (orgId: string, input: GenericRestInput) =>
    request<Integration>("/workspace/integrations/generic-rest", {
      method: "PUT",
      query: { org_id: orgId },
      body: input,
    }),

  saveShopify: (orgId: string, input: ShopifyInput) =>
    request<Integration & { webhook_path?: string }>("/workspace/integrations/shopify", {
      method: "PUT",
      query: { org_id: orgId },
      body: input,
    }),

  saveStripe: (orgId: string, input: StripeInput) =>
    request<Integration>("/workspace/integrations/stripe", {
      method: "PUT",
      query: { org_id: orgId },
      body: input,
    }),

  syncShopifyOrder: (orgId: string, orderNumber: string) =>
    request<ShopifyOrderSync>("/workspace/shopify/orders/sync", {
      method: "POST",
      query: { org_id: orgId, order_number: orderNumber },
    }),

  webhookEndpoints: (orgId: string) =>
    request<WebhookEndpoint[]>("/workspace/webhook-endpoints", { query: { org_id: orgId } }),

  createWebhookEndpoint: (orgId: string, input: WebhookEndpointInput) =>
    request<WebhookEndpoint>("/workspace/webhook-endpoints", {
      method: "POST",
      query: { org_id: orgId },
      body: input,
    }),

  disableWebhookEndpoint: (orgId: string, id: string) =>
    request<void>(`/workspace/webhook-endpoints/${id}`, { method: "DELETE", query: { org_id: orgId } }),
};
