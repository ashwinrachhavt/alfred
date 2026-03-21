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
        <div className="flex flex-col items-center py-20 text-center">
          <div className="mb-6 flex size-16 items-center justify-center rounded-full bg-muted">
            <svg className="size-8 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
            </svg>
          </div>
          <h3 className="text-foreground text-lg font-medium">Your knowledge inbox is empty</h3>
          <p className="text-muted-foreground mt-2 max-w-sm text-sm">
            Connect a source like Readwise, Notion, or RSS — or paste a URL to start building your knowledge base.
          </p>
          <Button className="mt-6" variant="default" onClick={() => {
            const { openToolPanel } = require("@/lib/stores/shell-store").useShellStore.getState();
            openToolPanel("connectors");
          }}>
            Connect Sources
          </Button>
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
