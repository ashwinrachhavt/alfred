"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChevronRight, Loader2, Sparkles, X } from "lucide-react";
import type { Editor } from "@tiptap/react";

import { cn } from "@/lib/utils";
import { useShellStore } from "@/lib/stores/shell-store";
import { useAgentStore } from "@/lib/stores/agent-store";
import {
  AI_COMMANDS,
  aiCommandsByGroup,
  editSubmenu,
  type AICommand,
  type AICommandGroup,
} from "@/lib/notes-ai/commands";

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

// Visible group order in the flyout.
const GROUP_ORDER: AICommandGroup[] = ["edit", "generate", "draft", "ask"];

const GROUP_LABEL: Record<AICommandGroup, string> = {
  edit: "Edit or review",
  generate: "Generate from this note",
  draft: "Draft with AI",
  ask: "Ask AI",
};

// Flat menu rows include both "leaf" commands and "submenu" parent rows.
// Submenu rows expand into a child set on hover/right-arrow.
type MenuRow =
  | { kind: "leaf"; command: AICommand }
  | { kind: "submenu"; key: "tone" | "translate"; label: string; commands: AICommand[] };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getPlaceholder(mode: AIPromptMode): string {
  switch (mode) {
    case "generate":
      return "What should Polymath write here?";
    case "edit":
      return "How should Polymath revise this passage?";
    case "transform":
      return "How should Polymath transform this selection?";
  }
}

function getStatusText(mode: AIPromptMode, charCount: number, isStreaming: boolean): string {
  if (isStreaming) return "Streaming · Esc to cancel";
  if (mode === "generate") return "Uses full note context · Enter to write · Esc to cancel";
  return `Editing ${charCount} chars with note context · Enter to apply · Esc to cancel`;
}

/**
 * Build the visible menu rows for the current mode.
 *
 * Edit mode: surface tone + translate as collapsed submenus alongside the
 * five base edit commands, then the Ask group.
 * Generate / Transform: skip Edit (those commands need a paragraph or
 * selection that isn't being mutated yet) and lead with Generate / Draft.
 */
