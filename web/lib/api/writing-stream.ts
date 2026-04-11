import { apiRoutes } from "@/lib/api/routes";

export type StreamWritingOptions = {
  intent: "compose" | "rewrite" | "reply" | "edit";
  instruction: string;
  draft?: string;
  selection?: string;
  pageTitle?: string;
  pageText?: string;
  preset?: string;
  siteUrl?: string;
  threadId?: string;
  signal?: AbortSignal;
  onToken: (token: string) => void;
  onComplete: () => void;
  onError: (error: Error) => void;
};

function directBackendUrl(path: string): string {
  const base =
    process.env.NEXT_PUBLIC_API_URL ||
    (typeof window !== "undefined" ? "http://localhost:8000" : "");
  return `${base}${path}`;
}

export async function streamWritingCompose(opts: StreamWritingOptions): Promise<void> {
  const {
    intent,
    instruction,
    draft = "",
    selection = "",
    pageTitle = "",
    pageText = "",
    preset = "notion",
    siteUrl = "",
    threadId,
    signal,
    onToken,
    onComplete,
    onError,
  } = opts;

  try {
    const response = await fetch(directBackendUrl(apiRoutes.writing.composeStream), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        intent,
        instruction,
        draft,
        selection,
        page_title: pageTitle,
        page_text: pageText,
        preset,
        site_url: siteUrl,
        thread_id: threadId,
      }),
      signal,
    });

    if (!response.ok || !response.body) {
      throw new Error(`Writer stream failed: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let eventType = "";
    let dataLines: string[] = [];

    const flushEvent = () => {
      if (!eventType) return;
      const data = dataLines.join("\n");

      if (eventType === "token" && data) {
        onToken(data);
      } else if (eventType === "error") {
        onError(new Error(data || "Writing failed"));
      } else if (eventType === "done") {
        onComplete();
      }

      eventType = "";
      dataLines = [];
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        flushEvent();
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const rawLine of lines) {
        const line = rawLine.replace(/\r$/, "");
        if (line.startsWith("event: ")) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          dataLines.push(line.slice(6));
        } else if (line === "") {
          flushEvent();
        }
      }
    }
  } catch (err) {
    if (signal?.aborted) return;
    onError(err instanceof Error ? err : new Error("Writing failed"));
  }
}
