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
  zettelViewerCardId: number | null;
  openAiPanel: (mode?: ChatMode) => void;
  closeAiPanel: () => void;
  toggleAiPanel: (mode?: ChatMode) => void;
  setAiPanelOpen: (open: boolean) => void;
  setChatMode: (mode: ChatMode) => void;
  toggleChatExpanded: () => void;
  openToolPanel: (type: ToolPanelType, props?: Record<string, unknown>) => void;
  closeToolPanel: () => void;
  openZettelViewer: (cardId: number) => void;
  closeZettelViewer: () => void;
};

export const useShellStore = create<ShellState>((set) => ({
  aiPanelOpen: false,
  chatMode: "sidebar",
  toolPanel: null,
  zettelViewerCardId: null,
  openAiPanel: (mode = "expanded") => set({ aiPanelOpen: true, chatMode: mode }),
  closeAiPanel: () => set({ aiPanelOpen: false }),
  toggleAiPanel: (mode = "sidebar") =>
    set((s) => (s.aiPanelOpen ? { aiPanelOpen: false } : { aiPanelOpen: true, chatMode: mode })),
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
  openZettelViewer: (cardId) => set({ zettelViewerCardId: cardId }),
  closeZettelViewer: () => set({ zettelViewerCardId: null }),
}));
