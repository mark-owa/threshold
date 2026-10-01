import { request } from "./client";
import type { JoinResponse, Me, RegisterResponse, TokenResponse } from "@/types/api";

export const authApi = {
  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", { method: "POST", auth: false, body: { email, password } }),

  register: (input: {
    email: string;
    password: string;
    full_name: string;
    organization_name: string;
    organization_slug: string;
  }) => request<RegisterResponse>("/auth/register", { method: "POST", auth: false, body: input }),

  join: (input: { email: string; password: string; full_name: string | null; invitation_token: string }) =>
    request<JoinResponse>("/auth/join", { method: "POST", auth: false, body: input }),

  me: () => request<Me>("/auth/me"),
};
