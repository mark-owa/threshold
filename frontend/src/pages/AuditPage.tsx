import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronRight, ScrollText } from "lucide-react";
import { SearchInput } from "@/components/ui/Fields";
import { DataState, EmptyState, TableSkeleton } from "@/components/ui/Feedback";
import { JsonViewer } from "@/components/ui/JsonViewer";
import { PageHeader, Time } from "@/components/ui/Layout";
import { useAudit } from "@/hooks/queries";
import { cn, humanize, shortId } from "@/utils/format";

export function AuditPage() {
  const [limit, setLimit] = useState(100);
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState<Set<string>>(new Set());
  const query = useAudit(limit);

  const toggle = (id: string) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <>
      <PageHeader title="Audit log" description="An append-only record of what happened, who or what did it, and when." />
      <div className="table-toolbar">
        <SearchInput aria-label="Search audit events" placeholder="Search event type or actor…" value={search} onChange={(e) => setSearch(e.target.value)} />
        <span className="grow" />
        <select className="input select select--sm" aria-label="Number of entries to load" value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
          {[50, 100, 200].map((n) => <option key={n} value={n}>Load latest {n}</option>)}
        </select>
      </div>
      <DataState
        query={query}
        errorTitle="Couldn't load the audit log"
        loading={<div className="table-wrap"><TableSkeleton rows={8} columns={5} /></div>}
        isEmpty={(d) => d.length === 0}
        empty={<EmptyState icon={<ScrollText size={18} />} title="No audit entries yet" description="Every decision and action is recorded here as it happens." />}
      >
        {(rows) => {
          const term = search.trim().toLowerCase();
          const shown = term ? rows.filter((r) => `${r.event_type} ${r.actor_type} ${r.actor_id ?? ""}`.toLowerCase().includes(term)) : rows;
          return shown.length === 0 ? (
            <div className="table-wrap"><EmptyState compact title="No entries match your search" /></div>
          ) : (
            <>
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th scope="col" style={{ width: 32 }}><span className="sr-only">Expand</span></th>
                      <th scope="col">Time</th>
                      <th scope="col">Event</th>
                      <th scope="col">Actor</th>
                      <th scope="col">Execution</th>
                    </tr>
                  </thead>
                  <tbody>
                    {shown.map((r) => {
                      const expanded = open.has(r.id);
                      return (
                        <Fragment key={r.id}>
                          <tr className="clickable" onClick={() => toggle(r.id)}>
                            <td>
                              <button type="button" className={cn("json__toggle audit__toggle", expanded && "json__toggle--open")} aria-expanded={expanded} aria-label={`${expanded ? "Hide" : "Show"} payload for ${r.event_type}`} onClick={(e) => { e.stopPropagation(); toggle(r.id); }}>
                                <ChevronRight size={14} />
                              </button>
                            </td>
                            <td className="nowrap"><Time value={r.created_at} absolute /></td>
                            <td className="mono">{r.event_type}</td>
                            <td>{humanize(r.actor_type)}{r.actor_id && <span className="muted mono small"> · {shortId(r.actor_id)}</span>}</td>
                            <td>{r.execution_id ? <Link to={`/executions/${r.execution_id}`} className="mono" onClick={(e) => e.stopPropagation()}>{shortId(r.execution_id)}</Link> : <span className="muted">—</span>}</td>
                          </tr>
                          {expanded && (
                            <tr className="row-detail">
                              <td />
                              <td colSpan={4}>
                                <JsonViewer value={r.payload} expandDepth={2} maxHeight={280} label={`Payload for ${r.event_type}`} />
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="table-footnote">Showing {shown.length} of the latest {rows.length} entries.</p>
            </>
          );
        }}
      </DataState>
    </>
  );
}
