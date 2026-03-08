"use client";

import Link from "next/link";
import { useMemo } from "react";

import { ArrowLeft, ExternalLink, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { enqueueDocumentImage } from "@/lib/api/documents";

import { useDocumentDetails } from "@/features/documents/queries";
import { useTaskTracker } from "@/features/tasks/task-tracker-provider";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";

import { DocumentEditor } from "./document-editor";

import { extractSummary } from "@/lib/utils/format";

export function DocumentReaderClient({ docId }: { docId: string }) {
  const taskTracker = useTaskTracker();
  const detailsQuery = useDocumentDetails(docId);

  const details = detailsQuery.data ?? null;
  const title = details?.title?.trim() || "Untitled document";
  const coverUrl = details?.cover_image_url?.trim() || null;
  const summary = extractSummary(details);
  const initialMarkdown = useMemo(() => {
    return details?.raw_markdown ?? details?.cleaned_text ?? "";
  }, [details?.cleaned_text, details?.raw_markdown]);

  const topic = useMemo(() => {
    const primary = details?.topics?.primary as unknown as string | undefined;
    return typeof primary === "string" && primary.trim() ? primary.trim() : null;
  }, [details?.topics]);

  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button asChild variant="ghost">
            <Link href="/documents">
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
              Back to library
            </Link>
          </Button>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => detailsQuery.refetch()}
              disabled={detailsQuery.isFetching}
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Refresh
            </Button>

            {details?.source_url ? (
              <Button asChild size="sm" variant="outline">
                <a href={details.source_url} target="_blank" rel="noreferrer">
                  <ExternalLink className="h-4 w-4" aria-hidden="true" />
                  Open source
                </a>
              </Button>
            ) : null}

            {details?.cleaned_text ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(details.cleaned_text);
                    toast.success("Copied document text.");
                  } catch {
                    toast.error("Failed to copy text.");
                  }
                }}
              >
                Copy text
              </Button>
            ) : null}

            <Button
              type="button"
              size="sm"
              onClick={async () => {
                try {
                  const res = await enqueueDocumentImage(docId, {}, {});
                  if (res.task_id) {
                    taskTracker.trackTask({
                      id: res.task_id,
                      source: "generic",
                      label: "Generating cover image",
                      href: `/documents/${docId}`,
                    });
                    toast.message("Cover image generation queued.");
                  }
                } catch (err) {
                  toast.error(
                    err instanceof Error ? err.message : "Failed to queue image generation.",
                  );
                }
              }}
            >
              Generate cover
            </Button>
          </div>
        </div>

        <div className="space-y-1">
          <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
          <p className="text-muted-foreground text-sm">
            {details?.domain || details?.source_url || "—"}
          </p>
        </div>

        {topic ? (
          <div className="flex flex-wrap gap-2">
            <Badge variant="secondary">{topic}</Badge>
            {details?.tags?.slice(0, 6).map((tag) => (
              <Badge key={tag} variant="outline">
                {tag}
              </Badge>
            ))}
          </div>
        ) : details?.tags?.length ? (
          <div className="flex flex-wrap gap-2">
            {details.tags.slice(0, 8).map((tag) => (
              <Badge key={tag} variant="secondary">
                {tag}
              </Badge>
            ))}
          </div>
        ) : null}
      </header>

      {detailsQuery.isError ? (
        <div className="text-sm">
          <p className="font-medium">Failed to load document.</p>
          <p className="text-muted-foreground">
            {detailsQuery.error instanceof Error ? detailsQuery.error.message : "Unknown error"}
          </p>
        </div>
      ) : null}

      {detailsQuery.isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-56 w-full" />
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
        </div>
      ) : (
        <div className="space-y-6">
          {coverUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={coverUrl}
              alt={title}
              loading="lazy"
              className="max-h-[420px] w-full rounded-2xl border object-cover"
            />
          ) : null}

          {summary ? (
            <div className="space-y-2">
              <p className="text-sm font-medium">Summary</p>
              <p className="text-muted-foreground text-sm whitespace-pre-wrap">{summary}</p>
            </div>
          ) : null}

          <Separator />

          <DocumentEditor docId={docId} initialMarkdown={initialMarkdown} />
        </div>
      )}
    </div>
  );
}
