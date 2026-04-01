import { describe, it, expect, beforeEach } from "vitest";
import { useShellStore } from "../shell-store";

// Reset store between tests
beforeEach(() => {
  useShellStore.setState({
    aiPanelOpen: false,
    chatMode: "sidebar",
    toolPanel: null,
  });
});

describe("shell-store", () => {
  describe("chatMode state", () => {
    it("defaults to sidebar mode", () => {
      expect(useShellStore.getState().chatMode).toBe("sidebar");
    });

    it("setChatMode sets mode and opens panel", () => {
      useShellStore.getState().setChatMode("expanded");
      const state = useShellStore.getState();
      expect(state.chatMode).toBe("expanded");
      expect(state.aiPanelOpen).toBe(true);
    });

    it("setChatMode to sidebar also opens panel", () => {
      useShellStore.getState().setChatMode("sidebar");
      const state = useShellStore.getState();
      expect(state.chatMode).toBe("sidebar");
      expect(state.aiPanelOpen).toBe(true);
    });
  });

  describe("toggleChatExpanded", () => {
    it("switches from sidebar to expanded and opens panel", () => {
      useShellStore.setState({ chatMode: "sidebar", aiPanelOpen: false });
      useShellStore.getState().toggleChatExpanded();
      const state = useShellStore.getState();
      expect(state.chatMode).toBe("expanded");
      expect(state.aiPanelOpen).toBe(true);
    });

    it("switches from expanded back to sidebar", () => {
      useShellStore.setState({ chatMode: "expanded", aiPanelOpen: true });
      useShellStore.getState().toggleChatExpanded();
      expect(useShellStore.getState().chatMode).toBe("sidebar");
    });
  });

  describe("toggleAiPanel", () => {
    it("opening panel resets to sidebar mode", () => {
      useShellStore.setState({ aiPanelOpen: false, chatMode: "expanded" });
      useShellStore.getState().toggleAiPanel();
      const state = useShellStore.getState();
      expect(state.aiPanelOpen).toBe(true);
      expect(state.chatMode).toBe("sidebar");
    });

    it("closing panel preserves current chatMode", () => {
      useShellStore.setState({ aiPanelOpen: true, chatMode: "expanded" });
      useShellStore.getState().toggleAiPanel();
      const state = useShellStore.getState();
      expect(state.aiPanelOpen).toBe(false);
      expect(state.chatMode).toBe("expanded");
    });
  });
});
