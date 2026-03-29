"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

/**
 * Renders markdown content with the same Literary Terminal prose styling
 * used in the Notes editor (MarkdownNotesEditor). This ensures assistant
 * messages in the agent chat look identical to edited content.
 *
 * Uses the same Tailwind prose classes as markdown-notes-editor.tsx:258-276
 */
export function MarkdownMessage({
  content,
  className,
}: {
  content: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "prose prose-sm dark:prose-invert max-w-none",
        // Headings: Instrument Serif (matches Notes editor)
        "prose-headings:font-serif prose-headings:tracking-tight prose-headings:font-normal",
        "prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg",
        // Body: DM Sans
        "prose-p:leading-relaxed prose-p:text-foreground",
        // Code: JetBrains Mono
        "prose-code:font-mono prose-code:text-[13px] prose-code:bg-secondary prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-sm prose-code:before:content-none prose-code:after:content-none",
        "prose-pre:bg-secondary prose-pre:text-foreground prose-pre:font-mono prose-pre:text-[13px] prose-pre:rounded-md",
        // Blockquote: accent left border
        "prose-blockquote:border-l-primary prose-blockquote:bg-[var(--alfred-accent-subtle)] prose-blockquote:py-1 prose-blockquote:px-4 prose-blockquote:not-italic prose-blockquote:rounded-r-md",
        // Links: accent color
        "prose-a:text-primary prose-a:no-underline hover:prose-a:underline",
        // Lists
        "prose-li:text-foreground prose-li:marker:text-muted-foreground",
        // Strong
        "prose-strong:font-semibold prose-strong:text-foreground",
        // HR
        "prose-hr:border-border",
        className,
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
