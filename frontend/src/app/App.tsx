import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Spinner } from "@/components/ui/Feedback";
import { JoinPage, LoginPage, RegisterPage } from "@/features/auth/AuthPages";
import { useSession } from "@/features/auth/session";
import { AppShell } from "@/layouts/AppShell";
import { ActionsPage } from "@/pages/ActionsPage";
import { ApprovalsPage } from "@/pages/ApprovalsPage";
import { AuditPage } from "@/pages/AuditPage";
import { BillingPage } from "@/pages/BillingPage";
import { DemoPage } from "@/pages/DemoPage";
import { ExecutionDetailPage } from "@/pages/ExecutionDetailPage";
import { ExecutionsPage } from "@/pages/ExecutionsPage";
import { IntegrationsPage } from "@/pages/IntegrationsPage";
import { LiveExecutionPage } from "@/pages/LiveExecutionPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { OverviewPage } from "@/pages/OverviewPage";
import { PoliciesPage } from "@/pages/PoliciesPage";
import { RecoveryPage } from "@/pages/RecoveryPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { TeamPage } from "@/pages/TeamPage";
import { WebhooksPage } from "@/pages/WebhooksPage";
import { WorkflowsPage } from "@/pages/WorkflowsPage";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { status } = useSession();
  const location = useLocation();
  if (status === "loading") {
    return (
      <div className="center-screen">
        <Spinner size={22} />
      </div>
    );
  }
  if (status === "anonymous") return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <>{children}</>;
}

/** Stripe checkout returns to `/?billing=success|cancelled`; keep that query and land on Billing. */
function RootRedirect() {
  const { search } = useLocation();
  const billing = new URLSearchParams(search).get("billing");
  return <Navigate to={billing ? `/billing?billing=${encodeURIComponent(billing)}` : "/overview"} replace />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/join" element={<JoinPage />} />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<RootRedirect />} />
        <Route path="overview" element={<OverviewPage />} />
        <Route path="workflows" element={<WorkflowsPage />} />
        <Route path="executions" element={<ExecutionsPage />} />
        <Route path="executions/:id" element={<ExecutionDetailPage />} />
        <Route path="approvals" element={<ApprovalsPage />} />
        <Route path="actions" element={<ActionsPage />} />
        <Route path="recovery" element={<RecoveryPage />} />
        <Route path="audit" element={<AuditPage />} />
        <Route path="integrations" element={<IntegrationsPage />} />
        <Route path="webhooks" element={<WebhooksPage />} />
        <Route path="policies" element={<PoliciesPage />} />
        <Route path="live-execution" element={<LiveExecutionPage />} />
        <Route path="team" element={<TeamPage />} />
        <Route path="billing" element={<BillingPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="demo" element={<DemoPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
