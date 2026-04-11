"use client";

import { useCallback, useEffect, useState } from "react";

import { Expand, Loader2, Save, X } from "lucide-react";

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

export function EditorDrawer({
  zettelId,
  onClose,
}: {
  zettelId: number | null;
  onClose: () => void;
}) {
  const [zettel, setZettel] = useState<ZettelData | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasUnsaved, setHasUnsaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editedContent, setEditedContent] = useState("");
  const [editedTitle, setEditedTitle] = useState("");

  useEffect(() => {
    if (!zettelId) {
      setZettel(null);
      return;
    }

    setLoading(true);
    apiFetch<ZettelData>(apiRoutes.zettels.cardById(zettelId))
      .then((data) => {
        setZettel(data);
        setEditedContent(data.content || "");
        setEditedTitle(data.title);
        setHasUnsaved(false);
      })
      .catch(() => setZettel(null))
      .finally(() => setLoading(false));
  }, [zettelId]);

  const handleContentChange = useCallback((content: string) => {
    setEditedContent(content);
    setHasUnsaved(true);
  }, []);

  const handleSave = async () => {
    if (!zettel) return;
    setSaving(true);
    try {
      await apiFetch(apiRoutes.zettels.cardById(zettel.id), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: editedTitle, content: editedContent }),
      });
      setHasUnsaved(false);
    } catch {
      // TODO: show error toast
    } finally {
      setSaving(false);
    }
  };

  const handleClose = () => {
    if (hasUnsaved) {
      const confirmed = window.confirm("You have unsaved changes. Close anyway?");
      if (!confirmed) return;
    }
    onClose();
  };

  const handleOpenFullView = useCallback(() => {
    if (!zettel) return;
    if (hasUnsaved) {
      const confirmed = window.confirm("You have unsaved changes. Open full view anyway?");
      if (!confirmed) return;
    }
    useShellStore.getState().openZettelViewer(zettel.id);
    onClose();
  }, [hasUnsaved, onClose, zettel]);

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
            {/* Header */}
            <div className="flex items-center justify-between border-b px-4 py-2.5">
              <div className="flex min-w-0 flex-1 items-center gap-2">
                {hasUnsaved && <span className="bg-primary h-2 w-2 shrink-0 rounded-full" />}
                <input
                  value={editedTitle}
                  onChange={(e) => {
                    setEditedTitle(e.target.value);
                    setHasUnsaved(true);
                  }}
                  className="text-foreground flex-1 truncate border-none bg-transparent text-sm font-medium outline-none"
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

            {/* Editor */}
            <div className="flex-1 overflow-y-auto px-4 py-3">
              <MarkdownNotesEditor
                markdown={zettel.content || ""}
                onMarkdownChange={handleContentChange}
                contextCardId={zettel.id}
              />
            </div>

            {/* Footer */}
            <div className="flex justify-end border-t px-4 py-2">
              <Button size="sm" onClick={handleSave} disabled={!hasUnsaved || saving}>
                {saving ? (
                  <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Save className="mr-1 h-3.5 w-3.5" />
                )}
                Save
              </Button>
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
