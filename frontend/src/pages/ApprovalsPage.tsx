import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, ExternalLink, Pencil, ShieldCheck, X } from "lucide-react";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { IdChip } from "@/components/ui/CopyButton";
import { CardSkeleton, DataState, EmptyState, ErrorState } from "@/components/ui/Feedback";
import { KeyValue, PageHeader, Panel, Tabs, Time } from "@/components/ui/Layout";
import { useWorkspace } from "@/features/auth/session";
import { formatParameter, parameterLabel } from "@/features/executions/approvalFormat";
import { DecisionDialog, type DecisionMode } from "@/features/executions/DecisionDialog";
import { useApprovals } from "@/hooks/queries";
import type { Approval, ApprovalStatus } from "@/types/api";
import { cn, humanize } from "@/utils/format";
import { extractRiskFactors, riskFactorText, statusOf } from "@/utils/status";

const TABS: { value: ApprovalStatus; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "modified", label: "Modified" },
  { value: "rejected", label: "Rejected" },
];

function riskTone(level: string) {
  return statusOf.risk(level).tone;
}

function ApprovalDetail({ approval, onDecide }: { approval: Approval; onDecide: (mode: DecisionMode) => void }) {
  const factors = extractRiskFactors(approval.risk_factors);
  const params = approval.generated_parameters ?? {};
  const pending = approval.status === "pending";

  return (
    <Panel
      title={
        <span className="row">
          {humanize(approval.proposed_action?.action_type ?? "Action")} <StatusBadge kind="approval" value={approval.status} /> <StatusBadge kind="risk" value={approval.risk_level} />
        </span>
      }
      description={<>Requested <Time value={approval.created_at} /></>}
    >
      <div className="stack">
        <section>
          <h3 className="section-label">Why this needs review</h3>
          <p className="approval__reason">{approval.reason}</p>
          {factors.length > 0 && (
            <ul className="approval__factors">
              {factors.map((f) => (
                <li key={f}>{riskFactorText(f)}</li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <h3 className="section-label">Proposed action</h3>
          {Object.keys(params).length === 0 ? (
            <p className="muted small">No parameters were generated.</p>
          ) : (
            <div className="params">
              {Object.entries(params).map(([k, v]) => (
                <div key={k} className="params__item">
                  <div className="params__label">{parameterLabel(k)}</div>
                  <div className="params__value mono">{formatParameter(k, v)}</div>
                </div>
              ))}
            </div>
          )}
        </section>

        <KeyValue
          items={[
            { label: "Execution", value: <span className="row" style={{ justifyContent: "flex-end" }}><IdChip id={approval.execution_id} /><Link to={`/executions/${approval.execution_id}`} className="row small">View <ExternalLink size={11} aria-hidden /></Link></span> },
            { label: "Approval ID", value: <IdChip id={approval.id} /> },
            { label: "Requested", value: <Time value={approval.created_at} absolute /> },
          ]}
        />

        {pending ? (
          <div className="approval__actions">
            <Button variant="primary" icon={<CheckCircle2 size={14} />} onClick={() => onDecide("approved")}>
              Approve
            </Button>
            <Button icon={<Pencil size={14} />} onClick={() => onDecide("modified")}>
              Modify and approve
            </Button>
            <Button variant="danger" icon={<X size={14} />} onClick={() => onDecide("rejected")}>
              Reject
            </Button>
          </div>
        ) : (
          <p className="small muted">This approval has been {approval.status}. Reviewer notes are recorded in the audit log.</p>
        )}
      </div>
    </Panel>
  );
}

export function ApprovalsPage() {
  const { canReview } = useWorkspace();
  const [tab, setTab] = useState<ApprovalStatus>("pending");
  const [params, setParams] = useSearchParams();
  const focus = params.get("focus");
  const query = useApprovals(tab, canReview);
  const [selectedId, setSelectedId] = useState<string | null>(focus);
  const [mode, setMode] = useState<DecisionMode | null>(null);

  const rows = useMemo(() => query.data ?? [], [query.data]);
  const selected = rows.find((a) => a.id === selectedId) ?? rows[0] ?? null;

  useEffect(() => {
    if (focus) setSelectedId(focus);
  }, [focus]);

  if (!canReview) {
    return (
      <>
        <PageHeader title="Approvals" description="Human review for actions that policy won't authorise automatically." />
        <Panel>
          <EmptyState icon={<ShieldCheck size={18} />} title="Reviewer access required" description="Your role can view executions but can't see or decide approvals. Ask an owner or admin for the reviewer role." />
        </Panel>
      </>
    );
  }

  return (
    <>
      <PageHeader title="Approvals" description="Actions that policy won't authorise automatically wait here for a human decision." actions={<Tabs label="Approval status" value={tab} onChange={(v) => { setTab(v); setSelectedId(null); setParams({}); }} items={TABS} />} />
      <DataState
        query={query}
        errorTitle="Couldn't load approvals"
        loading={
          <div className="approvals">
            <Panel><CardSkeleton lines={4} /></Panel>
            <Panel><CardSkeleton lines={6} /></Panel>
          </div>
        }
        isEmpty={(d) => d.length === 0}
        empty={
          <Panel>
            <EmptyState
              icon={<CheckCircle2 size={18} />}
              title={tab === "pending" ? "No pending approvals" : `No ${tab} approvals`}
              description={tab === "pending" ? "Nothing requires review right now." : "Decisions will appear here once they've been made."}
            />
          </Panel>
        }
      >
        {(list) => (
          <div className="approvals">
            <div className="approvals__list" role="listbox" aria-label="Approval requests">
              {list.map((a) => {
                const factors = extractRiskFactors(a.risk_factors);
                const active = a.id === selected?.id;
                return (
                  <button key={a.id} type="button" role="option" aria-selected={active} className={cn("approvals__row", active && "approvals__row--active")} onClick={() => setSelectedId(a.id)}>
                    <span className="row" style={{ justifyContent: "space-between", width: "100%" }}>
                      <strong>{humanize(a.proposed_action?.action_type ?? "Action")}</strong>
                      <Badge tone={riskTone(a.risk_level)}>{humanize(a.risk_level)}</Badge>
                    </span>
                    <span className="approvals__sub">{factors.length ? riskFactorText(factors[0] ?? "") : a.reason}</span>
                    <span className="approvals__meta">
                      {a.generated_parameters && Object.entries(a.generated_parameters).slice(0, 2).map(([k, v]) => <span key={k} className="mono">{formatParameter(k, v)}</span>)}
                      <Time value={a.created_at} />
                    </span>
                  </button>
                );
              })}
            </div>
            {selected ? <ApprovalDetail approval={selected} onDecide={setMode} /> : <ErrorState title="Select an approval" error={new Error("Choose a request from the list.")} compact />}
          </div>
        )}
      </DataState>
      {selected && <DecisionDialog key={`${selected.id}-${mode}`} approval={selected} mode={mode} onClose={() => setMode(null)} onDone={() => setMode(null)} />}
    </>
  );
}
