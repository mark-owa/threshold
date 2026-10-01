import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { authApi } from "@/api/auth";
import { onUnauthorized, tokenExpiry, tokenStore } from "@/api/client";
import { organizationsApi } from "@/api/organizations";
import type { Me, Role, Workspace } from "@/types/api";

type Status = "loading" | "authenticated" | "anonymous";

interface SessionValue {
  status: Status;
  user: Me | null;
  workspaces: Workspace[];
  workspace: Workspace | null;
  /** Message to show on the sign-in screen (e.g. session expired). */
  notice: string | null;
  clearNotice: () => void;
  signIn: (email: string, password: string) => Promise<void>;
  register: (input: {
    email: string;
    password: string;
    full_name: string;
    organization_name: string;
    organization_slug: string;
  }) => Promise<void>;
  join: (input: { email: string; password: string; full_name: string | null; invitation_token: string }) => Promise<void>;
  signOut: (notice?: string) => void;
  switchWorkspace: (id: string) => void;
  createWorkspace: (name: string, slug: string) => Promise<Workspace>;
}

const SessionContext = createContext<SessionValue | null>(null);
const WORKSPACE_KEY = "threshold.workspace";

function readWorkspaceId(): string | null {
  try {
    return localStorage.getItem(WORKSPACE_KEY);
  } catch {
    return null;
  }
}
function writeWorkspaceId(id: string | null) {
  try {
    if (id) localStorage.setItem(WORKSPACE_KEY, id);
    else localStorage.removeItem(WORKSPACE_KEY);
  } catch {
    /* ignore */
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<Status>(() => (tokenStore.get() ? "loading" : "anonymous"));
  const [user, setUser] = useState<Me | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeId, setActiveId] = useState<string | null>(readWorkspaceId);
  const [notice, setNotice] = useState<string | null>(null);
  const expiryTimer = useRef<number | undefined>(undefined);

  const signOut = useCallback(
    (message?: string) => {
      window.clearTimeout(expiryTimer.current);
      tokenStore.clear();
      queryClient.clear();
      setUser(null);
      setWorkspaces([]);
      setStatus("anonymous");
      setNotice(message ?? null);
    },
    [queryClient],
  );

  const scheduleExpiry = useCallback(
    (token: string) => {
      window.clearTimeout(expiryTimer.current);
      const exp = tokenExpiry(token);
      if (!exp) return;
      const delay = Math.max(exp - Date.now(), 0);
      // setTimeout caps at ~24.8 days; access tokens are short-lived so this is safe.
      expiryTimer.current = window.setTimeout(() => signOut("Your session expired. Sign in again."), Math.min(delay, 2 ** 31 - 1));
    },
    [signOut],
  );

  const load = useCallback(
    async (preferredOrgId?: string | null) => {
      const [me, orgs] = await Promise.all([authApi.me(), organizationsApi.list()]);
      setUser(me);
      setWorkspaces(orgs);
      const next =
        orgs.find((o) => o.id === preferredOrgId)?.id ?? orgs.find((o) => o.id === readWorkspaceId())?.id ?? orgs[0]?.id ?? null;
      setActiveId(next);
      writeWorkspaceId(next);
      setStatus("authenticated");
    },
    [],
  );

  // Restore a session after reload.
  useEffect(() => {
    const token = tokenStore.get();
    if (!token) return;
    const exp = tokenExpiry(token);
    if (exp && exp <= Date.now()) {
      signOut("Your session expired. Sign in again.");
      return;
    }
    scheduleExpiry(token);
    load().catch(() => signOut());
  }, [load, scheduleExpiry, signOut]);

  // Any 401 from an authenticated request ends the session.
  useEffect(() => {
    onUnauthorized(() => signOut("Your session expired. Sign in again."));
    return () => onUnauthorized(null);
  }, [signOut]);

  const startSession = useCallback(
    async (token: string, orgId?: string | null) => {
      tokenStore.set(token);
      scheduleExpiry(token);
      setNotice(null);
      await load(orgId);
    },
    [load, scheduleExpiry],
  );

  const value = useMemo<SessionValue>(
    () => ({
      status,
      user,
      workspaces,
      workspace: workspaces.find((w) => w.id === activeId) ?? null,
      notice,
      clearNotice: () => setNotice(null),
      signIn: async (email, password) => {
        const res = await authApi.login(email.trim(), password);
        await startSession(res.access_token);
      },
      register: async (input) => {
        const res = await authApi.register({ ...input, email: input.email.trim() });
        await startSession(res.access_token, res.organization_id);
      },
      join: async (input) => {
        const res = await authApi.join({ ...input, email: input.email.trim() });
        await startSession(res.access_token, res.organization_id);
      },
      signOut,
      switchWorkspace: (id) => {
        if (id === activeId) return;
        writeWorkspaceId(id);
        setActiveId(id);
      },
      createWorkspace: async (name, slug) => {
        const created = await organizationsApi.create({ name, slug });
        const orgs = await organizationsApi.list();
        setWorkspaces(orgs);
        writeWorkspaceId(created.id);
        setActiveId(created.id);
        return created;
      },
    }),
    [status, user, workspaces, activeId, notice, signOut, startSession],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside SessionProvider");
  return ctx;
}

/** Active-workspace helpers. Only call inside routes rendered after a workspace is selected. */
export function useWorkspace() {
  const { workspace } = useSession();
  if (!workspace) throw new Error("useWorkspace requires an active workspace");
  const role: Role = workspace.role;
  return {
    workspace,
    orgId: workspace.id,
    role,
    isDemo: workspace.plan === "demo",
    isOwner: role === "owner",
    /** Owner or admin: manage team, policies, integrations, recovery. */
    canManage: role === "owner" || role === "admin",
    /** Owner, admin or reviewer: make approval decisions and retry failed work. */
    canReview: role === "owner" || role === "admin" || role === "reviewer",
  };
}
