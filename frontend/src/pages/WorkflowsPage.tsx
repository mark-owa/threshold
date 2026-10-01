import { useMemo } from "react";
import { Link } from "react-router-dom";
import { GitBranch } from "lucide-react";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { DataState, EmptyState, TableSkeleton } from "@/components/ui/Feedback";
import { Callout, PageHeader, Panel, Time } from "@/components/ui/Layout";
import { useExecutions, useWorkflows } from "@/hooks/queries";
import { humanize } from "@/utils/format";

export function WorkflowsPage() {
  const workflows = useWorkflows();
  const executions = useExecutions(100);

  const stats = useMemo(() => {
    const map = new Map<string, { latest: (typeof executions.data extends (infer T)[] | undefined ? T : never) | null; runs: number; failed: number }>();
    for (const e of executions.data ?? []) {
      const s = map.get(e.workflow_id) ?? { latest: null, runs: 0, failed: 0 };
      if (!s.latest) s.latest = e; // list is newest-first
      s.runs += 1;
      if (e.status === "failed") s.failed += 1;
      map.set(e.workflow_id, s);
    }
    return map;
  }, [executions.data]);

  return (
    <>
      <PageHeader title="Workflows" description="The processes Threshold runs when an event arrives." />
      <div className="section">
        <Callout tone="neutral" title="Read-only">
          Workflow definitions are shown as configured. Editing them isn't available in the dashboard.
        </Callout>
      </div>
      <DataState
        query={workflows}
        errorTitle="Couldn't load workflows"
        loading={
          <div className="table-wrap">
            <TableSkeleton rows={3} columns={6} />
          </div>
        }
        isEmpty={(d) => d.length === 0}
        empty={<Panel><EmptyState icon={<GitBranch size={18} />} title="No workflows" description="No workflow definitions are available to this workspace." /></Panel>}
      >
        {(rows) => (
          <>
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th scope="col">Workflow</th>
                    <th scope="col">Trigger</th>
                    <th scope="col">Scope</th>
                    <th scope="col">State</th>
                    <th scope="col">Latest execution</th>
                    <th scope="col" className="num">Recent runs</th>
                    <th scope="col" className="num">Failed</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((w) => {
                    const s = stats.get(w.id);
                    return (
                      <tr key={w.id}>
                        <td>
                          <div className="cell-main">
                            {w.name} <span className="muted mono small">v{w.version}</span>
                          </div>
                          <div className="cell-sub">{w.description ?? <span className="mono">{w.key}</span>}</div>
                        </td>
                        <td>{humanize(w.trigger_category)}</td>
                        <td>
                          <Badge>{w.scope === "template" ? "Template" : "Workspace"}</Badge>
                        </td>
                        <td>{w.is_active ? <Badge tone="success" dot>Active</Badge> : <Badge>Inactive</Badge>}</td>
                        <td>
                          {s?.latest ? (
                            <Link to={`/executions/${s.latest.id}`} className="row">
                              <StatusBadge kind="workflow" value={s.latest.status} /> <span className="small muted"><Time value={s.latest.started_at} /></span>
                            </Link>
                          ) : (
                            <span className="muted">{executions.isPending ? "…" : "No runs yet"}</span>
                          )}
                        </td>
                        <td className="num">{s?.runs ?? 0}</td>
                        <td className="num">{s?.failed ? <span className="text-danger">{s.failed}</span> : 0}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="table-footnote">Run counts cover the 100 most recent executions in this workspace.</p>
          </>
        )}
      </DataState>
    </>
  );
}
