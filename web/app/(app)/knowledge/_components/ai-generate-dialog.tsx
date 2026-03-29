"use client";

import { useCallback, useState } from "react";

import { Sparkles } from "lucide-react";

import {
 Dialog,
 DialogContent,
 DialogHeader,
 DialogTitle,
 DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useGenerateZettel } from "@/features/zettels/mutations";

type Props = {
 open: boolean;
 onOpenChange: (open: boolean) => void;
};

type Mode = "prompt" | "content";

export function AIGenerateDialog({ open, onOpenChange }: Props) {
 const [mode, setMode] = useState<Mode>("prompt");
 const [prompt, setPrompt] = useState("");
 const [content, setContent] = useState("");
 const [topic, setTopic] = useState("");
 const [tags, setTags] = useState("");

 const generateMutation = useGenerateZettel();

 const reset = useCallback(() => {
 setPrompt("");
 setContent("");
 setTopic("");
 setTags("");
 }, []);

 const handleGenerate = useCallback(() => {
 const hasInput = mode === "prompt" ? prompt.trim() : content.trim();
 if (!hasInput) return;

 const tagList = tags
 .split(",")
 .map((t) => t.trim().toLowerCase())
 .filter(Boolean);

 generateMutation.mutate(
 {
 prompt: mode === "prompt" ? prompt.trim() : undefined,
 content: mode === "content" ? content.trim() : undefined,
 topic: topic.trim() || undefined,
 tags: tagList.length > 0 ? tagList : undefined,
 },
 {
 onSuccess: () => {
 reset();
 onOpenChange(false);
 },
 },
 );
 }, [mode, prompt, content, topic, tags, generateMutation, reset, onOpenChange]);

 const hasInput = mode === "prompt" ? prompt.trim() : content.trim();

 return (
 <Dialog open={open} onOpenChange={onOpenChange}>
 <DialogContent className="sm:max-w-[520px]">
 <DialogHeader>
 <DialogTitle className="flex items-center gap-2 text-xl">
 <Sparkles className="size-5 text-primary" />
 AI Generate Zettel
 </DialogTitle>
 </DialogHeader>

 <div className="space-y-4 py-2">
 {/* Mode toggle */}
 <div className="flex gap-1 rounded-md border p-1">
 <button
 onClick={() => setMode("prompt")}
 className={`flex-1 rounded px-3 py-1.5 text-[11px] uppercase tracking-wider transition-colors ${
 mode === "prompt"
 ? "bg-[var(--alfred-accent-muted)] text-primary"
 : "text-muted-foreground hover:text-foreground"
 }`}
 >
 From Topic
 </button>
 <button
 onClick={() => setMode("content")}
 className={`flex-1 rounded px-3 py-1.5 text-[11px] uppercase tracking-wider transition-colors ${
 mode === "content"
 ? "bg-[var(--alfred-accent-muted)] text-primary"
 : "text-muted-foreground hover:text-foreground"
 }`}
 >
 From Content
 </button>
 </div>

 {mode === "prompt" ? (
 <div>
 <label className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-1.5 block">
 What should the zettel be about?
 </label>
 <Input
 value={prompt}
 onChange={(e) => setPrompt(e.target.value)}
 placeholder='e.g. "CAP theorem and its practical limits"'
 className=""
 autoFocus
 />
 </div>
 ) : (
 <div>
 <label className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-1.5 block">
 Paste content to extract a zettel from
 </label>
 <Textarea
 value={content}
 onChange={(e) => setContent(e.target.value)}
 placeholder="Paste article text, notes, or raw content..."
 rows={6}
 className="text-[13px]"
 autoFocus
 />
 </div>
 )}

 <div className="grid grid-cols-2 gap-3">
 <div>
 <label className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-1.5 block">
 Topic (optional)
 </label>
 <Input
 value={topic}
 onChange={(e) => setTopic(e.target.value)}
 placeholder="e.g. distributed-systems"
 className="text-xs"
 />
 </div>
 <div>
 <label className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-1.5 block">
 Tags (optional)
 </label>
 <Input
 value={tags}
 onChange={(e) => setTags(e.target.value)}
 placeholder="comma-separated..."
 className="text-xs"
 />
 </div>
 </div>

 {generateMutation.isError && (
 <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3">
 <p className="text-xs text-destructive">
 Generation failed. Please try again.
 </p>
 </div>
 )}
 </div>

 <DialogFooter>
 <Button variant="outline" onClick={() => onOpenChange(false)} className="text-xs">
 Cancel
 </Button>
 <Button
 onClick={handleGenerate}
 disabled={!hasInput || generateMutation.isPending}
 className="gap-1.5 text-xs"
 >
 <Sparkles className="size-3.5" />
 {generateMutation.isPending ? "Generating..." : "Generate"}
 </Button>
 </DialogFooter>
 </DialogContent>
 </Dialog>
 );
}
