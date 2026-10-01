import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { RotateCcw } from "lucide-react";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { IdChip } from "@/components/ui/CopyButton";
import { CardSkeleton, DataState, ErrorState, Skeleton } from "@/components/ui/Feedback";
import { JsonViewer } from "@/components/ui/JsonViewer";
import { Callout, KeyValue, PageHeader, Panel, Time } from "@/components/ui/Layout";
import { ApiError } from "@/api/client";
import { useWorkspace } from "@/features/auth/session";
import { ExecutionTimeline } from "@/features/executions/ExecutionTimeline";
import { ActionCard } from "@/features/executions/ActionCard";
import { useExecutionLookups } from "@/features/executions/data";
import { useAudit, useExecution } from "@/hooks/queries";
import { useRetryExecution } from "@/hooks/mutations";
import type { ExecutionDetail } from "@/types/api";
import { durationMs, formatDuration, formatPercent, humanize } from "@/utils/format";
import { stepMeta } from "@/utils/status";

function AuditTrail({ executionId }: { executionId: string }) {
  const query = useAudit(200);
  return (
    <Panel title="Audit trail" description="Recorded events for this execution." flush>
      <DataState query={query} errorTitle="Couldn't load the audit log" loading={<CardSkeleton />} compactError>
        {(entries) => {
          const mine = entries.filter((e) => e.execution_id === executionId);
          if (mine.length === 0) return <p className="panel__pad muted small">No audit entries in the most recent 200 events.</p>;
          return (
            <ul className="list">
              {mine.map((e) => (
                <li key={e.id} className="list__item list__item--static">
                  <span className="list__text">
                    <span className="list__title mono">{e.event_type}</span>
                    <span className="list__sub">{humanize(e.actor_type)}</span>
                  </span>
                  <span className="small muted">
                    <Time value={e.created_at} />
                  </span>
                </li>
              ))}
            </ul>
          );
        }}
      </DataState>
    </Panel>
  );
}

function Body({ execution }: { execution: ExecutionDetail }) {
  const { canReview } = useWorkspace();
  const { workflowById, actionByExecution } = useExecutionLookups();
  const retry = useRetryExecution();
  const [confirmRetry, setConfirmRetry] = useState(false);

  const workflow = workflowById.get(execution.workflow_id);
  const action = actionByExecution.get(execution.id);
  const failedStep = execution.steps.find((s) => s.status === "failed");
  const approvalStep = execution.steps.find((s) => s.step_type === "approval_gate" && typeof s.output?.approval_id === "string");
  const approvalId = approvalStep?.output?.approval_id as string | undefined;
  const ctx = execution.context;
  const duration = durationMs(execution.started_at, execution.completed_at);

  return (
    <>
      <PageHeader
        back={{ to: "/executions", label: "Executions" }}
        title={
          <span className="row">
            {workflow?.name ?? "Execution"} <StatusBadge kind="workflow" value={execution.status} />
          </span>
        }
        description={<IdChip id={execution.id} full />}
        actions={
          execution.status === "failed" && canReview ? (
            <Button variant="primary" icon={<RotateCcw size={14} />} onClick={() => setConfirmRetry(true)}>
              Retry execution
            </Button>
          ) : undefined
        }
      />

      <div className="stack section">
        {execution.status === "failed" && (
          <Callout
            tone="danger"
            title={failedStep ? `Failed at “${stepMeta(failedStep.step_type).title}”` : "Execution failed"}
          >
            <span className="mono">{execution.error ?? failedStep?.error ?? "No error message was recorded."}</span>
            {!canReview && <div className="small muted">Reviewer access is required to retry.</div>}
          </Callout>
        )}
        {execution.status === "awaiting_approval" && (
          <Callout
            tone="warning"
            title="Waiting for a human decision"
            actions={
              canReview && approvalId ? (
                <Link to={`/approvals?focus=${approvalId}`}>
                  <Button size="sm" variant="primary">
                    Review approval
                  </Button>
                </Link>
              ) : undefined
            }
          >
            Policy requires a reviewer to approve this action before Threshold executes it.
          </Callout>
        )}
        {execution.status === "waiting_external" && (
          <Callout tone="info" title="Waiting on the external provider">
            The action was sent and Threshold is waiting for the provider to confirm the outcome.
          </Callout>
        )}
      </div>

      <div className="split split--detail">
        <Panel title="Control path" description="Each step Threshold ran, in order. Who decided is shown on every step.">
          <ExecutionTimeline steps={execution.steps} context={ctx} />
        </Panel>
        <div className="stack">
          <Panel title="Summary">
            <KeyValue
              items={[
                { label: "Workflow", value: workflow ? `${workflow.name} v${workflow.version}` : "—" },
                { label: "Trigger", value: workflow ? humanize(workflow.trigger_category) : "—" },
                { label: "Category", value: ctx.category ? humanize(String(ctx.category)) : "—" },
                { label: "AI confidence", value: typeof ctx.ai_confidence === "number" ? formatPercent(Math.round(ctx.ai_confidence * 100)) : "—" },
                { label: "Risk", value: ctx.risk_level ? <Badge tone={ctx.risk_level === "high" ? "danger" : ctx.risk_level === "medium" ? "warning" : "success"}>{humanize(ctx.risk_level)}</Badge> : "—" },
                { label: "Approval", value: ctx.approval_required === undefined ? "—" : ctx.approval_required ? "Required" : "Not required" },
                { label: "Started", value: <Time value={execution.started_at} absolute /> },
                { label: "Completed", value: <Time value={execution.completed_at} absolute /> },
                { label: "Duration", value: formatDuration(duration) },
              ]}
            />
            {ctx.ai_rationale && <p className="small muted rationale">AI rationale: {String(ctx.ai_rationale)}</p>}
          </Panel>
          {action && <ActionCard actionId={action.id} summary={action} />}
          <AuditTrail executionId={execution.id} />
          <Panel title="Execution context" description="Advanced: the raw data passed between steps.">
            <JsonViewer value={ctx as never} expandDepth={0} maxHeight={320} label="Execution context" />
          </Panel>
        </div>
      </div>

      <ConfirmDialog
        open={confirmRetry}
        onClose={() => setConfirmRetry(false)}
        title="Retry this execution?"
        description="Threshold will re-run the failed execution. The outcome is recorded in the audit log."
        confirmLabel="Retry execution"
        loading={retry.isPending}
        onConfirm={() => retry.mutate(execution.id, { onSettled: () => setConfirmRetry(false) })}
      />
    </>
  );
}

export function ExecutionDetailPage() {
  const { id = "" } = useParams();
  const query = useExecution(id);

  if (query.isError && query.error instanceof ApiError && query.error.status === 404) {
    return (
      <>
        <PageHeader back={{ to: "/executions", label: "Executions" }} title="Execution not found" />
        <ErrorState title="Execution not found" error={new Error("It may belong to another workspace, or the link is wrong.")} />
      </>
    );
  }

  return (
    <DataState
      query={query}
      errorTitle="Couldn't load this execution"
      loading={
        <>
          <PageHeader back={{ to: "/executions", label: "Executions" }} title={<Skeleton width={260} height={24} />} />
          <div className="split split--detail">
            <Panel>
              <CardSkeleton lines={8} />
            </Panel>
            <Panel>
              <CardSkeleton lines={6} />
            </Panel>
          </div>
        </>
      }
    >
      {(execution) => <Body execution={execution} />}
    </DataState>
  );
}

