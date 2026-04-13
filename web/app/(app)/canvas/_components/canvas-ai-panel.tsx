"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Bot, GripVertical, Loader2, MessageSquareText, Send, Sparkles, X } from "lucide-react";
import ReactMarkdown from "react-markdown";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { streamSSE } from "@/lib/api/sse";
import { useStickToBottom } from "@/lib/hooks/use-stick-to-bottom";
import { apiRoutes } from "@/lib/api/routes";
import { safeGetItem, safeSetItem } from "@/lib/storage";
import { useAgentStore } from "@/lib/stores/agent-store";

type CanvasMode = "ask" | "visualize";

type CanvasAIPanelProps = {
  canvasTitle: string;
  getCanvasContext?: () => string;
  onInsertText: (text: string) => void;
  onInsertDiagram: (payload: {
    elements: unknown[];
    prompt: string;
    description?: string;
    canvasContext?: string;
  }) => Promise<void> | void;
  onClose: () => void;
};

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  mode: CanvasMode;
};

type DiagramResponse = {
  elements: unknown[];
  description?: string | null;
};

const STORAGE_KEY = "alfred:canvas:ai-panel-pos:v1";
const MIN_W = 320;
const MIN_H = 300;
const MAX_W = 600;
const DEFAULT_W = 400;
const DEFAULT_H = 430;
const DEFAULT_MODE: CanvasMode = "visualize";
const STARTER_PROMPTS = [
  {
    label: "User flow",
    prompt: "Map the user flow from landing page to successful signup and activation.",
  },
  {
    label: "Mind map",
    prompt: "Turn this topic into a mind map with core idea, major branches, and sub-branches.",
  },
  {
    label: "Architecture",
    prompt: "Visualize this system architecture with main services, data stores, and request flow.",
  },
  {
    label: "Decision tree",
    prompt: "Create a decision tree that compares the main options and key tradeoffs.",
  },
];

function readCanvasContext(canvasTitle: string, getCanvasContext?: () => string): string {
  const context = getCanvasContext?.().trim();
  return context || `Canvas: "${canvasTitle}"`;
}

function loadPersistedLayout(): { x: number; y: number; w: number; h: number } {
  if (typeof window === "undefined") {
    return { x: 0, y: 0, w: DEFAULT_W, h: DEFAULT_H };
  }
  try {
    const raw = safeGetItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as { x?: number; y?: number; w?: number; h?: number };
      return {
        x: typeof parsed.x === "number" ? parsed.x : window.innerWidth - DEFAULT_W - 20,
        y: typeof parsed.y === "number" ? parsed.y : window.innerHeight - DEFAULT_H - 20,
        w: typeof parsed.w === "number" ? parsed.w : DEFAULT_W,
        h: typeof parsed.h === "number" ? parsed.h : DEFAULT_H,
      };
    }
  } catch {
    // ignore persisted layout errors
  }
  return {
    x: window.innerWidth - DEFAULT_W - 20,
    y: window.innerHeight - DEFAULT_H - 20,
    w: DEFAULT_W,
    h: DEFAULT_H,
  };
}

function persistLayout(layout: { x: number; y: number; w: number; h: number }) {
  safeSetItem(STORAGE_KEY, JSON.stringify(layout));
}

function clamp(val: number, min: number, max: number) {
  return Math.min(Math.max(val, min), max);
}

