import React, { useState } from "react";
import { API_BASE, CONNECTION_ERROR, jsonBody, makeRequest, parseResponse } from "./api";
import { NAV, tabTitle } from "./nav";
import type { Tab } from "./nav";
import type {
  AuthWithWorkspaceResponse,
  CurrentUser,
  ExecutionDetail,
  TokenResponse,
  Workspace,
} from "./types";
import { EMPTY_WORKSPACE_DATA, loadWorkspaceData } from "./workspaceData";
import type { WorkspaceData } from "./workspaceData";
import { createWorkspaceActions } from "./workspaceActions";
import { Actions } from "./components/Actions";
import { Approvals } from "./components/Approvals";
import { Audit } from "./components/Audit";
import { AuthScreen } from "./components/AuthScreen";
import type { JoinInput, LoginInput, RegisterInput } from "./components/AuthScreen";
import { BetaReadiness } from "./components/BetaReadiness";
import { Billing } from "./components/Billing";
import { CreateWorkspacePanel } from "./components/CreateWorkspacePanel";
import { Executions } from "./components/Executions";
import { Integrations } from "./components/Integrations";
import { Overview } from "./components/Overview";
import { Policies } from "./components/Policies";
import { Recovery } from "./components/Recovery";
import { Sandbox } from "./components/Sandbox";
import { Team } from "./components/Team";

