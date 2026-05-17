"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FilePlus2, MoreHorizontal, NotebookPen, Sparkles } from "lucide-react";
import { toast } from "sonner";

import type { NoteResponse } from "@/lib/api/types/notes";

import {
  MarkdownNotesEditor,
  type EditorDraft,
  type MarkdownNotesEditorHandle,
} from "@/components/editor/markdown-notes-editor";
import { Button } from "@/components/ui/button";
import { formatRelativeTimestamp } from "@/lib/utils/date-format";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
// Tooltip import removed — save button removed for seamless autosave
import { useUpdateNote, useUploadNoteAsset } from "@/features/notes/mutations";
import { useNote } from "@/features/notes/queries";
import { syncWikiLinks } from "@/lib/api/zettels";

type AutosaveState = "idle" | "dirty" | "saving" | "saved" | "error";

// Autosave is seamless — no visible status label (Notion-style).
// Error state shown inline only when save fails.

type NoteDraft = EditorDraft & {
  title: string;
};

function jsonSignature(value: Record<string, unknown> | null): string {
  if (!value) return "null";
  try {
    return JSON.stringify(value);
  } catch {
    return "";
  }
}

function normalizeNote(note: NoteResponse | null): NoteDraft {
  if (!note) return { title: "", markdown: "", tiptapJson: null };
  return {
    title: note.title || "Untitled",
    markdown: note.content_markdown ?? "",
    tiptapJson: note.content_json ?? null,
  };
}

