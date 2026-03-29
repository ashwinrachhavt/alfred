"use client";

import { useCallback, useEffect, useState } from "react";

import { Expand, Loader2, Save, X } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { MarkdownNotesEditor } from "@/components/editor/markdown-notes-editor";
import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

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

  return (
    <Sheet open={!!zettelId} onOpenChange={(open) => !open && handleClose()}>
      <SheetContent side="right" className="w-[480px] sm:max-w-[480px] p-0 border-l">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : zettel ? (
          <div className="flex flex-col h-full">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-2.5 border-b">
              <div className="flex items-center gap-2 flex-1 min-w-0">
                {hasUnsaved && (
                  <span className="w-2 h-2 rounded-full bg-primary shrink-0" />
                )}
                <input
                  value={editedTitle}
                  onChange={(e) => { setEditedTitle(e.target.value); setHasUnsaved(true); }}
                  className="flex-1 bg-transparent text-sm font-medium text-foreground border-none outline-none truncate"
                />
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <Link href={`/agent/editor/${zettel.id}`}>
                  <Button variant="ghost" size="icon" className="h-7 w-7">
                    <Expand className="h-3.5 w-3.5" />
                  </Button>
                </Link>
                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleClose}>
                  <X className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>

            {/* Metadata */}
            <div className="px-4 py-2 border-b flex items-center gap-2">
              {zettel.topic && (
                <span className="font-mono text-[10px] uppercase tracking-wider text-primary px-1.5 py-0.5 rounded bg-[var(--alfred-accent-subtle)]">
                  {zettel.topic}
                </span>
              )}
              {zettel.tags?.map((tag) => (
                <span key={tag} className="font-mono text-[10px] text-muted-foreground px-1.5 py-0.5 rounded bg-secondary">
                  {tag}
                </span>
              ))}
            </div>

            {/* Editor */}
            <div className="flex-1 overflow-y-auto px-4 py-3">
              <MarkdownNotesEditor
                markdown={zettel.content || ""}
                onMarkdownChange={handleContentChange}
              />
            </div>

            {/* Footer */}
            <div className="border-t px-4 py-2 flex justify-end">
              <Button
                size="sm"
                onClick={handleSave}
                disabled={!hasUnsaved || saving}
              >
                {saving ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
                ) : (
                  <Save className="h-3.5 w-3.5 mr-1" />
                )}
                Save
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
            Zettel not found
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
