"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import dynamic from "next/dynamic";

import { ArrowLeft, Loader2, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

const MarkdownNotesEditor = dynamic(
  () => import("@/components/editor/markdown-notes-editor").then((mod) => ({ default: mod.MarkdownNotesEditor })),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        Loading editor...
      </div>
    ),
  },
);

type ZettelData = {
  id: number;
  title: string;
  content: string | null;
  topic: string | null;
  tags: string[];
};

export default function ZettelEditorPage() {
  const params = useParams();
  const router = useRouter();
  const zettelId = Number(params.id);

  const [zettel, setZettel] = useState<ZettelData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasUnsaved, setHasUnsaved] = useState(false);
  const [editedContent, setEditedContent] = useState("");
  const [editedTitle, setEditedTitle] = useState("");

  useEffect(() => {
    apiFetch<ZettelData>(apiRoutes.zettels.cardById(zettelId))
      .then((data) => {
        setZettel(data);
        setEditedContent(data.content || "");
        setEditedTitle(data.title);
      })
      .catch(() => setZettel(null))
      .finally(() => setLoading(false));
  }, [zettelId]);

  // Warn on navigate away with unsaved changes
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (hasUnsaved) {
        e.preventDefault();
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [hasUnsaved]);

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
        body: JSON.stringify({ title: editedTitle, content: editedContent }),
      });
      setHasUnsaved(false);
    } catch {
      // TODO: error toast
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-5 w-5 animate-spin text-[var(--text-tertiary)]" />
      </div>
    );
  }

  if (!zettel) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-[var(--text-tertiary)]">
        Zettel not found
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {/* Editor */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex items-center gap-3 px-6 py-3 border-b border-[var(--border)]">
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4" />
          </Button>

          <div className="flex items-center gap-2 flex-1 min-w-0">
            {hasUnsaved && <span className="w-2 h-2 rounded-full bg-[var(--accent)] shrink-0" />}
            <input
              value={editedTitle}
              onChange={(e) => { setEditedTitle(e.target.value); setHasUnsaved(true); }}
              className="flex-1 bg-transparent text-lg font-serif text-[var(--text-primary)] border-none outline-none"
            />
          </div>

          <Button
            variant="default"
            size="sm"
            onClick={handleSave}
            disabled={!hasUnsaved || saving}
            className="bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white"
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <Save className="h-3.5 w-3.5 mr-1" />}
            Save
          </Button>
        </div>

        {/* Metadata */}
        <div className="px-6 py-2 border-b border-[var(--border)] flex items-center gap-2">
          {zettel.topic && (
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--accent)] px-1.5 py-0.5 rounded bg-[var(--accent-subtle)]">
              {zettel.topic}
            </span>
          )}
          {zettel.tags?.map((tag) => (
            <span key={tag} className="font-mono text-[10px] text-[var(--text-tertiary)] px-1.5 py-0.5 rounded bg-[var(--bg-tertiary)]">
              {tag}
            </span>
          ))}
        </div>

        {/* Editor body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 max-w-3xl mx-auto w-full">
          <MarkdownNotesEditor
            markdown={zettel.content || ""}
            onMarkdownChange={handleContentChange}
          />
        </div>
      </div>

      {/* Related knowledge sidebar (placeholder for v2) */}
      <div className="w-72 shrink-0 border-l border-[var(--border)] bg-[var(--bg-secondary)] p-4 overflow-y-auto hidden lg:block">
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--text-tertiary)]">
          Related Knowledge
        </span>
        <p className="text-xs text-[var(--text-tertiary)] mt-4">
          Related cards will appear here as you edit.
        </p>
      </div>
    </div>
  );
}
