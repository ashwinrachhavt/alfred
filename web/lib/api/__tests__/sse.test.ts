import { describe, it, expect, vi, beforeEach } from "vitest";

import { streamSSE } from "../sse";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a ReadableStream that emits SSE-formatted chunks. */
function sseStream(events: Array<{ event: string; data: string }>): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  const lines = events
    .map((e) => `event: ${e.event}\ndata: ${e.data}\n\n`)
    .join("");

  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(lines));
      controller.close();
    },
  });
}

/** Minimal Response-like object returned by our mocked fetch. */
function mockResponse(
  body: ReadableStream<Uint8Array>,
  status = 200,
): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    body,
    headers: new Headers(),
  } as unknown as Response;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("streamSSE", () => {
  it("parses SSE events and fires onEvent with correct event/data", async () => {
    const events = [
      { event: "token", data: JSON.stringify({ content: "Hello" }) },
      { event: "token", data: JSON.stringify({ content: " world" }) },
      { event: "done", data: JSON.stringify({}) },
    ];

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(sseStream(events))),
    );

    const onEvent = vi.fn();
    await streamSSE("/api/agent/stream", { message: "hi" }, onEvent);

    expect(onEvent).toHaveBeenCalledTimes(3);
    expect(onEvent).toHaveBeenNthCalledWith(1, "token", { content: "Hello" });
    expect(onEvent).toHaveBeenNthCalledWith(2, "token", { content: " world" });
    expect(onEvent).toHaveBeenNthCalledWith(3, "done", {});
  });

  it("skips malformed JSON data lines without throwing", async () => {
    const raw =
      "event: token\ndata: {not json!!\n\n" +
      'event: token\ndata: {"content":"ok"}\n\n';

    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(raw));
        controller.close();
      },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(stream)),
    );

    const onEvent = vi.fn();
    await streamSSE("/api/agent/stream", {}, onEvent);

    // Only the valid event should fire
    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onEvent).toHaveBeenCalledWith("token", { content: "ok" });
  });

  it("rejects when aborted via AbortSignal", async () => {
    const controller = new AbortController();
    controller.abort(); // pre-abort

    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new DOMException("Aborted", "AbortError")),
    );

    const onEvent = vi.fn();
    await expect(
      streamSSE("/api/agent/stream", {}, onEvent, controller.signal),
    ).rejects.toThrow("Aborted");

    expect(onEvent).not.toHaveBeenCalled();
  });

  it("throws on non-200 HTTP response", async () => {
    const body = new ReadableStream({
      start(c) {
        c.close();
      },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(body, 500)),
    );

    const onEvent = vi.fn();
    await expect(
      streamSSE("/api/agent/stream", {}, onEvent),
    ).rejects.toThrow("Stream failed: 500");

    expect(onEvent).not.toHaveBeenCalled();
  });

  it("handles chunked delivery split mid-data-line", async () => {
    // When a data line is split across chunks, the parser buffers until it sees
    // a complete event block (terminated by \n\n) before processing.
    const encoder = new TextEncoder();
    // Chunk 1 ends mid-data-line (buffer retains incomplete block)
    const chunk1 = 'event: token\ndata: {"cont';
    // Chunk 2 completes the data line and includes the blank separator
    const chunk2 = 'ent":"split"}\n\nevent: done\ndata: {}\n\n';

    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(chunk1));
        controller.enqueue(encoder.encode(chunk2));
        controller.close();
      },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(stream)),
    );

    const onEvent = vi.fn();
    await streamSSE("/api/agent/stream", {}, onEvent);

    // Both events fire correctly — the parser buffers until it sees
    // a complete event block (terminated by \n\n).
    expect(onEvent).toHaveBeenCalledTimes(2);
    expect(onEvent).toHaveBeenNthCalledWith(1, "token", { content: "split" });
    expect(onEvent).toHaveBeenNthCalledWith(2, "done", {});
  });

  it("handles chunk boundary between event: and data: lines", async () => {
    // The chunk boundary falls exactly between the event: line and the data: line.
    // The parser must buffer until it sees \n\n before processing the event block.
    const encoder = new TextEncoder();
    const chunk1 = "event: thinking\n";
    const chunk2 = 'data: {"content":"deep thought"}\n\n';
    const chunk3 = 'event: done\ndata: {"status":"ok"}\n\n';

    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(chunk1));
        controller.enqueue(encoder.encode(chunk2));
        controller.enqueue(encoder.encode(chunk3));
        controller.close();
      },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(stream)),
    );

    const onEvent = vi.fn();
    await streamSSE("/api/agent/stream", {}, onEvent);

    expect(onEvent).toHaveBeenCalledTimes(2);
    expect(onEvent).toHaveBeenNthCalledWith(1, "thinking", { content: "deep thought" });
    expect(onEvent).toHaveBeenNthCalledWith(2, "done", { status: "ok" });
  });

  it("handles rapid events split across many small chunks", async () => {
    // Each line arrives as its own chunk — worst case for the old line-by-line parser.
    const encoder = new TextEncoder();
    const chunks = [
      "event: token\n",
      'data: {"content":"a"}\n',
      "\n",
      "event: token\n",
      'data: {"content":"b"}\n',
      "\n",
      "event: done\n",
      "data: {}\n",
      "\n",
    ];

    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) {
          controller.enqueue(encoder.encode(chunk));
        }
        controller.close();
      },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(stream)),
    );

    const onEvent = vi.fn();
    await streamSSE("/api/agent/stream", {}, onEvent);

    expect(onEvent).toHaveBeenCalledTimes(3);
    expect(onEvent).toHaveBeenNthCalledWith(1, "token", { content: "a" });
    expect(onEvent).toHaveBeenNthCalledWith(2, "token", { content: "b" });
    expect(onEvent).toHaveBeenNthCalledWith(3, "done", {});
  });

  it("handles chunked delivery when event+data arrive in same read", async () => {
    // Both event: and data: lines must be in the same read() call
    // because eventType resets per iteration of the while loop.
    const encoder = new TextEncoder();
    const chunk1 = 'event: token\ndata: {"content":"hello"}\n\n';
    const chunk2 = 'event: done\ndata: {}\n\n';

    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(chunk1));
        controller.enqueue(encoder.encode(chunk2));
        controller.close();
      },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(stream)),
    );

    const onEvent = vi.fn();
    await streamSSE("/api/agent/stream", {}, onEvent);

    expect(onEvent).toHaveBeenCalledTimes(2);
    expect(onEvent).toHaveBeenNthCalledWith(1, "token", { content: "hello" });
    expect(onEvent).toHaveBeenNthCalledWith(2, "done", {});
  });

  it("sends POST with JSON body to the resolved URL", async () => {
    const stream = sseStream([
      { event: "done", data: JSON.stringify({}) },
    ]);
    const fetchMock = vi.fn().mockResolvedValue(mockResponse(stream));
    vi.stubGlobal("fetch", fetchMock);

    await streamSSE("/api/agent/stream", { message: "hello", model: "gpt-5.4" }, vi.fn());

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/agent/stream");
    expect(init.method).toBe("POST");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({ message: "hello", model: "gpt-5.4" });
  });
});
