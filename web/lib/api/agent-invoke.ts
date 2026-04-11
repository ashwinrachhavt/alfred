/**
 * Headless agent invocation — sends an intent to the orchestrator via SSE
 * and returns the assembled text response. Used for inline AI operations
 * (notes editor rewrite/summarize/complete) that need a text result
 * without the full chat UI.
 */

import { apiRoutes } from "@/lib/api/routes";
import { streamSSE } from "@/lib/api/sse";

export async function agentInvoke(opts: {
  intent: string;
  intentArgs: Record<string, unknown>;
  model?: string;
}): Promise<string> {
  let result = "";

  await streamSSE(
    apiRoutes.agent.stream,
    {
      message: "",
      intent: opts.intent,
      intent_args: opts.intentArgs,
      model: opts.model ?? "gpt-5.4",
    },
    (event, data) => {
      if (event === "token" && typeof data.content === "string") {
        result += data.content;
      }
      if (event === "error" && typeof data.message === "string") {
        throw new Error(data.message);
      }
    },
  );

  return result.trim();
}
