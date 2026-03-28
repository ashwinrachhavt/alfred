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
    <aside className="flex h-full w-[380px] shrink-0 flex-col border-l bg-card">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-2.5">
        <div className="flex items-center gap-2">
          <div className="size-2 rounded-full bg-primary animate-pulse" />
          <h2 className="font-mono text-xs uppercase tracking-wider">Alfred AI</h2>
        </div>
        <div className="flex gap-1">
          <Button variant="ghost" size="sm" className="h-7 font-mono text-[10px] uppercase tracking-wider" onClick={clearHistory}>
            Clear
          </Button>
          <Button variant="ghost" size="icon" className="size-7" onClick={toggleAiPanel}>
            <X className="size-4" />
          </Button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center pt-12 text-center">
            <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-[var(--alfred-accent-subtle)]">
              <svg className="size-6 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
              </svg>
            </div>
            <p className="text-sm text-muted-foreground">Ask anything about your knowledge</p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {["What do I know about...", "Summarize my recent readings", "Find connections between..."].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => setInput(suggestion)}
                  className="rounded-sm border px-3 py-1.5 font-mono text-[11px] text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, i) => (
            <div key={i} className={`text-sm ${msg.role === "user" ? "text-right" : ""}`}>
              <div
                className={`inline-block max-w-[90%] rounded-md px-3 py-2 ${
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary"
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

      {/* Input */}
      <form onSubmit={handleSubmit} className="border-t p-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your knowledge..."
            className="flex-1 rounded-md bg-secondary px-3 py-2 text-sm outline-none placeholder:text-[var(--alfred-text-tertiary)] focus:ring-1 focus:ring-primary"
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
