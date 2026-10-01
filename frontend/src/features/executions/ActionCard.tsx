import { useState } from "react";
import { RefreshCcw } from "lucide-react";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { CardSkeleton, ErrorState } from "@/components/ui/Feedback";
import { IdChip } from "@/components/ui/CopyButton";
import { JsonViewer } from "@/components/ui/JsonViewer";
import { KeyValue, Panel, Time } from "@/components/ui/Layout";
import { useWorkspace } from "@/features/auth/session";
import { useReconcileAction } from "@/hooks/mutations";
import { useAction } from "@/hooks/queries";
import type { ActionSummary } from "@/types/api";
import { humanize } from "@/utils/format";
import type { Tone } from "@/utils/status";

const RECONCILABLE = new Set(["unknown", "retrying", "failed", "dead_letter"]);

function outcomeTone(outcome: string): Tone {
  if (/succe|ok|confirmed|found/i.test(outcome)) return "success";
  if (/fail|error|timeout|reject/i.test(outcome)) return "danger";
  return "neutral";
}

/** Attempts ledger and reconcile control for one external action. */
export function ActionBody({ actionId, summary }: { actionId: string; summary: ActionSummary }) {
  const { canReview } = useWorkspace();
  const query = useAction(actionId);
  const reconcile = useReconcileAction();
  const [confirming, setConfirming] = useState(false);

  return (
    <div className="stack">
      <KeyValue
        items={[
          { label: "Action", value: humanize(summary.action_type) },
          { label: "Status", value: <StatusBadge kind="action" value={summary.status} /> },
          { label: "Attempts", value: `${summary.attempt_count} of ${summary.max_attempts}` },
          { label: "Verified", value: summary.verified_at ? <Time value={summary.verified_at} absolute /> : "Not verified" },
          { label: "Next retry", value: summary.next_retry_at ? <Time value={summary.next_retry_at} absolute /> : "—" },
          { label: "Action ID", value: <IdChip id={summary.id} /> },
        ]}
      />
      {summary.error && (
        <p className="form-error mono" role="alert">
          {summary.error}
        </p>
      )}

      {query.isPending ? (
        <CardSkeleton lines={2} />
      ) : query.isError ? (
        <ErrorState compact title="Couldn't load attempts" error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        <div>
          <div className="tl__detail-label">Provider attempts</div>
          {query.data.attempts.length === 0 ? (
            <p className="muted small">No provider calls have been made yet.</p>
          ) : (
            <ul className="attempts">
              {query.data.attempts.map((a) => (
                <li key={a.id} className="attempts__item">
                  <span className="attempts__n mono">#{a.attempt_number}</span>
                  <span className="attempts__body">
                    <span className="row">
                      <strong>{humanize(a.operation)}</strong>
                      <span className="muted">via {a.provider}</span>
                      <Badge tone={outcomeTone(a.outcome)}>{humanize(a.outcome)}</Badge>
                    </span>
                    {a.error && <span className="mono small attempts__err">{a.error}</span>}
                    <span className="small muted">
                      <Time value={a.started_at} absolute />
                      {a.provider_operation_id && <> · provider ref {a.provider_operation_id}</>}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          )}
          <details className="advanced">
            <summary>Idempotency key &amp; payloads</summary>
            <div className="stack stack--sm">
              <p className="small">
                Idempotency key: <code className="mono">{query.data.idempotency_key}</code>
              </p>
              <JsonViewer value={{ request: query.data.request_payload, response: query.data.response_payload }} expandDepth={2} maxHeight={260} label="Action payloads" />
            </div>
          </details>
        </div>
      )}

      {canReview && RECONCILABLE.has(summary.status) && (
        <div>
          <Button size="sm" icon={<RefreshCcw size={13} />} onClick={() => setConfirming(true)}>
            Reconcile with provider
          </Button>
        </div>
      )}
      <ConfirmDialog
        open={confirming}
        onClose={() => setConfirming(false)}
        title="Reconcile this action?"
        description="Threshold asks the provider what happened. It does not issue the side effect again."
        confirmLabel="Reconcile"
        loading={reconcile.isPending}
        onConfirm={() => reconcile.mutate(summary.id, { onSettled: () => setConfirming(false) })}
      />
    </div>
  );
}

export function ActionCard({ actionId, summary }: { actionId: string; summary: ActionSummary }) {
  return (
    <Panel title="External action" description="What Threshold did outside the platform.">
      <ActionBody actionId={actionId} summary={summary} />
    </Panel>
  );
}
