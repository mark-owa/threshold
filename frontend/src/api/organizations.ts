import { request } from "./client";
import type { CreatedInvitation, Invitation, Member, Role, Workspace } from "@/types/api";

export const organizationsApi = {
  list: () => request<Workspace[]>("/organizations"),

  create: (input: { name: string; slug: string }) =>
    request<Workspace>("/organizations", { method: "POST", body: input }),

  members: (orgId: string) => request<Member[]>(`/organizations/${orgId}/members`),

  invitations: (orgId: string) => request<Invitation[]>(`/organizations/${orgId}/invitations`),

  invite: (orgId: string, input: { email: string; role: Role }) =>
    request<CreatedInvitation>(`/organizations/${orgId}/invitations`, { method: "POST", body: input }),

  revokeInvitation: (orgId: string, invitationId: string) =>
    request<void>(`/organizations/${orgId}/invitations/${invitationId}`, { method: "DELETE" }),

  updateMemberRole: (orgId: string, membershipId: string, role: Role) =>
    request<Member>(`/organizations/${orgId}/members/${membershipId}`, { method: "PATCH", body: { role } }),

  removeMember: (orgId: string, membershipId: string) =>
    request<void>(`/organizations/${orgId}/members/${membershipId}`, { method: "DELETE" }),
};
