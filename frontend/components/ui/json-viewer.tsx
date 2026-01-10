"use client";

import { useMemo } from "react";

import { Copy } from "lucide-react";
import { toast } from "sonner";

import { copyTextToClipboard } from "@/lib/clipboard";

import { Button } from "@/components/ui/button";

function safeJsonStringify(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function JsonViewer({
  value,
  title = "Response",
  collapsed = false,
  className = "",
}: {
  value: unknown;
  title?: string;
  collapsed?: boolean;
  className?: string;
}) {
  const jsonText = useMemo(() => safeJsonStringify(value), [value]);

  return (
    <div className={`space-y-2 ${className}`}>
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-medium">{title}</p>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={async () => {
            try {
              await copyTextToClipboard(jsonText);
              toast.success("Copied JSON.");
            } catch {
              toast.error("Failed to copy.");
            }
          }}
        >
          <Copy className="h-4 w-4" aria-hidden="true" />
          Copy
        </Button>
      </div>
      <details className="bg-muted/20 rounded-xl border" open={!collapsed}>
        <summary className="text-muted-foreground cursor-pointer px-4 py-3 text-xs font-medium select-none">
          {collapsed ? "Show JSON" : "Hide JSON"}
        </summary>
        <pre className="max-h-[520px] overflow-auto whitespace-pre-wrap break-words px-4 pb-4 text-xs leading-relaxed">
          {jsonText}
        </pre>
      </details>
    </div>
  );
}

