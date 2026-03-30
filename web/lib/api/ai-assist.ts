/**
 * AI Assist functions — routed through the agent orchestrator.
 *
 * These functions call the LangGraph agent with intents for inline text
 * operations (complete, rewrite, summarize). The agent dispatches to the
 * appropriate tool (autocomplete, edit_text, summarize_content).
 */

import { agentInvoke } from "@/lib/api/agent-invoke";

export async function completeText(
  text: string,
  contextBefore = "",
  contextAfter = "",
): Promise<string> {
  return agentInvoke({
    intent: "autocomplete",
    intentArgs: {
      text: contextBefore.slice(-500) + text + contextAfter.slice(0, 500),
      tone: "",
      max_chars: 600,
    },
  });
}

export async function rewriteText(
  text: string,
  instruction = "Improve clarity and grammar",
): Promise<string> {
  return agentInvoke({
    intent: "edit_text",
    intentArgs: {
      text,
      instruction,
    },
  });
}

export async function summarizeText(text: string): Promise<string> {
  return agentInvoke({
    intent: "summarize",
    intentArgs: {
      text,
    },
  });
}
