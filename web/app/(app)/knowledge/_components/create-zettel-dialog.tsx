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
};

export function CreateZettelDialog({ open, onOpenChange }: Props) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [summary, setSummary] = useState("");
  const [tags, setTags] = useState("");
  const [topic, setTopic] = useState("");

  const createMutation = useCreateZettel();

  const reset = useCallback(() => {
    setTitle("");
    setContent("");
    setSummary("");
    setTags("");
    setTopic("");
  }, []);

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
          <DialogTitle className="font-serif text-xl">New Zettel</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div>
            <label className="font-mono text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-1.5 block">
              Title
            </label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Concept name..."
              className="font-serif"
              autoFocus
            />
          </div>

          <div>
            <label className="font-mono text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-1.5 block">
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
            <label className="font-mono text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-1.5 block">
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
              <label className="font-mono text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-1.5 block">
                Topic
              </label>
              <Input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="Primary domain..."
                className="font-mono text-xs"
              />
            </div>
            <div>
              <label className="font-mono text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-1.5 block">
                Tags
              </label>
              <Input
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="comma-separated..."
                className="font-mono text-xs"
              />
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} className="font-mono text-xs">
            Cancel
          </Button>
          <Button
            onClick={handleCreate}
            disabled={!title.trim() || createMutation.isPending}
            className="font-mono text-xs"
          >
            {createMutation.isPending ? "Creating..." : "Create Zettel"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
