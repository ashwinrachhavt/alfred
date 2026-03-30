"use client";

import { useEffect, useRef, useState } from "react";

import {
 Brain,
 ChevronDown,
 Loader2,
 Plus,
 RotateCcw,
 Send,
 Settings2,
 Square,
 ThumbsDown,
 ThumbsUp,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
 useAgentStore,
 PHILOSOPHICAL_LENSES,
 type AgentMessage,
 type ArtifactCard,
} from "@/lib/stores/agent-store";
import { ArtifactCardComponent } from "@/components/agent/artifact-card";
import { RelatedCards } from "@/components/agent/related-cards";
import { EditorDrawer } from "@/components/agent/editor-drawer";
import { InsightToCard } from "@/components/agent/insight-to-card";
import { MarkdownMessage } from "@/components/agent/markdown-message";
import { cn } from "@/lib/utils";

export function AgentChatClient() {
 const {
 messages,
 threads,
 activeThreadId,
 isStreaming,
 activeLens,
 activeModel,
 activeToolCalls,
 sendMessage,
 cancelStream,
 setLens,
 setModel,
 loadThreads,
 createThread,
 clearMessages,
 } = useAgentStore();

 const [input, setInput] = useState("");
 const [editingZettelId, setEditingZettelId] = useState<number | null>(null);
 const [showSettings, setShowSettings] = useState(false);
 const messagesEndRef = useRef<HTMLDivElement>(null);
 const inputRef = useRef<HTMLTextAreaElement>(null);

 useEffect(() => {
 loadThreads();
 }, [loadThreads]);

 useEffect(() => {
 messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
 }, [messages]);

 const handleSend = async () => {
 const text = input.trim();
 if (!text) return;
 setInput("");

 if (!activeThreadId) {
 await createThread(text.slice(0, 60));
 }

 await sendMessage(text);
 };

 const handleKeyDown = (e: React.KeyboardEvent) => {
 if (e.key === "Enter" && !e.shiftKey) {
 e.preventDefault();
 handleSend();
 }
 };

 const handleArtifactClick = (artifact: ArtifactCard) => {
 setEditingZettelId(artifact.id);
 };

 const activeThread = threads.find((t) => t.id === activeThreadId);

 return (
 <div className="flex flex-col h-full">
 {/* Conversation header */}
 <div className="flex items-center gap-2 px-6 py-2 border-b">
 <span className="font-medium text-[10px] uppercase tracking-wider text-[var(--alfred-text-tertiary)]">
 Alfred AI
 </span>
 {activeThread && (
 <>
 <span className="text-[var(--alfred-text-tertiary)]">/</span>
 <span className="text-sm text-foreground truncate max-w-xs">
 {activeThread.title}
 </span>
 <ChevronDown className="size-3 text-muted-foreground" />
 </>
 )}

 <div className="ml-auto flex items-center gap-1">
 <Button
 variant="ghost"
 size="sm"
 className="h-7 gap-1.5 font-medium text-[10px] uppercase tracking-wider text-muted-foreground"
 onClick={() => { clearMessages(); createThread(); }}
 >
 <Plus className="size-3.5" />
 New
 </Button>
 </div>
 </div>

 {/* Messages area — centered, generous spacing */}
 <div className="flex-1 overflow-y-auto">
 <div className="max-w-2xl mx-auto px-6 py-6 space-y-6">
 {messages.length === 0 && (
 <div className="flex flex-col items-center pt-24 text-center">
 <div className="mb-5 flex size-14 items-center justify-center rounded-full bg-[var(--alfred-accent-subtle)]">
 <Brain className="size-7 text-primary" />
 </div>
 <h2 className="text-2xl text-foreground mb-2">
 What would you like to explore?
 </h2>
 <p className="text-sm text-muted-foreground max-w-sm mb-8">
 Ask anything. Alfred will search your knowledge base, create new
 cards, and help you think.
 </p>
 <div className="flex flex-wrap justify-center gap-2">
 {[
 "What do I know about...",
 "Summarize my recent readings",
 "Find connections between...",
 "Create a zettel about...",
 ].map((suggestion) => (
 <button
 key={suggestion}
 onClick={() => setInput(suggestion)}
 className="rounded-full border px-4 py-2 text-[13px] text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
 >
 {suggestion}
 </button>
 ))}
 </div>
 </div>
 )}

 {messages.map((msg) => (
 <MessageBubble
 key={msg.id}
 message={msg}
 onArtifactClick={handleArtifactClick}
 />
 ))}

 {/* Tool call indicator */}
 {isStreaming && activeToolCalls.some((tc) => tc.status === "pending") && (
 <div className="flex items-center gap-2 py-2">
 <Loader2 className="size-3.5 animate-spin text-primary" />
 <span className="text-xs text-muted-foreground ">
 {activeToolCalls.filter((tc) => tc.status === "pending").map((tc) => tc.tool).join(", ")}...
 </span>
 </div>
 )}

 <div ref={messagesEndRef} />
 </div>
 </div>

 {/* Input area — Notion-style clean centered bar */}
 <div className="border-t">
 <div className="max-w-2xl mx-auto px-6 py-4">
 {/* Lens selector row — only show if a lens is active or settings open */}
 {(activeLens || showSettings) && (
 <div className="flex items-center gap-2 mb-3">
 {PHILOSOPHICAL_LENSES.map((l) => (
 <button
 key={l.id}
 onClick={() => setLens(activeLens === l.id ? null : l.id)}
 className={cn(
 "rounded-full px-3 py-1 text-[11px] transition-colors border",
 activeLens === l.id
 ? "border-primary bg-[var(--alfred-accent-subtle)] text-primary"
 : "border-transparent text-muted-foreground hover:border-border hover:text-foreground",
 )}
 >
 {l.label}
 </button>
 ))}
 </div>
 )}

 {/* Main input bar */}
 <div className="flex items-end gap-0 rounded-xl border bg-card shadow-sm focus-within:border-primary transition-colors">
 <textarea
 ref={inputRef}
 value={input}
 onChange={(e) => setInput(e.target.value)}
 onKeyDown={handleKeyDown}
 placeholder="Do anything with AI..."
 rows={1}
 className="flex-1 resize-none bg-transparent px-4 py-3 text-sm outline-none placeholder:text-muted-foreground"
 />

 <div className="flex items-center gap-1 px-2 py-2">
 {/* Settings toggle (shows lens chips) */}
 <button
 onClick={() => setShowSettings(!showSettings)}
 className="p-1.5 rounded-md text-muted-foreground hover:text-foreground transition-colors"
 >
 <Settings2 className="size-4" />
 </button>

 {/* Model indicator */}
 <button className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] text-muted-foreground hover:text-foreground transition-colors">
 <span className="text-primary">★</span>
 <select
 value={activeModel}
 onChange={(e) => setModel(e.target.value)}
 className="bg-transparent outline-none cursor-pointer text-[11px] "
 >
 <option value="gpt-5.4">GPT-5.4</option>
 <option value="gpt-5.4-mini">GPT-5.4 mini</option>
 <option value="gpt-5.4-pro">GPT-5.4 Pro</option>
 <option value="gpt-4o">GPT-4o</option>
 <option value="o3">o3</option>
 <option value="o4-mini">o4-mini</option>
 </select>
 </button>

 {/* Send / Stop */}
 {isStreaming ? (
 <button
 onClick={cancelStream}
 className="p-1.5 rounded-md text-primary hover:bg-[var(--alfred-accent-subtle)] transition-colors"
 >
 <Square className="size-4" />
 </button>
 ) : (
 <button
 onClick={handleSend}
 disabled={!input.trim()}
 className={cn(
 "p-1.5 rounded-md transition-colors",
 input.trim()
 ? "text-primary hover:bg-[var(--alfred-accent-subtle)]"
 : "text-muted-foreground/40 cursor-not-allowed",
 )}
 >
 <Send className="size-4" />
 </button>
 )}
 </div>
 </div>
 </div>
 </div>

 {/* Editor drawer */}
 <EditorDrawer
 zettelId={editingZettelId}
 onClose={() => setEditingZettelId(null)}
 />
 </div>
 );
}