export function NoteEditorPanel({
  noteId,
  workspaceId,
  onCreateNote,
}: {
  noteId: string | null;
  workspaceId: string | null;
  onCreateNote: () => void;
}) {
  const noteQuery = useNote(noteId);

  const updateNoteMutation = useUpdateNote(noteId ?? "disabled", { workspaceId });
  const uploadAssetMutation = useUploadNoteAsset(noteId ?? "disabled");

  const [title, setTitle] = useState("");
  const [markdown, setMarkdown] = useState("");
  const [autosaveState, setAutosaveState] = useState<AutosaveState>("idle");

  const editorRef = useRef<MarkdownNotesEditorHandle | null>(null);
  const hydratedNoteIdRef = useRef<string | null>(null);
  const lastSavedRef = useRef<NoteDraft>({ title: "", markdown: "", tiptapJson: null });
  const draftRef = useRef<NoteDraft>({ title: "", markdown: "", tiptapJson: null });
  const debounceTimerRef = useRef<number | null>(null);
  const queuedSaveRef = useRef(false);
  const saveInFlightRef = useRef(false);
  const lastSyncedWikiLinksRef = useRef("");

  const loaded = useMemo(() => normalizeNote(noteQuery.data ?? null), [noteQuery.data]);
  const lastEditedLabel = useMemo(
    () => formatRelativeTimestamp(noteQuery.data?.updated_at),
    [noteQuery.data?.updated_at],
  );

  const saveNow = useCallback(async () => {
    if (!noteId) return;
    const flushed = editorRef.current?.flushPendingChanges();
    if (flushed) {
      draftRef.current.markdown = flushed.markdown;
      draftRef.current.tiptapJson = flushed.tiptapJson;
    }

    const current = draftRef.current;
    const lastSaved = lastSavedRef.current;
    const nextTitle = current.title.trim() || "Untitled";
    const lastJsonSignature = jsonSignature(lastSaved.tiptapJson);
    const currentJsonSignature = jsonSignature(current.tiptapJson);
    const titleChanged = nextTitle !== lastSaved.title;
    const markdownChanged = current.markdown !== lastSaved.markdown;
    const jsonChanged = currentJsonSignature !== lastJsonSignature;

    if (!titleChanged && !markdownChanged && !jsonChanged) {
      setAutosaveState("idle");
      return;
    }

    if (saveInFlightRef.current) {
      queuedSaveRef.current = true;
      return;
    }

    setAutosaveState("saving");
    saveInFlightRef.current = true;
    try {
      const payload = {
        ...(titleChanged ? { title: nextTitle } : {}),
        ...(markdownChanged ? { content_markdown: current.markdown } : {}),
        ...(jsonChanged ? { content_json: current.tiptapJson } : {}),
      };
      const updated = await updateNoteMutation.mutateAsync(payload);
      lastSavedRef.current = normalizeNote(updated);
      const latestDraft = draftRef.current;
      const latestTitle = latestDraft.title.trim() || "Untitled";
      const hasNewerLocalChanges =
        latestTitle !== lastSavedRef.current.title ||
        latestDraft.markdown !== lastSavedRef.current.markdown ||
        jsonSignature(latestDraft.tiptapJson) !== jsonSignature(lastSavedRef.current.tiptapJson);
      setAutosaveState(hasNewerLocalChanges ? "dirty" : "saved");
      if (hasNewerLocalChanges) {
        queuedSaveRef.current = true;
      }
    } catch (err) {
      setAutosaveState("error");
      toast.error(err instanceof Error ? err.message : "Failed to save note.");
    } finally {
      saveInFlightRef.current = false;
      if (queuedSaveRef.current) {
        queuedSaveRef.current = false;
        void saveNow();
      }
    }
  }, [noteId, updateNoteMutation]);

  const queueSave = useCallback(() => {
    if (!noteId) return;
    setAutosaveState("dirty");
    if (debounceTimerRef.current) {
      window.clearTimeout(debounceTimerRef.current);
    }
    debounceTimerRef.current = window.setTimeout(() => {
      void saveNow();
    }, 650);
  }, [noteId, saveNow]);

  useEffect(() => {
    if (!noteId) {
      hydratedNoteIdRef.current = null;
      return;
    }
    if (!noteQuery.data) return;
    if (hydratedNoteIdRef.current === noteId) return;

    setTitle(loaded.title);
    setMarkdown(loaded.markdown);
    lastSavedRef.current = loaded;
    draftRef.current = loaded;
    hydratedNoteIdRef.current = noteId;
    setAutosaveState("idle");
    lastSyncedWikiLinksRef.current = "";
  }, [loaded, noteId, noteQuery.data]);

  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) window.clearTimeout(debounceTimerRef.current);
    };
  }, []);

  useEffect(() => {
    const onVisibilityChange = () => {
      if (document.visibilityState !== "hidden") return;
      void saveNow();
    };
    window.addEventListener("visibilitychange", onVisibilityChange);
    return () => window.removeEventListener("visibilitychange", onVisibilityChange);
  }, [saveNow]);

  if (!noteId) {
    return (
      <section className="flex h-full min-h-0 flex-col">
        <EmptyState
          icon={NotebookPen}
          title="Pick a note"
          description="Select a note on the left, or create a new one."
          action={
            <Button type="button" onClick={onCreateNote} className="text-xs">
              <FilePlus2 className="h-4 w-4" aria-hidden="true" />
              New note
            </Button>
          }
          className="h-full"
        />
      </section>
    );
  }

  if (noteQuery.isLoading) {
    return (
      <section className="flex h-full min-h-0 flex-col p-6">
        <div className="space-y-3">
          <Skeleton className="h-9 w-1/2" />
          <Skeleton className="h-7 w-1/3" />
          <Skeleton className="h-64 w-full" />
        </div>
      </section>
    );
  }

  if (noteQuery.isError) {
    return (
      <section className="flex h-full min-h-0 flex-col p-6">
        <EmptyState
          title="Failed to load note"
          description={noteQuery.error instanceof Error ? noteQuery.error.message : "Unknown error"}
          action={
            <Button
              type="button"
              variant="outline"
              onClick={() => noteQuery.refetch()}
              className="text-xs"
            >
              Retry
            </Button>
          }
          className="h-full"
        />
      </section>
    );
  }

  return (
    <section className="flex h-full min-h-0 flex-col bg-background">
      <div className="min-h-0 flex-1 overflow-y-auto px-6 pt-14 pb-28">
        <div className="mx-auto flex min-h-full w-full max-w-[700px] flex-col">
          {/* Document header — Notion behavior, Alfred editorial mood. */}
          <header className="pb-5">
            <div className="mb-6 flex items-center justify-between gap-3 text-[11px] text-[var(--alfred-text-tertiary)]">
              <div className="flex min-w-0 items-center gap-2">
                <span className="font-mono font-medium tracking-[0.14em] uppercase">Pages</span>
                <span aria-hidden="true">/</span>
                <span className="truncate">{title.trim() || "Untitled"}</span>
              </div>
              <div className="flex shrink-0 items-center gap-1.5">
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-7 gap-1.5 px-2 text-[11px] text-muted-foreground hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground"
                >
                  <Sparkles className="size-3" aria-hidden="true" />
                  Ask AI
                </Button>
                <Button
                  type="button"
                  size="icon-sm"
                  variant="ghost"
                  className="text-muted-foreground hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground"
                  aria-label="Page actions"
                >
                  <MoreHorizontal className="size-4" aria-hidden="true" />
                </Button>
              </div>
            </div>

            <input
              value={title}
              onChange={(e) => {
                const next = e.target.value;
                setTitle(next);
                draftRef.current.title = next;
                queueSave();
              }}
              onBlur={() => void saveNow()}
              className="w-full bg-transparent font-serif text-[2.5rem] leading-[1.1] tracking-[-0.025em] outline-none placeholder:text-[var(--alfred-text-tertiary)]"
              placeholder="Untitled"
            />

            <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-[var(--alfred-text-tertiary)]">
              <span>Edited {lastEditedLabel}</span>
              <span aria-hidden="true">·</span>
              <span>Silent autosave</span>
              <span aria-hidden="true">·</span>
              <span>Press / for blocks</span>
            </div>

            {/* Only show error state — everything else is silent */}
            {autosaveState === "error" && (
              <div className="mt-3 flex items-center gap-2 rounded-sm border border-[var(--error)]/30 bg-[var(--error)]/10 px-3 py-2">
                <span className="text-[10px] font-medium tracking-widest text-[var(--error)] uppercase">
                  Save failed
                </span>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-6 px-2 text-[10px]"
                  onClick={() => void saveNow()}
                >
                  Retry
                </Button>
              </div>
            )}
          </header>

          <div className="min-h-0 flex-1 border-t border-[var(--alfred-ruled-line)] pt-5">
            <MarkdownNotesEditor
            ref={editorRef}
            markdown={markdown}
            tiptapJson={draftRef.current.tiptapJson}
            documentTitle={title}
            documentId={noteId}
            onMarkdownChange={(nextMarkdown) => {
              setMarkdown(nextMarkdown);
              draftRef.current.markdown = nextMarkdown;
            }}
            onDraftChange={({ markdown: nextMarkdown, tiptapJson }) => {
              draftRef.current.markdown = nextMarkdown;
              draftRef.current.tiptapJson = tiptapJson;
              queueSave();
            }}
            className="h-full border-none bg-transparent shadow-none focus-within:ring-0 focus-within:ring-offset-0"
            placeholder="Start writing... (Type / for blocks, select text for AI)"
            uploadImage={async (file) => {
              if (!noteId) throw new Error("No note selected.");
              const res = await uploadAssetMutation.mutateAsync(file);
              return res.url;
            }}
            onKeyboardCommand={async (command) => {
              if (command === "save") {
                await saveNow();
              }
            }}
            onWikiLinksChange={(cardIds) => {
              if (!noteId) return;
              const key = cardIds.join(",");
              if (key === lastSyncedWikiLinksRef.current) return;
              lastSyncedWikiLinksRef.current = key;
              void syncWikiLinks("note", noteId, cardIds).catch((error) => {
                lastSyncedWikiLinksRef.current = "";
                toast.error(error instanceof Error ? error.message : "Failed to sync note links.");
              });
            }}
            />
          </div>
        </div>
      </div>
    </section>
  );
}
