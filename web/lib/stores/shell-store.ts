import { create } from "zustand";

export type ToolPanelType = "notes" | "document" | "connectors" | "quiz" | "writing";

export type ChatMode = "sidebar" | "expanded";

type ToolPanel = {
  type: ToolPanelType;
  props: Record<string, unknown>;
};

type ShellState = {
  aiPanelOpen: boolean;
  chatMode: ChatMode;
  toolPanel: ToolPanel | null;
  toggleAiPanel: () => void;
  setAiPanelOpen: (open: boolean) => void;
  setChatMode: (mode: ChatMode) => void;
  toggleChatExpanded: () => void;
  openToolPanel: (type: ToolPanelType, props?: Record<string, unknown>) => void;
  closeToolPanel: () => void;
};

export const useShellStore = create<ShellState>((set) => ({
  aiPanelOpen: false,
  chatMode: "sidebar",
  toolPanel: null,
  toggleAiPanel: () => set((s) => ({ aiPanelOpen: !s.aiPanelOpen, chatMode: s.aiPanelOpen ? s.chatMode : "sidebar" })),
  setAiPanelOpen: (open) => set({ aiPanelOpen: open }),
  setChatMode: (mode) => set({ chatMode: mode, aiPanelOpen: true }),
  toggleChatExpanded: () =>
    set((s) => {
      if (s.chatMode === "expanded") {
        return { chatMode: "sidebar" };
      }
      return { chatMode: "expanded", aiPanelOpen: true };
    }),
  openToolPanel: (type, props = {}) => set({ toolPanel: { type, props } }),
  closeToolPanel: () => set({ toolPanel: null }),
}));
