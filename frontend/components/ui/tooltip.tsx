import * as React from "react";

import { cn } from "@/lib/utils";

type TooltipProps = {
  children: React.ReactNode;
  content: React.ReactNode;
  className?: string;
};

/**
 * A lightweight tooltip implementation with hover/focus support.
 * Intended for simple UI hints without external dependencies.
 */
export function Tooltip({ children, content, className }: TooltipProps) {
  return (
    <span className={cn("group relative inline-flex", className)}>
      {children}
      <span
        role="tooltip"
        className={cn(
          "bg-popover text-popover-foreground pointer-events-none absolute top-full left-1/2 z-50 mt-2 hidden -translate-x-1/2 rounded-md border px-2 py-1 text-xs shadow-md",
          "group-focus-within:block group-hover:block",
        )}
      >
        {content}
      </span>
    </span>
  );
}
