import { apiFetch, apiPostJson } from "@/lib/api/client";

import type { WritingPreset, WritingRequest, WritingResponse } from "@/lib/api/types/writing";

export async function listWritingPresets(): Promise<WritingPreset[]> {
  return apiFetch<WritingPreset[]>("/api/writing/presets", { cache: "no-store" });
}

export async function composeWriting(
  body: WritingRequest,
  token?: string | null,
): Promise<WritingResponse> {
  return apiPostJson<WritingResponse, WritingRequest>("/api/writing/compose", body, {
    cache: "no-store",
    headers: token ? { "X-Alfred-Token": token } : undefined,
  });
}

export async function composeWritingStream(
  body: WritingRequest,
  {
    token,
    signal,
    onMeta,
    onToken,
    onDone,
  }: {
    token?: string | null;
    signal?: AbortSignal;
    onMeta?: (payload: unknown) => void;
    onToken?: (payload: unknown) => void;
    onDone?: (payload: unknown) => void;
  },
): Promise<void> {
  const response = await fetch("/api/writing/compose/stream", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(token ? { "X-Alfred-Token": token } : {}),
    },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(text || response.statusText);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("Streaming not supported.");

  const decoder = new TextDecoder();
  let buffer = "";
  const dispatch = (event: string, data: string) => {
    let payload: unknown = data;
    try {
      payload = data ? JSON.parse(data) : data;
    } catch {}

    if (event === "meta") onMeta?.(payload);
    if (event === "token") onToken?.(payload);
    if (event === "done") onDone?.(payload);
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE: split by double newline, parse "event:" and "data:" lines
    let idx = buffer.indexOf("\n\n");
    while (idx !== -1) {
      const raw = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);

      let event = "message";
      const dataLines: string[] = [];
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) event = line.slice("event:".length).trim();
        if (line.startsWith("data:")) dataLines.push(line.slice("data:".length).trimStart());
      }
      dispatch(event, dataLines.join("\n"));

      idx = buffer.indexOf("\n\n");
    }
  }
}

