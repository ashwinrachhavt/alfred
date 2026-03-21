"use client";

import { useEffect, useRef, useState } from "react";

import { Send, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAiPanelStore } from "@/lib/stores/ai-panel-store";
import { useShellStore } from "@/lib/stores/shell-store";

export function AiPanel() {
  const { aiPanelOpen, toggleAiPanel } = useShellStore();
  const { messages, isStreaming, sendMessage, clearHistory } = useAiPanelStore();
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (!aiPanelOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput("");
    await sendMessage(text);
  };

  return (
    <aside className="border-l bg-background flex h-full w-[380px] shrink-0 flex-col">
      <div className="flex items-center justify-between border-b px-4 py-2">
        <h2 className="text-sm font-semibold">Alfred AI</h2>
        <div className="flex gap-1">
          <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={clearHistory}>
            Clear
          </Button>
          <Button variant="ghost" size="icon" className="size-7" onClick={toggleAiPanel}>
            <X className="size-4" />
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="text-muted-foreground text-sm space-y-2 pt-8 text-center">
            <p>Ask anything about your knowledge...</p>
            <p className="text-xs">Try: &quot;What do I know about distributed systems?&quot;</p>
          </div>
        ) : (
          messages.map((msg, i) => (
            <div key={i} className={`text-sm ${msg.role === "user" ? "text-right" : ""}`}>
              <div
                className={`inline-block max-w-[90%] rounded-lg px-3 py-2 ${
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted"
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))
        )}
        {isStreaming && (
          <div className="text-muted-foreground text-sm">
            <span className="animate-pulse">Thinking...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="border-t p-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your knowledge..."
            className="bg-muted flex-1 rounded-md px-3 py-2 text-sm outline-none"
            disabled={isStreaming}
          />
          <Button type="submit" size="icon" disabled={isStreaming || !input.trim()}>
            <Send className="size-4" />
          </Button>
        </div>
      </form>
    </aside>
  );
}
