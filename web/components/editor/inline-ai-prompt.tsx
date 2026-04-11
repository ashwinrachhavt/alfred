"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ExternalLink, Loader2, Sparkles, X } from "lucide-react";
import type { Editor } from "@tiptap/react";

import { cn } from "@/lib/utils";
import { useShellStore } from "@/lib/stores/shell-store";
import { useAgentStore } from "@/lib/stores/agent-store";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type AIPromptMode = "generate" | "edit" | "transform";

export type InlineAIPromptProps = {
  editor: Editor;
  mode: AIPromptMode;
  position: { top: number; left: number };
  targetText: string;
  targetRange: { from: number; to: number } | null;
  onSubmit: (instruction: string) => void;
  onClose: () => void;
  isStreaming: boolean;
};

// ---------------------------------------------------------------------------
// Preset definitions
// ---------------------------------------------------------------------------

type Preset = {
  label: string;
  prompt: string;
  panel?: boolean;
};

const GENERATE_PRESETS: Preset[] = [
  { label: "Continue", prompt: "__CONTINUE__" },
  { label: "Draft intro", prompt: "Write a strong opening paragraph for this section" },
  { label: "Add example", prompt: "Add a concrete example that makes this idea easier to grasp" },
  {
    label: "Sharpen thesis",
    prompt: "Write a sharper paragraph that states the core idea clearly",
  },
  { label: "Outline", prompt: "Create a compact outline for what this section should cover next" },
];

const EDIT_PRESETS: Preset[] = [
  { label: "Clarify", prompt: "Rewrite this so the thinking is clearer and easier to follow" },
  {
    label: "More precise",
    prompt: "Make this more precise, specific, and intellectually rigorous",
  },
  { label: "In my voice", prompt: "Rewrite this to sound more natural, confident, and human" },
  { label: "Condense", prompt: "Make this more concise without flattening the ideas" },
  { label: "Expand", prompt: "Expand this with stronger explanation and sharper transitions" },
  { label: "Stronger argument", prompt: "Strengthen the argument while preserving the core claim" },
];

const PANEL_PRESETS: Preset[] = [
  { label: "Explain", prompt: "Explain this in simpler terms", panel: true },
  { label: "Research", prompt: "Research this topic in my knowledge base", panel: true },
  { label: "Ask Alfred", prompt: "", panel: true },
];

// ---------------------------------------------------------------------------
// Placeholder & status helpers
// ---------------------------------------------------------------------------

function getPlaceholder(mode: AIPromptMode): string {
  switch (mode) {
    case "generate":
      return "What should Alfred write here?";
    case "edit":
      return "How should Alfred revise this passage?";
    case "transform":
      return "How should Alfred transform this selection?";
  }
}

function getStatusText(mode: AIPromptMode, charCount: number): string {
  if (mode === "generate") {
    return "Uses full note context · Enter to write · Esc to cancel";
  }
  return `Editing ${charCount} chars with note context · Enter to apply · Esc to cancel`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function InlineAIPrompt(props: InlineAIPromptProps) {
  const { mode, position, targetText, onSubmit, onClose, isStreaming } = props;
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-focus on mount
  useEffect(() => {
    requestAnimationFrame(() => inputRef.current?.focus());
  }, []);

  // Click-outside to close
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [onClose]);

  // Escape to close
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const handleSubmit = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;
    onSubmit(trimmed);
  }, [input, isStreaming, onSubmit]);

  const handlePresetClick = useCallback(
    (preset: Preset) => {
      if (preset.panel) {
        // Open AI side panel and optionally send a message
        useShellStore.getState().openAiPanel("sidebar");
        if (preset.prompt) {
          const message = targetText ? `${preset.prompt}:\n\n${targetText}` : preset.prompt;
          useAgentStore.getState().sendMessage(message);
        }
        onClose();
        return;
      }
      onSubmit(preset.prompt);
    },
    [targetText, onSubmit, onClose],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  // Determine which presets to show
  const presets = mode === "generate" ? GENERATE_PRESETS : [...EDIT_PRESETS, ...PANEL_PRESETS];

  return (
    <div
      ref={containerRef}
      className="border-border/80 bg-card/98 fixed z-50 w-[min(360px,calc(100vw-1.5rem))] rounded-xl border shadow-xl backdrop-blur"
      style={{ top: position.top, left: position.left }}
    >
      {/* Top row: icon + input + close/loading */}
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <Sparkles className="text-primary h-4 w-4 shrink-0" />
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={getPlaceholder(mode)}
          disabled={isStreaming}
          className="text-foreground flex-1 bg-transparent text-[13px] outline-none placeholder:text-[var(--alfred-text-tertiary)] disabled:opacity-50"
        />
        {isStreaming ? (
          <Loader2 className="h-4 w-4 shrink-0 animate-spin text-[var(--alfred-text-tertiary)]" />
        ) : (
          <button
            type="button"
            onClick={onClose}
            className="hover:text-foreground shrink-0 rounded p-0.5 text-[var(--alfred-text-tertiary)] transition-colors"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Preset chips — hidden during streaming */}
      {!isStreaming && (
        <div className="flex flex-wrap gap-1.5 px-3 py-2">
          {presets.map((preset) => (
            <button
              key={preset.label}
              type="button"
              onClick={() => handlePresetClick(preset)}
              className={cn(
                "inline-flex items-center gap-1 rounded-md border px-2 py-1",
                "text-[10px] font-medium tracking-[0.12em] uppercase",
                "hover:text-foreground text-[var(--alfred-text-tertiary)] hover:bg-[var(--alfred-accent-subtle)]",
                "transition-colors",
              )}
            >
              {preset.label}
              {preset.panel && <ExternalLink className="h-2.5 w-2.5" />}
            </button>
          ))}
        </div>
      )}

      {/* Status bar */}
      <div className="border-t px-3 py-1.5">
        <span className="text-[10px] font-medium tracking-[0.12em] text-[var(--alfred-text-tertiary)] uppercase">
          {getStatusText(mode, targetText.length)}
        </span>
      </div>
    </div>
  );
}
