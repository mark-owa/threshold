import { useEffect, useRef, useState, type ReactNode } from "react";
import { Check } from "lucide-react";
import { cn } from "@/utils/format";

export type MenuEntry =
  | { type?: "item"; label: string; icon?: ReactNode; description?: string; onSelect: () => void; tone?: "danger"; disabled?: boolean; selected?: boolean }
  | { type: "label"; label: string }
  | { type: "separator" };

interface MenuProps {
  /** Content of the trigger button. */
  trigger: ReactNode;
  label: string;
  entries: MenuEntry[];
  align?: "start" | "end";
  side?: "bottom" | "top";
  triggerClassName?: string;
}

/** Small accessible dropdown: Escape closes, arrow keys move between items, focus returns to the trigger. */
export function Menu({ trigger, label, entries, align = "end", side = "bottom", triggerClassName }: MenuProps) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    list.current?.querySelector<HTMLElement>('[role^="menuitem"]:not([disabled])')?.focus();
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const close = (refocus = true) => {
    setOpen(false);
    if (refocus) button.current?.focus();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.stopPropagation();
      close();
      return;
    }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const items = Array.from(list.current?.querySelectorAll<HTMLElement>('[role^="menuitem"]:not([disabled])') ?? []);
    const index = items.indexOf(document.activeElement as HTMLElement);
    const next = e.key === "ArrowDown" ? (index + 1) % items.length : (index - 1 + items.length) % items.length;
    items[next]?.focus();
  };

  return (
    <div className="menu" ref={root} onKeyDown={onKeyDown}>
      <button ref={button} type="button" className={triggerClassName} aria-haspopup="menu" aria-expanded={open} aria-label={label} onClick={() => setOpen((v) => !v)}>
        {trigger}
      </button>
      {open && (
        <div ref={list} className={cn("menu__list", `menu__list--${align}`, side === "top" && "menu__list--top")} role="menu" aria-label={label}>
          {entries.map((entry, i) => {
            if (entry.type === "separator") return <div key={i} className="menu__sep" role="separator" />;
            if (entry.type === "label")
              return (
                <div key={i} className="menu__label">
                  {entry.label}
                </div>
              );
            return (
              <button
                key={i}
                type="button"
                role={entry.selected !== undefined ? "menuitemradio" : "menuitem"}
                aria-checked={entry.selected}
                disabled={entry.disabled}
                className={cn("menu__item", entry.tone === "danger" && "menu__item--danger")}
                onClick={() => {
                  close();
                  entry.onSelect();
                }}
              >
                {entry.icon && <span className="menu__icon">{entry.icon}</span>}
                <span className="menu__text">
                  <span>{entry.label}</span>
                  {entry.description && <span className="menu__desc">{entry.description}</span>}
                </span>
                {entry.selected && <Check size={14} aria-hidden />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
