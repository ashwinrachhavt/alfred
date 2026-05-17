import { apiRoutes } from "@/lib/api/routes";
import { streamSSE } from "@/lib/api/sse";
import { createAguiEventProjector } from "@/lib/streaming/agui-runtime";

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
  /** Optional — fires when the AG-UI message frame opens. */
  onMessageStart?: (messageId: string) => void;
  /** Optional — fires when the AG-UI message frame closes. */
  onMessageEnd?: (messageId: string) => void;
};

const MESSAGE_BOUNDARY_EVENTS = new Set(["TEXT_MESSAGE_START", "TEXT_MESSAGE_END"]);

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
    onMessageStart,
    onMessageEnd,
  } = opts;

  const projector = createAguiEventProjector();
  let completed = false;
  let errored = false;

  try {
    await streamSSE(
      apiRoutes.writing.composeStream,
      {
        intent,
        instruction,
        draft,
        selection,
        page_title: pageTitle,
        page_text: pageText,
        preset,
        site_url: siteUrl,
        thread_id: threadId,
      },
      (event, data) => {
        // Capture AG-UI message boundaries before they hit the projector,
        // since the projector intentionally drops them in the legacy mapping.
        if (event === "TEXT_MESSAGE_START") {
          const messageId = String(data.messageId || "");
          if (messageId) onMessageStart?.(messageId);
        } else if (event === "TEXT_MESSAGE_END") {
          const messageId = String(data.messageId || "");
          if (messageId) onMessageEnd?.(messageId);
        }

        // Skip projecting boundary events — they don't map to legacy callbacks.
        if (MESSAGE_BOUNDARY_EVENTS.has(event)) return;

        const projected = projector.project(event, data);
        for (const out of projected) {
          if (out.event === "token") {
            const content = typeof out.data.content === "string" ? out.data.content : "";
            if (content) onToken(content);
          } else if (out.event === "done") {
            completed = true;
            onComplete();
          } else if (out.event === "error") {
            errored = true;
            const message = typeof out.data.message === "string" ? out.data.message : "Writing failed";
            onError(new Error(message));
          }
        }
      },
      signal,
    );

    // Some servers may close the SSE connection without a terminal RUN_FINISHED
    // (e.g. if the underlying generator simply exhausts). Treat clean EOF as
    // success so the caller's onComplete still fires.
    if (!completed && !errored) {
      onComplete();
    }
  } catch (err) {
    if (signal?.aborted) return;
    if (!errored) {
      onError(err instanceof Error ? err : new Error("Writing failed"));
    }
  }
}
