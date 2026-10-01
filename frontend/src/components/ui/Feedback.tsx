import type { ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { AlertCircle, Inbox, Loader2, Lock } from "lucide-react";
import { ApiError, errorMessage } from "@/api/client";
import { Button } from "./Button";
import { cn } from "@/utils/format";

export function Spinner({ size = 16 }: { size?: number }) {
  return <Loader2 size={size} className="spin" aria-label="Loading" role="status" />;
}

export function Skeleton({ width, height = 12, className }: { width?: number | string; height?: number | string; className?: string }) {
  return <span className={cn("skeleton", className)} style={{ width, height }} aria-hidden />;
}

export function TableSkeleton({ rows = 6, columns = 5 }: { rows?: number; columns?: number }) {
  return (
    <div className="table-skeleton" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, r) => (
        <div className="table-skeleton__row" key={r} style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}>
          {Array.from({ length: columns }, (_, c) => (
            <Skeleton key={c} width={c === 0 ? "70%" : `${45 + ((r * 7 + c * 13) % 40)}%`} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function CardSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="panel__pad stack" aria-busy="true" aria-label="Loading">
      <Skeleton width="40%" height={14} />
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} width={`${90 - i * 15}%`} />
      ))}
    </div>
  );
}

export function EmptyState({ icon, title, description, action, compact }: { icon?: ReactNode; title: string; description?: ReactNode; action?: ReactNode; compact?: boolean }) {
  return (
    <div className={cn("empty", compact && "empty--compact")}>
      <div className="empty__icon">{icon ?? <Inbox size={18} />}</div>
      <h3 className="empty__title">{title}</h3>
      {description && <p className="empty__desc">{description}</p>}
      {action && <div className="empty__action">{action}</div>}
    </div>
  );
}

export function ErrorState({ title, error, onRetry, compact }: { title: string; error: unknown; onRetry?: () => void; compact?: boolean }) {
  const forbidden = error instanceof ApiError && error.isForbidden;
  return (
    <div className={cn("empty", "empty--error", compact && "empty--compact")} role="alert">
      <div className="empty__icon">{forbidden ? <Lock size={18} /> : <AlertCircle size={18} />}</div>
      <h3 className="empty__title">{forbidden ? "You don't have access to this" : title}</h3>
      <p className="empty__desc">{errorMessage(error)}</p>
      {onRetry && !forbidden && (
        <div className="empty__action">
          <Button size="sm" onClick={onRetry}>
            Try again
          </Button>
        </div>
      )}
    </div>
  );
}

interface DataStateProps<T> {
  query: UseQueryResult<T>;
  errorTitle: string;
  loading: ReactNode;
  isEmpty?: (data: T) => boolean;
  empty?: ReactNode;
  compactError?: boolean;
  children: (data: T) => ReactNode;
}

/** Renders loading / error (with retry) / empty / data for a query, so every page handles all four states. */
export function DataState<T>({ query, errorTitle, loading, isEmpty, empty, compactError, children }: DataStateProps<T>) {
  if (query.isPending) return <>{loading}</>;
  if (query.isError) return <ErrorState title={errorTitle} error={query.error} onRetry={() => void query.refetch()} compact={compactError} />;
  if (isEmpty?.(query.data)) return <>{empty}</>;
  return <>{children(query.data)}</>;
}
