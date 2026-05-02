/**
 * SSE stream wrappers for the Zettel Workspace (T10).
 *
 * Exposes two async generators that each yield `{event, data}` records so the
 * caller can drive the UI however it likes (setState, dispatch, store action).
 *
 * We bypass Next.js rewrites and hit the backend directly — Next rewrites buffer
 * responses, which breaks SSE (see lib/api/sse.ts for the legacy pattern).
 */
import { apiRoutes } from "@/lib/api/routes";

export type SSEEvent = {
  event: string;
  data: Record<string, unknown>;
};

export type StreamCreationPayload = {
  title: string;
  content: string;
  session_id?: number;
  summary?: string;
  tags?: string[];
  topic?: string;
};

export type StreamDecomposePayload = {
  raw_text: string;
  session_id?: number;
  shared_topic?: string;
  source_url?: string;
};

function directBackendUrl(path: string): string {
  const base =
    process.env.NEXT_PUBLIC_API_URL ||
    (typeof window !== "undefined" ? "http://localhost:8000" : "");
  return `${base}${path}`;
}

async function* streamSSEGenerator(
  url: string,
  body: Record<string, unknown>,
  signal: AbortSignal,
): AsyncGenerator<SSEEvent, void, unknown> {
  const response = await fetch(directBackendUrl(url), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`Stream failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE events are separated by blank lines (\n\n).
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";

    for (const block of blocks) {
      if (!block.trim()) continue;

      let eventType = "";
      let dataPayload = "";

      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          dataPayload = line.slice(6);
        }
      }

      if (!eventType || !dataPayload) continue;

      let parsed: Record<string, unknown> | null = null;
      try {
        parsed = JSON.parse(dataPayload) as Record<string, unknown>;
      } catch {
        parsed = null;
      }
      if (!parsed) continue;

      yield { event: eventType, data: parsed };
    }
  }
}

export function streamCreationEvents(
  payload: StreamCreationPayload,
  signal: AbortSignal,
): AsyncGenerator<SSEEvent, void, unknown> {
  return streamSSEGenerator(
    apiRoutes.zettels.createStream,
    payload as unknown as Record<string, unknown>,
    signal,
  );
}

export function streamDecomposeEvents(
  payload: StreamDecomposePayload,
  signal: AbortSignal,
): AsyncGenerator<SSEEvent, void, unknown> {
  return streamSSEGenerator(
    apiRoutes.zettels.decomposeStream,
    payload as unknown as Record<string, unknown>,
    signal,
  );
}
