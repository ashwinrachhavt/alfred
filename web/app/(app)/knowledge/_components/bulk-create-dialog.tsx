"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useBulkCreateZettels } from "@/features/zettels/mutations";
import { useZettelTopics } from "@/features/zettels/queries";
import { Layers, Loader2 } from "lucide-react";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function BulkCreateDialog({ open, onOpenChange }: Props) {
  const [text, setText] = useState("");
  const [topic, setTopic] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const bulkMutation = useBulkCreateZettels();
  const { data: availableTopics = [] } = useZettelTopics();

  const titles = text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  const count = titles.length;

  useEffect(() => {
    if (open) {
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  }, [open]);

  const reset = useCallback(() => {
    setText("");
    setTopic("");
  }, []);

  const handleCreate = useCallback(() => {
    if (titles.length === 0) return;
    if (titles.length > 50) return;

    const payload = titles.map((title) => ({
      title,
      topic: topic.trim() || undefined,
    }));

    bulkMutation.mutate(payload, {
      onSuccess: () => {
        reset();
        onOpenChange(false);
      },
    });
  }, [titles, topic, bulkMutation, reset, onOpenChange]);

  const canSubmit = count > 0 && count <= 50 && !bulkMutation.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl">
            <Layers className="size-5 text-primary" />
            Bulk Create Zettels
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div>
            <label className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-1.5 block">
              Titles (one per line)
            </label>
            <Textarea
              ref={textareaRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={"CAP theorem\nRaft consensus\nVector clocks\nCRDTs\n..."}
              rows={8}
              className="text-[13px] font-mono"
            />
          </div>

          <div>
            <label className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-1.5 block">
              Topic (optional, applies to all)
            </label>
            <select
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              className="w-full rounded-lg border bg-card px-3 py-2 text-[13px] outline-none focus:ring-1 focus:ring-primary/50"
            >
              <option value="">No topic</option>
              {availableTopics.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center justify-between rounded-md border bg-muted/50 px-3 py-2">
            <span className="text-xs text-muted-foreground">
              Will create{" "}
              <span className="font-semibold text-foreground">{count}</span>{" "}
              zettel{count !== 1 ? "s" : ""}
            </span>
            {count > 50 && (
              <span className="text-xs text-destructive">Max 50 per batch</span>
            )}
          </div>

          {bulkMutation.isError && (
            <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3">
              <p className="text-xs text-destructive">
                Bulk creation failed. Please try again.
              </p>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} className="text-xs">
            Cancel
          </Button>
          <Button
            onClick={handleCreate}
            disabled={!canSubmit}
            className="gap-1.5 text-xs"
          >
            {bulkMutation.isPending ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Layers className="size-3.5" />
            )}
            {bulkMutation.isPending
              ? "Creating..."
              : `Create ${count} Zettel${count !== 1 ? "s" : ""}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