// Session and navigation state lives here. Everything the dashboard shows for
// the active workspace is one `data` object (see workspaceData.ts); the
// operational handlers live in workspaceActions.ts.
export function App() {
  const [token, setToken] = useState("");
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [orgId, setOrgId] = useState("");
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [status, setStatus] = useState("Sign in to Threshold.");
  const [data, setData] = useState<WorkspaceData>(EMPTY_WORKSPACE_DATA);
  const [execution, setExecution] = useState<ExecutionDetail | null>(null);
  const [latestInviteToken, setLatestInviteToken] = useState("");
  const [showCreateWorkspace, setShowCreateWorkspace] = useState(false);

  const request = makeRequest(token);
  const activeWorkspace = workspaces.find(w => w.id === orgId) ?? null;
  const isDemo = activeWorkspace?.plan === "demo";
  const isOwner = activeWorkspace?.role === "owner";
  const canManageWorkspace = isOwner || activeWorkspace?.role === "admin";

  async function refresh(targetOrg = orgId, accessToken = token) {
    try {
      if (!targetOrg || !accessToken) return;
      const result = await loadWorkspaceData(request, targetOrg, accessToken);
      if (result.unauthorized) return logout("Session expired. Sign in again.");
      setData(result.data);
      setStatus(result.complete ? "Workspace refreshed." : "Some workspace data could not be loaded.");
    } catch {
      setStatus(CONNECTION_ERROR);
    }
  }

  function logout(message = "Signed out.") {
    setToken("");
    setUser(null);
    setWorkspaces([]);
    setOrgId("");
    setData(EMPTY_WORKSPACE_DATA);
    setExecution(null);
    setLatestInviteToken("");
    setStatus(message);
  }

  async function bootstrap(accessToken: string, preferredOrgId = "") {
    const [meRes, orgRes] = await Promise.all([
      request("/api/v1/auth/me", {}, accessToken),
      request("/api/v1/organizations", {}, accessToken),
    ]);
    if (!meRes.ok || !orgRes.ok) throw new Error("Unable to load account");
    const me: CurrentUser = await meRes.json();
    const orgs: Workspace[] = await orgRes.json();
    setToken(accessToken);
    setUser(me);
    setWorkspaces(orgs);
    const target = orgs.find(org => org.id === preferredOrgId)?.id ?? orgs[0]?.id ?? "";
    setOrgId(target);
    if (target) await refresh(target, accessToken);
    setStatus(target ? "Workspace loaded." : "Account created. Create your first workspace.");
  }

  async function login({ email, password }: LoginInput) {
    try {
      setStatus("Authenticating...");
      const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
        method: "POST",
        ...jsonBody({ email, password }),
      });
      const result = await parseResponse<TokenResponse>(res, `Login failed (${res.status}).`);
      if (!result.ok) return setStatus(result.errorMessage);
      await bootstrap(result.body.access_token);
    } catch {
      setStatus(CONNECTION_ERROR);
    }
  }

  async function register({ email, password, fullName, workspaceName, workspaceSlug }: RegisterInput) {
    try {
      setStatus("Creating account and workspace...");
      const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
        method: "POST",
        ...jsonBody({
          email,
          password,
          full_name: fullName,
          organization_name: workspaceName,
          organization_slug: workspaceSlug,
        }),
      });
      const result = await parseResponse<AuthWithWorkspaceResponse>(res, `Registration failed (${res.status}).`);
      if (!result.ok) return setStatus(result.errorMessage);
      await bootstrap(result.body.access_token, result.body.organization_id);
    } catch {
      setStatus(CONNECTION_ERROR);
    }
  }

  async function joinWorkspace({ email, password, fullName, invitationToken }: JoinInput) {
    try {
      setStatus("Accepting workspace invitation...");
      const res = await fetch(`${API_BASE}/api/v1/auth/join`, {
        method: "POST",
        ...jsonBody({
          email,
          password,
          full_name: fullName || null,
          invitation_token: invitationToken,
        }),
      });
      const result = await parseResponse<AuthWithWorkspaceResponse>(res, `Invitation failed (${res.status}).`);
      if (!result.ok) return setStatus(result.errorMessage);
      await bootstrap(result.body.access_token, result.body.organization_id);
    } catch {
      setStatus(CONNECTION_ERROR);
    }
  }

  async function createWorkspace(name: string, slug: string) {
    try {
      setStatus("Creating workspace...");
      const res = await request("/api/v1/organizations", {
        method: "POST",
        ...jsonBody({ name, slug }),
      });
      const result = await parseResponse<Workspace>(res, `Workspace creation failed (${res.status}).`);
      if (!result.ok) return setStatus(result.errorMessage);
      const created = result.body;
      const orgRes = await request("/api/v1/organizations");
      const orgs: Workspace[] = await orgRes.json();
      setWorkspaces(orgs);
      setOrgId(created.id);
      setShowCreateWorkspace(false);
      setActiveTab("overview");
      await refresh(created.id);
      setStatus(`${created.name} created as a trial workspace.`);
    } catch {
      setStatus(CONNECTION_ERROR);
    }
  }

  async function switchWorkspace(nextOrgId: string) {
    setOrgId(nextOrgId);
    setExecution(null);
    setLatestInviteToken("");
    setActiveTab("overview");
    setStatus("Switching workspace...");
    await refresh(nextOrgId);
  }

  const actions = createWorkspaceActions({
    request,
    orgId,
    isDemo,
    setStatus,
    refresh: () => refresh(),
    setExecution,
    setActiveTab,
    setLatestInviteToken,
  });

  if (!token) {
    return <AuthScreen status={status} onLogin={login} onRegister={register} onJoin={joinWorkspace} />;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="logo-row"><div className="brand-mark small">T</div><div><strong>Threshold</strong><span>Operations control</span></div></div>
        <div className="workspace-picker">
          <span>Workspace</span>
          <select value={orgId} onChange={e => switchWorkspace(e.target.value)}>
            {workspaces.map(workspace => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}
          </select>
          {activeWorkspace && <div className="workspace-meta"><span className={`plan ${activeWorkspace.plan}`}>{activeWorkspace.plan}</span><span>{activeWorkspace.role}</span></div>}
        </div>
        <nav>
          {NAV.map(item => <button key={item.key} className={activeTab === item.key ? "nav-active" : "nav-item"} onClick={() => setActiveTab(item.key)}>{item.label}</button>)}
          {isDemo && <button className={activeTab === "sandbox" ? "nav-active" : "nav-item"} onClick={() => setActiveTab("sandbox")}>Demo sandbox</button>}
        </nav>
        <div className="sidebar-foot">
          <button className="outline wide" onClick={() => setShowCreateWorkspace(v => !v)}>+ New workspace</button>
          <div className="user-card"><strong>{user?.full_name}</strong><span>{user?.email}</span></div>
          <button className="text-button" onClick={() => logout()}>Sign out</button>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div><div className="eyebrow dark">THRESHOLD / {activeTab.toUpperCase()}</div><h1>{tabTitle(activeTab)}</h1></div>
          <button className="outline" onClick={() => refresh()}>Refresh</button>
        </header>

        <div className="status" role="status">{status}</div>

        {showCreateWorkspace && <CreateWorkspacePanel onCreate={createWorkspace} />}

        {activeTab === "overview" && <Overview metrics={data.metrics} workflows={data.workflows} approvals={data.approvals} executions={data.executions} onboarding={data.onboarding} onExecution={actions.loadExecution} onNavigate={setActiveTab} />}
        {activeTab === "approvals" && <Approvals approvals={data.approvals} onDecision={actions.decideApproval} />}
        {activeTab === "executions" && <Executions executions={data.executions} execution={execution} onSelect={actions.loadExecution} onRetry={actions.retryExecution} />}
        {activeTab === "actions" && <Actions actions={data.actions} onReconcile={actions.reconcileAction} />}
        {activeTab === "recovery" && <Recovery recovery={data.recovery} canAdmin={canManageWorkspace} onReplayEvent={actions.replayEvent} onRequeueOutbox={actions.requeueOutbox} onReconcile={actions.reconcileAction} />}
        {activeTab === "policies" && <Policies policies={data.policies} canEdit={canManageWorkspace} onSave={actions.saveRefundPolicy} />}
        {activeTab === "integrations" && <Integrations integrations={data.integrations} webhookEndpoints={data.webhookEndpoints} canEdit={canManageWorkspace} isDemo={isDemo} onSave={actions.saveGenericRestIntegration} onSaveShopify={actions.saveShopifyIntegration} onSaveStripe={actions.saveStripeIntegration} onSyncShopifyOrder={actions.syncShopifyOrder} onCreateWebhook={actions.createWebhookEndpoint} onDisableWebhook={actions.disableWebhookEndpoint} />}
        {activeTab === "team" && <Team members={data.members} invitations={data.invitations} currentUserId={user?.user_id} canManage={canManageWorkspace} latestInviteToken={latestInviteToken} onInvite={actions.inviteMember} onRoleChange={actions.updateMemberRole} onRemove={actions.removeMember} onRevoke={actions.revokeInvitation} />}
        {activeTab === "billing" && <Billing commercial={data.commercial} isOwner={isOwner} onCheckout={actions.startCheckout} onPortal={actions.openBillingPortal} onShopifyOAuth={actions.startShopifyOAuth} />}
        {activeTab === "beta" && <BetaReadiness report={data.betaReadiness} isOwner={isOwner} canAdmin={canManageWorkspace} onToggle={actions.setLiveExecution} />}
        {activeTab === "audit" && <Audit audit={data.audit} />}
        {activeTab === "sandbox" && isDemo && <Sandbox onRun={actions.runScenario} />}
      </main>
    </div>
  );
}
