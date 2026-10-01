import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/utils/format";

export function CopyButton({ value, label = "Copy", className }: { value: string; label?: string; className?: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // Clipboard API can be unavailable on non-secure origins; fall back to a temporary textarea.
      const area = document.createElement("textarea");
      area.value = value;
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  return (
    <button type="button" className={cn("icon-btn icon-btn--sm", className)} onClick={copy} aria-label={copied ? "Copied" : label} data-tip={copied ? "Copied" : label}>
      {copied ? <Check size={13} /> : <Copy size={13} />}
    </button>
  );
}

/** Monospace identifier with an inline copy affordance. */
export function IdChip({ id, length = 8, full }: { id: string; length?: number; full?: boolean }) {
  return (
    <span className="idchip">
      <code className="mono" title={id}>
        {full ? id : id.slice(0, length)}
      </code>
      <CopyButton value={id} label="Copy ID" />
    </span>
  );
}
