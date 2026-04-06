"use client";

import { useState } from "react";
import { ChevronRight } from "lucide-react";

export function EtymologySection({ etymology }: { etymology: string }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border-l-2 border-[var(--alfred-accent-muted)] pl-4">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
      >
        <ChevronRight
          className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-90" : ""}`}
        />
        Etymology
      </button>
      {open && (
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          {etymology}
        </p>
      )}
    </div>
  );
}
