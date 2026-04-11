// web/lib/api/ai-stream.ts
import { apiRoutes } from "@/lib/api/routes";
import { streamSSE } from "@/lib/api/sse";

export type StreamAIOptions = {
  intent: "autocomplete" | "edit_text" | "summarize" | "generate";
  intentArgs: Record<string, unknown>;
  onToken: (token: string) => void;
  onComplete: () => void;
  onError: (error: Error) => void;
  signal?: AbortSignal;
  model?: string;
};

export async function streamAIInline(opts: StreamAIOptions): Promise<void> {
  const { intent, intentArgs, onToken, onComplete, onError, signal, model } = opts;

  try {
    await streamSSE(
      apiRoutes.agent.stream,
      {
        message: "",
        intent,
        intent_args: intentArgs,
        model: model ?? "gpt-5.4",
      },
      (event, data) => {
        if (event === "token" && typeof data.content === "string") {
          onToken(data.content);
        }
        if (event === "error" && typeof data.message === "string") {
          onError(new Error(data.message));
        }
      },
      signal,
    );
    onComplete();
  } catch (err) {
    if (signal?.aborted) return; // Clean abort, not an error
    onError(err instanceof Error ? err : new Error("AI streaming failed"));
  }
}
