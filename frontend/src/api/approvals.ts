import { request } from "./client";
import type { ApprovalDecisionRequest, ApprovalDecisionResult } from "@/types/api";

export const approvalsApi = {
  decide: (orgId: string, approvalId: string, input: ApprovalDecisionRequest) =>
    request<ApprovalDecisionResult>(`/approvals/${approvalId}/decision`, {
      method: "POST",
      query: { org_id: orgId },
      body: input,
    }),
};
