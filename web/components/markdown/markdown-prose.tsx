"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

const proseClassName = [
  "prose prose-sm max-w-none dark:prose-invert",
  "prose-headings:font-sans prose-headings:font-semibold prose-headings:tracking-tight",
  "prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg",
  "prose-p:leading-relaxed prose-p:text-foreground",
  "prose-code:rounded-sm prose-code:bg-secondary prose-code:px-1.5 prose-code:py-0.5 prose-code:font-mono prose-code:text-[13px] prose-code:before:content-none prose-code:after:content-none",
  "prose-pre:overflow-x-auto prose-pre:rounded-md prose-pre:bg-secondary prose-pre:font-mono prose-pre:text-[13px] prose-pre:text-foreground",
  "prose-blockquote:rounded-r-md prose-blockquote:border-l-primary prose-blockquote:bg-[var(--alfred-accent-subtle)] prose-blockquote:px-4 prose-blockquote:py-1 prose-blockquote:not-italic",
  "prose-a:text-primary prose-a:no-underline hover:prose-a:underline",
  "prose-li:text-foreground prose-li:marker:text-muted-foreground",
  "prose-strong:font-semibold prose-strong:text-foreground",
  "prose-hr:border-border",
].join(" ");

export function MarkdownProse({ content, className }: { content: string; className?: string }) {
  return (
    <div className={cn(proseClassName, className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
