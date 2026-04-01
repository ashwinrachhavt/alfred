"use client";

import { useEffect } from "react";

import { useShellStore } from "@/lib/stores/shell-store";
import { UnifiedChat } from "@/components/chat/unified-chat";

import { AppSidebar } from "./app-sidebar";
import { ToolPanel } from "./tool-panel";
import { TopBar } from "./top-bar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { toggleAiPanel, toggleChatExpanded, chatMode } = useShellStore();

  useEffect(() => {
    const pillarRoutes = ["/inbox", "/canvas", "#ai", "/dashboard"];
    const handler = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey)) {
        if (e.key === "Escape") {
          useShellStore.getState().closeToolPanel();
        }
        return;
      }

      // Cmd+Shift+J — toggle expanded mode
      if (e.key === "j" && e.shiftKey) {
        e.preventDefault();
        toggleChatExpanded();
        return;
      }

      // Cmd+J — toggle sidebar mode
      if (e.key === "j") {
        e.preventDefault();
        toggleAiPanel();
        return;
      }

      const num = parseInt(e.key, 10);
      if (num >= 1 && num <= 4) {
        e.preventDefault();
        const route = pillarRoutes[num - 1];
        if (route === "#ai") {
          toggleAiPanel();
        } else {
          window.location.href = route;
        }
      }
      if (e.key === "n") {
        e.preventDefault();
        useShellStore.getState().openToolPanel("notes");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [toggleAiPanel, toggleChatExpanded]);

  const isExpanded = chatMode === "expanded";

  return (
    <div className="flex h-dvh">
      <AppSidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar />
        <div className="flex flex-1 overflow-hidden">
          {isExpanded ? (
            /* Expanded mode: UnifiedChat replaces main content */
            <UnifiedChat mode="expanded" />
          ) : (
            <>
              <main
                id="main-content"
                tabIndex={-1}
                className="flex-1 overflow-y-auto focus:outline-none"
              >
                {children}
              </main>
              <UnifiedChat mode="sidebar" />
            </>
          )}
        </div>
      </div>
      <ToolPanel />
    </div>
  );
}
