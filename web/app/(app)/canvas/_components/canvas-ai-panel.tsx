"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Bot, GripVertical, Loader2, Send, X } from "lucide-react";
import ReactMarkdown from "react-markdown";

import { Button } from "@/components/ui/button";
import { streamSSE } from "@/lib/api/sse";
import { apiRoutes } from "@/lib/api/routes";
import { safeGetItem, safeSetItem } from "@/lib/storage";

type CanvasAIPanelProps = {
 canvasTitle: string;
 onInsertText: (text: string) => void;
 onClose: () => void;
};

type Message = {
 id: string;
 role: "user" | "assistant";
 content: string;
};

const STORAGE_KEY = "alfred:canvas:ai-panel-pos:v1";
const MIN_W = 320;
const MIN_H = 300;
const MAX_W = 600;
const DEFAULT_W = 380;
const DEFAULT_H = 400;

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
 // ignore
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

export function CanvasAIPanel({ canvasTitle, onInsertText, onClose }: CanvasAIPanelProps) {
 const [messages, setMessages] = useState<Message[]>([]);
 const [input, setInput] = useState("");
 const [isStreaming, setIsStreaming] = useState(false);
 const abortRef = useRef<AbortController | null>(null);
 const messagesEndRef = useRef<HTMLDivElement>(null);
 const inputRef = useRef<HTMLTextAreaElement>(null);

 // --- Drag / Resize state ---
 const [pos, setPos] = useState<{ x: number; y: number }>(() => {
 const l = loadPersistedLayout();
 return { x: l.x, y: l.y };
 });
 const [size, setSize] = useState<{ w: number; h: number }>(() => {
 const l = loadPersistedLayout();
 return { w: l.w, h: l.h };
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

 // Persist on change (debounced)
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

 // --- Drag handlers ---
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

 // --- Resize handlers ---
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

 // --- Chat logic ---
 const scrollToBottom = useCallback(() => {
 messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
 }, []);

 const handleSend = useCallback(async () => {
 const text = input.trim();
 if (!text || isStreaming) return;

 setInput("");

 const userMsg: Message = {
 id:`user-${Date.now()}`,
 role: "user",
 content: text,
 };

 const assistantMsg: Message = {
 id:`assistant-${Date.now()}`,
 role: "assistant",
 content: "",
 };

 setMessages((prev) => [...prev, userMsg, assistantMsg]);
 setIsStreaming(true);

 const controller = new AbortController();
 abortRef.current = controller;

 let buffer = "";

 try {
 await streamSSE(
 apiRoutes.agent.stream,
 {
 message:`[Canvas context: "${canvasTitle}"]\n\n${text}`,
 lens: null,
 model: "gpt-5.4",
 history: messages.slice(-10).map((m) => ({
 role: m.role,
 content: m.content,
 })),
 },
 (event, data) => {
 if (event === "token") {
 buffer += data.content as string;
 const current = buffer;
 setMessages((prev) =>
 prev.map((m, i) =>
 i === prev.length - 1 && m.role === "assistant"
 ? { ...m, content: current }
 : m,
 ),
 );
 scrollToBottom();
 }
 },
 controller.signal,
 );
 } catch (err: unknown) {
 if (err instanceof DOMException && err.name === "AbortError") {
 // User cancelled
 } else {
 setMessages((prev) =>
 prev.map((m, i) =>
 i === prev.length - 1 && m.role === "assistant" && !m.content
 ? { ...m, content: "Something went wrong. Please try again." }
 : m,
 ),
 );
 }
 } finally {
 setIsStreaming(false);
 abortRef.current = null;
 scrollToBottom();
 }
 }, [input, isStreaming, messages, canvasTitle, scrollToBottom]);

 return (
 <div
 className="fixed z-50 flex flex-col rounded-lg border bg-card shadow-lg"
 style={{
 left: pos.x,
 top: pos.y,
 width: size.w,
 height: size.h,
 }}
 >
 {/* Draggable title bar */}
 <header
 className="flex items-center justify-between gap-2 rounded-t-lg border-b bg-secondary px-3 py-2 cursor-grab active:cursor-grabbing select-none"
 onPointerDown={onDragStart}
 onPointerMove={onDragMove}
 onPointerUp={onDragEnd}
 >
 <div className="flex items-center gap-2">
 <GripVertical className="size-3.5 text-muted-foreground/60" />
 <Bot className="size-4 text-primary" />
 <span className="font-medium text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
 Alfred AI
 </span>
 </div>
 <Button
 type="button"
 size="icon"
 variant="ghost"
 className="size-7"
 onPointerDown={(e) => e.stopPropagation()}
 onClick={onClose}
 >
 <X className="size-3.5" />
 <span className="sr-only">Close AI panel</span>
 </Button>
 </header>

 {/* Messages */}
 <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3 min-h-0">
 {messages.length === 0 && (
 <div className="flex flex-col items-center justify-center h-full gap-2 text-center px-4">
 <Bot className="size-8 text-muted-foreground/40" />
 <p className="text-sm text-muted-foreground">
 Ask Alfred anything about your canvas. Responses can be inserted as text elements.
 </p>
 </div>
 )}

 {messages.map((msg) => (
 <div key={msg.id} className="space-y-1">
 <span className="font-medium text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
 {msg.role === "user" ? "You" : "Alfred"}
 </span>
 <div
 className={
 msg.role === "user"
 ? "rounded-md bg-muted/50 px-3 py-2 text-sm"
 : "text-sm prose prose-sm max-w-none dark:prose-invert"
 }
 >
 {msg.role === "assistant" ? (
 <>
 <ReactMarkdown>{msg.content || "..."}</ReactMarkdown>
 {msg.content && !isStreaming && (
 <Button
 type="button"
 size="sm"
 variant="outline"
 className="mt-2 h-7 text-[10px]"
 onClick={() => onInsertText(msg.content)}
 >
 Insert on canvas
 </Button>
 )}
 </>
 ) : (
 msg.content
 )}
 </div>
 </div>
 ))}

 <div ref={messagesEndRef} />
 </div>

 {/* Input */}
 <div className="border-t px-3 py-2">
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
 placeholder="Ask Alfred..."
 rows={1}
 className="flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-muted-foreground/60"
 />
 <Button
 type="button"
 size="icon"
 variant="ghost"
 className="size-7 shrink-0"
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

 {/* Resize handle — bottom-right corner */}
 <div
 className="absolute right-0 bottom-0 flex size-4 cursor-se-resize items-center justify-center rounded-bl-sm"
 onPointerDown={onResizeStart}
 onPointerMove={onResizeMove}
 onPointerUp={onResizeEnd}
 >
 <svg
 width="8"
 height="8"
 viewBox="0 0 8 8"
 className="text-muted-foreground/40"
 >
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
