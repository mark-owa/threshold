import { Link } from "react-router-dom";
import { ArrowRight, CheckCircle2, ShieldAlert } from "lucide-react";
import { StatusBadge, Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CardSkeleton, DataState, EmptyState, Skeleton, TableSkeleton } from "@/components/ui/Feedback";
import { Callout, Metric, PageHeader, Panel, Time } from "@/components/ui/Layout";
import { useWorkspace } from "@/features/auth/session";
import { ExecutionsTable } from "@/features/executions/ExecutionsTable";
import { StepStrip } from "@/features/executions/ExecutionTimeline";
import { useApprovals, useExecution, useExecutions, useIntegrations, useMetrics, useOnboarding, useRecovery, useWorkflows } from "@/hooks/queries";
import type { Metrics } from "@/types/api";
import { formatCurrency, formatDuration, formatNumber, formatPercent, humanize, shortId } from "@/utils/format";
import { riskFactorText, extractRiskFactors } from "@/utils/status";

function MetricStrip({ metrics, recoveryCount }: { metrics: Metrics; recoveryCount: number | null }) {
  const settledNote = "of runs that have finished";
  const hasRuns = metrics.total_executions > 0;
  return (
    <div className="metrics" role="group" aria-label="Key metrics">
      <Metric label="Executions" value={formatNumber(metrics.total_executions)} note={`${formatNumber(metrics.completed)} completed`} to="/executions" />
      <Metric
        label="Success rate"
        value={hasRuns ? formatPercent(metrics.workflow_success_rate_percent) : "—"}
        note={settledNote}
      />
      <Metric label="Automation rate" value={hasRuns ? formatPercent(metrics.automation_rate_percent) : "—"} note="completed with no approval needed" />
      <Metric
        label="Awaiting approval"
        value={formatNumber(metrics.awaiting_approval)}
        tone={metrics.awaiting_approval ? "warning" : undefined}
        note={metrics.awaiting_approval ? "Needs a reviewer" : "Nothing to review"}
        to="/approvals"
      />
      <Metric
        label="Failed"
        value={formatNumber(metrics.failed)}
        tone={metrics.failed ? "danger" : undefined}
        note={metrics.failed ? (recoveryCount ? `${recoveryCount} item${recoveryCount === 1 ? "" : "s"} in recovery` : "Open the failed runs") : "No failed executions"}
        to="/executions"
      />
      <Metric label="Avg step latency" value={hasRuns ? formatDuration(metrics.average_step_latency_ms) : "—"} note={`AI spend ${formatCurrency(metrics.estimated_ai_cost_usd)}`} />
    </div>
  );
}

function LatestRun({ executionId }: { executionId: string }) {
  const query = useExecution(executionId);
  const workflows = useWorkflows().data;
  return (
    <DataState query={query} errorTitle="Couldn't load the latest execution" loading={<CardSkeleton lines={2} />} compactError>
      {(execution) => (
        <div className="stack">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div className="row">
              <Link to={`/executions/${execution.id}`} className="mono">
                {shortId(execution.id)}
              </Link>
              <span className="muted">·</span>
              <span>{workflows?.find((w) => w.id === execution.workflow_id)?.name ?? "Workflow"}</span>
              <StatusBadge kind="workflow" value={execution.status} />
            </div>
            <Time value={execution.started_at} />
          </div>
          <StepStrip steps={execution.steps} />
          <Link to={`/executions/${execution.id}`} className="row small">
            Open the full control path <ArrowRight size={12} aria-hidden />
          </Link>
        </div>
      )}
    </DataState>
  );
}

