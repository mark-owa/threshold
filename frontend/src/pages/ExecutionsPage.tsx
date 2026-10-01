import { useMemo, useState } from "react";
import { Activity, SearchX } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { SearchInput } from "@/components/ui/Fields";
import { DataState, EmptyState, TableSkeleton } from "@/components/ui/Feedback";
import { PageHeader } from "@/components/ui/Layout";
import { ExecutionsTable } from "@/features/executions/ExecutionsTable";
import { useExecutionLookups } from "@/features/executions/data";
import { useExecutions } from "@/hooks/queries";
import { humanize } from "@/utils/format";
import { WORKFLOW_STATUSES } from "@/utils/status";

const RANGES = [
  { value: "all", label: "Any time", ms: 0 },
  { value: "24h", label: "Last 24 hours", ms: 86_400_000 },
  { value: "7d", label: "Last 7 days", ms: 7 * 86_400_000 },
  { value: "30d", label: "Last 30 days", ms: 30 * 86_400_000 },
];

export function ExecutionsPage() {
  const [limit, setLimit] = useState(50);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [workflow, setWorkflow] = useState("all");
  const [range, setRange] = useState("all");
  const query = useExecutions(limit);
  const { workflowById, workflows } = useExecutionLookups();

  const filtered = useMemo(() => {
    const rows = query.data ?? [];
    const term = search.trim().toLowerCase();
    const rangeMs = RANGES.find((r) => r.value === range)?.ms ?? 0;
    const cutoff = rangeMs ? Date.now() - rangeMs : 0;
    return rows.filter((row) => {
      if (status !== "all" && row.status !== status) return false;
      if (workflow !== "all" && row.workflow_id !== workflow) return false;
      if (cutoff && (!row.started_at || new Date(row.started_at).getTime() < cutoff)) return false;
      if (term) {
        const haystack = [row.id, workflowById.get(row.workflow_id)?.name, row.current_step, row.error].filter(Boolean).join(" ").toLowerCase();
        if (!haystack.includes(term)) return false;
      }
      return true;
    });
  }, [query.data, search, status, workflow, range, workflowById]);

  const filtersActive = search !== "" || status !== "all" || workflow !== "all" || range !== "all";
  const clear = () => {
    setSearch("");
    setStatus("all");
    setWorkflow("all");
    setRange("all");
  };

  return (
    <>
      <PageHeader title="Executions" description="Every workflow run, from the incoming event to the external action. Open one to see exactly what happened." />
      <div className="table-toolbar">
        <SearchInput aria-label="Search executions" placeholder="Search ID, workflow, step, error…" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select className="input select select--sm" aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="all">All statuses</option>
          {WORKFLOW_STATUSES.map((s) => (
            <option key={s} value={s}>
              {humanize(s)}
            </option>
          ))}
        </select>
        <select className="input select select--sm" aria-label="Filter by workflow" value={workflow} onChange={(e) => setWorkflow(e.target.value)}>
          <option value="all">All workflows</option>
          {workflows.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>
        <select className="input select select--sm" aria-label="Filter by date" value={range} onChange={(e) => setRange(e.target.value)}>
          {RANGES.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
        {filtersActive && (
          <Button variant="ghost" size="sm" onClick={clear}>
            Clear filters
          </Button>
        )}
        <span className="grow" />
        <select className="input select select--sm" aria-label="Number of executions to load" value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
          {[25, 50, 100].map((n) => (
            <option key={n} value={n}>
              Load latest {n}
            </option>
          ))}
        </select>
      </div>

      <DataState
        query={query}
        errorTitle="Couldn't load executions"
        loading={
          <div className="table-wrap">
            <TableSkeleton rows={8} columns={7} />
          </div>
        }
        isEmpty={(d) => d.length === 0}
        empty={<EmptyState icon={<Activity size={18} />} title="No executions yet" description="Workflow executions will appear here after Threshold processes its first event." />}
      >
        {(all) =>
          filtered.length === 0 ? (
            <div className="table-wrap">
              <EmptyState
                icon={<SearchX size={18} />}
                title="No executions match these filters"
                description="Filters apply to the executions loaded here. Try loading more or clearing filters."
                action={
                  <Button size="sm" onClick={clear}>
                    Clear filters
                  </Button>
                }
              />
            </div>
          ) : (
            <>
              <ExecutionsTable rows={filtered} />
              <p className="table-footnote">
                Showing {filtered.length} of {all.length} loaded executions. The API returns the most recent {limit}; search and filters run on those.
              </p>
            </>
          )
        }
      </DataState>
    </>
  );
}