export function CanvasAIPanel({
  canvasTitle,
  getCanvasContext,
  onInsertText,
  onInsertDiagram,
  onClose,
}: CanvasAIPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<CanvasMode>(DEFAULT_MODE);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const activeModel = useAgentStore((s) => s.activeModel);
  const {
    containerRef: messagesContainerRef,
    endRef: messagesEndRef,
    maybeScrollToBottom,
    scrollToBottom,
  } = useStickToBottom();

  const [pos, setPos] = useState<{ x: number; y: number }>(() => {
    const layout = loadPersistedLayout();
    return { x: layout.x, y: layout.y };
  });
  const [size, setSize] = useState<{ w: number; h: number }>(() => {
    const layout = loadPersistedLayout();
    return { w: layout.w, h: layout.h };
  });

  const dragRef = useRef<{
    startX: number;
    startY: number;
    startPosX: number;
    startPosY: number;
  } | null>(null);

  const resizeRef = useRef<{
    startX: number;
    startY: number;
    startW: number;
    startH: number;
  } | null>(null);

  const persistTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (persistTimeoutRef.current) clearTimeout(persistTimeoutRef.current);
    persistTimeoutRef.current = setTimeout(() => {
      persistLayout({ ...pos, ...size });
    }, 300);
    return () => {
      if (persistTimeoutRef.current) clearTimeout(persistTimeoutRef.current);
    };
  }, [pos, size]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      inputRef.current?.focus();
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(
    () => () => {
      abortRef.current?.abort();
    },
    [],
  );

  const onDragStart = useCallback(
    (e: React.PointerEvent) => {
      dragRef.current = {
        startX: e.clientX,
        startY: e.clientY,
        startPosX: pos.x,
        startPosY: pos.y,
      };
      e.currentTarget.setPointerCapture(e.pointerId);
    },
    [pos],
  );

  const onDragMove = useCallback((e: React.PointerEvent) => {
    if (!dragRef.current) return;
    const newX = dragRef.current.startPosX + (e.clientX - dragRef.current.startX);
    const newY = dragRef.current.startPosY + (e.clientY - dragRef.current.startY);
    setPos({
      x: clamp(newX, 0, window.innerWidth - 100),
      y: clamp(newY, 0, window.innerHeight - 40),
    });
  }, []);

  const onDragEnd = useCallback(() => {
    dragRef.current = null;
  }, []);

  const onResizeStart = useCallback(
    (e: React.PointerEvent) => {
      resizeRef.current = {
        startX: e.clientX,
        startY: e.clientY,
        startW: size.w,
        startH: size.h,
      };
      e.currentTarget.setPointerCapture(e.pointerId);
      e.stopPropagation();
    },
    [size],
  );

  const onResizeMove = useCallback((e: React.PointerEvent) => {
    if (!resizeRef.current) return;
    const maxH = window.innerHeight * 0.8;
    const newW = clamp(
      resizeRef.current.startW + (e.clientX - resizeRef.current.startX),
      MIN_W,
      MAX_W,
    );
    const newH = clamp(
      resizeRef.current.startH + (e.clientY - resizeRef.current.startY),
      MIN_H,
      maxH,
    );
    setSize({ w: newW, h: newH });
  }, []);

  const onResizeEnd = useCallback(() => {
    resizeRef.current = null;
  }, []);

  useEffect(() => {
    if (messages.length === 0) return;
    maybeScrollToBottom(isStreaming ? "auto" : "smooth");
  }, [messages, isStreaming, maybeScrollToBottom]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isStreaming) return;

    const nextMode = mode;
    const canvasContext = readCanvasContext(canvasTitle, getCanvasContext);

    setInput("");
    scrollToBottom("smooth");

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
      mode: nextMode,
    };

    const assistantMsg: Message = {
      id: `assistant-${Date.now()}`,
      role: "assistant",
      content: "",
      mode: nextMode,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      if (nextMode === "visualize") {
        const response = await fetch(apiRoutes.canvas.generateDiagram, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prompt: text,
            canvas_context: canvasContext,
          }),
          signal: controller.signal,
        });

        const data = (await response.json().catch(() => null)) as DiagramResponse | null;
        if (!response.ok) {
          throw new Error(data?.description || "Failed to generate diagram");
        }

        if (!data || !Array.isArray(data.elements) || data.elements.length === 0) {
          throw new Error(
            data?.description || "Alfred could not generate a diagram for that prompt.",
          );
        }

        await Promise.resolve(
          onInsertDiagram({
            elements: data.elements,
            prompt: text,
            description: data.description ?? undefined,
            canvasContext,
          }),
        );

        const description =
          data.description || `Created ${data.elements.length} diagram elements on the canvas.`;
        setMessages((prev) =>
          prev.map((message, index) =>
            index === prev.length - 1 && message.role === "assistant"
              ? { ...message, content: description }
              : message,
          ),
        );
      } else {
        let buffer = "";
        await streamSSE(
          apiRoutes.agent.stream,
          {
            message: `[Canvas context]\n${canvasContext}\n\n${text}`,
            lens: null,
            model: activeModel,
            history: messages.slice(-10).map((message) => ({
              role: message.role,
              content: message.content,
            })),
          },
          (event, data) => {
            if (event === "token") {
              buffer += data.content as string;
              const current = buffer;
              setMessages((prev) =>
                prev.map((message, index) =>
                  index === prev.length - 1 && message.role === "assistant"
                    ? { ...message, content: current }
                    : message,
                ),
              );
            }
          },
          controller.signal,
        );
      }
    } catch (err: unknown) {
      if (!(err instanceof DOMException && err.name === "AbortError")) {
        const message =
          err instanceof Error ? err.message : "Something went wrong. Please try again.";
        setMessages((prev) =>
          prev.map((entry, index) =>
            index === prev.length - 1 && entry.role === "assistant"
              ? { ...entry, content: message }
              : entry,
          ),
        );
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [
    activeModel,
    canvasTitle,
    getCanvasContext,
    input,
    isStreaming,
    messages,
    mode,
    onInsertDiagram,
    scrollToBottom,
  ]);

  const placeholder =
    mode === "visualize"
      ? "Describe what to draw: flowchart, mind map, user journey, architecture, timeline..."
      : "Ask Alfred about this canvas...";

  return (
    <div
      className="bg-card fixed z-50 flex flex-col rounded-lg border shadow-lg"
      style={{
        left: pos.x,
        top: pos.y,
        width: size.w,
        height: size.h,
      }}
    >
      <header
        className="bg-secondary flex cursor-grab items-center justify-between gap-3 rounded-t-lg border-b px-3 py-2 select-none active:cursor-grabbing"
        onPointerDown={onDragStart}
        onPointerMove={onDragMove}
        onPointerUp={onDragEnd}
      >
        <div className="flex items-center gap-2">
          <GripVertical className="text-muted-foreground/60 size-3.5" />
          <Bot className="text-primary size-4" />
          <span className="text-[10px] font-medium tracking-widest text-[var(--alfred-text-tertiary)] uppercase">
            Alfred AI
          </span>
        </div>

        <div className="flex items-center gap-2" onPointerDown={(e) => e.stopPropagation()}>
          <div className="bg-background flex items-center rounded-md border p-0.5">
            <button
              type="button"
              className={cn(
                "flex items-center gap-1 rounded-[6px] px-2 py-1 text-[11px] font-medium transition-colors",
                mode === "visualize"
                  ? "text-foreground bg-[var(--alfred-accent-subtle)]"
                  : "text-muted-foreground hover:text-foreground",
              )}
              onClick={() => setMode("visualize")}
              disabled={isStreaming}
            >
              <Sparkles className="size-3.5" />
              Visualize
            </button>
            <button
              type="button"
              className={cn(
                "flex items-center gap-1 rounded-[6px] px-2 py-1 text-[11px] font-medium transition-colors",
                mode === "ask"
                  ? "text-foreground bg-[var(--alfred-accent-subtle)]"
                  : "text-muted-foreground hover:text-foreground",
              )}
              onClick={() => setMode("ask")}
              disabled={isStreaming}
            >
              <MessageSquareText className="size-3.5" />
              Ask
            </button>
          </div>

          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="size-7"
            onClick={() => {
              abortRef.current?.abort();
              onClose();
            }}
          >
            <X className="size-3.5" />
            <span className="sr-only">Close AI panel</span>
          </Button>
        </div>
      </header>

      <div
        ref={messagesContainerRef}
        className="min-h-0 flex-1 space-y-3 overflow-y-auto px-3 py-3"
      >
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-3 px-4 text-center">
            <Bot className="text-muted-foreground/40 size-8" />
            <p className="text-muted-foreground text-sm">
              {mode === "visualize"
                ? "Describe any concept and Alfred will turn it into a smart, editable diagram on your canvas."
                : "Ask Alfred about the current canvas. Chat responses stay textual and can be copied onto the board."}
            </p>

            {mode === "visualize" && (
              <div className="flex flex-wrap justify-center gap-2">
                {STARTER_PROMPTS.map((starter) => (
                  <button
                    key={starter.label}
                    type="button"
                    className="bg-background rounded-md border px-2.5 py-1.5 text-[11px] transition-colors hover:bg-[var(--alfred-accent-subtle)]"
                    onClick={() => {
                      setMode("visualize");
                      setInput(starter.prompt);
                      window.requestAnimationFrame(() => inputRef.current?.focus());
                    }}
                  >
                    {starter.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {messages.map((message) => (
          <div key={message.id} className="space-y-1">
            <span className="text-[10px] font-medium tracking-widest text-[var(--alfred-text-tertiary)] uppercase">
              {message.role === "user" ? "You" : "Alfred"}
            </span>
            <div
              className={
                message.role === "user"
                  ? "bg-muted/50 rounded-md px-3 py-2 text-sm"
                  : "prose prose-sm dark:prose-invert max-w-none text-sm"
              }
            >
              {message.role === "assistant" ? (
                <>
                  <ReactMarkdown>{message.content || "..."}</ReactMarkdown>
                  {message.content && !isStreaming && message.mode === "ask" && (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="mt-2 h-7 text-[10px]"
                      onClick={() => onInsertText(message.content)}
                    >
                      Insert on canvas
                    </Button>
                  )}
                  {message.content && message.mode === "visualize" && (
                    <div className="text-muted-foreground mt-2 text-[10px] font-medium tracking-widest uppercase">
                      Inserted on canvas
                    </div>
                  )}
                </>
              ) : (
                message.content
              )}
            </div>
          </div>
        ))}

        <div ref={messagesEndRef} />
      </div>

      <div className="border-t px-3 py-2">
        <div className="text-muted-foreground mb-2 text-[10px] font-medium tracking-widest uppercase">
          {mode === "visualize" ? "Diagram mode" : "Chat mode"}
        </div>
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void handleSend();
              }
            }}
            placeholder={placeholder}
            rows={2}
            className="placeholder:text-muted-foreground/60 min-h-[52px] flex-1 resize-none bg-transparent text-sm outline-none"
          />
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="size-8 shrink-0"
            disabled={!input.trim() || isStreaming}
            onClick={() => void handleSend()}
          >
            {isStreaming ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Send className="size-3.5" />
            )}
          </Button>
        </div>
      </div>

      <div
        className="absolute right-0 bottom-0 flex size-4 cursor-se-resize items-center justify-center rounded-bl-sm"
        onPointerDown={onResizeStart}
        onPointerMove={onResizeMove}
        onPointerUp={onResizeEnd}
      >
        <svg width="8" height="8" viewBox="0 0 8 8" className="text-muted-foreground/40">
          <path
            d="M7 1L1 7M7 4L4 7"
            stroke="currentColor"
            strokeWidth="1.2"
            fill="none"
            strokeLinecap="round"
          />
        </svg>
      </div>
    </div>
  );
}
