"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Plus, X } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { apiPostJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

type Props = {
  open: boolean;
  onClose: () => void;
};

export function CreateCardForm({ open, onClose }: Props) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const titleRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  // Focus title input when form opens
  useEffect(() => {
    if (open) {
      // Slight delay to let the DOM paint first
      const t = setTimeout(() => titleRef.current?.focus(), 50);
      return () => clearTimeout(t);
    }
  }, [open]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!title.trim()) return;

      setSubmitting(true);
      setError(null);

      try {
        await apiPostJson(apiRoutes.zettels.cards, {
          title: title.trim(),
          content: content.trim() || undefined,
        });
        await queryClient.invalidateQueries({
          queryKey: ["zettel-graph-extended"],
        });
        setTitle("");
        setContent("");
        onClose();
      } catch (err: any) {
        setError(err.message || "Failed to create card");
      } finally {
        setSubmitting(false);
      }
    },
    [title, content, queryClient, onClose],
  );

  if (!open) return null;

  return (
    <div className="pointer-events-auto absolute right-4 top-4 z-20 w-80">
      <form
        onSubmit={handleSubmit}
        className="rounded-xl border border-white/10 bg-[#1a1918]/95 p-4 shadow-2xl backdrop-blur-sm"
      >
        {/* Header */}
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Plus className="h-3.5 w-3.5 text-[#E8590C]" />
            <span className="font-mono text-[10px] uppercase tracking-wider text-white/50">
              New Card
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-white/30 transition-colors hover:bg-white/5 hover:text-white/60"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Title */}
        <input
          ref={titleRef}
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Card title..."
          className="mb-2 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 font-serif text-sm text-white placeholder:text-white/30 focus:border-[#E8590C]/30 focus:outline-none"
        />

        {/* Content */}
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Content (optional)..."
          rows={4}
          className="mb-3 w-full resize-none rounded-lg border border-white/10 bg-white/5 px-3 py-2 font-sans text-xs leading-relaxed text-white/80 placeholder:text-white/30 focus:border-[#E8590C]/30 focus:outline-none"
        />

        {/* Error */}
        {error && (
          <p className="mb-2 font-mono text-[10px] text-red-400/80">{error}</p>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={submitting || !title.trim()}
          className="w-full rounded-lg bg-[#E8590C]/10 px-4 py-2 font-sans text-xs font-medium text-[#E8590C] transition-colors hover:bg-[#E8590C]/20 disabled:opacity-40 disabled:hover:bg-[#E8590C]/10"
        >
          {submitting ? "Creating..." : "Create Card"}
        </button>
      </form>
    </div>
  );
}
