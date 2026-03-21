"use client";

import { useState, useMemo } from "react";

import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useExplorerDocuments } from "@/features/documents/queries";

import { InboxDetail } from "./inbox-detail";
import { InboxFilters } from "./inbox-filters";
import { InboxItem } from "./inbox-item";

export function InboxStream() {
  const [activeTab, setActiveTab] = useState("all");
  const [search, setSearch] = useState("");
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);

  const { data, isLoading, hasNextPage, fetchNextPage, isFetchingNextPage } = useExplorerDocuments({
    limit: 24,
    search: search || undefined,
  });

  const items = useMemo(
    () => data?.pages.flatMap((p) => p.items) ?? [],
    [data],
  );

  return (
    <div className="space-y-4">
      <InboxFilters
        activeTab={activeTab}
        onTabChange={setActiveTab}
        search={search}
        onSearchChange={setSearch}
      />

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-lg border bg-muted" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="py-16 text-center">
          <p className="text-muted-foreground">Your knowledge inbox is empty.</p>
          <p className="text-muted-foreground text-sm mt-1">Connect a source or paste a URL to get started.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <InboxItem
              key={item.id}
              id={item.id}
              title={item.title}
              summary={item.summary ?? null}
              sourceUrl={item.source_url ?? null}
              primaryTopic={item.primary_topic ?? null}
              createdAt={item.created_at}
              onClick={() => setSelectedDocId(item.id)}
            />
          ))}
        </div>
      )}

      {hasNextPage && (
        <div className="flex justify-center py-4">
          <Button variant="outline" onClick={() => fetchNextPage()} disabled={isFetchingNextPage}>
            {isFetchingNextPage ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
            Load more
          </Button>
        </div>
      )}

      {selectedDocId && (
        <InboxDetail docId={selectedDocId} onClose={() => setSelectedDocId(null)} />
      )}
    </div>
  );
}
