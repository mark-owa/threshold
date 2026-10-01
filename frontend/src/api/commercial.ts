import { request } from "./client";
import type { CommercialStatus, DemoRunResult, PlanDefinition } from "@/types/api";

export const commercialApi = {
  status: (orgId: string) => request<CommercialStatus>("/commercial/status", { query: { org_id: orgId } }),

  plans: () => request<Record<string, PlanDefinition>>("/commercial/plans", { auth: false }),

  checkout: (orgId: string, plan: string) =>
    request<{ checkout_url: string | null; session_id: string | null }>("/commercial/checkout", {
      method: "POST",
      query: { org_id: orgId },
      body: { plan },
    }),

  portal: (orgId: string) =>
    request<{ url: string | null }>("/commercial/portal", { method: "POST", query: { org_id: orgId } }),

  shopifyInstall: (orgId: string, shop: string) =>
    request<{ authorization_url: string | null }>("/commercial/shopify/install", {
      query: { org_id: orgId, shop },
    }),
};

export const demoApi = {
  run: (orgId: string, scenario: string) =>
    request<DemoRunResult>("/demo/run", { method: "POST", query: { org_id: orgId }, body: { scenario } }),
};