function ApprovalsPanel() {
  const { canReview } = useWorkspace();
  const query = useApprovals("pending", canReview);
  return (
    <Panel title="Pending approvals" description="Actions waiting on a human decision." actions={<Link to="/approvals" className="small">View all</Link>} flush>
      {!canReview ? (
        <EmptyState compact title="Reviewer access required" description="Ask an admin for the reviewer role to see and decide approvals." />
      ) : (
        <DataState query={query} errorTitle="Couldn't load approvals" loading={<CardSkeleton />} compactError isEmpty={(d) => d.length === 0} empty={<EmptyState compact icon={<CheckCircle2 size={18} />} title="Nothing requires review" description="Approvals appear here when policy needs a human decision." />}>
          {(approvals) => (
            <ul className="list">
              {approvals.slice(0, 5).map((a) => {
                const factors = extractRiskFactors(a.risk_factors);
                return (
                  <li key={a.id}>
                    <Link to={`/approvals?focus=${a.id}`} className="list__item">
                      <ShieldAlert size={16} className="list__icon list__icon--warning" aria-hidden />
                      <span className="list__text">
                        <span className="list__title">{humanize(a.proposed_action?.action_type ?? "action")}</span>
                        <span className="list__sub">{factors.length ? riskFactorText(factors[0] ?? "") : a.reason}</span>
                      </span>
                      <Badge tone={a.risk_level === "high" ? "danger" : a.risk_level === "medium" ? "warning" : "success"}>{humanize(a.risk_level)}</Badge>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </DataState>
      )}
    </Panel>
  );
}

function IntegrationsPanel() {
  const query = useIntegrations();
  return (
    <Panel title="Integration health" actions={<Link to="/integrations" className="small">Manage</Link>} flush>
      <DataState query={query} errorTitle="Couldn't load integrations" loading={<CardSkeleton />} compactError isEmpty={(d) => d.length === 0} empty={<EmptyState compact title="No integrations" description="Connect a service so Threshold can execute actions outside the platform." />}>
        {(integrations) => (
          <ul className="list">
            {integrations.map((i) => (
              <li key={i.id} className="list__item">
                <span className="list__text">
                  <span className="list__title">{humanize(i.provider)}</span>
                  <span className="list__sub">{i.consecutive_failures > 0 ? `${i.consecutive_failures}/${i.failure_threshold} consecutive failures` : "No recent failures"}</span>
                </span>
                {!i.is_enabled ? <Badge>Disabled</Badge> : i.health === "circuit_open" ? <Badge tone="danger" dot>Circuit open</Badge> : <Badge tone="success" dot>Available</Badge>}
              </li>
            ))}
          </ul>
        )}
      </DataState>
    </Panel>
  );
}

function RecoveryPanel({ count }: { count: number | null }) {
  return (
    <Panel title="Recovery" actions={<Link to="/recovery" className="small">Open</Link>}>
      {count === null ? (
        <Skeleton width="60%" />
      ) : count === 0 ? (
        <p className="row muted">
          <CheckCircle2 size={15} className="ok" aria-hidden /> Nothing is stuck or waiting to be recovered.
        </p>
      ) : (
        <p>
          <strong>{count}</strong> item{count === 1 ? "" : "s"} failed or are retrying and may need attention.
        </p>
      )}
    </Panel>
  );
}

export function OverviewPage() {
  const { workspace, isDemo } = useWorkspace();
  const metrics = useMetrics();
  const executions = useExecutions(25);
  const recovery = useRecovery();
  const onboarding = useOnboarding();

  const recoveryCount = recovery.data ? recovery.data.events.length + recovery.data.outbox.length + recovery.data.actions.length : recovery.isError ? 0 : null;
  const nextStep = !isDemo ? onboarding.data?.steps.find((s) => !s.complete) : undefined;
  const latest = executions.data?.[0];

  return (
    <>
      <PageHeader
        title="Overview"
        description={`Operational overview for ${workspace.name}`}
        actions={
          <Link to="/executions">
            <Button>View executions</Button>
          </Link>
        }
      />

      {onboarding.data && nextStep && onboarding.data.percent_complete < 100 && (
        <div className="section">
          <Callout tone="info" title={`Workspace setup: ${onboarding.data.completed_steps} of ${onboarding.data.total_steps} steps complete`}>
            Next: <strong>{nextStep.title}</strong>. {nextStep.description}
          </Callout>
        </div>
      )}

      <div className="section">
        <DataState query={metrics} errorTitle="Couldn't load metrics" loading={<div className="metrics">{Array.from({ length: 6 }, (_, i) => <div className="metric" key={i}><Skeleton width="50%" /><Skeleton width="40%" height={26} className="mt" /></div>)}</div>}>
          {(m) => <MetricStrip metrics={m} recoveryCount={recoveryCount} />}
        </DataState>
      </div>

      <div className="split">
        <div className="stack">
          <Panel title="Recent executions" description="Latest workflow runs in this workspace." actions={<Link to="/executions" className="small">View all</Link>} flush>
            <DataState
              query={executions}
              errorTitle="Couldn't load executions"
              loading={<TableSkeleton rows={6} columns={5} />}
              isEmpty={(d) => d.length === 0}
              empty={<EmptyState title="No executions yet" description="Workflow executions will appear here after Threshold processes its first event." />}
            >
              {(rows) => <ExecutionsTable rows={rows.slice(0, 8)} compact />}
            </DataState>
          </Panel>
          {latest && (
            <Panel title="Latest execution" description="How the most recent event moved through Threshold.">
              <LatestRun executionId={latest.id} />
            </Panel>
          )}
        </div>
        <div className="stack">
          <ApprovalsPanel />
          <IntegrationsPanel />
          <RecoveryPanel count={recoveryCount} />
        </div>
      </div>
    </>
  );
}
