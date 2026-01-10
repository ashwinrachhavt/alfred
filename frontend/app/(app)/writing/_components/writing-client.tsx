"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { Copy, Feather, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { composeWriting, composeWritingStream, listWritingPresets } from "@/lib/api/writing";
import type { WritingPreset, WritingRequest, WritingResponse } from "@/lib/api/types/writing";
import { copyTextToClipboard } from "@/lib/clipboard";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { JsonViewer } from "@/components/ui/json-viewer";

type StreamMeta = {
  preset?: WritingPreset;
  raw?: unknown;
};

function toTokenString(payload: unknown): string {
  if (typeof payload === "string") return payload;
  if (!payload) return "";
  if (typeof payload === "object") {
    const maybe = (payload as { text?: unknown; token?: unknown }).text ?? (payload as { token?: unknown }).token;
    if (typeof maybe === "string") return maybe;
  }
  return String(payload);
}

export function WritingClient() {
  const [presets, setPresets] = useState<WritingPreset[]>([]);
  const [presetsLoading, setPresetsLoading] = useState(false);

  const [token, setToken] = useState("");
  const [useStream, setUseStream] = useState(false);

  const [intent, setIntent] = useState<NonNullable<WritingRequest["intent"]>>("rewrite");
  const [siteUrl, setSiteUrl] = useState("");
  const [preset, setPreset] = useState<string>("");
  const [instruction, setInstruction] = useState("");
  const [draft, setDraft] = useState("");
  const [selection, setSelection] = useState("");
  const [pageTitle, setPageTitle] = useState("");
  const [pageText, setPageText] = useState("");
  const [temperature, setTemperature] = useState<string>("");
  const [maxChars, setMaxChars] = useState<string>("");

  const [isRunning, setIsRunning] = useState(false);
  const [response, setResponse] = useState<WritingResponse | null>(null);
  const [streamText, setStreamText] = useState("");
  const [streamMeta, setStreamMeta] = useState<StreamMeta | null>(null);
  const [streamRawEvents, setStreamRawEvents] = useState<unknown[]>([]);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    async function load() {
      setPresetsLoading(true);
      try {
        const res = await listWritingPresets();
        setPresets(res);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to load presets.");
      } finally {
        setPresetsLoading(false);
      }
    }
    void load();
  }, []);

  const normalizedToken = token.trim() || null;

  const requestBody = useMemo(() => {
    const body: WritingRequest = {
      intent,
      site_url: siteUrl,
      preset: preset.trim() || null,
      instruction,
      draft,
      selection,
      page_title: pageTitle,
      page_text: pageText,
    };
    const temp = Number(temperature);
    if (temperature.trim() && Number.isFinite(temp)) body.temperature = temp;
    const max = Number(maxChars);
    if (maxChars.trim() && Number.isFinite(max)) body.max_chars = max;
    return body;
  }, [draft, instruction, intent, maxChars, pageText, pageTitle, preset, selection, siteUrl, temperature]);

  async function runNonStreaming() {
    setIsRunning(true);
    setError(null);
    setResponse(null);
    setStreamText("");
    setStreamMeta(null);
    setStreamRawEvents([]);
    try {
      const res = await composeWriting(requestBody, normalizedToken);
      setResponse(res);
      toast.success("Writing ready.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Compose failed.");
    } finally {
      setIsRunning(false);
    }
  }

  async function runStreaming() {
    setIsRunning(true);
    setError(null);
    setResponse(null);
    setStreamText("");
    setStreamMeta(null);
    setStreamRawEvents([]);

    const abort = new AbortController();
    abortRef.current = abort;

    try {
      await composeWritingStream(requestBody, {
        token: normalizedToken,
        signal: abort.signal,
        onMeta: (payload) => {
          setStreamRawEvents((prev) => [...prev, { event: "meta", payload }]);
          if (payload && typeof payload === "object") {
            const maybePreset = (payload as { preset?: unknown }).preset;
            if (maybePreset && typeof maybePreset === "object") {
              setStreamMeta({ preset: maybePreset as WritingPreset, raw: payload });
              return;
            }
          }
          setStreamMeta({ raw: payload });
        },
        onToken: (payload) => {
          setStreamRawEvents((prev) => [...prev, { event: "token", payload }]);
          setStreamText((prev) => prev + toTokenString(payload));
        },
        onDone: (payload) => {
          setStreamRawEvents((prev) => [...prev, { event: "done", payload }]);
          toast.success("Stream complete.");
        },
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Streaming failed.");
    } finally {
      setIsRunning(false);
      abortRef.current = null;
    }
  }

  async function run() {
    if (useStream) return runStreaming();
    return runNonStreaming();
  }

  const output = response?.output ?? streamText;
  const presetUsed = response?.preset_used ?? streamMeta?.preset ?? null;

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex items-center gap-2">
          <Feather className="text-muted-foreground h-5 w-5" aria-hidden="true" />
          <h1 className="text-3xl font-semibold tracking-tight">Writing</h1>
        </div>
        <p className="text-muted-foreground">Compose, rewrite, reply, and edit — with presets.</p>
      </header>

      <Tabs defaultValue="compose">
        <TabsList>
          <TabsTrigger value="compose">Compose</TabsTrigger>
          <TabsTrigger value="presets">Presets</TabsTrigger>
        </TabsList>

        <TabsContent value="compose" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Request</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="wIntent">Intent</Label>
                  <select
                    id="wIntent"
                    className="bg-background h-10 w-full rounded-md border px-3 text-sm"
                    value={intent}
                    onChange={(e) => setIntent(e.target.value as typeof intent)}
                  >
                    <option value="compose">compose</option>
                    <option value="rewrite">rewrite</option>
                    <option value="reply">reply</option>
                    <option value="edit">edit</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="wSite">Site URL</Label>
                  <Input id="wSite" value={siteUrl} onChange={(e) => setSiteUrl(e.target.value)} />
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="wPreset">Preset (optional)</Label>
                  <select
                    id="wPreset"
                    className="bg-background h-10 w-full rounded-md border px-3 text-sm"
                    value={preset}
                    onChange={(e) => setPreset(e.target.value)}
                    disabled={presetsLoading}
                  >
                    <option value="">Auto</option>
                    {presets.map((p) => (
                      <option key={p.key} value={p.key}>
                        {p.title} ({p.key})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="wToken">X-Alfred-Token (optional)</Label>
                  <Input
                    id="wToken"
                    value={token}
                    onChange={(e) => setToken(e.target.value)}
                    placeholder="If your backend requires a token"
                  />
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="wTemp">Temperature (optional)</Label>
                  <Input
                    id="wTemp"
                    inputMode="decimal"
                    value={temperature}
                    onChange={(e) => setTemperature(e.target.value)}
                    placeholder="e.g. 0.4"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="wMax">Max chars (optional)</Label>
                  <Input
                    id="wMax"
                    inputMode="numeric"
                    value={maxChars}
                    onChange={(e) => setMaxChars(e.target.value)}
                    placeholder="e.g. 280"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="wInstruction">Instruction</Label>
                <Textarea
                  id="wInstruction"
                  value={instruction}
                  onChange={(e) => setInstruction(e.target.value)}
                  rows={3}
                  placeholder='e.g. "Make this clearer and more confident."'
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="wDraft">Draft</Label>
                <Textarea
                  id="wDraft"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  rows={6}
                  placeholder="Paste your text…"
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="wSelection">Selection (optional)</Label>
                  <Textarea
                    id="wSelection"
                    value={selection}
                    onChange={(e) => setSelection(e.target.value)}
                    rows={3}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="wPageTitle">Page title (optional)</Label>
                  <Input
                    id="wPageTitle"
                    value={pageTitle}
                    onChange={(e) => setPageTitle(e.target.value)}
                  />
                  <Label htmlFor="wPageText" className="mt-2 block">
                    Page text (optional)
                  </Label>
                  <Textarea
                    id="wPageText"
                    value={pageText}
                    onChange={(e) => setPageText(e.target.value)}
                    rows={3}
                  />
                </div>
              </div>

              <div className="flex items-center justify-between rounded-lg border p-4">
                <div className="space-y-1">
                  <p className="text-sm font-medium">Stream</p>
                  <p className="text-muted-foreground text-xs">
                    Uses the SSE endpoint for incremental tokens.
                  </p>
                </div>
                <Switch checked={useStream} onCheckedChange={setUseStream} />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button type="button" onClick={() => void run()} disabled={isRunning}>
                  {isRunning ? "Running…" : useStream ? "Stream" : "Compose"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    abortRef.current?.abort();
                    setIsRunning(false);
                    toast.message("Cancelled.");
                  }}
                  disabled={!isRunning}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setResponse(null);
                    setStreamText("");
                    setStreamMeta(null);
                    setStreamRawEvents([]);
                    setError(null);
                  }}
                  disabled={isRunning}
                >
                  <RefreshCw className="h-4 w-4" aria-hidden="true" />
                  Reset
                </Button>
              </div>

              {error ? <p className="text-destructive text-sm">{error}</p> : null}
            </CardContent>
          </Card>

          {presetUsed || output ? (
            <Card>
              <CardHeader>
                <CardTitle>Output</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {presetUsed ? (
                  <p className="text-muted-foreground text-xs">
                    preset: <span className="font-medium">{presetUsed.title}</span> ({presetUsed.key})
                  </p>
                ) : null}
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-sm font-medium">Result</p>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={async () => {
                      try {
                        await copyTextToClipboard(output);
                        toast.success("Copied output.");
                      } catch {
                        toast.error("Failed to copy.");
                      }
                    }}
                    disabled={!output}
                  >
                    <Copy className="h-4 w-4" aria-hidden="true" />
                    Copy
                  </Button>
                </div>
                <Separator />
                <pre className="whitespace-pre-wrap break-words text-sm leading-relaxed">{output || "—"}</pre>
              </CardContent>
            </Card>
          ) : null}

          {response ? <JsonViewer value={response} title="Compose response" collapsed /> : null}
          {useStream && streamRawEvents.length ? (
            <JsonViewer value={streamRawEvents} title="Stream events" collapsed />
          ) : null}
        </TabsContent>

        <TabsContent value="presets" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Available presets</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {presetsLoading ? (
                <p className="text-muted-foreground text-sm">Loading…</p>
              ) : presets.length ? (
                <div className="space-y-2">
                  {presets.map((p) => (
                    <div key={p.key} className="rounded-lg border p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="font-medium">
                            {p.title}{" "}
                            <span className="text-muted-foreground text-xs">({p.key})</span>
                          </p>
                          {p.description ? (
                            <p className="text-muted-foreground mt-1 text-sm">{p.description}</p>
                          ) : null}
                        </div>
                        {typeof p.max_chars === "number" ? (
                          <span className="text-muted-foreground text-xs">max: {p.max_chars}</span>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground text-sm">No presets found.</p>
              )}
            </CardContent>
          </Card>

          {presets.length ? <JsonViewer value={presets} title="Raw presets" collapsed /> : null}
        </TabsContent>
      </Tabs>
    </div>
  );
}

