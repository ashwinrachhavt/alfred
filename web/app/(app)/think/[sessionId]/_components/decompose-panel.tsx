"use client";

import { useState } from "react";

import { Loader2, Sparkles, X } from "lucide-react";
import { toast } from "sonner";

import { useDecompose } from "@/features/thinking/mutations";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";

// ---------------------------------------------------------------------------
// Decompose Panel
// ---------------------------------------------------------------------------

export function DecomposePanel({ onClose }: { onClose: () => void }) {
  const [topic, setTopic] = useState("");
  const [text, setText] = useState("");
  const decomposeMutation = useDecompose();

  const handleDecompose = async () => {
    const payload: { topic?: string; text?: string } = {};
    if (topic.trim()) payload.topic = topic.trim();
    if (text.trim()) payload.text = text.trim();

    if (!payload.topic && !payload.text) {
      toast.error("Enter a topic or text to decompose.");
      return;
    }

    try {
      await decomposeMutation.mutateAsync(payload);
      toast.info("Decompose is coming soon. The API stub was called successfully.");
    } catch {
      toast.error("Decompose failed. This feature is coming soon.");
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <h3 className="font-serif text-base tracking-tight">Decompose</h3>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="h-7 w-7"
          onClick={onClose}
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>

      <Separator />

      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        <p className="text-muted-foreground text-xs leading-relaxed">
          Break down a topic, URL, or text into structured thinking blocks using
          the Jiang decomposition method.
        </p>

        <div className="space-y-2">
          <Label htmlFor="decompose-topic" className="text-xs">
            Topic or URL
          </Label>
          <Input
            id="decompose-topic"
            placeholder="e.g. Transformer architecture"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            className="h-8 text-xs"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="decompose-text" className="text-xs">
            Text (optional)
          </Label>
          <Textarea
            id="decompose-text"
            placeholder="Paste source text to decompose..."
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="min-h-[120px] text-xs"
          />
        </div>

        <Button
          type="button"
          className="w-full"
          size="sm"
          onClick={handleDecompose}
          disabled={decomposeMutation.isPending}
        >
          {decomposeMutation.isPending ? (
            <>
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              Decomposing...
            </>
          ) : (
            <>
              <Sparkles className="mr-1.5 h-3.5 w-3.5" />
              Decompose
            </>
          )}
        </Button>

        {decomposeMutation.data ? (
          <div className="rounded-lg border p-3">
            <p className="text-muted-foreground text-xs">
              {decomposeMutation.data.blocks?.length ?? 0} blocks generated.
              Insertion into editor coming in v2.
            </p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
