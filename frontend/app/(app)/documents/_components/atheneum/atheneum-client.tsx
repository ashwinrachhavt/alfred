"use client";

import { useMemo, useState } from "react";

import dynamic from "next/dynamic";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { useDocumentDetails, useExplorerDocuments } from "@/features/documents/queries";

import { QuickLookSheet } from "./quick-look-sheet";
import { ShelfView } from "./shelf-view";

type AtheneumView = "shelf" | "galaxy" | "stream";

const GalaxyView = dynamic(
  () => import("./galaxy-view").then((mod) => mod.GalaxyView),
  {
    ssr: false,
    loading: () => (
      <div className="text-muted-foreground rounded-xl border p-6 text-sm">
        Loading the semantic galaxy…
      </div>
    ),
  },
);

export function AtheneumClient() {
  const [view, setView] = useState<AtheneumView>("shelf");
  const [search, setSearch] = useState("");
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);

  const docsQuery = useExplorerDocuments({ limit: 24, search });
  const detailsQuery = useDocumentDetails(selectedDocumentId);

  const items = useMemo(() => {
    const pages = docsQuery.data?.pages ?? [];
    return pages.flatMap((page) => page.items);
  }, [docsQuery.data?.pages]);

  const loading = docsQuery.isLoading || (docsQuery.isFetching && !docsQuery.data);
  const errorMessage =
    docsQuery.isError && docsQuery.error instanceof Error ? docsQuery.error.message : null;

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">The Atheneum</h1>
            <p className="text-muted-foreground">
              Explore your captured knowledge through multiple lenses.
            </p>
          </div>
          <Badge variant="secondary">Alpha</Badge>
        </div>
      </header>

      <Tabs value={view} onValueChange={(v) => setView(v as AtheneumView)}>
        <TabsList>
          <TabsTrigger value="shelf">Shelf</TabsTrigger>
          <TabsTrigger value="galaxy">Galaxy</TabsTrigger>
          <TabsTrigger value="stream">Stream</TabsTrigger>
        </TabsList>

        <TabsContent value="shelf" className="pt-4">
          <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search your library…"
              className="sm:max-w-sm"
            />
            {docsQuery.hasNextPage ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => docsQuery.fetchNextPage()}
                disabled={docsQuery.isFetchingNextPage}
              >
                {docsQuery.isFetchingNextPage ? "Loading…" : "Load more"}
              </Button>
            ) : null}
          </div>
          <ShelfView
            items={items}
            loading={loading}
            errorMessage={errorMessage}
            onRetry={() => docsQuery.refetch()}
            onSelect={setSelectedDocumentId}
          />
        </TabsContent>

        <TabsContent value="galaxy" className="pt-4">
          {view === "galaxy" ? <GalaxyView active onOpenDocument={setSelectedDocumentId} /> : null}
        </TabsContent>

        <TabsContent value="stream" className="pt-4">
          <div className="text-muted-foreground text-sm">
            Stream view planned (timeline + reading velocity).
          </div>
        </TabsContent>
      </Tabs>

      <QuickLookSheet
        open={Boolean(selectedDocumentId)}
        onOpenChange={(open) => {
          if (!open) setSelectedDocumentId(null);
        }}
        details={detailsQuery.data ?? null}
        loading={detailsQuery.isLoading || detailsQuery.isFetching}
      />
    </div>
  );
}
