import { useState, type ReactNode } from "react";
import { CheckCircle2 } from "lucide-react";
import { StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { CopyButton } from "@/components/ui/CopyButton";
import { DataState, EmptyState, TableSkeleton } from "@/components/ui/Feedback";
import { Callout, PageHeader, Panel, Time } from "@/components/ui/Layout";
import { useWorkspace } from "@/features/auth/session";
import { useReconcileAction, useReplayEvent, useRequeueOutbox } from "@/hooks/mutations";
import { useRecovery } from "@/hooks/queries";
import { humanize, shortId } from "@/utils/format";

type Pending = { kind: "event" | "outbox" | "action"; id: string } | null;

function Section({ title, description, count, children }: { title: string; description: string; count: number; children: ReactNode }) {
  if (count === 0) return null;
  return (
    <Panel title={<>{title} <span className="muted">({count})</span></>} description={description} flush>
      <div className="table-wrap">{children}</div>
    </Panel>
  );
}

const Id = ({ id }: { id: string }) => (
  <span className="idchip">
    <code className="mono">{shortId(id)}</code>
    <CopyButton value={id} label="Copy ID" />
  </span>
);
const Err = ({ text }: { text: string | null }) => (text ? <span className="cell-err mono small" title={text}>{text}</span> : <span className="muted">—</span>);

export function RecoveryPage() {
  const { canReview, canManage } = useWorkspace();
  const query = useRecovery();
  const replay = useReplayEvent();
  const requeue = useRequeueOutbox();
  const reconcile = useReconcileAction();
  const [pending, setPending] = useState<Pending>(null);

  const close = () => setPending(null);
  const confirm = () => {
    if (!pending) return;
    const opts = { onSettled: close };
    if (pending.kind === "event") replay.mutate(pending.id, opts);
    if (pending.kind === "outbox") requeue.mutate(pending.id, opts);
    if (pending.kind === "action") reconcile.mutate(pending.id, opts);
  };
  const busy = replay.isPending || requeue.isPending || reconcile.isPending;

  const copy = {
    event: { title: "Replay this event?", description: "Threshold re-submits the inbound event for processing. If it already produced an execution, the API will refuse and tell you why.", label: "Replay event" },
    outbox: { title: "Requeue this delivery?", description: "The outbox message returns to the queue and will be delivered again.", label: "Requeue" },
    action: { title: "Reconcile this action?", description: "Threshold asks the provider what happened. It does not issue the side effect again.", label: "Reconcile" },
  };

  return (
    <>
      <PageHeader title="Recovery" description="Inbound events, deliveries and actions that failed or are retrying. Nothing here is lost: each can be replayed, requeued or reconciled." />
      <DataState
        query={query}
        errorTitle="Couldn't load recovery items"
        loading={<div className="table-wrap"><TableSkeleton rows={4} columns={6} /></div>}
        isEmpty={(d) => d.events.length + d.outbox.length + d.actions.length === 0}
        empty={<Panel><EmptyState icon={<CheckCircle2 size={18} />} title="Nothing needs recovery" description="No failed events, stuck deliveries or unresolved actions right now." /></Panel>}
      >
        {(data) => (
          <div className="stack">
            {!canReview && <Callout tone="neutral">Reviewer access is required to recover items. You can view them here.</Callout>}
            <Section title="Failed inbound events" description="Events that couldn't be processed." count={data.events.length}>
              <table className="data">
                <thead><tr><th scope="col">Event</th><th scope="col">External ID</th><th scope="col">Status</th><th scope="col" className="num">Attempts</th><th scope="col">Next retry</th><th scope="col">Error</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
                <tbody>
                  {data.events.map((e) => (
                    <tr key={e.id}>
                      <td><Id id={e.id} /></td>
                      <td className="mono small">{e.external_id ?? "—"}</td>
                      <td><StatusBadge kind="event" value={e.status} /></td>
                      <td className="num">{e.attempts}/{e.max_attempts}</td>
                      <td>{e.next_retry_at ? <Time value={e.next_retry_at} /> : <span className="muted">—</span>}</td>
                      <td><Err text={e.error} /></td>
                      <td className="cell-actions"><Button size="sm" disabled={!canReview} onClick={() => setPending({ kind: "event", id: e.id })}>Replay</Button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>
            <Section title="Outbox deliveries" description="Internal messages that haven't been delivered." count={data.outbox.length}>
              <table className="data">
                <thead><tr><th scope="col">Message</th><th scope="col">Topic</th><th scope="col">Aggregate</th><th scope="col">Status</th><th scope="col" className="num">Attempts</th><th scope="col">Error</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
                <tbody>
                  {data.outbox.map((o) => (
                    <tr key={o.id}>
                      <td><Id id={o.id} /></td>
                      <td className="mono small">{o.topic}</td>
                      <td className="small">{humanize(o.aggregate_type)} <span className="mono muted">{shortId(o.aggregate_id)}</span></td>
                      <td><StatusBadge kind="outbox" value={o.status} /></td>
                      <td className="num">{o.attempts}/{o.max_attempts}</td>
                      <td><Err text={o.error} /></td>
                      <td className="cell-actions"><Button size="sm" disabled={!canManage} title={canManage ? undefined : "Admin access required"} onClick={() => setPending({ kind: "outbox", id: o.id })}>Requeue</Button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>
            <Section title="Actions needing attention" description="External actions that failed, are retrying, or have an unknown outcome." count={data.actions.length}>
              <table className="data">
                <thead><tr><th scope="col">Action</th><th scope="col">Type</th><th scope="col">Status</th><th scope="col" className="num">Attempts</th><th scope="col">Next retry</th><th scope="col">Error</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
                <tbody>
                  {data.actions.map((a) => (
                    <tr key={a.id}>
                      <td><Id id={a.id} /></td>
                      <td>{humanize(a.action_type)}</td>
                      <td><StatusBadge kind="action" value={a.status} /></td>
                      <td className="num">{a.attempts}/{a.max_attempts}</td>
                      <td>{a.next_retry_at ? <Time value={a.next_retry_at} /> : <span className="muted">—</span>}</td>
                      <td><Err text={a.error} /></td>
                      <td className="cell-actions"><Button size="sm" disabled={!canReview} onClick={() => setPending({ kind: "action", id: a.id })}>Reconcile</Button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>
          </div>
        )}
      </DataState>
      {pending && (
        <ConfirmDialog open onClose={close} onConfirm={confirm} title={copy[pending.kind].title} description={copy[pending.kind].description} confirmLabel={copy[pending.kind].label} loading={busy} />
      )}
    </>
  );
}
