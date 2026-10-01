import { useState, type FormEvent } from "react";
import { ScrollText } from "lucide-react";
import { errorMessage } from "@/api/client";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { TextField, TextareaField } from "@/components/ui/Fields";
import { CardSkeleton, DataState, EmptyState } from "@/components/ui/Feedback";
import { JsonViewer } from "@/components/ui/JsonViewer";
import { Callout, PageHeader, Panel, Tabs, Time } from "@/components/ui/Layout";
import { useWorkspace } from "@/features/auth/session";
import { useSaveRefundPolicy } from "@/hooks/mutations";
import { usePolicies } from "@/hooks/queries";
import type { Policy } from "@/types/api";
import { formatCurrency, humanize } from "@/utils/format";

function RefundPolicyEditor({ policy }: { policy?: Policy }) {
  const { canManage } = useWorkspace();
  const save = useSaveRefundPolicy();
  const rules = policy?.structured_rules ?? {};
  const [view, setView] = useState<"simple" | "advanced">("simple");
  const [f, setF] = useState({
    title: policy?.title ?? "Refund policy",
    content: policy?.content ?? "",
    days: String(rules.refund_window_days ?? 30),
    max: String(rules.max_auto_refund_usd ?? 50),
  });
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const set = (k: keyof typeof f, v: string) => setF((p) => ({ ...p, [k]: v }));

  const days = Number(f.days);
  const max = Number(f.max);
  const previewOk = Number.isFinite(days) && Number.isFinite(max);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string | undefined> = {};
    if (f.title.trim().length < 2) errs.title = "Enter a title.";
    if (f.content.trim().length < 10) errs.content = "Describe the policy in at least 10 characters.";
    if (!Number.isInteger(days) || days < 1 || days > 365) errs.days = "Whole number from 1 to 365.";
    if (!Number.isFinite(max) || max < 0 || max > 1_000_000) errs.max = "Amount from 0 to 1,000,000.";
    setErrors(errs);
    if (Object.values(errs).some(Boolean)) return;
    save.mutate({ title: f.title.trim(), content: f.content.trim(), refund_window_days: days, max_auto_refund_usd: max });
  };

  return (
    <Panel
      title="Refund policy"
      description="Controls which refund requests are handled automatically and which need a reviewer."
      actions={<Tabs label="Policy view" value={view} onChange={setView} items={[{ value: "simple", label: "Simple" }, { value: "advanced", label: "Advanced" }]} />}
    >
      {view === "advanced" ? (
        <div className="stack">
          <p className="small muted">The structured rules the workflow engine evaluates. Read-only; edit them in the simple view.</p>
          <JsonViewer value={policy?.structured_rules ?? null} expandDepth={2} label="Structured rules" />
        </div>
      ) : (
        <form className="stack" onSubmit={submit} noValidate>
          {!canManage && <Callout tone="neutral">Admin access is required to change policies.</Callout>}
          <fieldset className="fieldset" disabled={!canManage || save.isPending}>
            <TextField label="Title" value={f.title} error={errors.title} onChange={(e) => set("title", e.target.value)} />
            <TextareaField label="Policy text" hint="Shown to reviewers and used as context by the AI model." rows={5} value={f.content} error={errors.content} onChange={(e) => set("content", e.target.value)} />
            <div className="form-grid">
              <TextField label="Refund window (days)" type="number" min={1} max={365} hint="Orders older than this fail the eligibility check." value={f.days} error={errors.days} onChange={(e) => set("days", e.target.value)} />
              <TextField label="Automatic approval limit (USD)" type="number" min={0} step="0.01" hint="Refunds above this need human approval." value={f.max} error={errors.max} onChange={(e) => set("max", e.target.value)} />
            </div>
          </fieldset>
          {previewOk && (
            <div className="policy-preview" aria-live="polite">
              <div className="small muted">What this means</div>
              <p>
                Refund requests up to <strong>{formatCurrency(max)}</strong> on orders within <strong>{days} days</strong> can run without review. Larger amounts require a reviewer's approval, and orders outside the window fail the eligibility check.
              </p>
            </div>
          )}
          {save.isError && <p className="form-error" role="alert">{errorMessage(save.error)}</p>}
          <div>
            <Button variant="primary" type="submit" loading={save.isPending} disabled={!canManage}>Save policy</Button>
          </div>
        </form>
      )}
    </Panel>
  );
}

export function PoliciesPage() {
  const query = usePolicies();
  return (
    <>
      <PageHeader title="Policies" description="The deterministic rules that decide what AI-proposed actions are allowed to do." />
      <DataState
        query={query}
        errorTitle="Couldn't load policies"
        loading={<Panel><CardSkeleton lines={5} /></Panel>}
      >
        {(policies) => {
          const refund = policies.find((p) => p.category === "refund_request");
          const others = policies.filter((p) => p.category !== "refund_request");
          return (
            <div className="stack">
              <RefundPolicyEditor key={refund?.updated_at ?? "new"} policy={refund} />
              <Panel title="Policy library" description="Every policy loaded for this workspace." flush>
                {policies.length === 0 ? (
                  <EmptyState compact icon={<ScrollText size={18} />} title="No policies yet" description="Save the refund policy above to create the first one." />
                ) : (
                  <div className="table-wrap">
                    <table className="data">
                      <thead><tr><th scope="col">Policy</th><th scope="col">Category</th><th scope="col">Rules</th><th scope="col">Editable</th><th scope="col">Updated</th></tr></thead>
                      <tbody>
                        {[...(refund ? [refund] : []), ...others].map((p) => (
                          <tr key={p.id}>
                            <td>
                              <div className="cell-main">{p.title}</div>
                              <div className="cell-sub truncate policy-snippet">{p.content}</div>
                            </td>
                            <td>{humanize(p.category)}</td>
                            <td>
                              <span className="row">
                                {Object.entries(p.structured_rules ?? {}).filter(([, v]) => typeof v !== "object").map(([k, v]) => (
                                  <Badge key={k}>{humanize(k)}: {String(v)}</Badge>
                                ))}
                              </span>
                            </td>
                            <td>{p.category === "refund_request" ? "Yes" : <span className="muted">Read-only</span>}</td>
                            <td><Time value={p.updated_at} /></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Panel>
            </div>
          );
        }}
      </DataState>
    </>
  );
}
