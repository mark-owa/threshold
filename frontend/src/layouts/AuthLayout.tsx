import type { ReactNode } from "react";
import { Logo } from "@/components/Logo";

const PRINCIPLES = [
  { title: "AI proposes", body: "Models classify requests and draft actions. They never execute anything." },
  { title: "Policy decides", body: "Deterministic rules and risk thresholds authorise or block each action." },
  { title: "Humans approve", body: "High-risk actions pause for a reviewer, who can approve, reject or modify." },
  { title: "Threshold executes and audits", body: "Actions run idempotently against providers, with retries, recovery and a full audit trail." },
];

export function AuthLayout({ title, description, children, footer }: { title: string; description: string; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="auth">
      <aside className="auth__aside">
        <div className="auth__brand">
          <Logo size={22} />
          <span>Threshold</span>
        </div>
        <div>
          <h2 className="auth__headline">Reliable operations for AI-assisted business processes.</h2>
          <ol className="auth__list">
            {PRINCIPLES.map((p, i) => (
              <li key={p.title}>
                <span className="auth__step" aria-hidden>
                  {i + 1}
                </span>
                <div>
                  <div className="auth__step-title">{p.title}</div>
                  <div className="auth__step-body">{p.body}</div>
                </div>
              </li>
            ))}
          </ol>
        </div>
        <div className="auth__foot">Workflow automation with an auditable control path.</div>
      </aside>
      <main className="auth__main">
        <div className="auth__card">
          <h1 className="auth__title">{title}</h1>
          <p className="auth__desc">{description}</p>
          {children}
          {footer && <div className="auth__footer">{footer}</div>}
        </div>
      </main>
    </div>
  );
}
