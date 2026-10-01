import type { ReactNode } from "react";
import type { Role } from "@/types/api";
import { cn } from "@/utils/format";
import { ROLE_LABEL, statusOf, type StatusKind, type Tone } from "@/utils/status";

export function Badge({ tone = "neutral", dot, children, className, mono }: { tone?: Tone; dot?: boolean; children: ReactNode; className?: string; mono?: boolean }) {
  return (
    <span className={cn("badge", `badge--${tone}`, mono && "mono", className)}>
      {dot && <span className="badge__dot" aria-hidden />}
      {children}
    </span>
  );
}

/** One badge for every backend status enum; the label is always the backend value, humanised. */
export function StatusBadge({ kind, value }: { kind: StatusKind; value: string }) {
  const view = statusOf[kind](value);
  return (
    <Badge tone={view.tone} dot>
      {view.label}
    </Badge>
  );
}

export function RoleBadge({ role }: { role: Role }) {
  return <span className={cn("role", `role--${role}`)}>{ROLE_LABEL[role]}</span>;
}
