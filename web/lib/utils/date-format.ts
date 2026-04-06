/**
 * Centralized date formatting utilities.
 *
 * Consolidates duplicate helpers that were previously scattered across
 * task-center-sheet, company-research-history-sheet,
 * dashboard-client, notion-client, and notion-notetaker.
 */

// ---------------------------------------------------------------------------
// Relative timestamps  ("just now", "3m ago", "2h ago", "5d ago")
// ---------------------------------------------------------------------------

/**
 * Formats a date string as a human-readable relative timestamp.
 *
 * Returns "just now" for < 1 min, "Xm ago", "Xh ago", or "Xd ago".
 * Returns "—" for missing / invalid input.
 */
export function formatRelativeTimestamp(
  value: string | null | undefined,
): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";

  const now = Date.now();
  const deltaMs = now - date.getTime();
  const deltaMinutes = Math.floor(deltaMs / 60_000);
  if (deltaMinutes < 1) return "just now";
  if (deltaMinutes < 60) return `${deltaMinutes}m ago`;
  const deltaHours = Math.floor(deltaMinutes / 60);
  if (deltaHours < 24) return `${deltaHours}h ago`;
  const deltaDays = Math.floor(deltaHours / 24);
  return `${deltaDays}d ago`;
}

// ---------------------------------------------------------------------------
// Due-date formatting
// ---------------------------------------------------------------------------

/**
 * Formats a due-date string as "Mon D, h:mm AM/PM" (locale-aware).
 *
 * Includes month, day, hour, and minute.  Returns `null` for invalid input.
 */
export function formatDue(value: string): string | null {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return null;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

/**
 * Formats a due-date as a short label — "Mon D" only (no time).
 *
 * Returns `null` for missing / invalid input.
 */
export function formatDueTimestamp(
  value: string | undefined,
): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return null;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  }).format(date);
}

// ---------------------------------------------------------------------------
// ISO / date-input helpers
// ---------------------------------------------------------------------------

/**
 * Extracts the "YYYY-MM-DD" portion from an ISO date string.
 *
 * - `toDateInputValue("2026-01-10T14:30:00Z")` → `"2026-01-10"`
 * - Returns `""` when no match is found.
 */
export function toDateInputValue(iso: string): string {
  const match = iso.match(/^(\d{4}-\d{2}-\d{2})/);
  return match ? match[1] : "";
}

/**
 * Same as `toDateInputValue` but accepts nullable input and returns `null`
 * instead of `""` on failure.
 */
export function formatIsoDate(
  iso: string | null | undefined,
): string | null {
  if (!iso) return null;
  const match = iso.match(/^(\d{4}-\d{2}-\d{2})/);
  return match ? match[1] : null;
}
