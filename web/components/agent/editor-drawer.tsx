"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Expand, Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { VisuallyHidden } from "@radix-ui/react-visually-hidden";
import { MarkdownNotesEditor } from "@/components/editor/markdown-notes-editor";
import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import { useShellStore } from "@/lib/stores/shell-store";

type ZettelData = {
  id: number;
  title: string;
  content: string | null;
  topic: string | null;
  tags: string[];
};

const AUTOSAVE_DELAY_MS = 800;

export function EditorDrawer({
  zettelId,
  onClose,
}: {
  zettelId: number | null;
  onClose: () => void;
}) {
  const [zettel, setZettel] = useState<ZettelData | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editedTitle, setEditedTitle] = useState("");

  // Refs for autosave
  const draftRef = useRef({ title: "", content: "" });
  const lastSavedRef = useRef({ title: "", content: "" });
  const debounceTimerRef = useRef<number | null>(null);
  const savingRef = useRef(false);
  const queuedSaveRef = useRef(false);

  useEffect(() => {
    if (!zettelId) {
      setZettel(null);
      return;
    }

    setLoading(true);
    apiFetch<ZettelData>(apiRoutes.zettels.cardById(zettelId))
      .then((data) => {
        setZettel(data);
        setEditedTitle(data.title);
        draftRef.current = { title: data.title, content: data.content || "" };
        lastSavedRef.current = { title: data.title, content: data.content || "" };
      })
      .catch(() => setZettel(null))
      .finally(() => setLoading(false));
  }, [zettelId]);

  // Autosave function
  const saveNow = useCallback(async () => {
    if (!zettel) return;
    const current = draftRef.current;
    const lastSaved = lastSavedRef.current;

    // Nothing changed
    if (current.title === lastSaved.title && current.content === lastSaved.content) {
      setSaving(false);
      return;
    }

    if (savingRef.current) {
      queuedSaveRef.current = true;
      return;
    }

    savingRef.current = true;
    setSaving(true);
    try {
      await apiFetch(apiRoutes.zettels.cardById(zettel.id), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: current.title, content: current.content }),
      });
      lastSavedRef.current = { ...current };
    } catch {
      // Silent fail — the user can see the saving indicator
    } finally {
      savingRef.current = false;
      setSaving(false);
      if (queuedSaveRef.current) {
        queuedSaveRef.current = false;
        void saveNow();
      }
    }
  }, [zettel]);

  // Debounced save trigger
  const queueSave = useCallback(() => {
    if (debounceTimerRef.current) {
      window.clearTimeout(debounceTimerRef.current);
    }
    debounceTimerRef.current = window.setTimeout(() => {
      void saveNow();
    }, AUTOSAVE_DELAY_MS);
  }, [saveNow]);

  // Save on tab/window close
  useEffect(() => {
    const onVisibilityChange = () => {
      if (document.visibilityState === "hidden") void saveNow();
    };
    window.addEventListener("visibilitychange", onVisibilityChange);
    return () => window.removeEventListener("visibilitychange", onVisibilityChange);
  }, [saveNow]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) window.clearTimeout(debounceTimerRef.current);
    };
  }, []);

  const handleContentChange = useCallback(
    (content: string) => {
      draftRef.current.content = content;
      queueSave();
    },
    [queueSave],
  );

  const handleTitleChange = useCallback(
    (title: string) => {
      setEditedTitle(title);
      draftRef.current.title = title;
      queueSave();
    },
    [queueSave],
  );

  const handleClose = useCallback(() => {
    // Flush any pending save before closing
    if (debounceTimerRef.current) {
      window.clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }
    void saveNow().then(onClose);
  }, [saveNow, onClose]);

  const handleOpenFullView = useCallback(() => {
    if (!zettel) return;
    // Flush save, then open full view
    if (debounceTimerRef.current) {
      window.clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }
    void saveNow().then(() => {
      useShellStore.getState().openZettelViewer(zettel.id);
      onClose();
    });
  }, [onClose, zettel, saveNow]);

  return (
    <Sheet open={!!zettelId} onOpenChange={(open) => !open && handleClose()}>
      <SheetContent side="right" className="w-[480px] border-l p-0 sm:max-w-[480px]">
        <VisuallyHidden>
          <SheetTitle>Edit Zettel</SheetTitle>
        </VisuallyHidden>
        {loading ? (
          <div className="flex h-full items-center justify-center">
            <Loader2 className="text-muted-foreground h-5 w-5 animate-spin" />
          </div>
        ) : zettel ? (
          <div className="flex h-full flex-col">
            {/* Header — clean, minimal */}
            <div className="flex items-center justify-between border-b px-4 py-2.5">
              <div className="flex min-w-0 flex-1 items-center gap-2">
                {saving && (
                  <Loader2 className="text-muted-foreground h-3 w-3 shrink-0 animate-spin" />
                )}
                <input
                  value={editedTitle}
                  onChange={(e) => handleTitleChange(e.target.value)}
                  onBlur={() => void saveNow()}
                  className="text-foreground flex-1 truncate border-none bg-transparent text-sm font-medium outline-none"
                  placeholder="Untitled"
                />
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={handleOpenFullView}
                >
                  <Expand className="h-3.5 w-3.5" />
                </Button>
                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleClose}>
                  <X className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>

            {/* Metadata */}
            <div className="flex items-center gap-2 border-b px-4 py-2">
              {zettel.topic && (
                <span className="text-primary rounded bg-[var(--alfred-accent-subtle)] px-1.5 py-0.5 text-[10px] font-medium tracking-wider uppercase">
                  {zettel.topic}
                </span>
              )}
              {zettel.tags?.map((tag) => (
                <span
                  key={tag}
                  className="text-muted-foreground bg-secondary rounded px-1.5 py-0.5 text-[10px]"
                >
                  {tag}
                </span>
              ))}
            </div>

            {/* Editor — takes full remaining space, no footer */}
            <div className="flex-1 overflow-y-auto px-4 py-3">
              <MarkdownNotesEditor
                markdown={zettel.content || ""}
                onMarkdownChange={handleContentChange}
                contextCardId={zettel.id}
                onKeyboardCommand={async (command) => {
                  if (command === "save") await saveNow();
                }}
              />
            </div>
          </div>
        ) : (
          <div className="text-muted-foreground flex h-full items-center justify-center text-sm">
            Zettel not found
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
