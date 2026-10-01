import type { JsonValue } from "@/types/api";
import { formatCurrency, humanize } from "@/utils/format";

export function parameterLabel(key: string): string {
  if (key === "amount_usd") return "Amount (USD)";
  if (key === "order_number") return "Order number";
  return humanize(key);
}

export function formatParameter(key: string, value: JsonValue): string {
  if (typeof value === "number" && key.endsWith("_usd")) return formatCurrency(value);
  if (value === null) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
