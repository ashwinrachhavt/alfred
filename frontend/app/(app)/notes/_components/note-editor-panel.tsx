"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FilePlus2, NotebookPen, Save } from "lucide-react";
import { toast } from "sonner";

import type { NoteResponse } from "@/lib/api/types/notes";

import { cn } from "@/lib/utils";
import { MarkdownNotesEditor, type MarkdownNotesEditorHandle } from "@/components/editor/markdown-notes-editor";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useUpdateNote, useUploadNoteAsset } from "@/features/notes/mutations";
import { useNote } from "@/features/notes/queries";

type AutosaveState = "idle" | "dirty" | "saving" | "saved" | "error";

function formatAutosaveLabel(state: AutosaveState): string {
  if (state === "saving") return "Saving…";
  if (state === "saved") return "Saved";
  if (state === "error") return "Save failed";
  if (state === "dirty") return "Unsaved";
  return " ";
}

function normalizeNote(note: NoteResponse | null): { title: string; markdown: string } {
  if (!note) return { title: "", markdown: "" };
  return {
    title: note.title || "Untitled",
    markdown: note.content_markdown ?? "",
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
  const lastSavedRef = useRef<{ title: string; markdown: string }>({ title: "", markdown: "" });
  const draftRef = useRef<{
    title: string;
    markdown: string;
    tiptapJson: Record<string, unknown> | null;
  }>({ title: "", markdown: "", tiptapJson: null });
  const debounceTimerRef = useRef<number | null>(null);
  const queuedSaveRef = useRef(false);

  const loaded = useMemo(() => normalizeNote(noteQuery.data ?? null), [noteQuery.data]);

  const saveNow = useCallback(async () => {
    if (!noteId) return;
    const current = draftRef.current;
    const lastSaved = lastSavedRef.current;
    if (current.title === lastSaved.title && current.markdown === lastSaved.markdown) {
      setAutosaveState("idle");
      return;
    }

    if (updateNoteMutation.isPending) {
      queuedSaveRef.current = true;
      return;
    }

    setAutosaveState("saving");
    try {
      const updated = await updateNoteMutation.mutateAsync({
        title: current.title.trim() || "Untitled",
        content_markdown: current.markdown,
        content_json: current.tiptapJson,
      });
      lastSavedRef.current = normalizeNote(updated);
      setAutosaveState("saved");
    } catch (err) {
      setAutosaveState("error");
      toast.error(err instanceof Error ? err.message : "Failed to save note.");
    } finally {
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
    if (!noteId) return;
    if (!noteQuery.data) return;

    setTitle(loaded.title);
    setMarkdown(loaded.markdown);
    lastSavedRef.current = loaded;
    draftRef.current = { title: loaded.title, markdown: loaded.markdown, tiptapJson: null };
    setAutosaveState("idle");
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
            <Button type="button" onClick={onCreateNote}>
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
      <section className="flex h-full min-h-0 flex-col p-5">
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
      <section className="flex h-full min-h-0 flex-col p-5">
        <EmptyState
          title="Failed to load note"
          description={noteQuery.error instanceof Error ? noteQuery.error.message : "Unknown error"}
          action={
            <Button type="button" variant="outline" onClick={() => noteQuery.refetch()}>
              Retry
            </Button>
          }
          className="h-full"
        />
      </section>
    );
  }

  const statusLabel = formatAutosaveLabel(autosaveState);

  return (
    <section className="flex h-full min-h-0 flex-col">
      <header className="flex items-start justify-between gap-3 p-5 pb-3">
        <div className="min-w-0 flex-1 space-y-2">
          <Input
            value={title}
            onChange={(e) => {
              const next = e.target.value;
              setTitle(next);
              draftRef.current.title = next;
              queueSave();
            }}
            onBlur={() => void saveNow()}
            className={cn(
              "h-10 border-none px-0 text-2xl font-semibold shadow-none focus-visible:ring-0",
            )}
            placeholder="Untitled"
          />
          <div className="text-muted-foreground flex items-center gap-2 text-xs">
            <span>{statusLabel}</span>
            {autosaveState === "error" ? (
              <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => void saveNow()}>
                Retry
              </Button>
            ) : null}
          </div>
        </div>

        <div className="flex items-center gap-2 pt-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                size="icon"
                variant="outline"
                onClick={() => void saveNow()}
                disabled={updateNoteMutation.isPending}
              >
                <Save className="h-4 w-4" aria-hidden="true" />
                <span className="sr-only">Save</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>Save (⌘S)</TooltipContent>
          </Tooltip>
        </div>
      </header>

      <Separator />

      <div className="min-h-0 flex-1 p-5">
        <MarkdownNotesEditor
          ref={editorRef}
          markdown={markdown}
          onMarkdownChange={(nextMarkdown) => {
            setMarkdown(nextMarkdown);
            draftRef.current.markdown = nextMarkdown;
            queueSave();
          }}
          onDraftChange={({ tiptapJson }) => {
            draftRef.current.tiptapJson = tiptapJson;
          }}
          className="h-full"
          placeholder="Write notes… (Type / for blocks, paste images, select text for AI)"
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
        />
      </div>
    </section>
  );
}
