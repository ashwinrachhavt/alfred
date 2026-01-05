import * as React from "react"

import { cn } from "@/lib/utils"

type TooltipProps = {
  children: React.ReactNode
  content: React.ReactNode
  className?: string
}

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
          "pointer-events-none absolute left-1/2 top-full z-50 mt-2 hidden -translate-x-1/2 rounded-md border bg-popover px-2 py-1 text-xs text-popover-foreground shadow-md",
          "group-hover:block group-focus-within:block"
        )}
      >
        {content}
      </span>
    </span>
  )
}
