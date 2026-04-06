"use client";

import { memo } from "react";
import { formatDistanceToNow } from "date-fns";
import { Loader2 } from "lucide-react";

type Props = {
 id: string;
 title: string | null;
 summary: string | null;
 sourceUrl: string | null;
 primaryTopic: string | null;
 pipelineStatus: string;
 createdAt: string;
 onClick: () => void;
};

type StatusInfo = {
 label: string;
 className: string;
 spinning?: boolean;
};

function getStatus(pipelineStatus: string, primaryTopic: string | null): StatusInfo {
 if (pipelineStatus === "pending") {
 return {
 label: "Queued",
 className: "text-primary bg-[var(--alfred-accent-muted)]",
 spinning: true,
 };
 }
 if (pipelineStatus === "processing") {
 return {
 label: "Processing",
 className: "text-primary bg-[var(--alfred-accent-muted)]",
 spinning: true,
 };
 }
 if (pipelineStatus === "error") {
 return {
 label: "Error",
 className: "text-destructive bg-destructive/15",
 };
 }
 if (primaryTopic) {
 return {
 label: "Connected",
 className: "text-[var(--success)] bg-[rgba(45,106,79,0.15)]",
 };
 }
 return {
 label: "Complete",
 className: "text-muted-foreground bg-muted/50",
 };
}

export const InboxItem = memo(function InboxItem({ id: _id, title, summary, sourceUrl: _sourceUrl, primaryTopic, pipelineStatus, createdAt, onClick }: Props) {
 const timeAgo = formatDistanceToNow(new Date(createdAt), { addSuffix: false });
 const status = getStatus(pipelineStatus, primaryTopic);
 const isRecent = pipelineStatus === "pending" || pipelineStatus === "processing";

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
 <span className="text-[11px] text-[var(--alfred-text-tertiary)]">
 {timeAgo} ago
 </span>
 <span
 className={`inline-flex items-center gap-1.5 rounded-sm px-2.5 py-0.5 font-medium text-[10px] uppercase tracking-wider ${status.className}`}
 >
 {status.spinning ? (
 <Loader2 className="size-3 animate-spin" />
 ) : (
 <span className="size-[5px] rounded-full bg-current" />
 )}
 {status.label}
 </span>
 </div>
 </button>
 );
});
