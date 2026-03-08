import type { DocumentDetailsResponse } from "@/lib/api/types/documents";
import { coerceString } from "@/lib/utils";

export function formatMaybeDate(raw?: string | null): string {
  if (!raw) return "\u2014";
  const maybeNumber = Number(raw);
  if (!Number.isNaN(maybeNumber) && Number.isFinite(maybeNumber)) {
    const date = new Date(maybeNumber);
    if (!Number.isNaN(date.getTime())) return date.toLocaleString();
  }
  const date = new Date(raw);
  if (!Number.isNaN(date.getTime())) return date.toLocaleString();
  return raw;
}

export function extractSummary(details: DocumentDetailsResponse | null): string | null {
  if (!details?.summary) return null;
  const short = coerceString(details.summary.short);
  if (short) return short;
  const summary = coerceString(details.summary.summary);
  if (summary) return summary;
  return null;
}
