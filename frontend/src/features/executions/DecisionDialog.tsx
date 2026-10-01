import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { TextField, TextareaField } from "@/components/ui/Fields";
import { Callout } from "@/components/ui/Layout";
import { useDecideApproval } from "@/hooks/mutations";
import { errorMessage } from "@/api/client";
import type { Approval, JsonObject, JsonValue } from "@/types/api";
import { humanize } from "@/utils/format";
import { formatParameter, parameterLabel } from "./approvalFormat";

export type DecisionMode = "approved" | "rejected" | "modified";

const COPY: Record<DecisionMode, { title: string; description: string; confirm: string }> = {
  approved: {
    title: "Approve this action?",
    description: "The workflow resumes and Threshold executes the action exactly as proposed.",
    confirm: "Approve",
  },
  rejected: {
    title: "Reject this action?",
    description: "The action will not be executed. This decision is recorded in the audit log.",
    confirm: "Reject",
  },
  modified: {
    title: "Modify and approve",
    description: "Edit the parameters. Threshold executes the action with your values instead of the proposed ones.",
    confirm: "Approve with changes",
  },
};

function isEditable(v: JsonValue): v is string | number {
  return typeof v === "string" || typeof v === "number";
}

interface Props {
  approval: Approval;
  mode: DecisionMode | null;
  onClose: () => void;
  onDone: () => void;
}

export function DecisionDialog({ approval, mode, onClose, onDone }: Props) {
  const decide = useDecideApproval();
  const params: JsonObject = approval.generated_parameters ?? {};
  const [notes, setNotes] = useState("");
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(Object.entries(params).filter(([, v]) => isEditable(v)).map(([k, v]) => [k, String(v)])));
  const [errors, setErrors] = useState<Record<string, string>>({});

  if (!mode) return <Dialog open={false} onClose={onClose} title="" />;
  const copy = COPY[mode];

  const submit = (e: FormEvent) => {
    e.preventDefault();
    let modified: JsonObject | undefined;
    if (mode === "modified") {
      const next: JsonObject = { ...params };
      const errs: Record<string, string> = {};
      for (const [key, original] of Object.entries(params)) {
        if (!isEditable(original)) continue;
        const raw = (values[key] ?? "").trim();
        if (typeof original === "number") {
          const n = Number(raw);
          if (raw === "" || !Number.isFinite(n)) errs[key] = "Enter a number.";
          else if (n < 0) errs[key] = "Must not be negative.";
          else next[key] = n;
        } else if (raw === "") errs[key] = "This can't be empty.";
        else next[key] = raw;
      }
      setErrors(errs);
      if (Object.keys(errs).length) return;
      // The backend replaces the generated parameters wholesale, so send the complete set.
      modified = next;
    }
    decide.mutate(
      { id: approval.id, body: { decision: mode, notes: notes.trim() || null, modified_parameters: modified ?? null } },
      { onSuccess: () => { setNotes(""); decide.reset(); onDone(); } },
    );
  };

  return (
    <Dialog
      open
      onClose={() => { decide.reset(); onClose(); }}
      title={copy.title}
      description={copy.description}
      busy={decide.isPending}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={decide.isPending}>
            Cancel
          </Button>
          <Button variant={mode === "rejected" ? "danger" : "primary"} type="submit" form="decision-form" loading={decide.isPending}>
            {copy.confirm}
          </Button>
        </>
      }
    >
      <form id="decision-form" className="stack" onSubmit={submit}>
        <div className="decision-summary">
          <div className="small muted">{humanize(approval.proposed_action?.action_type ?? "Action")}</div>
          <div className="decision-summary__values">
            {Object.entries(params).map(([k, v]) => (
              <span key={k}>
                {parameterLabel(k)}: <strong className="mono">{formatParameter(k, v)}</strong>
              </span>
            ))}
          </div>
        </div>

        {mode === "modified" && (
          <div className="stack">
            {Object.entries(params).map(([key, original]) =>
              isEditable(original) ? (
                <TextField
                  key={key}
                  label={parameterLabel(key)}
                  hint={`Proposed: ${formatParameter(key, original)}`}
                  type={typeof original === "number" ? "number" : "text"}
                  step={typeof original === "number" ? "0.01" : undefined}
                  inputMode={typeof original === "number" ? "decimal" : undefined}
                  value={values[key] ?? ""}
                  error={errors[key]}
                  onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
                />
              ) : null,
            )}
          </div>
        )}

        <TextareaField label="Reviewer note" optional hint={mode === "rejected" ? "Recording why helps the next reviewer." : "Saved with the decision."} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={2000} />

        {mode === "rejected" && <Callout tone="warning">Rejecting stops this workflow. It cannot be undone from this screen.</Callout>}
        {decide.isError && (
          <p className="form-error" role="alert">
            {errorMessage(decide.error)}
          </p>
        )}
      </form>
    </Dialog>
  );
}
