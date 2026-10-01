import { useState } from "react";
import { ChevronRight } from "lucide-react";
import type { JsonValue } from "@/types/api";
import { CopyButton } from "./CopyButton";
import { cn } from "@/utils/format";

function isContainer(value: JsonValue): value is JsonValue[] | { [key: string]: JsonValue } {
  return typeof value === "object" && value !== null;
}

function Primitive({ value }: { value: JsonValue }) {
  if (value === null) return <span className="json__null">null</span>;
  if (typeof value === "string") return <span className="json__str">"{value}"</span>;
  if (typeof value === "number") return <span className="json__num">{value}</span>;
  return <span className="json__bool">{String(value)}</span>;
}

function Node({ name, value, depth, expandDepth, last }: { name?: string; value: JsonValue; depth: number; expandDepth: number; last: boolean }) {
  const [open, setOpen] = useState(depth < expandDepth);
  const comma = last ? "" : ",";
  const key = name !== undefined ? (
    <>
      <span className="json__key">"{name}"</span>
      <span className="json__punct">: </span>
    </>
  ) : null;

  if (!isContainer(value)) {
    return (
      <div className="json__line">
        {key}
        <Primitive value={value} />
        <span className="json__punct">{comma}</span>
      </div>
    );
  }

  const isArray = Array.isArray(value);
  const entries: [string, JsonValue][] = isArray ? value.map((v, i) => [String(i), v]) : Object.entries(value);
  const [openBrace, closeBrace] = isArray ? ["[", "]"] : ["{", "}"];

  if (entries.length === 0) {
    return (
      <div className="json__line">
        {key}
        <span className="json__punct">
          {openBrace}
          {closeBrace}
          {comma}
        </span>
      </div>
    );
  }

  return (
    <div>
      <div className="json__line">
        <button type="button" className={cn("json__toggle", open && "json__toggle--open")} onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-label={name ? `Toggle ${name}` : "Toggle"}>
          <ChevronRight size={12} />
        </button>
        {key}
        <span className="json__punct">{openBrace}</span>
        {!open && (
          <>
            <span className="json__summary">
              {" "}
              {entries.length} {isArray ? (entries.length === 1 ? "item" : "items") : entries.length === 1 ? "key" : "keys"}{" "}
            </span>
            <span className="json__punct">
              {closeBrace}
              {comma}
            </span>
          </>
        )}
      </div>
      {open && (
        <>
          <div className="json__children">
            {entries.map(([k, v], i) => (
              <Node key={k} name={isArray ? undefined : k} value={v} depth={depth + 1} expandDepth={expandDepth} last={i === entries.length - 1} />
            ))}
          </div>
          <div className="json__line json__line--close">
            <span className="json__punct">
              {closeBrace}
              {comma}
            </span>
          </div>
        </>
      )}
    </div>
  );
}

/** Collapsible, copyable JSON viewer for payloads, contexts and step input/output. */
export function JsonViewer({ value, expandDepth = 1, maxHeight = 360, label }: { value: JsonValue | object | null | undefined; expandDepth?: number; maxHeight?: number; label?: string }) {
  if (value === null || value === undefined) return <p className="muted small">No data.</p>;
  const json = value as JsonValue;
  return (
    <div className="json" role="group" aria-label={label ?? "JSON viewer"}>
      <div className="json__copy">
        <CopyButton value={JSON.stringify(json, null, 2)} label="Copy JSON" />
      </div>
      <div className="json__body mono" style={{ maxHeight }}>
        <Node value={json} depth={0} expandDepth={expandDepth} last />
      </div>
    </div>
  );
}
