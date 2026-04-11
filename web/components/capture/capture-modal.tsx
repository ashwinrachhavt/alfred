"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Link2, FileText, ArrowUp, X } from "lucide-react";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { VisuallyHidden } from "@radix-ui/react-visually-hidden";
import { apiPostJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import { useIsApplePlatform } from "@/lib/hooks/use-is-apple-platform";
import { useQueryClient } from "@tanstack/react-query";

type CaptureResponse = {
  id: string;
  status: "accepted" | "duplicate" | "scraping";
  content_type: "url" | "text";
};

const URL_PATTERN = /^https?:\/\/[^\s]+$|^(youtube\.com|arxiv\.org|twitter\.com|x\.com|github\.com|medium\.com|notion\.so|substack\.com|reddit\.com)/i;

function isUrl(text: string): boolean {
  const trimmed = text.trim();
  return URL_PATTERN.test(trimmed) || /^[\w.-]+\.\w{2,}\//.test(trimmed);
}

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function CaptureModal({ open, onOpenChange }: Props) {
  const [content, setContent] = useState("");
  const [tags, setTags] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const queryClient = useQueryClient();
  const isApplePlatform = useIsApplePlatform();

  // Focus on open
  useEffect(() => {
    if (open) {
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  }, [open]);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, window.innerHeight * 0.4)}px`;
  }, [content]);

  const detectedType = content.trim() ? (isUrl(content.trim()) ? "url" : "text") : null;

  const handleSubmit = useCallback(async () => {
    const text = content.trim();
    if (!text || isSubmitting) return;

    setIsSubmitting(true);
    try {
      const tagList = tags
        .split(",")
        .map((t) => t.trim().toLowerCase())
        .filter(Boolean);

      const res = await apiPostJson<CaptureResponse, { content: string; tags?: string[]; source: string }>(
        apiRoutes.capture.ingest,
        {
          content: text,
          tags: tagList.length > 0 ? tagList : undefined,
          source: "web-app",
        },
      );

      if (res.status === "duplicate") {
        toast.info("Already captured", {
          description: "This content was previously captured.",
        });
      } else {
        toast.success("Captured", {
          description: detectedType === "url" ? "URL is being scraped and processed..." : "Processing your content...",
          action: {
            label: "View in Inbox",
            onClick: () => { window.location.href = "/inbox"; },
          },
        });
      }

      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: ["documents"] });

      setContent("");
      setTags("");
      onOpenChange(false);
    } catch (err) {
      toast.error("Capture failed", {
        description: err instanceof Error ? err.message : "Try again",
      });
      // Modal stays open, content preserved
    } finally {
      setIsSubmitting(false);
    }
  }, [content, tags, isSubmitting, detectedType, onOpenChange, queryClient]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[560px] p-0 gap-0 overflow-hidden">
        <VisuallyHidden><DialogTitle>Capture knowledge</DialogTitle></VisuallyHidden>

        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-4 pb-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-muted-foreground">Quick Capture</span>
            {detectedType && (
              <span className="flex items-center gap-1 rounded-full bg-[var(--alfred-accent-subtle)] px-2 py-0.5 text-[10px] font-medium text-primary">
                {detectedType === "url" ? <Link2 className="size-3" /> : <FileText className="size-3" />}
                {detectedType === "url" ? "URL" : "Text"}
              </span>
            )}
          </div>
          <button onClick={() => onOpenChange(false)} className="text-muted-foreground hover:text-foreground transition-colors">
            <X className="size-4" />
          </button>
        </div>

        {/* Main input */}
        <div className="px-5 pb-3">
          <div className="relative rounded-xl border bg-card focus-within:ring-1 focus-within:ring-primary/50 transition-all">
            <textarea
              ref={textareaRef}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Paste a URL, article, thought, or idea..."
              className="w-full resize-none bg-transparent px-4 py-3 text-[14px] leading-relaxed outline-none placeholder:text-muted-foreground/40"
              style={{ minHeight: "100px", maxHeight: "40vh" }}
              rows={3}
            />

            {/* Bottom bar */}
            <div className="flex items-center justify-between px-3 pb-2.5 pt-1">
              <div className="flex items-center gap-2">
                <input
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  placeholder="Tags (optional, comma-separated)"
                  className="w-48 bg-transparent text-[11px] text-muted-foreground outline-none placeholder:text-muted-foreground/30"
                />
              </div>

              <button
                onClick={handleSubmit}
                disabled={!content.trim() || isSubmitting}
                className="flex items-center justify-center size-8 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              >
                {isSubmitting ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <ArrowUp className="size-4" />
                )}
              </button>
            </div>
          </div>

          {/* Hints */}
          <div className="flex items-center justify-between mt-2 px-1">
            <span className="text-[10px] text-muted-foreground/50">
              {detectedType === "url"
                ? "URL detected — will scrape and decompose"
                : "Paste anything — Alfred handles the rest"}
            </span>
            <span className="text-[10px] text-muted-foreground/50">
              {isApplePlatform ? "⌘" : "Ctrl"}+Enter to capture
            </span>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
