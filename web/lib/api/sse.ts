/**
 * Resolve the direct backend URL for SSE streaming.
 * Next.js rewrites buffer responses, which breaks SSE.
 * We need to hit the backend directly for streaming endpoints.
 */
function directBackendUrl(path: string): string {
  // In the browser, use env var or default to localhost:8000
  const base = process.env.NEXT_PUBLIC_API_URL
    || (typeof window !== "undefined" ? "http://localhost:8000" : "");
  // The path comes in as "/api/agent/stream" — backend mounts at "/api/*"
  return `${base}${path}`;
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
      let dataPayload = "";

      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          dataPayload = line.slice(6);
        }
      }

      if (eventType && dataPayload) {
        try {
          const data = JSON.parse(dataPayload);
          onEvent(eventType, data);
        } catch {
          // Skip malformed JSON
        }
      }
    }
  }
}
