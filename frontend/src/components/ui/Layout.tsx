import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Info, ArrowLeft } from "lucide-react";
import { cn, formatDateTime, formatRelative } from "@/utils/format";
import type { Tone } from "@/utils/status";

export function PageHeader({ title, description, actions, back }: { title: ReactNode; description?: ReactNode; actions?: ReactNode; back?: { to: string; label: string } }) {
  return (
    <div className="page-header">
      {back && (
        <Link to={back.to} className="page-header__back">
          <ArrowLeft size={14} aria-hidden /> {back.label}
        </Link>
      )}
      <div className="page-header__row">
        <div className="page-header__text">
          <h1 className="page-title">{title}</h1>
          {description && <p className="page-desc">{description}</p>}
        </div>
        {actions && <div className="page-header__actions">{actions}</div>}
      </div>
    </div>
  );
}

export function Panel({ title, description, actions, children, flush, className, id }: { title?: ReactNode; description?: ReactNode; actions?: ReactNode; children: ReactNode; flush?: boolean; className?: string; id?: string }) {
  return (
    <section className={cn("panel", className)} id={id}>
      {(title || actions) && (
        <header className="panel__header">
          <div>
            {title && <h2 className="panel__title">{title}</h2>}
            {description && <p className="panel__desc">{description}</p>}
          </div>
          {actions && <div className="panel__actions">{actions}</div>}
        </header>
      )}
      <div className={cn(!flush && "panel__pad")}>{children}</div>
    </section>
  );
}

export function Tabs<T extends string>({ value, onChange, items, label }: { value: T; onChange: (v: T) => void; items: { value: T; label: string; count?: number }[]; label: string }) {
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {items.map((item) => (
        <button key={item.value} role="tab" type="button" aria-selected={value === item.value} className={cn("tabs__tab", value === item.value && "tabs__tab--active")} onClick={() => onChange(item.value)}>
          {item.label}
          {item.count !== undefined && <span className="tabs__count">{item.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function KeyValue({ items, columns = 1 }: { items: { label: string; value: ReactNode }[]; columns?: 1 | 2 }) {
  return (
    <dl className={cn("kv", columns === 2 && "kv--2")}>
      {items.map((item) => (
        <div className="kv__row" key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Time({ value, absolute }: { value: string | null | undefined; absolute?: boolean }) {
  if (!value) return <span className="muted">—</span>;
  return (
    <time dateTime={value} title={formatDateTime(value)}>
      {absolute ? formatDateTime(value) : formatRelative(value)}
    </time>
  );
}

const CALLOUT_ICON = { success: CheckCircle2, warning: AlertTriangle, danger: AlertTriangle, info: Info, neutral: Info } as const;

export function Callout({ tone = "info", title, children, actions }: { tone?: Tone; title?: ReactNode; children?: ReactNode; actions?: ReactNode }) {
  const Icon = CALLOUT_ICON[tone];
  return (
    <div className={cn("callout", `callout--${tone}`)} role={tone === "danger" ? "alert" : undefined}>
      <Icon size={16} className="callout__icon" aria-hidden />
      <div className="callout__body">
        {title && <div className="callout__title">{title}</div>}
        {children && <div className="callout__text">{children}</div>}
      </div>
      {actions && <div className="callout__actions">{actions}</div>}
    </div>
  );
}

export function Metric({ label, value, note, tone, to }: { label: string; value: ReactNode; note?: ReactNode; tone?: Tone; to?: string }) {
  const body = (
    <>
      <div className="metric__label">{label}</div>
      <div className={cn("metric__value", tone && `metric__value--${tone}`)}>{value}</div>
      {note && <div className="metric__note">{note}</div>}
    </>
  );
  return to ? (
    <Link to={to} className="metric metric--link">
      {body}
    </Link>
  ) : (
    <div className="metric">{body}</div>
  );
}
