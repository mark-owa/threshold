import { useState } from "react";
import { Link } from "react-router-dom";
import { Zap } from "lucide-react";
import { StatusBadge } from "@/components/ui/Badge";
import { Dialog } from "@/components/ui/Dialog";
import { CopyButton } from "@/components/ui/CopyButton";
import { DataState, EmptyState, TableSkeleton } from "@/components/ui/Feedback";
import { PageHeader, Time } from "@/components/ui/Layout";
import { ActionBody } from "@/features/executions/ActionCard";
import { useActions } from "@/hooks/queries";
import type { ActionStatus, ActionSummary } from "@/types/api";
import { humanize, shortId } from "@/utils/format";

const STATUSES: ActionStatus[] = ["pending", "executing", "succeeded", "failed", "retrying", "dead_letter", "rolled_back", "unknown"];

export function ActionsPage() {
  const query = useActions(100);
  const [status, setStatus] = useState("all");
  const [open, setOpen] = useState<ActionSummary | null>(null);

  return (
    <>
      <PageHeader title="Actions" description="Every side effect Threshold has attempted against an external provider, with attempts and verification state." />
      <div className="table-toolbar">
        <select className="input select select--sm" aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="all">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {humanize(s)}
            </option>
          ))}
        </select>
      </div>
      <DataState
        query={query}
        errorTitle="Couldn't load actions"
        loading={<div className="table-wrap"><TableSkeleton rows={6} columns={7} /></div>}
        isEmpty={(d) => d.length === 0}
        empty={<EmptyState icon={<Zap size={18} />} title="No actions yet" description="External actions appear here once a workflow executes one." />}
      >
        {(rows) => {
          const shown = rows.filter((r) => status === "all" || r.status === status);
          return shown.length === 0 ? (
            <div className="table-wrap"><EmptyState compact title="No actions with this status" /></div>
          ) : (
            <>
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th scope="col">Action</th>
                      <th scope="col">Type</th>
                      <th scope="col">Execution</th>
                      <th scope="col">Status</th>
                      <th scope="col" className="num">Attempts</th>
                      <th scope="col">Verified</th>
                      <th scope="col">Next retry</th>
                      <th scope="col">Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {shown.map((a) => (
                      <tr key={a.id} className="clickable" onClick={() => setOpen(a)}>
                        <td>
                          <span className="idchip">
                            <button type="button" className="linklike mono" onClick={(e) => { e.stopPropagation(); setOpen(a); }}>{shortId(a.id)}</button>
                            <CopyButton value={a.id} label="Copy action ID" />
                          </span>
                        </td>
                        <td>{humanize(a.action_type)}</td>
                        <td>
                          <Link to={`/executions/${a.execution_id}`} className="mono" onClick={(e) => e.stopPropagation()}>
                            {shortId(a.execution_id)}
                          </Link>
                        </td>
                        <td><StatusBadge kind="action" value={a.status} /></td>
                        <td className="num">{a.attempt_count}/{a.max_attempts}</td>
                        <td>{a.verified_at ? <Time value={a.verified_at} /> : <span className="muted">—</span>}</td>
                        <td>{a.next_retry_at ? <Time value={a.next_retry_at} /> : <span className="muted">—</span>}</td>
                        <td className="cell-err mono small" title={a.error ?? undefined}>{a.error ?? <span className="muted">—</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="table-footnote">Showing the {rows.length} most recent actions.</p>
            </>
          );
        }}
      </DataState>
      <Dialog variant="drawer" open={!!open} onClose={() => setOpen(null)} title={open ? `${humanize(open.action_type)} action` : ""} description="Provider attempts, verification and reconciliation.">
        {open && <ActionBody actionId={open.id} summary={open} />}
      </Dialog>
    </>
  );
}
