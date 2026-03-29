"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ReaderModeProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  sourceUrl?: string;
  summary?: { short?: string; long?: string };
  content: string;
}

export function ReaderMode({
  isOpen,
  onClose,
  title,
  sourceUrl,
  summary,
  content,
}: ReaderModeProps) {
  const [scrollProgress, setScrollProgress] = useState(0);

  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };

    const handleScroll = (e: Event) => {
      const target = e.target as HTMLElement;
      const scrollTop = target.scrollTop;
      const scrollHeight = target.scrollHeight - target.clientHeight;
      const progress = scrollHeight > 0 ? (scrollTop / scrollHeight) * 100 : 0;
      setScrollProgress(progress);
    };

    window.addEventListener("keydown", handleEscape);
    const scrollContainer = document.getElementById("reader-scroll-container");
    scrollContainer?.addEventListener("scroll", handleScroll);

    return () => {
      window.removeEventListener("keydown", handleEscape);
      scrollContainer?.removeEventListener("scroll", handleScroll);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // Format content for reading
  const formattedContent = content
    .split("\n\n")
    .filter((p) => p.trim().length > 0)
    .map((p, i) => (
      <p key={i} className="mb-4">
        {p.trim()}
      </p>
    ));

  return (
    <div className="fixed inset-0 z-50 bg-background">
      {/* Scroll progress bar */}
      <div className="fixed top-0 left-0 right-0 h-1 bg-muted z-50">
        <div
          className="h-full bg-[#E8590C] transition-all duration-150"
          style={{ width: `${scrollProgress}%` }}
        />
      </div>

      {/* Close button */}
      <Button
        variant="ghost"
        size="icon"
        className="fixed top-4 right-4 z-50 size-10 rounded-full bg-background/80 backdrop-blur-sm shadow-lg hover:bg-background"
        onClick={onClose}
      >
        <X className="size-5" />
      </Button>

      {/* Content */}
      <div
        id="reader-scroll-container"
        className="h-full overflow-y-auto px-6 py-12"
      >
        <div className="mx-auto max-w-[680px]">
          {/* Title */}
          <h1 className="mb-4 text-2xl font-semibold tracking-tight leading-tight">
            {title}
          </h1>

          {/* Source URL */}
          {sourceUrl && (
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="mb-6 block text-xs text-muted-foreground hover:text-primary hover:underline"
            >
              {sourceUrl}
            </a>
          )}

          {/* Summary section */}
          {(summary?.short || summary?.long) && (
            <details className="mb-8 rounded-lg bg-muted p-4">
              <summary className="cursor-pointer text-xs font-medium uppercase tracking-wide text-muted-foreground hover:text-foreground">
                Summary
              </summary>
              <div className="mt-3 space-y-3 text-sm leading-relaxed">
                {summary.short && <p>{summary.short}</p>}
                {summary.long && summary.long !== summary.short && (
                  <p className="text-muted-foreground">{summary.long}</p>
                )}
              </div>
            </details>
          )}

          {/* Main content */}
          <div className="prose prose-sm max-w-none text-[17px] leading-[1.8]">
            {formattedContent}
          </div>
        </div>
      </div>
    </div>
  );
}
