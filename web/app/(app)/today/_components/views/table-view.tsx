"use client";
// TODO(T6): TanStack Table with CRUD
export function TableView({ date }: { date?: string }) {
  return (
    <div className="rounded-md border border-[var(--alfred-ruled-line)] p-6">
      <p className="font-mono text-xs uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
        TABLE VIEW — coming in T6 {date ? `(focus: ${date})` : ""}
      </p>
    </div>
  );
}
