"use client";
// TODO(T8): 7-day swimlanes with dnd-kit
export function KanbanView({ week }: { week?: string }) {
  return (
    <div className="rounded-md border border-[var(--alfred-ruled-line)] p-6">
      <p className="font-mono text-xs uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
        KANBAN VIEW — coming in T8 {week ? `(week: ${week})` : ""}
      </p>
    </div>
  );
}
