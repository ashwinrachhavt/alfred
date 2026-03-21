import { create } from "zustand";

import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

type Message = {
  role: "user" | "assistant";
  content: string;
  citations?: string[];
};

type AiContext = {
  page: string;
  entityId?: string;
};

type AiPanelState = {
  messages: Message[];
  isStreaming: boolean;
  context: AiContext;
  sendMessage: (text: string) => Promise<void>;
  clearHistory: () => void;
  setContext: (ctx: AiContext) => void;
};

export const useAiPanelStore = create<AiPanelState>((set, get) => ({
  messages: [],
  isStreaming: false,
  context: { page: "inbox" },

  sendMessage: async (text: string) => {
    const userMsg: Message = { role: "user", content: text };
    set((s) => ({ messages: [...s.messages, userMsg], isStreaming: true }));

    try {
      const data = await apiFetch<{ answer: string }>(apiRoutes.rag.answer + "?" + new URLSearchParams({ q: text }));
      const assistantMsg: Message = { role: "assistant", content: data.answer };
      set((s) => ({ messages: [...s.messages, assistantMsg], isStreaming: false }));
    } catch {
      const errorMsg: Message = { role: "assistant", content: "Sorry, something went wrong. Please try again." };
      set((s) => ({ messages: [...s.messages, errorMsg], isStreaming: false }));
    }
  },

  clearHistory: () => set({ messages: [] }),
  setContext: (ctx) => set({ context: ctx }),
}));
