import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { ApiError, errorMessage } from "@/api/client";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { CardSkeleton, DataState } from "@/components/ui/Feedback";
import { Callout, PageHeader, Panel, Time } from "@/components/ui/Layout";
import { useWorkspace } from "@/features/auth/session";
import { useSetLiveExecution } from "@/hooks/mutations";
import { useReadiness } from "@/hooks/queries";
import type { ReadinessLevel } from "@/types/api";
import { humanize } from "@/utils/format";
import type { Tone } from "@/utils/status";

const LEVEL: Record<ReadinessLevel, { label: string; tone: Tone }> = {
  pass: { label: "Pass", tone: "success" },
  warn: { label: "Warning", tone: "warning" },
  block: { label: "Blocker", tone: "danger" },
};

/** Blocker details from a 409/422 body, if the API supplied them. */
function blockerLines(error: unknown): string[] {
  if (!(error instanceof ApiError)) return [];
  const detail = (error.body as { detail?: { blockers?: unknown } } | null)?.detail;
  const blockers = detail && typeof detail === "object" ? detail.blockers : null;
  if (!Array.isArray(blockers)) return [];
  return blockers.map((b) => (typeof b === "string" ? b : b && typeof b === "object" ? String((b as { title?: unknown; detail?: unknown }).title ?? (b as { detail?: unknown }).detail ?? "") : "")).filter(Boolean);
}

export function LiveExecutionPage() {
  const { isOwner } = useWorkspace();
  const [probe, setProbe] = useState(false);
  const query = useReadiness(probe);
  const toggle = useSetLiveExecution();
  const [confirm, setConfirm] = useState<"enable" | "disable" | null>(null);

  const close = () => {
    setConfirm(null);
    toggle.reset();
  };

  return (
    <>
      <PageHeader
        title="Live execution"
        description="Live execution lets Threshold act on real external systems. It stays off until this workspace passes the readiness checks."
        actions={
          <>
            <Button loading={query.isFetching && probe} onClick={() => (probe ? void query.refetch() : setProbe(true))}>
              Run full check
            </Button>
            <Button variant="danger" onClick={() => setConfirm("disable")}>Disable live execution</Button>
            <Button variant="primary" disabled={!isOwner} title={isOwner ? undefined : "Only the owner can enable live execution"} onClick={() => setConfirm("enable")}>
              Enable live execution
            </Button>
          </>
        }
      />
      <DataState query={query} errorTitle="Couldn't load the readiness report" loading={<Panel><CardSkeleton lines={6} /></Panel>}>
        {(report) => {
          const groups = new Map<string, typeof report.checks>();
          for (const c of report.checks) groups.set(c.category, [...(groups.get(c.category) ?? []), c]);
          return (
            <div className="stack">
              <Callout tone={report.summary.block ? "danger" : report.summary.warn ? "warning" : "success"} title={report.ready ? "Ready for live execution" : `${report.summary.block} blocker${report.summary.block === 1 ? "" : "s"} to resolve`}>
                {report.summary.pass} passing · {report.summary.warn} warning{report.summary.warn === 1 ? "" : "s"} · {report.summary.block} blocking. Generated <Time value={report.generated_at} />.
                {!probe && " Runtime probes (database, queue) are skipped until you run a full check."}
              </Callout>
              {[...groups.entries()].map(([category, checks]) => (
                <Panel key={category} title={humanize(category)} flush>
                  <ul className="list">
                    {checks.map((c) => (
                      <li key={c.key} className="list__item list__item--static">
                        <ShieldCheck size={16} className={`list__icon list__icon--${LEVEL[c.level].tone}`} aria-hidden />
                        <span className="list__text">
                          <span className="list__title">{c.title}</span>
                          <span className="list__sub list__sub--wrap">{c.detail}</span>
                        </span>
                        <Badge tone={LEVEL[c.level].tone} dot>{LEVEL[c.level].label}</Badge>
                      </li>
                    ))}
                  </ul>
                </Panel>
              ))}
            </div>
          );
        }}
      </DataState>
      <ConfirmDialog
        open={!!confirm}
        onClose={close}
        tone={confirm === "enable" ? "primary" : "danger"}
        title={confirm === "enable" ? "Enable live execution?" : "Disable live execution?"}
        description={confirm === "enable" ? "Threshold will be allowed to execute actions against real providers. The API refuses if any blocker remains." : "Threshold stops executing actions against real providers for this workspace."}
        confirmLabel={confirm === "enable" ? "Enable" : "Disable"}
        loading={toggle.isPending}
        onConfirm={() => confirm && toggle.mutate(confirm === "enable", { onSuccess: close })}
      >
        {toggle.isError && (
          <div className="form-error" role="alert">
            {errorMessage(toggle.error)}
            {blockerLines(toggle.error).length > 0 && (
              <ul className="approval__factors">
                {blockerLines(toggle.error).map((l) => <li key={l}>{l}</li>)}
              </ul>
            )}
          </div>
        )}
      </ConfirmDialog>
    </>
  );
}
