"use client";

import { useCallback, useState } from "react";

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

 const createMutation = useCreateZettel();

 const reset = useCallback(() => {
 setTitle(defaultTitle);
 setContent(defaultContent);
 setSummary(defaultSummary);
 setTags(defaultTags.join(", "));
 setTopic(defaultTopic);
 }, [defaultTitle, defaultContent, defaultSummary, defaultTags, defaultTopic]);

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

 return (
 <Dialog open={open} onOpenChange={onOpenChange}>
 <DialogContent className="sm:max-w-[500px]">
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
 <label className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-1.5 block">
 Content
 </label>
 <Textarea
 value={content}
 onChange={(e) => setContent(e.target.value)}
 placeholder="Detailed explanation..."
 rows={4}
 className="text-[13px]"
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
 <label className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-1.5 block">
 Tags
 </label>
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
 <Button variant="outline" onClick={() => onOpenChange(false)} className="text-xs">
 Cancel
 </Button>
 <Button
 onClick={handleCreate}
 disabled={!title.trim() || createMutation.isPending}
 className="text-xs"
 >
 {createMutation.isPending ? "Creating..." : "Create Zettel"}
 </Button>
 </DialogFooter>
 </DialogContent>
 </Dialog>
 );
}