function buildMenuStructure(
  mode: AIPromptMode,
): Array<{ group: AICommandGroup; rows: MenuRow[] }> {
  const grouped = aiCommandsByGroup();
  const submenu = editSubmenu();

  const editRows: MenuRow[] = [
    ...submenu.base.map((command): MenuRow => ({ kind: "leaf", command })),
    {
      kind: "submenu",
      key: "tone",
      label: "Change tone",
      commands: submenu.tone,
    },
    {
      kind: "submenu",
      key: "translate",
      label: "Translate",
      commands: submenu.translate,
    },
  ];

  const sections: Array<{ group: AICommandGroup; rows: MenuRow[] }> = [];

  for (const group of GROUP_ORDER) {
    if (group === "edit") {
      // Hide Edit group when there's nothing to edit (no selection, empty paragraph).
      if (mode === "generate") continue;
      sections.push({ group, rows: editRows });
    } else {
      const rows = grouped[group].map((command): MenuRow => ({ kind: "leaf", command }));
      if (rows.length > 0) sections.push({ group, rows });
    }
  }

  return sections;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function InlineAIPrompt(props: InlineAIPromptProps) {
  const { mode, position, targetText, onSubmit, onClose, isStreaming } = props;
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Hover/focus state for submenus. `null` means no submenu is open.
  const [openSubmenu, setOpenSubmenu] = useState<"tone" | "translate" | null>(null);
  // Active highlight in the *flat-merged* row index. -1 means no highlight.
  const [activeIndex, setActiveIndex] = useState(-1);

  const sections = useMemo(() => buildMenuStructure(mode), [mode]);

  // Flatten sections to a single array for keyboard navigation. Section
  // headers are not navigable, but their rows are.
  const flatRows = useMemo<MenuRow[]>(() => sections.flatMap((s) => s.rows), [sections]);

  // Auto-focus on mount.
  useEffect(() => {
    requestAnimationFrame(() => inputRef.current?.focus());
  }, []);

  // Click-outside to close.
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [onClose]);

  const handleSubmit = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;
    onSubmit(trimmed);
  }, [input, isStreaming, onSubmit]);

  const handleCommandRun = useCallback(
    (command: AICommand) => {
      if (command.panel) {
        useShellStore.getState().openAiPanel("sidebar");
        if (command.promptTemplate) {
          const message = targetText
            ? `${command.promptTemplate}:\n\n${targetText}`
            : command.promptTemplate;
          useAgentStore.getState().sendMessage(message);
        }
        onClose();
        return;
      }
      onSubmit(command.promptTemplate);
    },
    [onSubmit, onClose, targetText],
  );

  const handleRowActivate = useCallback(
    (row: MenuRow) => {
      if (row.kind === "leaf") {
        handleCommandRun(row.command);
      } else {
        setOpenSubmenu(row.key);
      }
    },
    [handleCommandRun],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (activeIndex >= 0 && flatRows[activeIndex]) {
          handleRowActivate(flatRows[activeIndex]);
        } else {
          handleSubmit();
        }
        return;
      }

      if (e.key === "Escape") {
        e.preventDefault();
        if (openSubmenu) {
          setOpenSubmenu(null);
          return;
        }
        onClose();
        return;
      }

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIndex((idx) => (idx + 1 >= flatRows.length ? 0 : idx + 1));
        return;
      }

      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIndex((idx) => (idx <= 0 ? flatRows.length - 1 : idx - 1));
        return;
      }

      if (e.key === "ArrowRight" && activeIndex >= 0) {
        const row = flatRows[activeIndex];
        if (row?.kind === "submenu") {
          e.preventDefault();
          setOpenSubmenu(row.key);
        }
        return;
      }

      if (e.key === "ArrowLeft" && openSubmenu) {
        e.preventDefault();
        setOpenSubmenu(null);
        return;
      }
    },
    [activeIndex, flatRows, openSubmenu, handleRowActivate, handleSubmit, onClose],
  );

  // Track flattened row index → command for activeIndex highlight.
  const indexOfRow = useCallback(
    (row: MenuRow): number => {
      if (row.kind === "leaf") {
        return flatRows.findIndex(
          (r) => r.kind === "leaf" && r.command.id === row.command.id,
        );
      }
      return flatRows.findIndex((r) => r.kind === "submenu" && r.key === row.key);
    },
    [flatRows],
  );

  // Resolve the submenu commands for the current openSubmenu.
  const submenuCommands = useMemo<AICommand[] | null>(() => {
    if (!openSubmenu) return null;
    const row = flatRows.find((r) => r.kind === "submenu" && r.key === openSubmenu);
    return row && row.kind === "submenu" ? row.commands : null;
  }, [openSubmenu, flatRows]);

  return (
    <div
      ref={containerRef}
      className="border-border/80 bg-card/98 fixed z-50 w-[min(380px,calc(100vw-1.5rem))] rounded-xl border shadow-xl backdrop-blur"
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
            aria-label="Close"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Grouped command flyout — hidden during streaming */}
      {!isStreaming && (
        <div className="max-h-[60vh] overflow-y-auto py-1.5">
          {sections.map((section, sectionIdx) => (
            <div key={section.group} className={cn(sectionIdx > 0 && "mt-1.5")}>
              <div className="px-3 py-1 font-mono text-[9px] tracking-[0.12em] text-[var(--alfred-text-tertiary)] uppercase">
                {GROUP_LABEL[section.group]}
              </div>
              {section.rows.map((row) => {
                const idx = indexOfRow(row);
                const isActive = idx === activeIndex;

                if (row.kind === "leaf") {
                  const Icon = row.command.icon;
                  return (
                    <button
                      key={row.command.id}
                      type="button"
                      onMouseEnter={() => setActiveIndex(idx)}
                      onClick={() => handleRowActivate(row)}
                      className={cn(
                        "flex w-full items-center gap-2.5 px-3 py-1.5 text-left",
                        "transition-colors",
                        isActive
                          ? "bg-[var(--alfred-accent-subtle)] text-foreground"
                          : "text-muted-foreground hover:text-foreground",
                      )}
                    >
                      <Icon className="h-3.5 w-3.5 shrink-0" />
                      <span className="flex-1 text-[12px]">{row.command.label}</span>
                      {row.command.description && (
                        <span className="hidden truncate text-[10px] text-[var(--alfred-text-tertiary)] sm:inline">
                          {row.command.description}
                        </span>
                      )}
                    </button>
                  );
                }

                return (
                  <button
                    key={row.key}
                    type="button"
                    onMouseEnter={() => {
                      setActiveIndex(idx);
                      setOpenSubmenu(row.key);
                    }}
                    onClick={() => handleRowActivate(row)}
                    className={cn(
                      "flex w-full items-center gap-2.5 px-3 py-1.5 text-left",
                      "transition-colors",
                      isActive || openSubmenu === row.key
                        ? "bg-[var(--alfred-accent-subtle)] text-foreground"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                    aria-expanded={openSubmenu === row.key}
                  >
                    <Sparkles className="h-3.5 w-3.5 shrink-0" />
                    <span className="flex-1 text-[12px]">{row.label}</span>
                    <ChevronRight className="h-3 w-3 shrink-0 text-[var(--alfred-text-tertiary)]" />
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      )}

      {/* Status bar */}
      <div className="border-t px-3 py-1.5">
        <span className="text-[10px] font-medium tracking-[0.12em] text-[var(--alfred-text-tertiary)] uppercase">
          {getStatusText(mode, targetText.length, isStreaming)}
        </span>
      </div>

      {/* Submenu panel — opens to the right of the parent menu */}
      {openSubmenu && submenuCommands && (
        <div
          className="border-border/80 bg-card/98 absolute top-0 left-full ml-2 w-56 rounded-xl border py-1.5 shadow-xl backdrop-blur"
          role="menu"
        >
          <div className="px-3 py-1 font-mono text-[9px] tracking-[0.12em] text-[var(--alfred-text-tertiary)] uppercase">
            {openSubmenu === "tone" ? "Tone" : "Translate to"}
          </div>
          {submenuCommands.map((command) => {
            const Icon = command.icon;
            return (
              <button
                key={command.id}
                type="button"
                role="menuitem"
                onClick={() => handleCommandRun(command)}
                className={cn(
                  "flex w-full items-center gap-2.5 px-3 py-1.5 text-left",
                  "text-muted-foreground hover:text-foreground hover:bg-[var(--alfred-accent-subtle)]",
                  "transition-colors",
                )}
              >
                <Icon className="h-3.5 w-3.5 shrink-0" />
                <span className="text-[12px]">{command.label}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// `AI_COMMANDS` is re-exported so callers can map commands to specific
// editor behaviors without re-importing from the commands module.
export { AI_COMMANDS };
