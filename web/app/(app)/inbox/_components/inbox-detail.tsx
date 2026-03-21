"use client";

import { useEffect } from "react";

import { ExternalLink, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocumentDetails } from "@/features/documents/queries";

type Props = {
  docId: string;
  onClose: () => void;
};

export function InboxDetail({ docId, onClose }: Props) {
  const { data, isLoading } = useDocumentDetails(docId);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40 bg-black/20 backdrop-blur-[2px]" onClick={onClose} />

      {/* Panel */}
      <div className="fixed inset-y-0 right-0 z-50 flex w-[55vw] max-w-2xl flex-col border-l bg-background shadow-2xl animate-in slide-in-from-right duration-200">
        <div className="flex items-center justify-between border-b px-5 py-3">
          <div className="flex items-center gap-3 min-w-0">
            <h2 className="truncate text-sm font-semibold">{data?.title ?? "Document"}</h2>
            {data?.content_type && (
              <Badge variant="secondary" className="shrink-0 text-[10px]">{data.content_type}</Badge>
            )}
          </div>
          <div className="flex items-center gap-1">
            {data?.source_url && (
              <Button variant="ghost" size="icon" className="size-7" asChild>
                <a href={data.source_url} target="_blank" rel="noopener noreferrer" title="Open source">
                  <ExternalLink className="size-3.5" />
                </a>
              </Button>
            )}
            <Button variant="ghost" size="icon" className="size-7" onClick={onClose}>
              <X className="size-4" />
            </Button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-8 w-3/4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-2/3" />
            </div>
          ) : data ? (
            <article className="prose prose-sm dark:prose-invert max-w-none">
              {data.source_url && (
                <p className="text-muted-foreground not-prose mb-4 flex items-center gap-2 text-xs">
                  <span className="truncate">{data.source_url}</span>
                </p>
              )}
              <div className="whitespace-pre-wrap leading-relaxed">{data.cleaned_text}</div>
              {data.topics && (
                <div className="not-prose mt-6 flex flex-wrap gap-1.5">
                  {Object.values(data.topics).flat().filter(Boolean).map((t: string) => (
                    <Badge key={t} variant="outline" className="text-[10px]">{t}</Badge>
                  ))}
                </div>
              )}
            </article>
          ) : (
            <p className="text-muted-foreground">Document not found.</p>
          )}
        </div>
      </div>
    </>
  );
}
