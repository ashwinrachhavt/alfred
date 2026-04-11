"use client";

import { MarkdownProse } from "@/components/markdown/markdown-prose";

type Props = {
  summary: string;
  content: string;
  labelClassName?: string;
  proseClassName?: string;
  emptyStateClassName?: string;
};

export function ZettelReadContent({
  summary,
  content,
  labelClassName = "mb-2 text-[9px] font-medium tracking-widest text-[var(--alfred-text-tertiary)] uppercase",
  proseClassName = "prose-headings:my-2 prose-h1:text-lg prose-h2:text-base prose-h3:text-sm prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-pre:my-3",
  emptyStateClassName = "text-[12px] text-[var(--alfred-text-tertiary)]",
}: Props) {
  const trimmedSummary = summary.trim();
  const trimmedContent = content.trim();
  const showSummary = Boolean(trimmedSummary) && trimmedSummary !== trimmedContent;

  return (
    <>
      {showSummary && (
        <div>
          <div className={labelClassName}>Summary</div>
          <MarkdownProse content={trimmedSummary} className={proseClassName} />
        </div>
      )}

      <div>
        <div className={labelClassName}>Content</div>
        {trimmedContent ? (
          <MarkdownProse content={trimmedContent} className={proseClassName} />
        ) : (
          <p className={emptyStateClassName}>No content yet.</p>
        )}
      </div>
    </>
  );
}
