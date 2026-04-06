"use client";

import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

export function AiExplanationSection({
  explanation,
  domains,
  isRegenerating,
  onRegenerate,
}: {
  explanation: string;
  domains?: string[] | null;
  isRegenerating?: boolean;
  onRegenerate?: () => void;
}) {
  return (
    <div className="rounded-lg border-l-2 border-[#E8590C] bg-card p-4">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
          AI Explanation
        </span>
        {onRegenerate && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onRegenerate}
            disabled={isRegenerating}
            className="h-7 gap-1 text-xs"
          >
            <RefreshCw
              className={`h-3 w-3 ${isRegenerating ? "animate-spin" : ""}`}
            />
            Regenerate
          </Button>
        )}
      </div>
      {domains && domains.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {domains.map((d) => (
            <span
              key={d}
              className="rounded bg-[var(--alfred-accent-subtle)] px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider"
            >
              {d}
            </span>
          ))}
        </div>
      )}
      <p className="mt-3 text-sm leading-relaxed whitespace-pre-line">
        {explanation}
      </p>
    </div>
  );
}
