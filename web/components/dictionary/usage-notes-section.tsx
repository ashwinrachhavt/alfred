"use client";

export function UsageNotesSection({ notes }: { notes: string }) {
  return (
    <div>
      <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
        Usage Notes
      </span>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
        {notes}
      </p>
    </div>
  );
}
