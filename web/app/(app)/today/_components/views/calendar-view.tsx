"use client";
// TODO(T7): month grid from /entries
export function CalendarView({ month }: { month?: string }) {
  return (
    <div className="rounded-md border border-[var(--alfred-ruled-line)] p-6">
      <p className="font-mono text-xs uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
        CALENDAR VIEW — coming in T7 {month ? `(month: ${month})` : ""}
      </p>
    </div>
  );
}
