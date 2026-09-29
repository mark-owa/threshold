import React, { useState } from "react";

export interface LoginInput {
  email: string;
  password: string;
}

export interface RegisterInput extends LoginInput {
  fullName: string;
  workspaceName: string;
  workspaceSlug: string;
}

export interface JoinInput extends LoginInput {
  fullName: string;
  invitationToken: string;
}

type AuthMode = "login" | "register" | "join";

interface AuthScreenProps {
  status: string;
  onLogin: (input: LoginInput) => void;
  onRegister: (input: RegisterInput) => void;
  onJoin: (input: JoinInput) => void;
}

// The signed-out screen. It owns the form fields, so typing in them does not
// re-render the rest of the app; the credentials pre-filled below are the
// public local-demo login documented in the README.
export function AuthScreen({ status, onLogin, onRegister, onJoin }: AuthScreenProps) {
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("owner@acme-demo.example.com");
  const [password, setPassword] = useState("demo1234");
  const [fullName, setFullName] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [workspaceSlug, setWorkspaceSlug] = useState("");
  const [invitationToken, setInvitationToken] = useState("");

  const isLogin = authMode === "login";
  const isRegister = authMode === "register";

  function submit() {
    if (isLogin) onLogin({ email, password });
    else if (isRegister) onRegister({ email, password, fullName, workspaceName, workspaceSlug });
    else onJoin({ email, password, fullName, invitationToken });
  }

  return (
    <div className="auth-page">
      <section className="auth-brand">
        <div className="brand-mark">T</div>
        <div className="eyebrow">THRESHOLD / CONTROL PLANE</div>
        <h1>Put a deterministic boundary around AI actions.</h1>
        <p>AI proposes. Policies authorize. Humans approve exceptions. Threshold executes, verifies, and records the outcome.</p>
        <div className="trust-row"><span>Policy gates</span><span>Human approvals</span><span>Verified execution</span><span>Audit trail</span></div>
      </section>
      <section className="auth-panel">
        <div className="auth-card">
          <div className="auth-switch three">
            <button className={isLogin ? "active" : "ghost"} onClick={() => setAuthMode("login")}>Sign in</button>
            <button className={isRegister ? "active" : "ghost"} onClick={() => setAuthMode("register")}>Create</button>
            <button className={authMode === "join" ? "active" : "ghost"} onClick={() => setAuthMode("join")}>Join team</button>
          </div>
          <h2>{isLogin ? "Welcome back" : isRegister ? "Create your workspace" : "Join a workspace"}</h2>
          <p>{isLogin ? "Use the seeded demo credentials or your account." : isRegister ? "Start with an isolated trial workspace." : "Paste the one-time invitation token from your workspace administrator."}</p>
          {!isLogin && <label>Full name<input value={fullName} onChange={e => setFullName(e.target.value)} placeholder="Ada Lovelace" /></label>}
          {isRegister && <>
            <label>Workspace name<input value={workspaceName} onChange={e => setWorkspaceName(e.target.value)} placeholder="Acme Operations" /></label>
            <label>Workspace slug<input value={workspaceSlug} onChange={e => setWorkspaceSlug(e.target.value.toLowerCase().replace(/\s+/g, "-"))} placeholder="acme-operations" /></label>
          </>}
          {authMode === "join" && <label>Invitation token<input value={invitationToken} onChange={e => setInvitationToken(e.target.value)} placeholder="Paste invitation token" /></label>}
          <label>Email<input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@company.com" /></label>
          <label>Password<input value={password} onChange={e => setPassword(e.target.value)} type="password" placeholder="At least 8 characters" /></label>
          <button className="primary wide" onClick={submit}>{isLogin ? "Sign in" : isRegister ? "Create account" : "Join workspace"}</button>
          {isLogin && <div className="demo-note"><strong>Local demo</strong><span>owner@acme-demo.example.com / demo1234</span></div>}
          <div className="status compact" role="status">{status}</div>
        </div>
      </section>
    </div>
  );
}
