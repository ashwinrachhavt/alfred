"use client";

import { RefreshCw, Sparkles } from "lucide-react";

import { Message, MessageContent, MessageResponse } from "@/components/ai-elements/message";
import { Shimmer } from "@/components/ai-elements/shimmer";
import { Button } from "@/components/ui/button";

export function AiExplanationSection({
  explanation,
  domains,
  isStreaming,
  isRegenerating,
  onRegenerate,
}: {
  explanation: string;
  domains?: string[] | null;
  isStreaming?: boolean;
  isRegenerating?: boolean;
  onRegenerate?: () => void;
}) {
  return (
    <div className="bg-card/90 rounded-md border border-[var(--alfred-accent-muted)] p-4 shadow-sm backdrop-blur">
      <div className="flex items-center justify-between">
        <span className="text-muted-foreground flex items-center gap-1.5 font-mono text-xs tracking-wider uppercase">
          <Sparkles className="h-3.5 w-3.5 text-[var(--alfred-accent)]" />
          AI Context
        </span>
        {onRegenerate && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onRegenerate}
            disabled={isRegenerating}
            className="h-7 gap-1 text-xs"
          >
            <RefreshCw className={`h-3 w-3 ${isRegenerating ? "animate-spin" : ""}`} />
            Regenerate
          </Button>
        )}
      </div>
      {domains && domains.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {domains.map((d) => (
            <span
              key={d}
              className="rounded bg-[var(--alfred-accent-subtle)] px-1.5 py-0.5 font-mono text-[10px] tracking-wider uppercase"
            >
              {d}
            </span>
          ))}
        </div>
      )}
      <Message from="assistant" className="mt-3 max-w-full">
        <MessageContent className="w-full">
          {explanation ? (
            <MessageResponse className="text-sm leading-relaxed" isAnimating={isStreaming}>
              {explanation}
            </MessageResponse>
          ) : (
            <Shimmer className="text-sm" duration={1.2}>
              Generating contextual explanation...
            </Shimmer>
          )}
        </MessageContent>
      </Message>
    </div>
  );
}