// --- Message components ---

function MessageBubble({
 message,
 onArtifactClick,
}: {
 message: AgentMessage;
 onArtifactClick: (artifact: ArtifactCard) => void;
}) {
 if (message.role === "user") {
 return (
 <div className="flex justify-end">
 <div className="max-w-[80%] rounded-2xl bg-secondary px-4 py-2.5 text-sm text-foreground">
 {message.content}
 </div>
 </div>
 );
 }

 return (
 <div className="space-y-3">
 {/* Assistant text — rendered as markdown with Literary Terminal prose styling */}
 {message.content && (
 <InsightToCard threadTopics={message.artifacts.map((a) => a.topic).filter(Boolean) as string[]}>
 <MarkdownMessage content={message.content} />
 </InsightToCard>
 )}

 {/* Artifact cards — Notion style: simple inline cards */}
 {message.artifacts.length > 0 && (
 <div className="space-y-2">
 {message.artifacts.map((artifact) => (
 <ArtifactCardComponent
 key={`${artifact.type}-${artifact.id}`}
 artifact={artifact}
 onClick={() => onArtifactClick(artifact)}
 />
 ))}
 </div>
 )}

 {/* Related knowledge */}
 {message.relatedCards.length > 0 && (
 <RelatedCards cards={message.relatedCards} onCardClick={onArtifactClick} />
 )}

 {/* Gap chips */}
 {message.gaps.length > 0 && (
 <div className="flex flex-wrap gap-1.5">
 {message.gaps.map((gap) => (
 <span
 key={gap.concept}
 className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] bg-[var(--alfred-accent-subtle)] text-primary"
 >
 gap: {gap.concept}
 </span>
 ))}
 </div>
 )}

 {/* Feedback actions — Notion style */}
 {message.content && !message.content.startsWith("Sorry") && (
 <div className="flex items-center gap-1 pt-1">
 <button className="p-1 rounded text-muted-foreground/40 hover:text-muted-foreground transition-colors">
 <ThumbsUp className="size-3.5" />
 </button>
 <button className="p-1 rounded text-muted-foreground/40 hover:text-muted-foreground transition-colors">
 <ThumbsDown className="size-3.5" />
 </button>
 <button className="p-1 rounded text-muted-foreground/40 hover:text-muted-foreground transition-colors">
 <RotateCcw className="size-3.5" />
 </button>
 </div>
 )}
 </div>
 );
}
