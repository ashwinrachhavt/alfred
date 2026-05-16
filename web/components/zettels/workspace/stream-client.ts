/**
 * SSE stream wrappers for the Zettel Workspace (T10).
 *
 * Exposes two async generators that each yield `{event, data}` records so the
 * caller can drive the UI however it likes (setState, dispatch, store action).
 *
 * Uses the shared SSE helper so workspace streams follow the same AG-UI +
 * legacy fallback behavior as the main agent chat.
 */
import { apiRoutes } from "@/lib/api/routes";
import { streamSSE } from "@/lib/api/sse";
import { createAguiEventProjector } from "@/lib/streaming/agui-runtime";

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

async function* streamSSEGenerator(
  urls: string[],
  body: Record<string, unknown>,
  signal: AbortSignal,
): AsyncGenerator<SSEEvent, void, unknown> {
  const projector = createAguiEventProjector();
  const queue: SSEEvent[] = [];
  const wakeups: Array<() => void> = [];
  let done = false;
  let error: unknown = null;

  function wake() {
    while (wakeups.length > 0) wakeups.shift()?.();
  }

  function push(event: string, data: Record<string, unknown>) {
    for (const projected of projector.project(event, data)) {
      queue.push(projected);
    }
    wake();
  }

  const pump = (async () => {
    try {
      for (const url of urls) {
        try {
          await streamSSE(url, body, push, signal);
          return;
        } catch (err) {
          const canFallback =
            err instanceof Error &&
            /Stream failed:\s*404/.test(err.message) &&
            url !== urls[urls.length - 1];
          if (!canFallback) throw err;
        }
      }
    } catch (err) {
      error = err;
    } finally {
      done = true;
      wake();
    }
  })();

  while (!done || queue.length > 0) {
    if (queue.length === 0) {
      await new Promise<void>((resolve) => wakeups.push(resolve));
      continue;
    }
    const next = queue.shift();
    if (next) yield next;
  }

  await pump;
  if (error) throw error;
}

export function streamCreationEvents(
  payload: StreamCreationPayload,
  signal: AbortSignal,
): AsyncGenerator<SSEEvent, void, unknown> {
  return streamSSEGenerator(
    [apiRoutes.zettels.createStreamV2, apiRoutes.zettels.createStream],
    payload as unknown as Record<string, unknown>,
    signal,
  );
}

export function streamDecomposeEvents(
  payload: StreamDecomposePayload,
  signal: AbortSignal,
): AsyncGenerator<SSEEvent, void, unknown> {
  return streamSSEGenerator(
    [apiRoutes.zettels.decomposeStream],
    payload as unknown as Record<string, unknown>,
    signal,
  );
}
