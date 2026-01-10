"use client";

import { useState } from "react";

import { Globe, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { webSearch } from "@/lib/api/web";
import { wikipediaSearch } from "@/lib/api/wikipedia";
import type { WebSearchResponse } from "@/lib/api/types/web";
import type { WikipediaSearchResponse } from "@/lib/api/types/wikipedia";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { JsonViewer } from "@/components/ui/json-viewer";

export function WebClient() {
  const [webQuery, setWebQuery] = useState("");
  const [searxK, setSearxK] = useState(10);
  const [webResult, setWebResult] = useState<WebSearchResponse | null>(null);
  const [webLoading, setWebLoading] = useState(false);

  const [wikiQuery, setWikiQuery] = useState("");
  const [wikiLang, setWikiLang] = useState("en");
  const [wikiTopK, setWikiTopK] = useState(3);
  const [wikiResult, setWikiResult] = useState<WikipediaSearchResponse | null>(null);
  const [wikiLoading, setWikiLoading] = useState(false);

  async function runWeb() {
    const q = webQuery.trim();
    if (!q) return;
    setWebLoading(true);
    try {
      const res = await webSearch({ q, searx_k: Math.max(1, Math.min(100, searxK)) });
      setWebResult(res);
      toast.success("Search complete.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Search failed.");
    } finally {
      setWebLoading(false);
    }
  }

  async function runWiki() {
    const q = wikiQuery.trim();
    if (!q) return;
    setWikiLoading(true);
    try {
      const res = await wikipediaSearch({
        q,
        lang: wikiLang.trim() || "en",
        top_k_results: Math.max(1, Math.min(50, wikiTopK)),
      });
      setWikiResult(res);
      toast.success("Wikipedia results ready.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Wikipedia search failed.");
    } finally {
      setWikiLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex items-center gap-2">
          <Globe className="text-muted-foreground h-5 w-5" aria-hidden="true" />
          <h1 className="text-3xl font-semibold tracking-tight">Web</h1>
        </div>
        <p className="text-muted-foreground">Search utilities used by research workflows.</p>
      </header>

      <Tabs defaultValue="search">
        <TabsList>
          <TabsTrigger value="search">Web search</TabsTrigger>
          <TabsTrigger value="wikipedia">Wikipedia</TabsTrigger>
        </TabsList>

        <TabsContent value="search" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Search</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-[1fr_140px_auto] sm:items-end">
                <div className="space-y-2">
                  <Label htmlFor="webQ">Query</Label>
                  <Input
                    id="webQ"
                    value={webQuery}
                    onChange={(e) => setWebQuery(e.target.value)}
                    placeholder="e.g. Alfred knowledge management"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="searxK">Top-k</Label>
                  <Input
                    id="searxK"
                    inputMode="numeric"
                    value={String(searxK)}
                    onChange={(e) => setSearxK(Number(e.target.value))}
                  />
                </div>
                <Button type="button" onClick={() => void runWeb()} disabled={webLoading || !webQuery.trim()}>
                  {webLoading ? "Searching…" : "Search"}
                </Button>
              </div>

              {webResult ? <JsonViewer value={webResult} title="Web search response" /> : null}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="wikipedia" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Wikipedia search</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-[1fr_120px_120px_auto] sm:items-end">
                <div className="space-y-2">
                  <Label htmlFor="wikiQ">Query</Label>
                  <Input
                    id="wikiQ"
                    value={wikiQuery}
                    onChange={(e) => setWikiQuery(e.target.value)}
                    placeholder="e.g. Zettelkasten"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="wikiLang">Lang</Label>
                  <Input
                    id="wikiLang"
                    value={wikiLang}
                    onChange={(e) => setWikiLang(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="wikiTopK">Top-k</Label>
                  <Input
                    id="wikiTopK"
                    inputMode="numeric"
                    value={String(wikiTopK)}
                    onChange={(e) => setWikiTopK(Number(e.target.value))}
                  />
                </div>
                <Button type="button" onClick={() => void runWiki()} disabled={wikiLoading || !wikiQuery.trim()}>
                  {wikiLoading ? "Searching…" : "Search"}
                </Button>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setWebQuery("");
                    setWebResult(null);
                    setWikiQuery("");
                    setWikiResult(null);
                  }}
                >
                  <RefreshCw className="h-4 w-4" aria-hidden="true" />
                  Reset
                </Button>
              </div>

              {wikiResult ? <JsonViewer value={wikiResult} title="Wikipedia response" /> : null}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

