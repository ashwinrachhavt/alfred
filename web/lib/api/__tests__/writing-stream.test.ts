import { beforeEach, describe, expect, it, vi } from "vitest";

import { streamWritingCompose } from "../writing-stream";

function sseStream(raw: string): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();

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
  it("streams raw token chunks from the writing SSE endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          mockResponse(
            sseStream(
              'event: meta\ndata: {"preset":{"key":"notion"}}\n\n' +
                "event: token\ndata: Hello\n\n" +
                "event: token\ndata: world\n\n" +
                "event: done\ndata: \n\n",
            ),
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
    expect(onToken).toHaveBeenNthCalledWith(2, "world");
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("surfaces writer errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(mockResponse(sseStream("event: error\ndata: Model unavailable\n\n"))),
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
    const fetchMock = vi.fn().mockResolvedValue(mockResponse(sseStream("event: done\ndata: \n\n")));
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
});
