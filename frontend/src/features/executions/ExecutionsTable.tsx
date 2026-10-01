import { useNavigate, Link } from "react-router-dom";
import { StatusBadge } from "@/components/ui/Badge";
import { CopyButton } from "@/components/ui/CopyButton";
import { Time } from "@/components/ui/Layout";
import type { ExecutionSummary } from "@/types/api";
import { durationMs, formatDuration, humanize, shortId } from "@/utils/format";
import { useExecutionLookups } from "./data";

export function ExecutionsTable({ rows, compact }: { rows: ExecutionSummary[]; compact?: boolean }) {
  const navigate = useNavigate();
  const { workflowById, actionByExecution } = useExecutionLookups();

  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th scope="col">Execution</th>
            <th scope="col">Workflow</th>
            <th scope="col">Status</th>
            {!compact && <th scope="col">Current step</th>}
            <th scope="col">Started</th>
            <th scope="col" className="num">
              Duration
            </th>
            {!compact && <th scope="col">External action</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const workflow = workflowById.get(row.workflow_id);
            const action = actionByExecution.get(row.id);
            const duration = durationMs(row.started_at, row.completed_at);
            return (
              <tr key={row.id} className="clickable" onClick={() => navigate(`/executions/${row.id}`)}>
                <td>
                  <span className="idchip">
                    <Link to={`/executions/${row.id}`} className="mono" onClick={(e) => e.stopPropagation()}>
                      {shortId(row.id)}
                    </Link>
                    <CopyButton value={row.id} label="Copy execution ID" />
                  </span>
                </td>
                <td>
                  <div className="cell-main">{workflow?.name ?? "—"}</div>
                  {workflow && <div className="cell-sub">{humanize(workflow.trigger_category)} trigger</div>}
                </td>
                <td>
                  <StatusBadge kind="workflow" value={row.status} />
                </td>
                {!compact && <td className="muted">{row.current_step ? humanize(row.current_step) : "—"}</td>}
                <td>
                  <Time value={row.started_at} />
                </td>
                <td className="num">{row.status === "completed" || row.status === "failed" ? formatDuration(duration) : <span className="muted">—</span>}</td>
                {!compact && (
                  <td>
                    {action ? (
                      <span className="row">
                        <StatusBadge kind="action" value={action.status} />
                        <span className="cell-sub">
                          {action.attempt_count}/{action.max_attempts}
                        </span>
                      </span>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
