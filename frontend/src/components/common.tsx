import React from "react";

export function Metric({ title, value, note }: { title: string; value: string | number; note: string }) {
  return <div className="metric"><span>{title}</span><strong>{value}</strong><small>{note}</small></div>;
}

export function Empty({ text }: { text: string }) {
  return <div className="empty">{text}</div>;
}
