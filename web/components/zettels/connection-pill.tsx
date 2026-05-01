"use client";

import { Pencil } from "lucide-react";

import { cn } from "@/lib/utils";

type Props = {
  title: string;
  onNavigate: () => void;
  onEdit?: () => void;
  className?: string;
};

export function ConnectionPill({ title, onNavigate, onEdit, className }: Props) {
  const editable = typeof onEdit === "function";
  return (
    <div
      className={cn(
        "group relative inline-flex max-w-full items-center",
        className,
      )}
    >
      <button
        type="button"
        onClick={onNavigate}
        className={cn(
          "text-muted-foreground hover:border-primary hover:text-foreground max-w-full truncate rounded-md border py-1 pl-2.5 text-[12px] transition-colors",
          editable ? "pr-7" : "pr-2.5",
        )}
      >
        {title}
      </button>
      {editable && (
        <button
          type="button"
          aria-label={`Edit link to ${title}`}
          onClick={(e) => {
            e.stopPropagation();
            onEdit?.();
          }}
          className="text-muted-foreground hover:text-primary absolute top-1/2 right-1.5 -translate-y-1/2 rounded p-0.5 opacity-0 transition-opacity group-hover:opacity-100"
        >
          <Pencil size={10} />
        </button>
      )}
    </div>
  );
}
