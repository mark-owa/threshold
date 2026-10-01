import { useId, useState, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { Eye, EyeOff } from "lucide-react";
import { cn } from "@/utils/format";

interface FieldShellProps {
  label: string;
  hint?: ReactNode;
  error?: string | null;
  optional?: boolean;
  htmlFor: string;
  children: ReactNode;
  className?: string;
}

export function FieldShell({ label, hint, error, optional, htmlFor, children, className }: FieldShellProps) {
  return (
    <div className={cn("field", className)}>
      <label className="field__label" htmlFor={htmlFor}>
        {label}
        {optional && <span className="field__optional"> · optional</span>}
      </label>
      {children}
      {hint && (
        <p className="field__hint" id={`${htmlFor}-hint`}>
          {hint}
        </p>
      )}
      {error && (
        <p className="field__error" id={`${htmlFor}-error`} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

function describedBy(id: string, error?: string | null, hint?: ReactNode) {
  const ids = [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean);
  return ids.length ? ids.join(" ") : undefined;
}

interface CommonProps {
  label: string;
  hint?: ReactNode;
  error?: string | null;
  optional?: boolean;
  fieldClassName?: string;
}

export function TextField({ label, hint, error, optional, fieldClassName, className, ...rest }: CommonProps & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  return (
    <FieldShell label={label} hint={hint} error={error} optional={optional} htmlFor={id} className={fieldClassName}>
      <input id={id} className={cn("input", error && "input--invalid", className)} aria-invalid={!!error || undefined} aria-describedby={describedBy(id, error, hint)} {...rest} />
    </FieldShell>
  );
}

/** For credential references and other sensitive values: masked by default with an explicit reveal. */
export function SecretField({ label, hint, error, optional, fieldClassName, className, ...rest }: CommonProps & Omit<InputHTMLAttributes<HTMLInputElement>, "type">) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  return (
    <FieldShell label={label} hint={hint} error={error} optional={optional} htmlFor={id} className={fieldClassName}>
      <div className="input-group">
        <input
          id={id}
          type={visible ? "text" : "password"}
          autoComplete="off"
          spellCheck={false}
          className={cn("input input--mono", error && "input--invalid", className)}
          aria-invalid={!!error || undefined}
          aria-describedby={describedBy(id, error, hint)}
          {...rest}
        />
        <button type="button" className="input-group__btn" onClick={() => setVisible((v) => !v)} aria-label={visible ? "Hide value" : "Show value"} aria-pressed={visible}>
          {visible ? <EyeOff size={14} /> : <Eye size={14} />}
        </button>
      </div>
    </FieldShell>
  );
}

export function SelectField({ label, hint, error, optional, fieldClassName, className, children, ...rest }: CommonProps & SelectHTMLAttributes<HTMLSelectElement>) {
  const id = useId();
  return (
    <FieldShell label={label} hint={hint} error={error} optional={optional} htmlFor={id} className={fieldClassName}>
      <select id={id} className={cn("input select", error && "input--invalid", className)} aria-invalid={!!error || undefined} aria-describedby={describedBy(id, error, hint)} {...rest}>
        {children}
      </select>
    </FieldShell>
  );
}

export function TextareaField({ label, hint, error, optional, fieldClassName, className, ...rest }: CommonProps & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const id = useId();
  return (
    <FieldShell label={label} hint={hint} error={error} optional={optional} htmlFor={id} className={fieldClassName}>
      <textarea id={id} className={cn("input textarea", error && "input--invalid", className)} aria-invalid={!!error || undefined} aria-describedby={describedBy(id, error, hint)} {...rest} />
    </FieldShell>
  );
}

export function CheckboxField({ label, hint, className, ...rest }: { label: string; hint?: ReactNode } & Omit<InputHTMLAttributes<HTMLInputElement>, "type">) {
  const id = useId();
  return (
    <div className={cn("check", className)}>
      <input id={id} type="checkbox" className="check__box" aria-describedby={hint ? `${id}-hint` : undefined} {...rest} />
      <div>
        <label htmlFor={id} className="check__label">
          {label}
        </label>
        {hint && (
          <p className="field__hint" id={`${id}-hint`}>
            {hint}
          </p>
        )}
      </div>
    </div>
  );
}

/** Bare filter input (search box) without a visible label; `aria-label` is required. */
export function SearchInput({ className, ...rest }: InputHTMLAttributes<HTMLInputElement> & { "aria-label": string }) {
  return <input type="search" className={cn("input input--search", className)} {...rest} />;
}
