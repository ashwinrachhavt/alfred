"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import { ExternalLink, Loader2, RefreshCcw, Save } from "lucide-react";

import type { NotionPageMarkdownResponse, NotionPageSearchResult } from "@/lib/api/types/notion";
import { formatErrorMessage } from "@/lib/utils";
import { useUpdateNotionPageMarkdown } from "@/features/notion/mutations";
import { useNotionPageSearch } from "@/features/notion/queries";
import { MarkdownNotesEditor } from "@/components/editor/markdown-notes-editor";
import { getNotionPageMarkdown } from "@/lib/api/notion";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";

function formatIsoDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const match = iso.match(/^(\d{4}-\d{2}-\d{2})/);
  return match ? match[1] : null;
}

function PageRow({
  page,
  isActive,
  onOpen,
}: {
  page: NotionPageSearchResult;
  isActive: boolean;
  onOpen: (pageId: string) => Promise<boolean>;
}) {
  const lastEdited = formatIsoDate(page.last_edited_time ?? null);

  return (
    <li className="rounded-lg border p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="truncate font-medium">{page.title || "Untitled"}</p>
          <div className="flex flex-wrap gap-2 pt-1">
            {lastEdited ? <Badge variant="outline">edited: {lastEdited}</Badge> : null}
            {isActive ? <Badge variant="secondary">open</Badge> : null}
          </div>
          <p className="text-muted-foreground truncate text-xs">id: {page.page_id}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant={isActive ? "secondary" : "outline"}
            onClick={() => void onOpen(page.page_id)}
          >
            Open
          </Button>
        </div>
      </div>
    </li>
  );
}

export function NotionNotetaker() {
  const [searchInput, setSearchInput] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");

  const [activePageId, setActivePageId] = useState<string | null>(null);
  const [activePage, setActivePage] = useState<NotionPageMarkdownResponse | null>(null);
  const [draftMarkdown, setDraftMarkdown] = useState("");
  const [baselineMarkdown, setBaselineMarkdown] = useState("");
  const [pageError, setPageError] = useState<string | null>(null);
  const [pageIsLoading, setPageIsLoading] = useState(false);

  const searchQuery = useNotionPageSearch({
    q: submittedQuery,
    limit: 25,
    enabled: Boolean(submittedQuery),
  });

  const updateMutation = useUpdateNotionPageMarkdown(activePageId ?? "");

  const pages = useMemo(() => searchQuery.data?.results ?? [], [searchQuery.data?.results]);
  const isDirty = Boolean(activePageId) && draftMarkdown !== baselineMarkdown;

  const openPage = async (pageId: string): Promise<boolean> => {
    setActivePageId(pageId);
    setActivePage(null);
    setDraftMarkdown("");
    setBaselineMarkdown("");
    setPageIsLoading(true);
    setPageError(null);

    try {
      const data = await getNotionPageMarkdown(pageId);
      setActivePage(data);
      setDraftMarkdown(data.markdown ?? "");
      setBaselineMarkdown(data.markdown ?? "");
      return true;
    } catch (err) {
      const msg = formatErrorMessage(err);
      setPageError(msg);
      toast.error(msg);
      return false;
    } finally {
      setPageIsLoading(false);
    }
  };

  const handleSearch = () => {
    const q = searchInput.trim();
    setSubmittedQuery(q);
    if (!q) {
      toast.message("Type a search query to find pages.");
    }
  };

  const saveToNotion = async () => {
    if (!activePageId) return;
    if (!activePage) return;

    try {
      await updateMutation.mutateAsync({ markdown: draftMarkdown, mode: "replace" });
      setBaselineMarkdown(draftMarkdown);
      toast.success("Saved to Notion.");
    } catch (err) {
      toast.error(formatErrorMessage(err));
    }
  };

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <h2 className="text-xl font-semibold">Notetaker</h2>
        <p className="text-muted-foreground text-sm">
          Search a Notion page, edit it as markdown with AI, and save back to Notion.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Find a page</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                handleSearch();
              }}
            >
              <Input
                placeholder="Search Notion…"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
              />
              <Button type="submit" variant="secondary" disabled={searchQuery.isFetching}>
                {searchQuery.isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : "Search"}
              </Button>
            </form>

            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">{searchQuery.isFetching ? "Searching…" : "Ready"}</Badge>
              <Badge variant="outline">results: {pages.length}</Badge>
            </div>

            {searchQuery.isError ? (
              <Alert variant="destructive">
                <AlertDescription className="text-destructive">
                  {formatErrorMessage(searchQuery.error)}
                </AlertDescription>
              </Alert>
            ) : null}

            <Separator />

            {pages.length ? (
              <ul className="max-h-[520px] space-y-3 overflow-y-auto pr-1">
                {pages.map((p) => (
                  <PageRow key={p.page_id} page={p} isActive={p.page_id === activePageId} onOpen={openPage} />
                ))}
              </ul>
            ) : (
              <p className="text-muted-foreground text-sm">
                Search for a page title. Make sure the page is shared with your Notion integration.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0 space-y-1">
                <CardTitle className="truncate">{activePage?.title ?? "Editor"}</CardTitle>
                {activePage?.page_id ? (
                  <p className="text-muted-foreground truncate text-xs">page_id: {activePage.page_id}</p>
                ) : (
                  <p className="text-muted-foreground text-xs">
                    Open a page from the left to start editing.
                  </p>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {activePageId ? (
                  <Badge variant={isDirty ? "secondary" : "outline"}>{isDirty ? "Unsaved" : "Saved"}</Badge>
                ) : null}
                {activePage?.url ? (
                  <Button asChild size="sm" variant="outline">
                    <a href={activePage.url} target="_blank" rel="noreferrer">
                      <ExternalLink className="mr-2 h-4 w-4" />
                      Open in Notion
                    </a>
                  </Button>
                ) : null}
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={async () => {
                    if (!activePageId) return;
                    if (isDirty) {
                      const ok = window.confirm("Discard unsaved changes and reload from Notion?");
                      if (!ok) return;
                    }
                    const ok = await openPage(activePageId);
                    if (ok) {
                      toast.success("Reloaded from Notion.");
                    }
                  }}
                  disabled={!activePageId || pageIsLoading}
                >
                  {pageIsLoading ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCcw className="mr-2 h-4 w-4" />
                  )}
                  Reload
                </Button>
                <Button
                  type="button"
                  size="sm"
                  onClick={() => void saveToNotion()}
                  disabled={!activePageId || updateMutation.isPending || !isDirty}
                >
                  {updateMutation.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Save className="mr-2 h-4 w-4" />
                  )}
                  Save
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {pageError ? (
              <Alert variant="destructive">
                <AlertDescription className="text-destructive">{pageError}</AlertDescription>
              </Alert>
            ) : null}

            <MarkdownNotesEditor
              markdown={draftMarkdown}
              onMarkdownChange={setDraftMarkdown}
              readOnly={!activePageId || !activePage || pageIsLoading}
              placeholder="Write… (Select text for AI)"
              className="min-h-[520px]"
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
