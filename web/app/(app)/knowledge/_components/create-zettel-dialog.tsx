"use client";

import { useCallback, useEffect, useState } from "react";

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
import { useCreateZettel } from "@/features/zettels/mutations";
import { usePasteDetection } from "@/lib/hooks/use-paste-detection";
import { apiPostJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

type Props = {
 open: boolean;
 onOpenChange: (open: boolean) => void;
 defaultTitle?: string;
 defaultContent?: string;
 defaultSummary?: string;
 defaultTags?: string[];
 defaultTopic?: string;
};

export function CreateZettelDialog({
 open,
 onOpenChange,
 defaultTitle = "",
 defaultContent = "",
 defaultSummary = "",
 defaultTags = [],
 defaultTopic = "",
}: Props) {
 const [title, setTitle] = useState(defaultTitle);
 const [content, setContent] = useState(defaultContent);
 const [summary, setSummary] = useState(defaultSummary);
 const [tags, setTags] = useState(defaultTags.join(", "));
 const [topic, setTopic] = useState(defaultTopic);
 const [isLoadingTags, setIsLoadingTags] = useState(false);

 const createMutation = useCreateZettel();
 const { isPasteMode, tokenEstimate, handlePaste, extractTitle, reset: resetPaste } = usePasteDetection();

 // Sync defaults when they change
 useEffect(() => {
 setTitle(defaultTitle);
 setContent(defaultContent);
 setSummary(defaultSummary);
 setTags(defaultTags.join(", "));
 setTopic(defaultTopic);
 }, [defaultTitle, defaultContent, defaultSummary, defaultTags, defaultTopic]);

 const reset = useCallback(() => {
 setTitle(defaultTitle);
 setContent(defaultContent);
 setSummary(defaultSummary);
 setTags(defaultTags.join(", "));
 setTopic(defaultTopic);
 resetPaste();
 }, [defaultTitle, defaultContent, defaultSummary, defaultTags, defaultTopic, resetPaste]);

 const handleCreate = useCallback(() => {
 if (!title.trim()) return;

 const tagList = tags
 .split(",")
 .map((t) => t.trim().toLowerCase())
 .filter(Boolean);

 createMutation.mutate(
 {
 title: title.trim(),
 content: content.trim() || undefined,
 summary: summary.trim() || undefined,
 tags: tagList.length > 0 ? tagList : undefined,
 topic: topic.trim() || undefined,
 importance: 5,
 confidence: 0.5,
 },
 {
 onSuccess: () => {
 reset();
 onOpenChange(false);
 },
 },
 );
 }, [title, content, summary, tags, topic, createMutation, reset, onOpenChange]);

 const handleContentPaste = useCallback((e: React.ClipboardEvent<HTMLTextAreaElement>) => {
 handlePaste(e);
 // Auto-fill title if empty
 const text = e.clipboardData.getData("text/plain");
 if (text.length > 100 && !title.trim()) {
 const autoTitle = extractTitle(text);
 if (autoTitle) {
 setTitle(autoTitle);
 }
 }
 }, [handlePaste, extractTitle, title]);

 const handleAutoTag = useCallback(async () => {
 if (!content.trim()) return;

 setIsLoadingTags(true);
 try {
 const response = await apiPostJson<{ tags: string[] }, { text: string }>(
 apiRoutes.zettels.suggestTags,
 { text: content.trim() }
 );
 if (response.tags && response.tags.length > 0) {
 setTags(response.tags.join(", "));
 }
 } catch (error) {
 console.error("Failed to suggest tags:", error);
 } finally {
 setIsLoadingTags(false);
 }
 }, [content]);

 const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
 if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
 e.preventDefault();
 handleCreate();
 }
 }, [handleCreate]);

 return (
 <Dialog open={open} onOpenChange={onOpenChange}>
 <DialogContent className="sm:max-w-[500px]" onKeyDown={handleKeyDown}>
 <DialogHeader>
 <DialogTitle className="text-xl">New Zettel</DialogTitle>
 </DialogHeader>

 <div className="space-y-4 py-2">
 <div>
 <label className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-1.5 block">
 Title
 </label>
 <Input
 value={title}
 onChange={(e) => setTitle(e.target.value)}
 placeholder="Concept name..."
 className=""
 autoFocus
 />
 </div>

 <div>
 <div className="flex items-center justify-between mb-1.5">
 <label className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
 Content
 </label>
 {isPasteMode && tokenEstimate > 0 && (
 <span className="text-[9px] font-medium uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
 ~{tokenEstimate} tokens
 </span>
 )}
 </div>
 <Textarea
 value={content}
 onChange={(e) => setContent(e.target.value)}
 onPaste={handleContentPaste}
 placeholder="Detailed explanation..."
 rows={4}
 className={`text-[13px] transition-all ${
 isPasteMode ? "min-h-[300px] max-h-[500px]" : ""
 }`}
 />
 </div>

 <div>
 <label className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-1.5 block">
 Summary
 </label>
 <Input
 value={summary}
 onChange={(e) => setSummary(e.target.value)}
 placeholder="One-sentence distillation..."
 className="text-[13px]"
 />
 </div>

 <div className="grid grid-cols-2 gap-3">
 <div>
 <label className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-1.5 block">
 Topic
 </label>
 <Input
 value={topic}
 onChange={(e) => setTopic(e.target.value)}
 placeholder="Primary domain..."
 className="text-xs"
 />
 </div>
 <div>
 <div className="flex items-center justify-between mb-1.5">
 <label className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
 Tags
 </label>
 <Button
 variant="ghost"
 size="sm"
 onClick={handleAutoTag}
 disabled={!content.trim() || isLoadingTags}
 className="h-auto py-0.5 px-2 text-[9px] font-medium uppercase tracking-widest"
 >
 {isLoadingTags ? "..." : "Auto-tag"}
 </Button>
 </div>
 <Input
 value={tags}
 onChange={(e) => setTags(e.target.value)}
 placeholder="comma-separated..."
 className="text-xs"
 />
 </div>
 </div>
 </div>

 <DialogFooter>
 <Button variant="outline" onClick={() => onOpenChange(false)} className="text-xs font-medium">
 Cancel
 </Button>
 <Button
 onClick={handleCreate}
 disabled={!title.trim() || createMutation.isPending}
 className="text-xs font-medium"
 >
 {createMutation.isPending ? "Creating..." : "Create Zettel"}
 </Button>
 </DialogFooter>
 </DialogContent>
 </Dialog>
 );
}
