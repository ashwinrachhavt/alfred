/**
 * Resolve the direct backend URL for SSE streaming.
 * Next.js rewrites buffer responses, which breaks SSE.
 * We need to hit the backend directly for streaming endpoints.
 */
function directBackendUrl(path: string): string {
  // In the browser, use env var or default to localhost:8000
  const base =
    process.env.NEXT_PUBLIC_API_URL ||
    (typeof window !== "undefined" ? "http://localhost:8000" : "");
  // The path comes in as "/api/agent/stream" — backend mounts at "/api/*"
  return `${base}${path}`;
}

async function readSSE(
  response: Response,
  onEvent: (event: string, data: Record<string, unknown>) => void,
): Promise<void> {
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
    // Only process complete event blocks; keep the trailing incomplete block in the buffer.
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";

    for (const block of blocks) {
      if (!block.trim()) continue;

      let eventType = "";
      const dataLines: string[] = [];

      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) {
          eventType = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).trimStart());
        }
      }

      const dataPayload = dataLines.join("\n");
      if (dataPayload) {
        try {
          const data = JSON.parse(dataPayload);
          const resolvedEvent =
            eventType ||
            (data && typeof data.type === "string" ? data.type : "");
          if (resolvedEvent) onEvent(resolvedEvent, data);
        } catch {
          // Skip malformed JSON
        }
      }
    }
  }
}

/**
 * Stream Server-Sent Events from a POST endpoint.
 * Handles buffer parsing, event extraction, JSON parsing.
 * Calls the backend directly (bypasses Next.js rewrites to avoid buffering).
 */
export async function streamSSE(
  url: string,
  body: Record<string, unknown>,
  onEvent: (event: string, data: Record<string, unknown>) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resolvedUrl = directBackendUrl(url);
  const response = await fetch(resolvedUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  await readSSE(response, onEvent);
}

/**
 * Stream Server-Sent Events from a GET endpoint.
 */
export async function streamSSEGet(
  url: string,
  onEvent: (event: string, data: Record<string, unknown>) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resolvedUrl = directBackendUrl(url);
  const response = await fetch(resolvedUrl, {
    method: "GET",
    signal,
  });

  await readSSE(response, onEvent);
}
