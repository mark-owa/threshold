import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API = import.meta.env.VITE_API_URL ?? "https://threshold-api-production.up.railway.app";

function App() {
  const [token, setToken] = useState("");
  const [orgId, setOrgId] = useState("");
  const [user, setUser] = useState<any>(null);
  const [email, setEmail] = useState("owner@acme-demo.example.com");
  const [password, setPassword] = useState("demo1234");
  const [status, setStatus] = useState("Sign in to inspect Threshold.");
  const [metrics, setMetrics] = useState<any>(null);
  const [approvals, setApprovals] = useState<any[]>([]);
  const [executions, setExecutions] = useState<any[]>([]);
  const [execution, setExecution] = useState<any>(null);
  const [audit, setAudit] = useState<any[]>([]);

  const headers = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  async function login() {
    try {
      setStatus("Authenticating...");
      const res = await fetch(`${API}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) return setStatus(`Login failed (${res.status}).`);
      const data = await res.json();
      const meRes = await fetch(`${API}/api/v1/auth/me`, { headers: { Authorization: `Bearer ${data.access_token}` } });
      if (!meRes.ok) return setStatus(`Profile lookup failed (${meRes.status}).`);
      const me = await meRes.json();
      setToken(data.access_token);
      setUser(me);
      const firstOrg = me.memberships?.[0]?.organization_id ?? "";
      setOrgId(firstOrg);
      setStatus("Authenticated. Loading operational view...");
      await refresh(firstOrg, data.access_token);
    } catch {
      setStatus("Request failed. Check the API connection and sign in again if needed.");
    }
  }

  async function refresh(targetOrg = orgId, accessToken = token) {
    try {
      if (!targetOrg || !accessToken) return;
      const authHeaders = { Authorization: `Bearer ${accessToken}` };
      const [m, a, e, au] = await Promise.all([
        fetch(`${API}/api/v1/ops/metrics?org_id=${targetOrg}`, { headers: authHeaders }),
        fetch(`${API}/api/v1/ops/approvals?org_id=${targetOrg}`, { headers: authHeaders }),
        fetch(`${API}/api/v1/ops/executions?org_id=${targetOrg}&limit=20`, { headers: authHeaders }),
        fetch(`${API}/api/v1/ops/audit?org_id=${targetOrg}&limit=20`, { headers: authHeaders }),
      ]);
      if (m.ok) setMetrics(await m.json());
      if (a.ok) setApprovals(await a.json());
      if (e.ok) setExecutions(await e.json());
      if (au.ok) setAudit(await au.json());
      if ([m, a, e, au].some(res => res.status === 401)) {
        setToken("");
        setUser(null);
        setExecution(null);
        setMetrics(null);
        setApprovals([]);
        setExecutions([]);
        setAudit([]);
        return setStatus("Session expired. Sign in again.");
      }
      setStatus([m, a, e, au].every(res => res.ok)
        ? "Dashboard refreshed." : "Some dashboard data could not be loaded.");
    } catch {
      setStatus("Request failed. Check the API connection and sign in again if needed.");
    }
  }

  async function runScenario(scenario: string) {
    try {
      setStatus(`Running ${scenario.replaceAll("_", " ")}...`);
      const res = await fetch(`${API}/api/v1/demo/run?org_id=${orgId}`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ scenario }),
      });
      if (!res.ok) return setStatus(`Demo run failed (${res.status}).`);
      const data = await res.json();
      await loadExecution(data.execution_id);
      await refresh();
      setStatus(`${scenario.replaceAll("_", " ")} executed: ${data.status}.`);
    } catch {
      setStatus("Request failed. Check the API connection and sign in again if needed.");
    }
  }

  async function loadExecution(id: string) {
    try {
      const res = await fetch(`${API}/api/v1/ops/executions/${id}?org_id=${orgId}`, { headers });
      if (!res.ok) return setStatus(`Execution lookup failed (${res.status}).`);
      setExecution(await res.json());
    } catch {
      setStatus("Request failed. Check the API connection and sign in again if needed.");
    }
  }

  async function retryExecution(id: string) {
    try {
      setStatus("Retrying failed action...");
      const res = await fetch(`${API}/api/v1/ops/executions/${id}/retry?org_id=${orgId}`, { method: "POST", headers });
      if (!res.ok) return setStatus(`Retry failed (${res.status}).`);
      const result = await res.json();
      await loadExecution(id);
      await refresh();
      setStatus(`Retry finished: ${result.status}.`);
    } catch {
      setStatus("Request failed. Check the API connection and sign in again if needed.");
    }
  }

  async function decideApproval(approvalId: string, decision: string) {
    try {
      setStatus(`${decision} approval...`);
      const res = await fetch(`${API}/api/v1/approvals/${approvalId}/decision?org_id=${orgId}`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ decision, notes: `Decision recorded from Threshold operator dashboard.` }),
      });
      if (!res.ok) return setStatus(`Approval decision failed (${res.status}).`);
      const result = await res.json();
      await loadExecution(result.execution_id);
      await refresh();
      setStatus(`Approval ${decision}. Execution is ${result.status}.`);
    } catch {
      setStatus("Request failed. Check the API connection and sign in again if needed.");
    }
  }

  return (
    <div className="page">
      <header className="hero">
        <div>
          <div className="eyebrow">THRESHOLD / OPERATIONS CONTROL</div>
          <h1>AI that proposes. Rules that decide. Humans that stay accountable.</h1>
          <p>Monitor automation, review risky actions, inspect execution paths, and see the boundary between probabilistic AI and deterministic business controls.</p>
          {user && <div className="identity">{user.full_name} · {user.email}</div>}
        </div>
        {!token ? (
          <div className="login-card">
            <input aria-label="Email" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="Email" />
            <input aria-label="Password" value={password} onChange={e => setPassword(e.target.value)} type="password" placeholder="Password" />
            <button onClick={login}>Sign in</button>
            <small>Demo credentials are seeded locally.</small>
          </div>
        ) : (
          <div className="login-card compact">
            <div><strong>Organization</strong><small>{orgId}</small></div>
            <button className="secondary" onClick={() => refresh()}>Refresh dashboard</button>
          </div>
        )}
      </header>

      <main className="content">
        <div className="status" role="status">{status}</div>
        {token && (
          <>
            <section className="demo-toolbar panel">
              <div>
                <h2>Run a controlled demo</h2>
                <p>These scenarios use seeded mock integrations and leave a full audit trail.</p>
              </div>
              <div className="scenario-buttons">
                <button onClick={() => runScenario("low_risk_refund")}>Low-risk refund</button>
                <button onClick={() => runScenario("high_risk_refund")}>High-risk refund</button>
                <button onClick={() => runScenario("rejected_refund")}>Policy-failing refund</button>
                <button onClick={() => runScenario("failed_refund")}>Failure + retry</button>
                <button onClick={() => runScenario("support_inquiry")}>Support inquiry</button>
                <button onClick={() => runScenario("lead_inquiry")}>Lead inquiry</button>
              </div>
            </section>

            <section className="grid four">
              <Metric title="Executions" value={metrics?.total_executions ?? "—"} />
              <Metric title="Automation rate" value={metrics ? `${metrics.automation_rate_percent}%` : "—"} />
              <Metric title="Pending approvals" value={metrics?.awaiting_approval ?? "—"} />
              <Metric title="Failed" value={metrics?.failed ?? "—"} />
              <Metric title="Estimated hours saved" value={metrics ? `${metrics.estimated_hours_saved}h` : "—"} />
            </section>

            <section className="panel">
              <div className="panel-head"><div><h2>Approval queue</h2><p>Risky actions stop here until an authorized reviewer decides.</p></div></div>
              {approvals.length === 0 ? <div className="empty">No pending approvals.</div> : approvals.map(a => (
                <div className="approval" key={a.id}>
                  <div className="approval-head"><strong>{a.proposed_action?.action_type}</strong><span>{a.risk_level}</span></div>
                  <p>{a.reason}</p>
                  <pre>{JSON.stringify(a.generated_parameters, null, 2)}</pre>
                  <div className="approval-actions">
                    <button onClick={() => decideApproval(a.id, "approved")}>Approve</button>
                    <button onClick={() => decideApproval(a.id, "rejected")} className="danger">Reject</button>
                  </div>
                </div>
              ))}
            </section>

            <section className="panel">
              <div className="panel-head"><div><h2>Recent executions</h2><p>Click any execution to inspect its recorded workflow steps.</p></div></div>
              {executions.length === 0 ? <div className="empty">No executions yet. Run a demo scenario above.</div> : executions.map(e => (
                <button className="execution-row" key={e.id} onClick={() => loadExecution(e.id)}>
                  <span>{e.id.slice(0, 8)}</span><strong>{e.status}</strong><small>{e.current_step ?? "complete"}</small>
                </button>
              ))}
            </section>

            <section className="panel">
              <div className="panel-head"><div><h2>Execution inspector</h2><p>Inspect recorded step outputs, timing, errors, and outcome.</p></div></div>
              {execution ? <div className="timeline">
                <div className="execution-summary"><strong>{execution.status}</strong><span>{execution.current_step ?? "complete"}</span></div>
                {execution.status === "failed" && <div className="inline-action"><button onClick={() => retryExecution(execution.id)}>Retry failed action</button><small>Safe retry reuses the existing action idempotency key.</small></div>}
                {execution.steps.map((s: any) => (
                  <div className={`step ${s.status}`} key={s.id}>
                    <div className="dot" />
                    <div className="step-main"><strong>{s.step_key}</strong><span>{s.step_type}</span><small>{s.status}</small></div>
                    <div className="latency">{s.latency_ms ?? 0}ms</div>
                    <pre>{JSON.stringify({ output: s.output ?? {}, error: s.error }, null, 2)}</pre>
                  </div>
                ))}
              </div> : <div className="empty">Select an execution above.</div>}
            </section>

            <section className="panel">
              <div className="panel-head"><div><h2>Audit trail</h2><p>Append-only operational history for the current organization.</p></div></div>
              {audit.map(item => (
                <div className="audit-row" key={item.id}><div><strong>{item.event_type}</strong><small>{item.actor_type}</small></div><code>{item.execution_id?.slice(0, 8) ?? "—"}</code></div>
              ))}
            </section>
          </>
        )}
      </main>
    </div>
  );
}

function Metric({ title, value }: { title: string; value: string | number }) {
  return <div className="metric"><span>{title}</span><strong>{value}</strong></div>;
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
