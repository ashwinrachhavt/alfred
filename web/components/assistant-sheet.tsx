"use client";

import * as React from "react";

import { Bot, CornerDownLeft, Loader2, Sparkles, X } from "lucide-react";

import { apiPostJson } from "@/lib/api/client";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";

type AssistantMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
};

type AssistantContextValue = {
  isAssistantOpen: boolean;
  setAssistantOpen: (open: boolean) => void;
};

const AssistantContext = React.createContext<AssistantContextValue | null>(null);

export function useAssistant(): AssistantContextValue {
  const ctx = React.useContext(AssistantContext);
  if (!ctx) {
    throw new Error("useAssistant must be used within AssistantProvider.");
  }
  return ctx;
}

export function AssistantProvider({ children }: { children: React.ReactNode }) {
  const [isAssistantOpen, setAssistantOpen] = React.useState(false);

  React.useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.defaultPrevented) return;
      const target = event.target;
      if (
        target instanceof HTMLElement &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable)
      ) {
        return;
      }

      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "j") {
        event.preventDefault();
        setAssistantOpen((prev) => !prev);
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const value = React.useMemo<AssistantContextValue>(
    () => ({ isAssistantOpen, setAssistantOpen }),
    [isAssistantOpen],
  );

  return <AssistantContext.Provider value={value}>{children}</AssistantContext.Provider>;
}

export function AssistantSheet() {
  const { isAssistantOpen, setAssistantOpen } = useAssistant();
  const [messages, setMessages] = React.useState<AssistantMessage[]>([]);
  const [input, setInput] = React.useState("");
  const [isLoading, setIsLoading] = React.useState(false);
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  React.useEffect(() => {
    if (isAssistantOpen) {
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  }, [isAssistantOpen]);

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = React.useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;

    const userMessage: AssistantMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
      createdAt: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await apiPostJson<
        { answer: string; sources?: Array<{ title: string; id: string }> },
        { query: string; history: Array<{ role: string; content: string }> }
      >("/api/ai/proxy", {
        query: trimmed,
        history: messages.map((m) => ({ role: m.role, content: m.content })),
      });

      const assistantMessage: AssistantMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: response.answer ?? "I couldn't find an answer. Try rephrasing your question.",
        createdAt: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch {
      const errorMessage: AssistantMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "Something went wrong. Please try again.",
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, messages]);

  const handleKeyDown = React.useCallback(
    (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        send();
      }
    },
    [send],
  );

  const clearChat = React.useCallback(() => {
    setMessages([]);
    setInput("");
  }, []);

  return (
    <Sheet open={isAssistantOpen} onOpenChange={setAssistantOpen}>
      <SheetContent side="right" className="flex w-[420px] flex-col sm:max-w-[520px]">
        <SheetHeader className="space-y-1">
          <div className="flex items-start justify-between gap-3 pr-8">
            <div className="space-y-1">
              <SheetTitle className="flex items-center gap-2">
                <Sparkles className="h-4 w-4" aria-hidden="true" />
                Ask Alfred
              </SheetTitle>
              <p className="text-muted-foreground text-sm">
                Ask questions across your knowledge base.
              </p>
            </div>
            {messages.length > 0 ? (
              <Button type="button" variant="ghost" size="sm" onClick={clearChat}>
                <X className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
                Clear
              </Button>
            ) : null}
          </div>
        </SheetHeader>

        <div ref={scrollRef} className="min-h-0 flex-1 overflow-auto">
          {messages.length === 0 ? (
            <EmptyState
              icon={Bot}
              title="Ask Alfred anything"
              description="Ask a question and Alfred will search your documents, notes, and knowledge base for answers."
            />
          ) : (
            <div className="space-y-4 p-1">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={
                    message.role === "user"
                      ? "flex justify-end"
                      : "flex justify-start"
                  }
                >
                  <div
                    className={
                      message.role === "user"
                        ? "bg-primary text-primary-foreground max-w-[85%] rounded-2xl rounded-br-md px-4 py-2.5 text-sm"
                        : "bg-muted max-w-[85%] rounded-2xl rounded-bl-md px-4 py-2.5 text-sm"
                    }
                  >
                    <p className="whitespace-pre-wrap">{message.content}</p>
                  </div>
                </div>
              ))}
              {isLoading ? (
                <div className="flex justify-start">
                  <div className="bg-muted flex items-center gap-2 rounded-2xl rounded-bl-md px-4 py-2.5 text-sm">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                    <span className="text-muted-foreground">Thinking…</span>
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </div>

        <div className="border-t pt-3">
          <div className="relative">
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question…"
              rows={2}
              className="resize-none pr-12"
              disabled={isLoading}
            />
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="absolute right-2 bottom-2"
              disabled={!input.trim() || isLoading}
              onClick={send}
              aria-label="Send message"
            >
              <CornerDownLeft className="h-4 w-4" aria-hidden="true" />
            </Button>
          </div>
          <p className="text-muted-foreground mt-1.5 text-center text-xs">
            ⌘J to toggle · Enter to send · Shift+Enter for new line
          </p>
        </div>
      </SheetContent>
    </Sheet>
  );
}

export function AssistantTrigger({ className }: { className?: string }) {
  const { setAssistantOpen } = useAssistant();

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className={className}
      aria-label="Ask Alfred"
      onClick={() => setAssistantOpen(true)}
    >
      <Sparkles className="h-4 w-4" aria-hidden="true" />
    </Button>
  );
}
