"use client";

import { formatDistanceToNow } from "date-fns";

type Props = {
  id: string;
  title: string | null;
  summary: string | null;
  sourceUrl: string | null;
  primaryTopic: string | null;
  createdAt: string;
  onClick: () => void;
};

type StatusInfo = {
  label: string;
  className: string;
};

function getStatus(primaryTopic: string | null, createdAt: string): StatusInfo {
  const ageMs = Date.now() - new Date(createdAt).getTime();
  const hourMs = 60 * 60 * 1000;

  if (ageMs < hourMs) {
    return {
      label: "Processing",
      className: "text-primary bg-[var(--alfred-accent-muted)]",
    };
  }
  if (primaryTopic) {
    return {
      label: "Connected",
      className: "text-[var(--success)] bg-[rgba(45,106,79,0.15)]",
    };
  }
  return {
    label: "Review",
    className: "text-[var(--warning)] bg-[rgba(180,83,9,0.15)]",
  };
}

export function InboxItem({ id: _id, title, summary, sourceUrl: _sourceUrl, primaryTopic, createdAt, onClick }: Props) {
  const timeAgo = formatDistanceToNow(new Date(createdAt), { addSuffix: false });
  const status = getStatus(primaryTopic, createdAt);
  const isRecent = Date.now() - new Date(createdAt).getTime() < 2 * 60 * 60 * 1000;

  return (
    <button
      onClick={onClick}
      className="group flex w-full items-start gap-4 border-b border-[var(--alfred-ruled-line)] px-2 py-4 text-left transition-colors hover:bg-[var(--alfred-accent-subtle)]"
    >
      {/* Dot indicator */}
      <div
        className={`mt-2 size-2 shrink-0 rounded-full ${
          isRecent ? "bg-primary" : "bg-[var(--border)]"
        }`}
      />

      {/* Content */}
      <div className="min-w-0 flex-1">
        <h3 className="truncate font-medium">{title || "Untitled"}</h3>
        {summary && (
          <p className="mt-1 line-clamp-1 text-sm text-muted-foreground">{summary}</p>
        )}
      </div>

      {/* Right side: timestamp + status badge */}
      <div className="flex shrink-0 flex-col items-end gap-2">
        <span className="font-mono text-[11px] text-[var(--alfred-text-tertiary)]">
          {timeAgo} ago
        </span>
        <span
          className={`inline-flex items-center gap-1.5 rounded-sm px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wider ${status.className}`}
        >
          <span className="size-[5px] rounded-full bg-current" />
          {status.label}
        </span>
      </div>
    </button>
  );
}
