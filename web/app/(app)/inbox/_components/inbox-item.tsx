"use client";

import { formatDistanceToNow } from "date-fns";
import { FileText } from "lucide-react";

import { Badge } from "@/components/ui/badge";

type Props = {
  id: string;
  title: string | null;
  summary: string | null;
  sourceUrl: string | null;
  primaryTopic: string | null;
  createdAt: string;
  onClick: () => void;
};

export function InboxItem({ id: _id, title, summary, sourceUrl: _sourceUrl, primaryTopic, createdAt, onClick }: Props) {
  const timeAgo = formatDistanceToNow(new Date(createdAt), { addSuffix: true });

  return (
    <button
      onClick={onClick}
      className="hover:bg-muted/50 w-full rounded-lg border p-4 text-left transition-colors"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <FileText className="text-muted-foreground mt-0.5 size-5 shrink-0" />
          <div className="min-w-0">
            <h3 className="truncate font-medium">{title || "Untitled"}</h3>
            {summary && (
              <p className="text-muted-foreground mt-1 line-clamp-2 text-sm">{summary}</p>
            )}
            <div className="mt-2 flex items-center gap-2">
              {primaryTopic && <Badge variant="secondary">{primaryTopic}</Badge>}
              <Badge variant="outline">New</Badge>
            </div>
          </div>
        </div>
        <span className="text-muted-foreground shrink-0 text-xs">{timeAgo}</span>
      </div>
    </button>
  );
}
