"use client";

import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocumentDetails } from "@/features/documents/queries";

type Props = {
  docId: string;
  onClose: () => void;
};

export function InboxDetail({ docId, onClose }: Props) {
  const { data, isLoading } = useDocumentDetails(docId);

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-[50vw] max-w-2xl flex-col border-l bg-background shadow-xl">
      <div className="flex items-center justify-between border-b px-4 py-2">
        <h2 className="truncate text-sm font-semibold">{data?.title ?? "Document"}</h2>
        <Button variant="ghost" size="icon" className="size-7" onClick={onClose}>
          <X className="size-4" />
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        ) : data ? (
          <article className="prose prose-sm dark:prose-invert max-w-none">
            <h1>{data.title}</h1>
            {data.source_url && (
              <p className="text-muted-foreground text-xs">
                Source: <a href={data.source_url} target="_blank" rel="noopener noreferrer">{data.source_url}</a>
              </p>
            )}
            <div className="whitespace-pre-wrap">{data.cleaned_text}</div>
          </article>
        ) : (
          <p className="text-muted-foreground">Document not found.</p>
        )}
      </div>
    </div>
  );
}
