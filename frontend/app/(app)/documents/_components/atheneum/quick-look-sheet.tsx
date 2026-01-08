"use client";

import { useMemo } from "react";
import Link from "next/link";

import { ExternalLink } from "lucide-react";
import { toast } from "sonner";

import type { DocumentDetailsResponse } from "@/lib/api/types/documents";
import { enqueueDocumentImage } from "@/lib/api/documents";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useTaskTracker } from "@/features/tasks/task-tracker-provider";

function formatMaybeDate(raw?: string | null): string {
  if (!raw) return "—";
  const date = new Date(raw);
  if (!Number.isNaN(date.getTime())) return date.toLocaleString();
  return raw;
}

function coerceString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function extractSummary(details: DocumentDetailsResponse | null): string | null {
  if (!details?.summary) return null;
  const short = coerceString(details.summary.short);
  if (short) return short;
  const summary = coerceString(details.summary.summary);
  if (summary) return summary;
  return null;
}

export function QuickLookSheet({
  open,
  onOpenChange,
  details,
  loading,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  details: DocumentDetailsResponse | null;
  loading: boolean;
}) {
  const taskTracker = useTaskTracker();
  const title = details?.title?.trim() || "Untitled document";
  const topic = useMemo(() => {
    const primary = details?.topics?.primary as unknown as string | undefined;
    return typeof primary === "string" && primary.trim() ? primary.trim() : null;
  }, [details?.topics]);

  const summary = extractSummary(details);
  const coverUrl = details?.cover_image_url?.trim() || null;
  const contentText = (details?.raw_markdown || details?.cleaned_text || "").trim();

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="sm:max-w-xl overflow-y-auto">
        <SheetHeader>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <SheetTitle className="truncate">{loading ? "Loading…" : title}</SheetTitle>
              <SheetDescription className="truncate">
                {details?.domain || details?.source_url || "—"}
              </SheetDescription>
            </div>
            {topic ? <Badge variant="secondary">{topic}</Badge> : null}
          </div>
        </SheetHeader>

        <div className="space-y-4 pb-6">
          {coverUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={coverUrl}
              alt={title}
              loading="lazy"
              className="w-full rounded-lg border object-cover"
            />
          ) : null}

          <div className="flex flex-wrap gap-2">
            {details?.source_url ? (
              <Button asChild size="sm" variant="outline">
                <a href={details.source_url} target="_blank" rel="noreferrer">
                  <ExternalLink className="h-4 w-4" aria-hidden="true" />
                  Open source
                </a>
              </Button>
            ) : null}
            {details?.id ? (
              <Button asChild size="sm" variant="outline">
                <Link href={`/documents/${details.id}`}>Open reader</Link>
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
            {details?.id ? (
              <Button
                type="button"
                size="sm"
                onClick={async () => {
                  try {
                    const res = await enqueueDocumentImage(details.id, {}, {});
                    if (res.task_id) {
                      taskTracker.trackTask({
                        id: res.task_id,
                        source: "generic",
                        label: "Generating cover image",
                        href: `/documents/${details.id}`,
                      });
                      toast.message("Cover image generation queued.");
                    }
                  } catch (err) {
                    toast.error(err instanceof Error ? err.message : "Failed to queue image generation.");
                  }
                }}
              >
                Generate cover
              </Button>
            ) : null}
          </div>

          <Separator />

          <Tabs defaultValue="summary" className="w-full">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="summary">Summary</TabsTrigger>
              <TabsTrigger value="text">Text</TabsTrigger>
              <TabsTrigger value="meta">Meta</TabsTrigger>
            </TabsList>

            <TabsContent value="summary" className="pt-4">
              {summary ? (
                <div className="space-y-2">
                  <p className="text-sm font-medium">Summary</p>
                  <p className="text-muted-foreground text-sm whitespace-pre-wrap">{summary}</p>
                </div>
              ) : (
                <p className="text-muted-foreground text-sm">{loading ? "Fetching details…" : "No summary yet."}</p>
              )}
            </TabsContent>

            <TabsContent value="text" className="pt-4">
              {contentText ? (
                <div className="prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap">
                  {contentText}
                </div>
              ) : (
                <p className="text-muted-foreground text-sm">{loading ? "Fetching content…" : "No text yet."}</p>
              )}
            </TabsContent>

            <TabsContent value="meta" className="pt-4 space-y-4">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-muted-foreground text-xs">Captured</p>
                  <p className="truncate">{formatMaybeDate(details?.captured_at ?? null)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">Updated</p>
                  <p className="truncate">{formatMaybeDate(details?.updated_at ?? null)}</p>
                </div>
              </div>

              {details?.tags?.length ? (
                <div className="space-y-2">
                  <p className="text-sm font-medium">Tags</p>
                  <div className="flex flex-wrap gap-2">
                    {details.tags.map((tag) => (
                      <Badge key={tag} variant="secondary">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                </div>
              ) : null}
            </TabsContent>
          </Tabs>
        </div>
      </SheetContent>
    </Sheet>
  );
}
