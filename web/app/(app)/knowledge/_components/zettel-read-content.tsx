"use client";

import { MarkdownProse } from "@/components/markdown/markdown-prose";

type Props = {
  title?: string;
  summary: string;
  content: string;
  labelClassName?: string;
  proseClassName?: string;
  summaryLabelClassName?: string;
  contentLabelClassName?: string;
  summarySectionClassName?: string;
  contentSectionClassName?: string;
  summaryProseClassName?: string;
  contentProseClassName?: string;
  emptyStateClassName?: string;
};

export function ZettelReadContent({
  title,
  summary,
  content,
  labelClassName = "mb-2 text-[9px] font-medium tracking-widest text-[var(--alfred-text-tertiary)] uppercase",
  proseClassName = "prose-headings:my-2 prose-h1:text-lg prose-h2:text-base prose-h3:text-sm prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-pre:my-3",
  summaryLabelClassName,
  contentLabelClassName,
  summarySectionClassName,
  contentSectionClassName,
  summaryProseClassName,
  contentProseClassName,
  emptyStateClassName = "text-[12px] text-[var(--alfred-text-tertiary)]",
}: Props) {
  const trimmedSummary = summary.trim();
  const trimmedContent = stripDuplicateHeading(content.trim(), title);
  const showSummary = Boolean(trimmedSummary) && trimmedSummary !== trimmedContent;

  return (
    <>
      {showSummary && (
        <div className={summarySectionClassName}>
          <div className={summaryLabelClassName ?? labelClassName}>Summary</div>
          <MarkdownProse content={trimmedSummary} className={summaryProseClassName ?? proseClassName} />
        </div>
      )}

      <div className={contentSectionClassName}>
        <div className={contentLabelClassName ?? labelClassName}>Content</div>
        {trimmedContent ? (
          <MarkdownProse content={trimmedContent} className={contentProseClassName ?? proseClassName} />
        ) : (
          <p className={emptyStateClassName}>No content yet.</p>
        )}
      </div>
    </>
  );
}

function stripDuplicateHeading(content: string, title?: string): string {
  if (!content || !title?.trim()) {
    return content;
  }

  const match = content.match(/^\s{0,3}#{1,6}\s+(.+?)\s*(?:\r?\n+|$)/);
  if (!match) {
    return content;
  }

  const headingText = normalizeHeading(match[1]);
  const titleText = normalizeHeading(title);

  if (!headingText || headingText !== titleText) {
    return content;
  }

  return content.slice(match[0].length).trimStart();
}

function normalizeHeading(value: string): string {
  return value
    .toLowerCase()
    .replace(/[`*_~]/g, "")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
}
