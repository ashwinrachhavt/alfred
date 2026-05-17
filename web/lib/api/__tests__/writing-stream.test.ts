import { beforeEach, describe, expect, it, vi } from "vitest";

import { streamWritingCompose } from "../writing-stream";

/**
 * Build an SSE body containing AG-UI frames.
 *
 * Each frame is rendered in the canonical `id: <seq>\ndata: <json>\n\n` shape
 * matching what `apps/alfred/api/writing/routes.py` emits after the AG-UI
 * migration.
 */
function aguiStream(frames: Array<Record<string, unknown>>): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  const raw = frames
    .map((frame, idx) => `id: ${idx}\ndata: ${JSON.stringify(frame)}\n\n`)
    .join("");

  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(raw));
      controller.close();
    },
  });
}

function mockResponse(body: ReadableStream<Uint8Array>, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    body,
    headers: new Headers(),
  } as unknown as Response;
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("streamWritingCompose", () => {
  it("projects AG-UI text content frames into onToken callbacks", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse(
          aguiStream([
            { type: "RUN_STARTED", runId: "run-1", threadId: null, runType: "writing_compose" },
            { type: "TEXT_MESSAGE_START", messageId: "msg-1", role: "assistant" },
            { type: "TEXT_MESSAGE_CONTENT", messageId: "msg-1", delta: "Hello" },
            { type: "TEXT_MESSAGE_CONTENT", messageId: "msg-1", delta: " world" },
            { type: "TEXT_MESSAGE_END", messageId: "msg-1" },
            { type: "RUN_FINISHED", runId: "run-1", result: {} },
          ]),
        ),
      ),
    );

    const onToken = vi.fn();
    const onComplete = vi.fn();

    await streamWritingCompose({
      intent: "compose",
      instruction: "Write a paragraph",
      onToken,
      onComplete,
      onError: vi.fn(),
    });

    expect(onToken).toHaveBeenNthCalledWith(1, "Hello");
    expect(onToken).toHaveBeenNthCalledWith(2, " world");
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("fires onMessageStart and onMessageEnd at message boundaries", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse(
          aguiStream([
            { type: "RUN_STARTED", runId: "run-1", threadId: null, runType: "writing_compose" },
            { type: "TEXT_MESSAGE_START", messageId: "msg-abc", role: "assistant" },
            { type: "TEXT_MESSAGE_CONTENT", messageId: "msg-abc", delta: "ok" },
            { type: "TEXT_MESSAGE_END", messageId: "msg-abc" },
            { type: "RUN_FINISHED", runId: "run-1", result: {} },
          ]),
        ),
      ),
    );

    const onMessageStart = vi.fn();
    const onMessageEnd = vi.fn();

    await streamWritingCompose({
      intent: "compose",
      instruction: "x",
      onToken: vi.fn(),
      onComplete: vi.fn(),
      onError: vi.fn(),
      onMessageStart,
      onMessageEnd,
    });

    expect(onMessageStart).toHaveBeenCalledWith("msg-abc");
    expect(onMessageEnd).toHaveBeenCalledWith("msg-abc");
    // Order matters: start fires before end.
    expect(onMessageStart.mock.invocationCallOrder[0]).toBeLessThan(
      onMessageEnd.mock.invocationCallOrder[0],
    );
  });

  it("surfaces RUN_ERROR as onError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse(
          aguiStream([
            { type: "RUN_STARTED", runId: "run-1", threadId: null, runType: "writing_compose" },
            { type: "RUN_ERROR", message: "Model unavailable", code: "ModelError" },
          ]),
        ),
      ),
    );

    const onError = vi.fn();

    await streamWritingCompose({
      intent: "edit",
      instruction: "Rewrite this",
      onToken: vi.fn(),
      onComplete: vi.fn(),
      onError,
    });

    expect(onError).toHaveBeenCalledWith(new Error("Model unavailable"));
  });

  it("posts the writing payload to the compose stream endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      mockResponse(
        aguiStream([
          { type: "RUN_STARTED", runId: "run-1", threadId: null, runType: "writing_compose" },
          { type: "RUN_FINISHED", runId: "run-1", result: {} },
        ]),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await streamWritingCompose({
      intent: "edit",
      instruction: "Make this tighter",
      draft: "Draft text",
      selection: "selected",
      pageTitle: "Thinking about systems",
      pageText: "Context excerpt",
      preset: "notion",
      threadId: "note-inline-1",
      onToken: vi.fn(),
      onComplete: vi.fn(),
      onError: vi.fn(),
    });

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/writing/compose/stream");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      intent: "edit",
      instruction: "Make this tighter",
      draft: "Draft text",
      selection: "selected",
      page_title: "Thinking about systems",
      page_text: "Context excerpt",
      preset: "notion",
      site_url: "",
      thread_id: "note-inline-1",
    });
  });

  it("falls back to onComplete on clean EOF without RUN_FINISHED", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse(
          aguiStream([
            { type: "RUN_STARTED", runId: "run-1", threadId: null, runType: "writing_compose" },
            { type: "TEXT_MESSAGE_START", messageId: "msg-1", role: "assistant" },
            { type: "TEXT_MESSAGE_CONTENT", messageId: "msg-1", delta: "partial" },
            // Stream ends here without TEXT_MESSAGE_END or RUN_FINISHED.
          ]),
        ),
      ),
    );

    const onToken = vi.fn();
    const onComplete = vi.fn();
    const onError = vi.fn();

    await streamWritingCompose({
      intent: "compose",
      instruction: "x",
      onToken,
      onComplete,
      onError,
    });

    expect(onToken).toHaveBeenCalledWith("partial");
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(onError).not.toHaveBeenCalled();
  });
});
