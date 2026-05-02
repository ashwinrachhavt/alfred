"use client";

/**
 * Ghost suggestion wiki-link UX (T10).
 *
 * Minimal viable version. Renders a muted-orange "ghost" suggestion that
 * extends the word the user is currently typing into the host textarea.
 * Tab accepts and inserts `[[<title>]]` at the caret.
 *
 * TODO(T10): the suggestion engine is STUBBED.
 *   - It currently uses a tiny in-memory candidate list.
 *   - For production we need to debounce queries against
 *     apiRoutes.zettels.search and prefer recent-session titles.
 *   - We also need a proper TipTap extension (NodeView) so the ghost
 *     renders inside the ProseMirror editor rather than alongside a
 *     textarea. Today the workspace uses a textarea for the editor body;
 *     the "extension" name is aspirational until that lands.
 *
 * This file ships the INTERACTION (ghost visible, Tab accepts) so that
 * downstream consumers have a stable surface to wire the real engine to.
 */

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";

import { cn } from "@/lib/utils";

const STUB_CANDIDATES: string[] = [
  "Meadows",
  "Feynman Technique",
  "Zettelkasten",
  "Bloom's Taxonomy",
  "Systems Thinking",
  "Spaced Repetition",
  "Active Recall",
];

function suggestTitle(prefix: string): string | null {
  if (prefix.length < 2) return null;
  const needle = prefix.toLowerCase();
  for (const title of STUB_CANDIDATES) {
    if (
      title.toLowerCase().startsWith(needle) &&
      title.toLowerCase() !== needle
    ) {
      return title;
    }
  }
  return null;
}

function getCurrentWordPrefix(
  value: string,
  caret: number,
): { word: string; start: number } {
  const before = value.slice(0, caret);
  const match = /[A-Za-z][A-Za-z0-9_-]*$/.exec(before);
  if (!match) return { word: "", start: caret };
  return { word: match[0], start: match.index };
}

export type GhostSuggestionTextareaHandle = {
  focus: () => void;
  getValue: () => string;
  setValue: (v: string) => void;
};

type Props = {
  value: string;
  placeholder?: string;
  onChange: (next: string) => void;
  onKeyCommand?: (cmd: "submit" | "next" | "prev") => void;
  className?: string;
  autoFocus?: boolean;
  readOnly?: boolean;
  ariaLabel?: string;
};

export const GhostSuggestionEditorExt = forwardRef<
  GhostSuggestionTextareaHandle,
  Props
>(function GhostSuggestionEditorExt(
  {
    value,
    placeholder,
    onChange,
    onKeyCommand,
    className,
    autoFocus,
    readOnly,
    ariaLabel,
  },
  ref,
) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [caret, setCaret] = useState<number>(value.length);

  useImperativeHandle(
    ref,
    () => ({
      focus: () => textareaRef.current?.focus(),
      getValue: () => textareaRef.current?.value ?? value,
      setValue: (v: string) => onChange(v),
    }),
    [onChange, value],
  );

  useEffect(() => {
    if (autoFocus) textareaRef.current?.focus();
  }, [autoFocus]);

  // Auto-grow textarea.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);

  const { word, start } = useMemo(
    () => getCurrentWordPrefix(value, caret),
    [value, caret],
  );
  const suggestion = useMemo(() => suggestTitle(word), [word]);
  const ghostSuffix =
    suggestion && word.length > 0 ? suggestion.slice(word.length) : "";

  const acceptSuggestion = useCallback(() => {
    if (!suggestion || !ghostSuffix) return false;
    const insert = `[[${suggestion}]]`;
    const next = value.slice(0, start) + insert + value.slice(caret);
    const nextCaret = start + insert.length;
    onChange(next);
    requestAnimationFrame(() => {
      const el = textareaRef.current;
      if (!el) return;
      el.selectionStart = nextCaret;
      el.selectionEnd = nextCaret;
    });
    return true;
  }, [suggestion, ghostSuffix, value, start, caret, onChange]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Tab" && ghostSuffix) {
      e.preventDefault();
      acceptSuggestion();
      return;
    }
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      onKeyCommand?.("submit");
      return;
    }
    if (e.key === "]" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      onKeyCommand?.("next");
      return;
    }
    if (e.key === "[" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      onKeyCommand?.("prev");
      return;
    }
  };

  return (
    <div className={cn("relative", className)}>
      {ghostSuffix && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 whitespace-pre-wrap break-words font-serif text-[17px] leading-[1.6] text-transparent"
        >
          {value.slice(0, caret)}
          <span className="text-primary/40">{ghostSuffix}</span>
        </div>
      )}

      <textarea
        ref={textareaRef}
        value={value}
        placeholder={placeholder}
        onChange={(e) => {
          onChange(e.target.value);
          setCaret(e.target.selectionStart ?? e.target.value.length);
        }}
        onKeyUp={(e) => {
          setCaret(
            e.currentTarget.selectionStart ?? e.currentTarget.value.length,
          );
        }}
        onClick={(e) => {
          setCaret(
            e.currentTarget.selectionStart ?? e.currentTarget.value.length,
          );
        }}
        onKeyDown={handleKeyDown}
        readOnly={readOnly}
        aria-label={ariaLabel ?? "Editor"}
        className={cn(
          "relative w-full resize-none bg-transparent font-serif text-[17px] leading-[1.6] text-foreground outline-none placeholder:text-muted-foreground",
          readOnly && "cursor-default",
        )}
        rows={8}
      />
      {ghostSuffix && (
        <div className="mt-1 font-mono text-[10px] uppercase tracking-wider text-[var(--alfred-text-tertiary)]">
          Tab to accept - {suggestion}
        </div>
      )}
    </div>
  );
});

export default GhostSuggestionEditorExt;
