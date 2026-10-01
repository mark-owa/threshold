import { useState } from "react";
import { AlertTriangle, Bot, CheckCircle2, ChevronRight, Circle, CircleDashed, Clock, Cog, MinusCircle, User, Zap, Inbox, type LucideIcon } from "lucide-react";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { JsonViewer } from "@/components/ui/JsonViewer";
import type { ExecutionContext, StepExecution } from "@/types/api";
import { cn, formatDuration } from "@/utils/format";
import { ACTOR_LABEL, stepMeta, type StepActor } from "@/utils/status";
import { summarizeStep } from "./stepSummary";

const ACTOR_ICON: Record<StepActor, LucideIcon> = { ai: Bot, rules: Cog, human: User, external: Zap, system: Circle };

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "succeeded":
      return <CheckCircle2 size={16} />;
    case "failed":
      return <AlertTriangle size={16} />;
    case "awaiting_approval":
      return <Clock size={16} />;
    case "running":
      return <CircleDashed size={16} className="spin" />;
    case "skipped":
      return <MinusCircle size={16} />;
    default:
      return <Circle size={16} />;
  }
}

function StepNode({ step, index, last, defaultOpen }: { step: StepExecution; index: number; last: boolean; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const meta = stepMeta(step.step_type);
  const ActorIcon = ACTOR_ICON[meta.actor];
  const summary = summarizeStep(step);
  const hasDetail = !!(step.input || step.output || step.error);

  return (
    <li className={cn("tl__item", `tl__item--${step.status}`)}>
      <div className="tl__rail" aria-hidden>
        <span className="tl__icon">
          <StatusIcon status={step.status} />
        </span>
        {!last && <span className="tl__line" />}
      </div>
      <div className="tl__content">
        <div className="tl__head">
          <div className="tl__title-row">
            <span className="tl__index mono">{String(index + 1).padStart(2, "0")}</span>
            <h3 className="tl__title">{meta.title}</h3>
            <Badge tone={meta.actor === "ai" ? "info" : "neutral"}>
              <ActorIcon size={11} aria-hidden /> {ACTOR_LABEL[meta.actor]}
            </Badge>
            <StatusBadge kind="step" value={step.status} />
          </div>
          <div className="tl__meta">
            <span className="mono" title="Step key">
              {step.step_key}
            </span>
            {step.latency_ms !== null && <span>{formatDuration(step.latency_ms)}</span>}
          </div>
        </div>
        {summary && <p className="tl__summary">{summary}</p>}
        {step.error && (
          <div className="tl__error" role="alert">
            <AlertTriangle size={13} aria-hidden />
            <span className="mono">{step.error}</span>
          </div>
        )}
        {hasDetail && (
          <>
            <button type="button" className="tl__toggle" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
              <ChevronRight size={13} className={cn(open && "tl__chevron--open")} aria-hidden />
              {open ? "Hide" : "Show"} input &amp; output
            </button>
            {open && (
              <div className="tl__detail">
                {step.input && (
                  <div>
                    <div className="tl__detail-label">Input</div>
                    <JsonViewer value={step.input} expandDepth={1} maxHeight={240} label={`${meta.title} input`} />
                  </div>
                )}
                {step.output && (
                  <div>
                    <div className="tl__detail-label">Output</div>
                    <JsonViewer value={step.output} expandDepth={1} maxHeight={280} label={`${meta.title} output`} />
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </li>
  );
}

/** The trigger that started the run, taken from the execution context (there's no separate event endpoint). */
function TriggerNode({ context }: { context: ExecutionContext }) {
  const event = context.event;
  return (
    <li className="tl__item tl__item--succeeded">
      <div className="tl__rail" aria-hidden>
        <span className="tl__icon tl__icon--trigger">
          <Inbox size={16} />
        </span>
        <span className="tl__line" />
      </div>
      <div className="tl__content">
        <div className="tl__head">
          <div className="tl__title-row">
            <span className="tl__index mono">00</span>
            <h3 className="tl__title">Incoming event</h3>
            <Badge>Trigger</Badge>
          </div>
          {event?.sender && <div className="tl__meta">from {String(event.sender)}</div>}
        </div>
        {event?.text ? <blockquote className="tl__quote">{String(event.text)}</blockquote> : <p className="tl__summary muted">No message text was recorded for this event.</p>}
      </div>
    </li>
  );
}

export function ExecutionTimeline({ steps, context }: { steps: StepExecution[]; context: ExecutionContext }) {
  return (
    <ol className="tl">
      <TriggerNode context={context} />
      {steps.map((step, i) => (
        <StepNode key={step.id} step={step} index={i} last={i === steps.length - 1} defaultOpen={step.status === "failed" || step.status === "awaiting_approval"} />
      ))}
    </ol>
  );
}

/** Horizontal, read-only summary of a run's steps (used on the overview). */
export function StepStrip({ steps }: { steps: StepExecution[] }) {
  return (
    <ol className="strip" aria-label="Execution steps">
      {steps.map((step) => {
        const meta = stepMeta(step.step_type);
        return (
          <li key={step.id} className={cn("strip__step", `strip__step--${step.status}`)} title={`${meta.title}: ${step.status.replace(/_/g, " ")}`}>
            <span className="strip__dot" aria-hidden />
            <span className="strip__label">{meta.title}</span>
            <span className="sr-only">{step.status.replace(/_/g, " ")}</span>
          </li>
        );
      })}
    </ol>
  );
}
