"use client";

import { MarkdownProse } from "@/components/markdown/markdown-prose";

/**
 * Renders markdown content with the same Literary Terminal prose styling
 * used in the Notes editor (MarkdownNotesEditor). This ensures assistant
 * messages in the agent chat look identical to edited content.
 *
 * Uses the same Tailwind prose classes as markdown-notes-editor.tsx:258-276
 */
export function MarkdownMessage({ content, className }: { content: string; className?: string }) {
  return <MarkdownProse content={content} className={className} />;
}
