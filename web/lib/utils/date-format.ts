/**
 * Centralized date formatting utilities.
 *
 * Consolidates duplicate helpers that were previously scattered across
 * task-center-sheet, company-research-history-sheet,
 * interview-prep-session-history-sheet, follow-up-center-sheet,
 * follow-ups-client, follow-up-provider, dashboard-client,
 * notion-client, and notion-notetaker.
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

/**
 * Smart due-date label used by the follow-up provider.
 *
 * If the due date is today, shows only the time ("h:mm AM/PM").
 * Otherwise shows month, day, hour, and minute.
 * Returns `null` for invalid input.
 */
export function formatDueLabel(dueAt: string): string | null {
  const due = new Date(dueAt);
  if (Number.isNaN(due.valueOf())) return null;
  const now = new Date();
  const sameDay = due.toDateString() === now.toDateString();
  if (sameDay) {
    return new Intl.DateTimeFormat(undefined, {
      hour: "numeric",
      minute: "2-digit",
    }).format(due);
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(due);
}

// ---------------------------------------------------------------------------
// Snooze helpers
// ---------------------------------------------------------------------------

/**
 * Formats a snooze-until timestamp as a short time string ("h:mm AM/PM").
 *
 * Returns `null` for invalid input.
 */
export function formatSnoozeUntil(value: string): string | null {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return null;
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

/**
 * Returns `true` when the snooze-until timestamp is still in the future.
 *
 * Accepts an optional `nowMs` parameter (milliseconds since epoch) so
 * callers that already track the current time via state can pass it in.
 * When omitted, `Date.now()` is used.
 */
export function isSnoozedUntilFuture(
  value: string | undefined,
  nowMs?: number,
): boolean {
  if (!value) return false;
  const until = Date.parse(value);
  if (Number.isNaN(until)) return false;
  return until > (nowMs ?? Date.now());
}

// ---------------------------------------------------------------------------
// Due-date badge variant helpers
// ---------------------------------------------------------------------------

/**
 * Returns a badge variant based on how soon a follow-up is due.
 *
 * - `"destructive"` — overdue (delta <= 0)
 * - `"default"` — due within 2 hours
 * - `"secondary"` — due later or missing/invalid
 *
 * Accepts `nowMs` so callers that track time via state can pass it in.
 * When omitted, `Date.now()` is used.
 */
export function dueBadgeVariant(
  dueAt: string | undefined,
  nowMs?: number,
): "default" | "secondary" | "destructive" {
  if (!dueAt) return "secondary";
  const dueMs = Date.parse(dueAt);
  if (Number.isNaN(dueMs)) return "secondary";
  const delta = dueMs - (nowMs ?? Date.now());
  if (delta <= 0) return "destructive";
  if (delta <= 2 * 60 * 60 * 1000) return "default";
  return "secondary";
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
