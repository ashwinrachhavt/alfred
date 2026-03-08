import type { DocumentDetailsResponse } from "@/lib/api/types/documents";

/**
 * Formats an ISO date string (or epoch-ms number) into a human-readable
 * short date. Returns "—" for null/invalid inputs.
 */
export function formatMaybeDate(value: string | number | null | undefined): string {
  if (value == null) return "—";
  const date = typeof value === "number" ? new Date(value) : new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

/**
 * Pulls a short plain-text summary from a DocumentDetailsResponse.
 * Tries the `summary` object first (looks for a `text` or `short` key),
 * then falls back to the first ~200 chars of cleaned_text.
 */
export function extractSummary(
  details: DocumentDetailsResponse | null | undefined,
): string | null {
  if (!details) return null;

  if (details.summary && typeof details.summary === "object") {
    const s = details.summary as Record<string, unknown>;
    if (typeof s.text === "string" && s.text.trim()) return s.text.trim();
    if (typeof s.short === "string" && s.short.trim()) return s.short.trim();
    if (typeof s.summary === "string" && s.summary.trim()) return s.summary.trim();
  }

  const text = (details.raw_markdown ?? details.cleaned_text ?? "").trim();
  if (!text) return null;
  return text.length > 200 ? `${text.slice(0, 200)}…` : text;
}
